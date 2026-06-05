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

"""Blender GPU module point renderer (CPU fallback)."""

from __future__ import annotations

import numpy as np

from ...core.particle_renderer import ParticleRenderer

_shader = None


def _get_shader():
    global _shader
    if _shader is not None:
        return _shader
    import gpu

    vert_out = gpu.types.GPUStageInterfaceInfo("point_interface")
    vert_out.smooth("VEC3", "v_color")

    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("FLOAT", "psize")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    gl_PointSize = psize;\n"
        "    v_color = vcol;\n"
        "}\n"
    )
    info.fragment_source(
        "void main() {\n"
        "    vec2 centered = gl_PointCoord * 2.0 - 1.0;\n"
        "    float r2 = dot(centered, centered);\n"
        "    if (r2 > 1.0) { discard; }\n"
        "    FragColor = vec4(v_color, 1.0);\n"
        "}\n"
    )
    _shader = gpu.shader.create_from_info(info)
    return _shader


class PointBasicRenderer(ParticleRenderer):
    def draw(self, context, pipeline, scene, params) -> bool:
        sk = scene.session_uid
        if not self.ensure_cpu_ready_for_params(scene, context, params):
            return True  # not ready yet; don't fallback further

        base = self.read_cpu_base_for_params(params, pipeline, sk)
        if base is None:
            return True
        positions, colors, count = base
        if count == 0:
            return True

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True
        draw_positions = np.ascontiguousarray(positions[indices], dtype=np.float32)
        draw_colors = np.ascontiguousarray(colors[indices], dtype=np.float32)

        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = _get_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        shader.uniform_float("psize", params.size)
        batch = batch_for_shader(shader, "POINTS", {"pos": draw_positions, "vcol": draw_colors})
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
