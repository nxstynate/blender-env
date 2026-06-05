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

"""CPU fallback axis-aligned pyramid particle modes."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer
from ..basic_utils import (
    blinn_phong_batch,
    resolve_forced_up,
    resolve_rotation_mode,
    rot_mats_for_shape,
    view_matrices,
)

_line_shader = None
_filled_shader = None


def _get_line_shader():
    global _line_shader
    if _line_shader is not None:
        return _line_shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("pyr3d_if")
    vert_out.flat("VEC3", "v_color")
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    v_color = vcol;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n    FragColor = vec4(v_color, 1.0);\n}\n")
    _line_shader = gpu.shader.create_from_info(info)
    return _line_shader


def _get_filled_shader():
    global _filled_shader
    if _filled_shader is not None:
        return _filled_shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("pyr3df_if")
    vert_out.smooth("VEC3", "v_color")
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    v_color = vcol;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n    FragColor = vec4(v_color, 1.0);\n}\n")
    _filled_shader = gpu.shader.create_from_info(info)
    return _filled_shader


_EDGES = np.array(
    [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (0, 4),
        (1, 4),
        (2, 4),
        (3, 4),
    ],
    dtype=np.int32,
)

_TRIS = np.array(
    [
        (0, 1, 2),
        (0, 2, 3),
        (0, 3, 4),
        (1, 4, 2),
        (3, 2, 4),
        (0, 4, 1),
    ],
    dtype=np.int32,
)

_INV_SQRT5 = float(1.0 / np.sqrt(5.0))
_TRI_FACE_NORMALS = np.array(
    [
        (0.0, -1.0, 0.0),
        (0.0, -1.0, 0.0),
        (-2.0 * _INV_SQRT5, _INV_SQRT5, 0.0),
        (2.0 * _INV_SQRT5, _INV_SQRT5, 0.0),
        (0.0, _INV_SQRT5, 2.0 * _INV_SQRT5),
        (0.0, _INV_SQRT5, -2.0 * _INV_SQRT5),
    ],
    dtype=np.float32,
)

_CORNERS = np.array(
    [
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, -1.0, 1.0),
        (-1.0, -1.0, 1.0),
        (0.0, 1.0, 0.0),
    ],
    dtype=np.float32,
)

_TRI_VERT_IDS = _TRIS.reshape(-1)  # (18,)
# Each triangle has its own face normal (no shared faces besides the base).
_FACE_OF_TRI_VERT = np.repeat(np.arange(_TRIS.shape[0], dtype=np.int32), 3)  # (18,)


class PyramidBasicRenderer(ParticleRenderer):
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
        default_half = np.float32(params.size) * np.float32(0.01)
        rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
        use_hpb = rotation_mode == "UP_VECTOR"
        use_tangential = rotation_mode in ("NONE", "TANGENTIAL")
        rot_result = self.read_cpu_rotations_for_params(params, pipeline, sk) if use_hpb else None
        vel_result = (
            self.read_cpu_velocities_for_params(params, pipeline, sk)
            if (use_tangential or not use_hpb)
            else None
        )
        use_hpb, use_tangential, rotations_arr, velocities_arr = resolve_rotation_mode(
            params, rot_result, vel_result
        )
        forced_up = resolve_forced_up(getattr(params, "rotation_up_vector", "Y_POS"))

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True
        K = indices.shape[0]

        pos_sub = positions[indices].astype(np.float32, copy=False)
        col_sub = colors[indices].astype(np.float32, copy=False)
        if radii_array is not None:
            h = radii_array[indices].astype(np.float32, copy=False)
        else:
            h = np.full(K, default_half, dtype=np.float32)
        rot_sub = rotations_arr[indices] if rotations_arr is not None else None
        vel_sub = velocities_arr[indices] if velocities_arr is not None else None
        rot_mats = rot_mats_for_shape(use_hpb, use_tangential, rot_sub, vel_sub, forced_up, K)

        corners_world = np.einsum("kij,cj->kci", rot_mats, _CORNERS) * h[:, None, None]
        corners_world += pos_sub[:, None, :]

        line_pos = corners_world[:, _EDGES, :].reshape(-1, 3)
        n_line_verts = _EDGES.shape[0] * 2
        line_cols = np.broadcast_to(col_sub[:, None, :], (K, n_line_verts, 3)).reshape(-1, 3)
        line_cols = np.ascontiguousarray(line_cols, dtype=np.float32)

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_line_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        batch = batch_for_shader(shader, "LINES", {"pos": line_pos, "vcol": line_cols})
        prev_depth_test = gpu.state.depth_test_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            batch.draw(shader)
        finally:
            gpu.state.depth_test_set(prev_depth_test)
        return True

    def shutdown(self) -> None:
        global _line_shader
        _line_shader = None


class PyramidFilledBasicRenderer(ParticleRenderer):
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

        view_gl, r3, l_v = view_matrices(region_data.view_matrix)

        radii_result = self.read_cpu_radii_for_params(params, pipeline, sk)
        radii_array = radii_result[0] if radii_result is not None else None
        default_half = np.float32(params.size) * np.float32(0.01)
        rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
        use_hpb = rotation_mode == "UP_VECTOR"
        use_tangential = rotation_mode in ("NONE", "TANGENTIAL")
        rot_result = self.read_cpu_rotations_for_params(params, pipeline, sk) if use_hpb else None
        vel_result = (
            self.read_cpu_velocities_for_params(params, pipeline, sk)
            if (use_tangential or not use_hpb)
            else None
        )
        use_hpb, use_tangential, rotations_arr, velocities_arr = resolve_rotation_mode(
            params, rot_result, vel_result
        )
        forced_up = resolve_forced_up(getattr(params, "rotation_up_vector", "Y_POS"))

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True
        K = indices.shape[0]

        pos_sub = positions[indices].astype(np.float32, copy=False)
        col_sub = colors[indices].astype(np.float32, copy=False)
        if radii_array is not None:
            h = radii_array[indices].astype(np.float32, copy=False)
            h = np.where(np.isfinite(h), h, default_half)
        else:
            h = np.full(K, default_half, dtype=np.float32)
        h = np.maximum(h, np.float32(1e-9))
        rot_sub = rotations_arr[indices] if rotations_arr is not None else None
        vel_sub = velocities_arr[indices] if velocities_arr is not None else None
        rot_mats = rot_mats_for_shape(use_hpb, use_tangential, rot_sub, vel_sub, forced_up, K)

        corners_world = np.einsum("kij,cj->kci", rot_mats, _CORNERS) * h[:, None, None]
        corners_world += pos_sub[:, None, :]
        face_normals_world = np.einsum("kij,fj->kfi", rot_mats, _TRI_FACE_NORMALS)

        tri_pos = corners_world[:, _TRI_VERT_IDS, :]
        tri_normals = face_normals_world[:, _FACE_OF_TRI_VERT, :]
        base_rgb = col_sub[:, None, :]

        tri_cols = blinn_phong_batch(tri_pos, tri_normals, view_gl, r3, l_v, base_rgb)

        tri_pos = tri_pos.reshape(-1, 3)
        tri_cols = tri_cols.reshape(-1, 3)

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_filled_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        batch = batch_for_shader(shader, "TRIS", {"pos": tri_pos, "vcol": tri_cols})
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
        global _filled_shader
        _filled_shader = None
