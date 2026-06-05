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

"""Blender GPU module square renderer (CPU fallback)."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer
from ..basic_utils import view_basis

_shader = None

# Per-vertex offsets expressed in (right, up) camera coordinates for a two-tri quad.
_QUAD_OFFSETS_RU = np.array(
    [
        (-1.0, -1.0),
        (1.0, -1.0),
        (1.0, 1.0),
        (-1.0, -1.0),
        (1.0, 1.0),
        (-1.0, 1.0),
    ],
    dtype=np.float32,
)

_QUAD_UVS = np.array(
    [
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    ],
    dtype=np.float32,
)


def _get_shader():
    global _shader
    if _shader is not None:
        return _shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("quad_interface")
    vert_out.smooth("VEC3", "v_color")
    vert_out.smooth("VEC2", "v_uv")

    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    info.vertex_in(2, "VEC2", "uv")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    v_color = vcol;\n"
        "    v_uv = uv;\n"
        "}\n"
    )
    info.fragment_source(
        "void main() {\n"
        "    vec2 c = v_uv * 2.0 - 1.0;\n"
        "    float edge = max(abs(c.x), abs(c.y));\n"
        "    const float vw = 0.12;\n"
        "    float vig = smoothstep(1.0 - vw, 1.0, edge);\n"
        "    const float k = 0.12;\n"
        "    FragColor = vec4(v_color * (1.0 - k * vig), 1.0);\n"
        "}\n"
    )
    _shader = gpu.shader.create_from_info(info)
    return _shader


def build_camera_quad_buffers(
    pos_sub: np.ndarray,
    col_sub: np.ndarray,
    hs: np.ndarray,
    right: np.ndarray,
    up: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(quad_pos, quad_uvs, quad_cols)`` for ``K`` camera-facing quads."""
    # (6, 3): six vertex offsets in world space (independent of particle size).
    quad_dirs = _QUAD_OFFSETS_RU[:, 0:1] * right[None, :] + _QUAD_OFFSETS_RU[:, 1:2] * up[None, :]
    # (K, 6, 3) world positions.
    quad_pos = pos_sub[:, None, :] + hs[:, None, None] * quad_dirs[None, :, :]
    quad_pos = quad_pos.reshape(-1, 3)
    # Broadcast color and uvs without per-particle loops.
    quad_cols = np.broadcast_to(col_sub[:, None, :], (col_sub.shape[0], 6, col_sub.shape[1]))
    quad_cols = np.ascontiguousarray(quad_cols.reshape(-1, col_sub.shape[1]))
    quad_uvs = np.broadcast_to(_QUAD_UVS, (pos_sub.shape[0], 6, 2)).reshape(-1, 2)
    quad_uvs = np.ascontiguousarray(quad_uvs)
    return quad_pos, quad_uvs, quad_cols


class SquareBasicRenderer(ParticleRenderer):
    def draw(self, context, pipeline, scene, params) -> bool:
        sk = scene.session_uid
        if not self.ensure_cpu_ready_for_params(scene, context, params):
            return True

        base = self.read_cpu_base_for_params(params, pipeline, sk)
        if base is None:
            return True
        positions, colors, count = base
        if count == 0:
            return True

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        radii_result = self.read_cpu_radii_for_params(params, pipeline, sk)
        radii_array = radii_result[0] if radii_result is not None else None

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True

        right, up, _forward = view_basis(region_data.view_matrix)
        default_half = np.float32(params.size) * np.float32(0.01)

        pos_sub = positions[indices].astype(np.float32, copy=False)
        col_sub = colors[indices].astype(np.float32, copy=False)
        if radii_array is not None:
            hs = radii_array[indices].astype(np.float32, copy=False)
        else:
            hs = np.full(pos_sub.shape[0], default_half, dtype=np.float32)

        quad_pos, quad_uvs, quad_cols = build_camera_quad_buffers(pos_sub, col_sub, hs, right, up)

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        batch = batch_for_shader(
            shader, "TRIS", {"pos": quad_pos, "vcol": quad_cols, "uv": quad_uvs}
        )
        prev_depth_mask = gpu.state.depth_mask_get()
        prev_depth_test = gpu.state.depth_test_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(True)
            batch.draw(shader)
        finally:
            gpu.state.depth_mask_set(prev_depth_mask)
            gpu.state.depth_test_set(prev_depth_test)
        return True

    def shutdown(self) -> None:
        global _shader
        _shader = None
