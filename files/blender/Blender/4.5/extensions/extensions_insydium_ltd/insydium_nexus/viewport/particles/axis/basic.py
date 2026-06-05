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

"""Blender GPU module axis renderer (CPU fallback) — velocity-oriented axes per particle."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer
from ..basic_utils import (
    _rot_mats_hpb,
    resolve_forced_up,
)

_shader = None

_AXIS_COLORS = np.array(
    [
        (0.0, 1.0, 0.0),  # velocity direction — green
        (1.0, 0.0, 0.0),  # right — red
        (0.0, 0.0, 1.0),  # up — blue
    ],
    dtype=np.float32,
)


def _get_shader():
    global _shader
    if _shader is not None:
        return _shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("axis_interface")
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
    _shader = gpu.shader.create_from_info(info)
    return _shader


class AxisBasicRenderer(ParticleRenderer):
    def draw(self, context, pipeline, scene, params) -> bool:
        sk = scene.session_uid
        if not self.ensure_cpu_ready_for_params(scene, context, params):
            return True

        base = self.read_cpu_base_for_params(params, pipeline, sk)
        if base is None:
            return True
        positions, _colors, count = base
        if count == 0:
            return True

        rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
        use_hpb = rotation_mode == "UP_VECTOR"
        use_tangential = rotation_mode in ("NONE", "TANGENTIAL")
        rot_result = self.read_cpu_rotations_for_params(params, pipeline, sk) if use_hpb else None
        vel_result = self.read_cpu_velocities_for_params(params, pipeline, sk)
        if use_hpb and rot_result is None:
            use_hpb = False
            use_tangential = True
        if use_tangential and vel_result is None:
            return True
        if not use_hpb and not use_tangential:
            if vel_result is None:
                return True
            use_tangential = True
        rotations = rot_result[0] if (use_hpb and rot_result is not None) else None
        velocities = vel_result[0] if vel_result is not None else None

        rad_result = self.read_cpu_radii_for_params(params, pipeline, sk)
        radii = rad_result[0] if rad_result is not None else None

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True

        pos_sub = positions[indices].astype(np.float32, copy=False)
        default_size = np.float32(params.size)
        if radii is not None:
            size = np.maximum(radii[indices].astype(np.float32, copy=False), np.float32(1e-6))
        else:
            size = np.full(pos_sub.shape[0], default_size, dtype=np.float32)

        forced_up = resolve_forced_up(getattr(params, "rotation_up_vector", "Y_POS"))

        # Build per-particle (forward, right, up) axes vectorized.
        if use_hpb and rotations is not None:
            rot_sub = rotations[indices]
            rot_mats = _rot_mats_hpb(rot_sub, forced_up)
            # Axis directions match the scalar version: forward=[0,1,0], right=[-1,0,0],up=[0,0,1].
            forward = rot_mats[:, :, 1]
            right = -rot_mats[:, :, 0]
            up = rot_mats[:, :, 2]
        else:
            vel_sub = velocities[indices]
            # Local frame from velocity (raw velocity, no 0.01 scale — matches legacy behavior).
            v = vel_sub.astype(np.float32, copy=False)
            len_sq = np.einsum("ki,ki->k", v, v)
            safe = len_sq > np.float32(1e-18)
            inv_len = np.zeros_like(len_sq)
            np.reciprocal(np.maximum(np.sqrt(len_sq), np.float32(1e-18)), out=inv_len)
            forward = np.where(safe[:, None], v * inv_len[:, None], np.float32([0.0, 0.0, 1.0]))
            z_up = np.float32([0.0, 0.0, 1.0])
            y_up = np.float32([0.0, 1.0, 0.0])
            ref = np.where(np.abs(forward[:, 2:3]) < 0.999, z_up, y_up)
            right = np.cross(forward, ref)
            r_len = np.linalg.norm(right, axis=1, keepdims=True)
            right = right / np.maximum(r_len, np.float32(1e-12))
            up = np.cross(right, forward)

        # Stack the three axes so that axis_dirs[:, a] is the a-th axis direction (3,).
        axis_dirs = np.stack([forward, right, up], axis=1)  # (K, 3, 3)

        # Build line segments: for each axis a and particle k produce (pos, pos + dir*size).
        starts = np.broadcast_to(pos_sub[:, None, :], (pos_sub.shape[0], 3, 3))
        ends = pos_sub[:, None, :] + axis_dirs * size[:, None, None]
        coords = np.stack([starts, ends], axis=2).reshape(-1, 3)  # (K*3*2, 3)
        line_colors = np.broadcast_to(_AXIS_COLORS[None, :, None, :], (pos_sub.shape[0], 3, 2, 3))
        line_colors = np.ascontiguousarray(line_colors.reshape(-1, 3))

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        batch = batch_for_shader(
            shader,
            "LINES",
            {"pos": coords, "vcol": line_colors},
        )
        prev_depth_test = gpu.state.depth_test_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            batch.draw(shader)
        finally:
            gpu.state.depth_test_set(prev_depth_test)
        return True

    def shutdown(self) -> None:
        global _shader
        _shader = None
