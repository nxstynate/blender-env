# INSYDIUM NeXus Add-on for Blender
# Copyright (C) 2026 INSYDIUM LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Native (Vulkan) renderer for NX_GENERATOR mesh-instancing."""

from __future__ import annotations

import ctypes
from ctypes import c_float, c_int, c_uint32

import numpy as np

from ..core.buffer_state import buf_identity
from ..core.renderer import NexusRenderer

_MAX_LAYERS = 16
_LAYER_FLOATS = 60  # GeneratorLayerGpu = 240 bytes = 60 floats


class _GeneratorLayerGpu(ctypes.Structure):
    """std430 layout matching ``GeneratorLayer`` in the GLSL shaders."""

    _fields_ = [
        ("mesh_color", c_float * 4),
        ("mesh_scale", c_float * 4),
        ("mesh_rot_row0", c_float * 4),
        ("mesh_rot_row1", c_float * 4),
        ("mesh_rot_row2", c_float * 4),
        ("custom_color", c_float * 4),
        ("custom_scale", c_float * 4),
        ("custom_rotation", c_float * 4),
        ("scale_variation", c_float * 4),
        ("color_variation", c_float * 4),
        ("rotation_variation", c_float * 4),
        ("source_ids", c_int * 4),
        ("per_axis_flags", c_int * 4),
        ("classifier", c_float * 4),
        ("mesh_offsets", c_uint32 * 4),
    ]


assert ctypes.sizeof(_GeneratorLayerGpu) == 240


def _fetch_buf(pipeline, prop):
    """Resolve a Theron property to a ``BufferExport`` or ``None``."""
    from ..core.particle_renderer import ParticleRenderer

    buf = ParticleRenderer.fetch_gpu_buffer(pipeline, prop)
    if buf is None or not buf.valid:
        return None
    return buf


class GeneratorNativeRenderer(NexusRenderer):
    """Vulkan generator renderer wired through the generator sentinel."""

    def __init__(self, bridge) -> None:
        self._bridge = bridge
        self._configured_externals: tuple | None = None

    def shutdown(self) -> None:
        self._configured_externals = None

    def draw(self, context, pipeline, scene, params) -> bool:
        if pipeline is None:
            return False
        bridge = self._bridge
        if not bridge.load():
            return False
        if not bridge.generator_hook_ready():
            return False

        if params.particle_count <= 0:
            return False

        emitter_mask = int(getattr(params, "emitter_filter_mask", 0)) & 0xFFFFFFFF
        if emitter_mask == 0:
            return True

        enabled = [layer for layer in params.layers if layer.enabled and layer.index_count > 0]
        if not enabled:
            return True
        if len(enabled) > _MAX_LAYERS:
            enabled = enabled[:_MAX_LAYERS]

        # Position + particle id are required.
        pos_buf = _fetch_buf(pipeline, "position")
        pid_buf = _fetch_buf(pipeline, "id")
        emit_buf = _fetch_buf(pipeline, "emitter_index")
        if pos_buf is None or pid_buf is None or emit_buf is None:
            return False

        # Optional buffers — only fetched when at least one layer wants them.
        need_color = any(layer.color_source_id == 1 for layer in enabled)
        need_radius = any(layer.scale_source_id == 1 for layer in enabled)
        need_scale = any(layer.scale_source_id == 2 for layer in enabled)
        need_rotation = any(layer.rotation_source_id == 1 for layer in enabled)
        col_buf = _fetch_buf(pipeline, "color") if need_color else None
        rad_buf = _fetch_buf(pipeline, "radius") if need_radius else None
        scl_buf = _fetch_buf(pipeline, "scale") if need_scale else None
        rot_buf = _fetch_buf(pipeline, "rotation") if need_rotation else None

        # Cumulative spawn weights (normalised, last layer pinned at 1.0).
        weights = [max(0.0, layer.spawn_chance) for layer in enabled]
        total = sum(weights) or 1.0
        cumulative = []
        running = 0.0
        for w in weights:
            running += w / total
            cumulative.append(running)
        cumulative[-1] = 1.0

        # Concatenate mesh data; record per-layer (firstIndex, baseVertex, indexCount).
        # Each vertex carries (position, corner_normal, smooth_normal) interleaved
        # as 9 floats — the fragment shader picks which normal to use based on
        # the layer's shading_mode_id.
        vert_chunks: list[np.ndarray] = []
        idx_chunks: list[np.ndarray] = []
        layer_mesh_offsets: list[tuple[int, int, int]] = []
        revision_acc = 0
        first_index = 0
        base_vertex = 0
        for layer in enabled:
            pos = np.ascontiguousarray(layer.mesh_vertices, dtype=np.float32).reshape(-1, 3)
            inds = np.ascontiguousarray(layer.mesh_indices, dtype=np.uint32).ravel()
            if pos.size == 0 or inds.size == 0:
                layer_mesh_offsets.append((0, 0, 0))
                # Hash empty layers too so revision changes when their state toggles.
                revision_acc = (
                    revision_acc * 2654435761 + hash(layer.mesh_revision_key)
                ) & 0xFFFFFFFFFFFFFFFF
                continue
            cn = np.ascontiguousarray(layer.mesh_corner_normals, dtype=np.float32).reshape(-1, 3)
            sn = np.ascontiguousarray(layer.mesh_smooth_normals, dtype=np.float32).reshape(-1, 3)
            interleaved = np.empty((pos.shape[0], 9), dtype=np.float32)
            interleaved[:, 0:3] = pos
            interleaved[:, 3:6] = cn
            interleaved[:, 6:9] = sn
            vert_chunks.append(interleaved.ravel())
            idx_chunks.append(inds)
            layer_mesh_offsets.append((first_index, base_vertex, int(inds.size)))
            revision_acc = (
                revision_acc * 2654435761 + hash(layer.mesh_revision_key)
            ) & 0xFFFFFFFFFFFFFFFF
            first_index += int(inds.size)
            base_vertex += int(pos.shape[0])

        if not vert_chunks:
            return True
        all_verts = np.concatenate(vert_chunks).astype(np.float32, copy=False)
        all_inds = np.concatenate(idx_chunks).astype(np.uint32, copy=False)

        # Build the per-layer GPU struct array.
        layer_arr = (_GeneratorLayerGpu * len(enabled))()
        for i, layer in enumerate(enabled):
            L = layer_arr[i]
            L.mesh_color[:] = (
                float(layer.mesh_color[0]),
                float(layer.mesh_color[1]),
                float(layer.mesh_color[2]),
                float(layer.mesh_color[3]),
            )
            L.mesh_scale[:] = (
                float(layer.mesh_scale[0]),
                float(layer.mesh_scale[1]),
                float(layer.mesh_scale[2]),
                0.0,
            )
            # mesh_rotation is row-major flat 9-tuple; pad each row to vec4.
            mr = layer.mesh_rotation
            L.mesh_rot_row0[:] = (float(mr[0]), float(mr[1]), float(mr[2]), 0.0)
            L.mesh_rot_row1[:] = (float(mr[3]), float(mr[4]), float(mr[5]), 0.0)
            L.mesh_rot_row2[:] = (float(mr[6]), float(mr[7]), float(mr[8]), 0.0)
            L.custom_color[:] = (
                float(layer.custom_color[0]),
                float(layer.custom_color[1]),
                float(layer.custom_color[2]),
                float(layer.custom_color[3]),
            )
            L.custom_scale[:] = (
                float(layer.custom_scale[0]),
                float(layer.custom_scale[1]),
                float(layer.custom_scale[2]),
                0.0,
            )
            L.custom_rotation[:] = (
                float(layer.custom_rotation[0]),
                float(layer.custom_rotation[1]),
                float(layer.custom_rotation[2]),
                0.0,
            )
            L.scale_variation[:] = (
                float(layer.scale_variation[0]),
                float(layer.scale_variation[1]),
                float(layer.scale_variation[2]),
                0.0,
            )
            L.color_variation[:] = (
                float(layer.color_variation[0]),
                float(layer.color_variation[1]),
                float(layer.color_variation[2]),
                0.0,
            )
            L.rotation_variation[:] = (
                float(layer.rotation_variation[0]),
                float(layer.rotation_variation[1]),
                float(layer.rotation_variation[2]),
                0.0,
            )
            # Effective sources fall back to mesh when the optional buffer is missing.
            eff_scale = layer.scale_source_id
            if eff_scale == 1 and rad_buf is None:
                eff_scale = 0
            elif eff_scale == 2 and scl_buf is None:
                eff_scale = 0
            eff_color = layer.color_source_id
            if eff_color == 1 and col_buf is None:
                eff_color = 0
            eff_rot = layer.rotation_source_id
            if eff_rot == 1 and rot_buf is None:
                eff_rot = 0
            L.source_ids[:] = (int(eff_scale), int(eff_color), int(eff_rot), 0)
            L.per_axis_flags[:] = (
                1 if layer.scale_variation_per_axis else 0,
                1 if layer.color_variation_per_axis else 0,
                1 if layer.rotation_variation_per_axis else 0,
                int(layer.shading_mode_id),
            )
            L.classifier[:] = (float(cumulative[i]), 0.0, 0.0, 0.0)
            fi, bv, ic = layer_mesh_offsets[i]
            L.mesh_offsets[:] = (int(fi), int(bv), int(ic), 0)

        # Camera position (world space) for fragment headlight lambert.
        try:
            cam = context.region_data.view_matrix.inverted().translation
            cam_xyz = (float(cam.x), float(cam.y), float(cam.z))
        except Exception:
            cam_xyz = (0.0, 0.0, 0.0)

        # Stage view + projection (shared with the particle path).
        region_data = getattr(context, "region_data", None)
        region = getattr(context, "region", None)
        if region_data is None or region is None:
            return False
        vm = [region_data.view_matrix[i][j] for i in range(4) for j in range(4)]
        pm = [region_data.window_matrix[i][j] for i in range(4) for j in range(4)]
        bridge.stage_frame(vm, pm, region.width, region.height)

        externals_state = (
            buf_identity(pos_buf),
            int(pos_buf.size),
            buf_identity(pid_buf),
            int(pid_buf.size),
            buf_identity(col_buf),
            int(col_buf.size) if col_buf is not None else 0,
            buf_identity(rad_buf),
            int(rad_buf.size) if rad_buf is not None else 0,
            buf_identity(scl_buf),
            int(scl_buf.size) if scl_buf is not None else 0,
            buf_identity(rot_buf),
            int(rot_buf.size) if rot_buf is not None else 0,
            buf_identity(emit_buf),
            int(emit_buf.size),
        )
        if externals_state != self._configured_externals:
            bridge.configure_generator_externals(
                int(pos_buf.handle),
                int(pos_buf.size),
                int(pid_buf.handle),
                int(pid_buf.size),
                int(col_buf.handle) if col_buf is not None else None,
                int(col_buf.size) if col_buf is not None else 0,
                int(rad_buf.handle) if rad_buf is not None else None,
                int(rad_buf.size) if rad_buf is not None else 0,
                int(scl_buf.handle) if scl_buf is not None else None,
                int(scl_buf.size) if scl_buf is not None else 0,
                int(rot_buf.handle) if rot_buf is not None else None,
                int(rot_buf.size) if rot_buf is not None else 0,
                int(emit_buf.handle),
                int(emit_buf.size),
            )
            self._configured_externals = externals_state

        # Numpy → ctypes pointers; the underlying buffers stay alive across
        # the call because the numpy arrays are bound to local names here.
        verts_ptr = all_verts.ctypes.data_as(ctypes.POINTER(c_float))
        idx_ptr = all_inds.ctypes.data_as(ctypes.POINTER(c_uint32))

        bridge.stage_generator_frame(
            cam_xyz,
            int(params.particle_count),
            len(enabled),
            emitter_mask,
            layer_arr,
            verts_ptr,
            int(all_verts.size),
            idx_ptr,
            int(all_inds.size),
            int(revision_acc),
        )
        return bridge.draw_generator_sentinel()
