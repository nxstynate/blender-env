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

"""Base class for particle display-mode renderers."""

from __future__ import annotations

import ctypes

import numpy as np

from .buffer_state import BufferExport
from .renderer import NexusRenderer

DRAW_MODE_BIN_INDEX = {
    "POINTS": 0,
    "SQUARE": 1,
    "DIRECTION": 2,
    "BOX3D": 3,
    "BOX3D_FILLED": 4,
    "CIRCLE": 5,
    "CIRCLE_FILLED": 6,
    "PYRAMID": 7,
    "PYRAMID_FILLED": 8,
    "ARROW": 9,
    "ARROW_FILLED": 10,
    "SPHERE": 11,
    "AXIS": 12,
    "NONE": 13,
}

_PROPERTY_MAP = {
    "position": "TR_PARTICLE_PROPERTY_POSITION",
    "velocity": "TR_PARTICLE_PROPERTY_VELOCITY",
    "radius": "TR_PARTICLE_PROPERTY_RADIUS",
    "scale": "TR_PARTICLE_PROPERTY_SCALE",
    "color": "TR_PARTICLE_PROPERTY_COLOR",
    "emitter_index": "TR_PARTICLE_PROPERTY_EMITTER_INDEX",
    "rotation": "TR_PARTICLE_PROPERTY_ROTATION",
    "rotation_up": "TR_PARTICLE_PROPERTY_ROTATION_UP",
    "id": "TR_PARTICLE_PROPERTY_ID",
}


class ParticleRenderer(NexusRenderer):
    """Shared helpers used by every particle display mode (point, circle, …).

    Concrete subclasses live under ``viewport.particles.<mode>/`` and are
    associated with a specific bridge backend (native / opengl / basic).
    """

    # -------------------------------------------------------------------
    # GPU zero-copy buffer helpers (native + OpenGL modes)
    # -------------------------------------------------------------------

    @staticmethod
    def _pipeline_has_property(pipeline, prop: int) -> bool:
        """Guard non-default properties to avoid export exceptions."""
        from ...libs import theron

        if not hasattr(theron, "_lib") or theron._lib is None:
            return False
        if not hasattr(theron._lib, "trParticleHasProperty"):
            return True
        try:
            has_property = ctypes.c_bool(False)
            result = theron._lib.trParticleHasProperty(
                ctypes.c_void_p(pipeline),
                ctypes.c_int(prop),
                ctypes.byref(has_property),
            )
            return bool(result == 0 and has_property.value)
        except Exception:
            return False

    @staticmethod
    def fetch_gpu_buffer(pipeline, property_name: str) -> BufferExport | None:
        """Fetch a single zero-copy buffer export from Theron.

        *property_name* is one of ``"position"``, ``"velocity"``,
        ``"radius"``, ``"color"``.
        """
        from ...libs import theron
        from ...libs.theron import TrParticleProperty

        attr = _PROPERTY_MAP.get(property_name)
        if attr is None:
            return None
        prop = getattr(TrParticleProperty, attr, None)
        if prop is None:
            return None
        if not ParticleRenderer._pipeline_has_property(pipeline, int(prop)):
            return None
        try:
            export = theron.get_particle_data_buffer_export(pipeline, prop)
            if export is not None and export[0] and export[1] > 0:
                return BufferExport(handle=export[0], size=export[1], uid=export[2])
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_gpu_buffers(pipeline, property_names: list[str]) -> dict[str, BufferExport]:
        """Fetch multiple GPU buffer exports at once."""
        result: dict[str, BufferExport] = {}
        for name in property_names:
            buf = ParticleRenderer.fetch_gpu_buffer(pipeline, name)
            if buf is not None:
                result[name] = buf
        return result

    @staticmethod
    def fetch_draw_mode_buffers(pipeline) -> tuple[BufferExport, BufferExport] | None:
        """Fetch draw-mode prefix + binned index buffer exports from Theron."""
        from ...libs import theron

        try:
            exports = theron.get_particle_draw_mode_buffer_exports(pipeline)
            if exports is None:
                return None
            (prefix_h, prefix_s, prefix_uid), (binned_h, binned_s, binned_uid) = exports
            prefix = BufferExport(handle=prefix_h, size=prefix_s, uid=prefix_uid)
            binned = BufferExport(handle=binned_h, size=binned_s, uid=binned_uid)
            if prefix.valid and binned.valid:
                return (prefix, binned)
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_constraints_buffer(pipeline) -> BufferExport | None:
        """Fetch the per-particle constraint array export from Theron."""
        from ...libs import theron

        try:
            export = theron.get_particle_constraints_buffer_export(pipeline)
            if export is None:
                return None
            handle, size, uid = export
            buf = BufferExport(handle=handle, size=size, uid=uid)
            if buf.valid:
                return buf
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_id_lut_buffer(pipeline) -> tuple[BufferExport, int] | None:
        """Fetch the particle ID-LUT buffer export + its slot capacity."""
        from ...libs import theron

        try:
            export = theron.get_particle_id_lut_buffer_export(pipeline)
            if export is None:
                return None
            handle, size, uid, capacity = export
            buf = BufferExport(handle=handle, size=size, uid=uid)
            if buf.valid and capacity > 0:
                return (buf, capacity)
        except Exception:
            pass
        return None

    @staticmethod
    def fetch_draw_mode_host_buffers(pipeline):
        """Fetch CPU-visible draw-mode prefix + binned indices from Theron."""
        from ...libs import theron

        try:
            return theron.get_particle_draw_mode_host_buffers(pipeline)
        except Exception:
            return None

    @staticmethod
    def mode_bin_index(display_shape: str) -> int:
        """Return draw-mode bin index for the given shape name."""
        key = str(display_shape or "").upper()
        return int(DRAW_MODE_BIN_INDEX.get(key, 0))

    @staticmethod
    def mode_bin_range(prefix_u32, display_shape: str) -> tuple[int, int]:
        """Return [start, end) binned-index range for a display shape."""
        mode_index = ParticleRenderer.mode_bin_index(display_shape)
        if prefix_u32 is None or len(prefix_u32) == 0:
            return (0, 0)
        if mode_index < 0 or mode_index >= len(prefix_u32):
            return (0, 0)
        end_val = int(prefix_u32[mode_index])
        start_val = int(prefix_u32[mode_index - 1]) if mode_index > 0 else 0
        end_val = max(0, end_val)
        start_val = max(0, min(start_val, end_val))
        return (start_val, end_val)

    @staticmethod
    def iter_particle_indices(params, particle_count: int) -> np.ndarray:
        """Return source particle indices for this draw call as a numpy array.

        When no indirect binning is active, returns an ``arange`` view of all
        valid indices. Otherwise returns the relevant slice of the binned
        index buffer (already in ``0..particle_count-1`` because the buffer
        is produced by argsort/prefix-sum over the same particle count).
        """
        particle_count = max(0, int(particle_count))
        binned = getattr(params, "indirect_binned_indices", None)
        if binned is None:
            return np.arange(particle_count, dtype=np.uint32)
        if particle_count == 0:
            return np.empty(0, dtype=np.uint32)
        start = int(getattr(params, "indirect_start", 0) or 0)
        end = int(getattr(params, "indirect_end", 0) or 0)
        binned_len = int(len(binned))
        start = max(0, min(start, binned_len))
        end = max(start, min(end, binned_len))
        if end <= start:
            return np.empty(0, dtype=np.uint32)
        sub = np.asarray(binned[start:end])
        if sub.dtype != np.uint32:
            sub = sub.astype(np.uint32, copy=False)
        return sub

    @staticmethod
    def build_draw_mode_bins_cpu(
        pipeline,
        scene_key: int,
        particle_count: int,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        """Rebuild prefix + binned indices on CPU (matches GPU prefix-sum layout).

        Used when ``trGetParticleDrawModeHostBuffers`` is unavailable but
        per-particle display mode ids can be read.
        """
        from ...libs import theron

        n = int(particle_count)
        if n <= 0:
            return None
        modes = theron.get_particle_display_modes(pipeline, scene_key)
        if modes is None or modes.size == 0:
            return None
        if modes.size > n:
            modes = modes[:n]
        elif modes.size < n:
            return None
        modes_i = np.clip(modes.astype(np.int64, copy=False), 0, 13)
        order = np.argsort(modes_i, kind="stable")
        binned = order.astype(np.uint32)
        counts = np.bincount(modes_i, minlength=14)
        prefix = np.cumsum(counts).astype(np.uint32)
        return (prefix, binned)

    # -------------------------------------------------------------------
    # CPU-read helpers (basic / fallback mode)
    # -------------------------------------------------------------------

    @staticmethod
    def ensure_cpu_ready(scene, context) -> bool:
        """Make sure the pipeline has run with GPU_CPU copy mode.

        Returns True when CPU particle data is safe to read.
        """
        from ...handlers import pipeline as pipeline_manager

        copy_mode = pipeline_manager.get_copy_mode(scene)
        if copy_mode != "GPU_CPU":
            pipeline_manager.request_gpu_cpu_next_frame(scene)
            pipeline_manager.tag_ui_redraw()
            return False

        try:
            context.view_layer.update()
        except (AttributeError, RuntimeError):
            pass

        copy_mode = pipeline_manager.get_copy_mode(scene)
        if copy_mode != "GPU_CPU":
            pipeline_manager.request_gpu_cpu_next_frame(scene)
            pipeline_manager.tag_ui_redraw()
            return False

        if not pipeline_manager.ensure_pipeline_ready_for_cpu_read(scene, context):
            return False
        return True

    @staticmethod
    def read_cpu_positions(pipeline, scene_key: int):
        """Read CPU-side particle positions. Returns (positions, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION, scene_key
        )

    @staticmethod
    def read_cpu_colors(pipeline, scene_key: int):
        """Read CPU-side particle colours. Returns (colors, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_COLOR, scene_key
        )

    @staticmethod
    def read_cpu_velocities(pipeline, scene_key: int):
        """Read CPU-side particle velocities. Returns (velocities, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY, scene_key
        )

    @staticmethod
    def read_cpu_radii(pipeline, scene_key: int):
        """Read CPU-side particle radii. Returns (radii, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS, scene_key
        )

    @staticmethod
    def read_cpu_rotations(pipeline, scene_key: int):
        """Read CPU-side particle HPB rotations. Returns (rotations, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION, scene_key
        )

    @staticmethod
    def read_cpu_emitter_indices(pipeline, scene_key: int):
        """Read CPU-side per-particle emitter ids. Returns (indices, count) or None."""
        from ...libs import theron

        return theron.get_particle_property_for_gpu(
            pipeline, theron.TrParticleProperty.TR_PARTICLE_PROPERTY_EMITTER_INDEX, scene_key
        )

    @staticmethod
    def read_cpu_base(pipeline, scene_key: int):
        """Read positions + colours in one call. Returns (positions, colors, count) or None."""
        pos = ParticleRenderer.read_cpu_positions(pipeline, scene_key)
        if pos is None:
            return None
        positions, count = pos
        col = ParticleRenderer.read_cpu_colors(pipeline, scene_key)
        if col is None:
            return None
        colors, _ = col
        return positions, colors, count

    @staticmethod
    def ensure_cpu_ready_for_params(scene, context, params) -> bool:
        """Return cached readiness if present, otherwise run readiness checks."""
        cached = getattr(params, "cpu_ready", None)
        if cached is not None:
            return bool(cached)
        return ParticleRenderer.ensure_cpu_ready(scene, context)

    @staticmethod
    def read_cpu_base_for_params(params, pipeline, scene_key: int):
        """Return cached base arrays when available, otherwise fetch them."""
        positions = getattr(params, "cpu_positions", None)
        colors = getattr(params, "cpu_colors", None)
        count = getattr(params, "cpu_count", None)
        if positions is not None and colors is not None and count is not None:
            return positions, colors, int(count)
        return ParticleRenderer.read_cpu_base(pipeline, scene_key)

    @staticmethod
    def read_cpu_velocities_for_params(params, pipeline, scene_key: int):
        """Return cached velocity array when available, otherwise fetch it."""
        velocities = getattr(params, "cpu_velocities", None)
        count = getattr(params, "cpu_count", None)
        if velocities is not None and count is not None:
            return velocities, int(count)
        return ParticleRenderer.read_cpu_velocities(pipeline, scene_key)

    @staticmethod
    def read_cpu_radii_for_params(params, pipeline, scene_key: int):
        """Return cached radii array when available, otherwise fetch it."""
        radii = getattr(params, "cpu_radii", None)
        count = getattr(params, "cpu_count", None)
        if radii is not None and count is not None:
            return radii, int(count)
        return ParticleRenderer.read_cpu_radii(pipeline, scene_key)

    @staticmethod
    def read_cpu_rotations_for_params(params, pipeline, scene_key: int):
        """Return cached rotation array when available, otherwise fetch it."""
        rotations = getattr(params, "cpu_rotations", None)
        count = getattr(params, "cpu_count", None)
        if rotations is not None and count is not None:
            return rotations, int(count)
        return ParticleRenderer.read_cpu_rotations(pipeline, scene_key)

    @staticmethod
    def read_cpu_emitter_indices_for_params(params, pipeline, scene_key: int):
        """Return cached per-particle emitter ids when present, else fetch them."""
        indices = getattr(params, "cpu_emitter_indices", None)
        count = getattr(params, "cpu_count", None)
        if indices is not None and count is not None:
            return indices, int(count)
        return ParticleRenderer.read_cpu_emitter_indices(pipeline, scene_key)

    # -------------------------------------------------------------------
    # View matrix helpers
    # -------------------------------------------------------------------

    @staticmethod
    def get_region_info(context):
        """Return (region_data, region) or (None, None)."""
        region_data = getattr(context, "region_data", None)
        region = getattr(context, "region", None)
        return region_data, region

    @staticmethod
    def get_mvp_view(context):
        """Return flattened (mvp_list, view_list) or None."""
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return None
        try:
            mvp_mat = region_data.perspective_matrix
            view_mat = region_data.view_matrix
            mvp = [mvp_mat[i][j] for i in range(4) for j in range(4)]
            view = [view_mat[i][j] for i in range(4) for j in range(4)]
            return mvp, view
        except Exception:
            return None
