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

"""CPU fallback arrow renderer (basic backend)."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer
from ..basic_utils import (
    resolve_forced_up,
    resolve_rotation_mode,
    rot_mats_for_shape,
)

_shaders: dict[bool, object] = {}


def _get_shader(filled: bool):
    cached = _shaders.get(filled)
    if cached is not None:
        return cached

    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("arrow_interface")
    vert_out.smooth("VEC3", "v_color")
    if filled:
        vert_out.smooth("VEC4", "v_param")

    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    if filled:
        info.vertex_in(2, "VEC4", "aux")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    v_color = vcol;\n" + ("    v_param = aux;\n" if filled else "") + "}\n"
    )
    if filled:
        info.fragment_source(
            "void main() {\n"
            "    const float k = 0.12;\n"
            "    const float vw_shaft = 0.12;\n"
            "    float vig = 0.0;\n"
            "    if (v_param.w < 0.5) {\n"
            "        float cx = v_param.x * 2.0 - 1.0;\n"
            "        float cy = v_param.y * 2.0 - 1.0;\n"
            "        float lateral = smoothstep(1.0 - vw_shaft, 1.0, abs(cx));\n"
            "        float tail = 1.0 - smoothstep(-1.0, -1.0 + vw_shaft, cy);\n"
            "        vig = max(lateral, tail);\n"
            "    } else {\n"
            "        vec3 b = v_param.xyz;\n"
            "        float m_st = min(b.x, b.y);\n"
            "        float suppress_base = smoothstep(0.04, 0.10, b.z);\n"
            "        float w = max(0.04, fwidth(m_st) * 2.5);\n"
            "        vig = (1.0 - smoothstep(0.0, w, m_st)) * suppress_base;\n"
            "    }\n"
            "    FragColor = vec4(v_color * (1.0 - k * vig), 1.0);\n"
            "}\n"
        )
    else:
        info.fragment_source("void main() {\n    FragColor = vec4(v_color, 1.0);\n}\n")

    shader = gpu.shader.create_from_info(info)
    _shaders[filled] = shader
    return shader


# Filled layout: 2 shaft triangles + 1 head triangle = 9 vertices per particle.
# Corner flags reference (start_left, start_right, end_left, end_right, head_left, head_right,tip).
_FILLED_CORNER_IDS = np.array(
    [0, 1, 3, 0, 3, 2, 4, 5, 6],
    dtype=np.int32,
)
_FILLED_AUX = np.array(
    [
        (0, 0, 0, 0),
        (1, 0, 0, 0),
        (1, 1, 0, 0),
        (0, 0, 0, 0),
        (1, 1, 0, 0),
        (0, 1, 0, 0),
        (1, 0, 0, 1),
        (0, 1, 0, 1),
        (0, 0, 1, 1),
    ],
    dtype=np.float32,
)

# Line layout: 7 line segments -> 14 vertices per particle.
_LINE_CORNER_IDS = np.array(
    [0, 1, 1, 3, 3, 2, 2, 0, 4, 5, 5, 6, 6, 4],
    dtype=np.int32,
)


class ArrowBasicRenderer(ParticleRenderer):
    def __init__(self, filled: bool = False) -> None:
        self._filled = filled

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

        radii_result = self.read_cpu_radii_for_params(params, pipeline, sk)
        radii_array = radii_result[0] if radii_result is not None else None

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True
        K = indices.shape[0]

        mode = int(getattr(params, "line_length_mode", 0))  # 0=SPEED, 1=RADIUS, 2=FIXED
        fixed_length = max(1e-6, float(getattr(params, "line_fixed_length", 0.1)))

        rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
        use_hpb = rotation_mode == "UP_VECTOR"
        use_tangential = rotation_mode in ("NONE", "TANGENTIAL")
        rot_result = self.read_cpu_rotations_for_params(params, pipeline, sk) if use_hpb else None
        needs_velocity = use_tangential or (not use_hpb) or mode == 0 or rot_result is None
        vel_result = (
            self.read_cpu_velocities_for_params(params, pipeline, sk) if needs_velocity else None
        )
        use_hpb, use_tangential, rotations_arr, velocities_arr = resolve_rotation_mode(
            params, rot_result, vel_result
        )
        if use_hpb and rotations_arr is None:
            return True
        if use_tangential and velocities_arr is None:
            return True

        pos_sub = positions[indices].astype(np.float32, copy=False)
        vel_sub = (
            velocities_arr[indices].astype(np.float32, copy=False)
            if velocities_arr is not None
            else np.zeros((K, 3), dtype=np.float32)
        )
        col_sub = colors[indices].astype(np.float32, copy=False)
        radii_sub = (
            radii_array[indices].astype(np.float32, copy=False)
            if radii_array is not None
            else None
        )
        rotations_sub = (
            rotations_arr[indices].astype(np.float32, copy=False)
            if rotations_arr is not None
            else None
        )

        forced_up = resolve_forced_up(getattr(params, "rotation_up_vector", "Y_POS"))
        rot_mats = rot_mats_for_shape(
            use_hpb=use_hpb,
            use_tangential=use_tangential,
            rotations_sub=rotations_sub,
            velocities_sub=vel_sub if use_tangential else None,
            forced_up=forced_up,
            count=K,
        )
        # Match axis orientation conventions:
        # - forward is local +Y
        # - "side up" is local +Z
        dir3 = rot_mats[:, :, 1]
        perp = rot_mats[:, :, 2]
        dir3 = dir3 / np.maximum(np.linalg.norm(dir3, axis=1, keepdims=True), np.float32(1e-12))
        perp = perp / np.maximum(np.linalg.norm(perp, axis=1, keepdims=True), np.float32(1e-12))

        speed_sq = np.einsum("ki,ki->k", vel_sub, vel_sub)
        speed = np.sqrt(speed_sq)
        if mode == 2:  # FIXED
            line_len = np.full(K, np.float32(fixed_length), dtype=np.float32)
        elif mode == 1 and radii_sub is not None:  # RADIUS
            line_len = np.maximum(radii_sub, np.float32(1e-6))
        else:  # SPEED (or RADIUS fallback)
            line_len = np.maximum(speed * np.float32(0.1), np.float32(1e-6))

        # Clamp Speed/Radius length to the optional min/max range (0 = bound off).
        if mode != 2:
            min_len = float(getattr(params, "line_min_length", 0.0))
            max_len = float(getattr(params, "line_max_length", 0.0))
            if min_len > 0.0:
                line_len = np.maximum(line_len, np.float32(min_len))
            if max_len > 0.0:
                line_len = np.minimum(line_len, np.float32(max_len))

        half_vec = dir3 * (line_len[:, None] * np.float32(0.5))
        tail = pos_sub - half_vec
        end = pos_sub + half_vec

        if radii_sub is not None:
            radius_blend = radii_sub
        else:
            radius_blend = line_len * np.float32(0.05)
        base_width = np.maximum(radius_blend * np.float32(0.5), line_len * np.float32(0.05))
        shaft_hw = base_width
        head_hw = base_width * np.float32(1.6)
        head_len = np.maximum(line_len * np.float32(0.25), np.float32(1e-6))
        shaft_end = end - dir3 * head_len[:, None]

        perp_shaft = perp * shaft_hw[:, None]
        perp_head = perp * head_hw[:, None]

        # Build the 7 named corners as a (K, 7, 3) tensor so the index buffers just gather them.
        corners = np.stack(
            [
                tail - perp_shaft,  # 0 start_left
                tail + perp_shaft,  # 1 start_right
                shaft_end - perp_shaft,  # 2 end_left
                shaft_end + perp_shaft,  # 3 end_right
                shaft_end - perp_head,  # 4 head_left
                shaft_end + perp_head,  # 5 head_right
                end,  # 6 tip
            ],
            axis=1,
        )

        import gpu
        from gpu_extras.batch import batch_for_shader

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        shader = _get_shader(self._filled)
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)

        prev_depth_mask = gpu.state.depth_mask_get()
        prev_depth_test = gpu.state.depth_test_get()

        if self._filled:
            verts = corners[:, _FILLED_CORNER_IDS, :].reshape(-1, 3)
            cols = np.broadcast_to(col_sub[:, None, :], (K, _FILLED_CORNER_IDS.size, 3))
            cols = np.ascontiguousarray(cols.reshape(-1, 3), dtype=np.float32)
            aux = np.broadcast_to(_FILLED_AUX, (K, _FILLED_AUX.shape[0], 4))
            aux = np.ascontiguousarray(aux.reshape(-1, 4), dtype=np.float32)
            batch = batch_for_shader(
                shader,
                "TRIS",
                {"pos": verts, "vcol": cols, "aux": aux},
            )
            try:
                gpu.state.depth_test_set("LESS_EQUAL")
                gpu.state.depth_mask_set(True)
                batch.draw(shader)
            finally:
                gpu.state.depth_mask_set(prev_depth_mask)
                gpu.state.depth_test_set(prev_depth_test)
        else:
            verts = corners[:, _LINE_CORNER_IDS, :].reshape(-1, 3)
            cols = np.broadcast_to(col_sub[:, None, :], (K, _LINE_CORNER_IDS.size, 3))
            cols = np.ascontiguousarray(cols.reshape(-1, 3), dtype=np.float32)
            batch = batch_for_shader(shader, "LINES", {"pos": verts, "vcol": cols})
            try:
                gpu.state.depth_test_set("LESS_EQUAL")
                batch.draw(shader)
            finally:
                gpu.state.depth_test_set(prev_depth_test)

        return True

    def shutdown(self) -> None:
        _shaders.clear()


class ArrowFilledBasicRenderer(ArrowBasicRenderer):
    def __init__(self) -> None:
        super().__init__(filled=True)
