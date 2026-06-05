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

"""OpenGL zero-copy direction-line renderer (indirect binned draw)."""

from __future__ import annotations

from ..indirect_opengl_base import FLAT_COLOR_FRAG
from ..vel_indirect_opengl import VelIndirectOpenGLBase

try:
    from OpenGL.GL import GL_LINES as _GL_LINES

    _GL_OK = True
except ImportError:
    _GL_LINES = 0
    _GL_OK = False

_LINE_VERT = """
#version 430 core
layout(location = 0) in vec3 dummy_vert;

layout(std430, binding = 3) readonly buffer Positions { vec4 positions[]; };
layout(std430, binding = 4) readonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 5) readonly buffer DrawState { uint start_index; };
layout(std430, binding = 6) readonly buffer Radii { float radii[]; };
layout(std430, binding = 7) readonly buffer Colors { vec4 colors[]; };
layout(std430, binding = 8) readonly buffer EmitterIndices { uint emitter_indices[]; };
layout(std430, binding = 9) readonly buffer Velocities { vec4 velocities[]; };

uniform mat4 mvp;
uniform float line_scale;
uniform int line_length_mode;
uniform vec4 color;
uniform int use_color_buffer;
uniform int use_radius;

uniform int emitter_line_modes_count;
uniform int emitter_line_modes[64];
uniform int emitter_fixed_lengths_count;
uniform float emitter_line_fixed[64];
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_colors_count;
uniform vec4 emitter_colors[64];

uniform float line_min_length;
uniform float line_max_length;
uniform int emitter_line_min_count;
uniform float emitter_line_min[64];
uniform int emitter_line_max_count;
uniform float emitter_line_max[64];

flat out vec4 v_color;

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    vec3 blender_pos = positions[particle_idx].xyz;
    vec3 blender_vel = velocities[particle_idx].xyz;

    float lenSq = dot(blender_vel, blender_vel);
    vec3 fallbackDir = vec3(0.0, 0.0, 1.0);
    vec3 dir = (lenSq <= 1e-18)
        ? fallbackDir
        : blender_vel * inversesqrt(lenSq);

    float particle_radius = 1.0;
    if (use_radius != 0) {
        particle_radius = radii[particle_idx];
    } else if (emitter_sizes_count > 0) {
        uint si = min(emitter_idx, uint(max(emitter_sizes_count - 1, 0)));
        particle_radius = emitter_sizes[si];
    }

    int llm = line_length_mode;
    if (emitter_line_modes_count > 0) {
        uint li = min(emitter_idx, uint(max(emitter_line_modes_count - 1, 0)));
        llm = emitter_line_modes[li];
    }

    float fixed_len = line_scale;
    if (emitter_fixed_lengths_count > 0) {
        uint fi = min(emitter_idx, uint(max(emitter_fixed_lengths_count - 1, 0)));
        fixed_len = emitter_line_fixed[fi];
    }

    float lineLen;
    if (llm == 0) {
        lineLen = sqrt(lenSq) * 0.1;
    } else if (llm == 1) {
        lineLen = particle_radius;
    } else {
        lineLen = fixed_len;
    }
    lineLen = max(lineLen, 1e-6);

    if (llm != 2) {
        float minL = line_min_length;
        if (emitter_line_min_count > 0) {
            uint mi = min(emitter_idx, uint(max(emitter_line_min_count - 1, 0)));
            minL = emitter_line_min[mi];
        }
        float maxL = line_max_length;
        if (emitter_line_max_count > 0) {
            uint xi = min(emitter_idx, uint(max(emitter_line_max_count - 1, 0)));
            maxL = emitter_line_max[xi];
        }
        if (minL > 0.0) lineLen = max(lineLen, minL);
        if (maxL > 0.0) lineLen = min(lineLen, maxL);
    }

    vec3 world = (gl_VertexID == 0)
        ? blender_pos
        : blender_pos + dir * lineLen;
    gl_Position = mvp * vec4(world, 1.0);

    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint ci = min(emitter_idx, uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[ci];
    } else {
        v_color = color;
    }
}
"""


class DirectionOpenGLRenderer(VelIndirectOpenGLBase):
    """Binned indirect GL_LINES (2 verts per instance)."""

    def __init__(self, bridge) -> None:
        super().__init__(
            bridge,
            gl_primitive=_GL_LINES,
            verts_per_instance=2,
            vertex_shader_src=_LINE_VERT,
            fragment_shader_src=FLAT_COLOR_FRAG,
        )

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        return super().draw(context, pipeline, scene, params)
