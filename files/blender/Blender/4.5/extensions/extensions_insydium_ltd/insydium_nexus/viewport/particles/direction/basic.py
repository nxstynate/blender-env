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

"""Blender GPU module direction-line renderer (CPU fallback)."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer

_shader = None


def _get_shader():
    global _shader
    if _shader is not None:
        return _shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("line_interface")
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


class DirectionBasicRenderer(ParticleRenderer):
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

        vel_result = self.read_cpu_velocities_for_params(params, pipeline, sk)
        if vel_result is None:
            return True
        velocities = vel_result[0]

        mode = int(getattr(params, "line_length_mode", 0))
        fixed_length = max(1e-6, float(getattr(params, "line_fixed_length", 0.1)))
        radii = None
        if mode == 1:  # RADIUS
            rad_result = self.read_cpu_radii_for_params(params, pipeline, sk)
            if rad_result is None:
                # Fallback to render by speed (no "particle size" usage).
                mode = 0
            else:
                radii = rad_result[0]

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True

        pos_sub = positions[indices].astype(np.float32, copy=False)
        vel_sub = velocities[indices].astype(np.float32, copy=False)
        col_sub = colors[indices].astype(np.float32, copy=False)

        speed_sq = np.einsum("ki,ki->k", vel_sub, vel_sub)
        speed = np.sqrt(speed_sq)
        # Per-particle line length
        if mode == 2:  # FIXED
            line_len = np.full(pos_sub.shape[0], np.float32(fixed_length), dtype=np.float32)
        elif mode == 1:  # RADIUS
            line_len = np.maximum(radii[indices].astype(np.float32, copy=False), np.float32(1e-6))
        else:  # SPEED
            line_len = np.maximum(speed * np.float32(0.1), np.float32(1e-6))

        # Clamp Speed/Radius length to the optional min/max range (0 = bound off).
        if mode != 2:
            min_len = float(getattr(params, "line_min_length", 0.0))
            max_len = float(getattr(params, "line_max_length", 0.0))
            if min_len > 0.0:
                line_len = np.maximum(line_len, np.float32(min_len))
            if max_len > 0.0:
                line_len = np.minimum(line_len, np.float32(max_len))

        # Direction: vel / |vel| with (0,0,1) fallback where |vel| is tiny.
        safe = speed_sq > np.float32(1e-18)
        inv_speed = np.zeros_like(speed)
        np.reciprocal(np.maximum(speed, np.float32(1e-18)), out=inv_speed)
        direction = np.where(
            safe[:, None], vel_sub * inv_speed[:, None], np.float32([0.0, 0.0, 1.0])
        )
        end = pos_sub + direction * line_len[:, None]

        # Interleave start/end for LINES primitive.
        line_pos = np.empty((pos_sub.shape[0] * 2, 3), dtype=np.float32)
        line_pos[0::2] = pos_sub
        line_pos[1::2] = end
        line_cols = np.repeat(col_sub, 2, axis=0)

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_shader()
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
        global _shader
        _shader = None
