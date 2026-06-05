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

"""OpenGL zero-copy arrow renderer (indirect binned draw)."""

from __future__ import annotations

from ..vel_indirect_opengl import VelIndirectOpenGLBase

try:
    from OpenGL.GL import GL_LINES as _GL_LINES
    from OpenGL.GL import GL_TRIANGLES as _GL_TRIANGLES

    _GL_OK = True
except ImportError:
    _GL_LINES = 0
    _GL_TRIANGLES = 0
    _GL_OK = False

_ARROW_SSBO_HEADER = """
#version 430 core
layout(location = 0) in vec3 dummy_vert;

layout(std430, binding = 3) readonly buffer Positions { vec4 positions[]; };
layout(std430, binding = 4) readonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 5) readonly buffer DrawState { uint start_index; };
layout(std430, binding = 6) readonly buffer Radii { float radii[]; };
layout(std430, binding = 7) readonly buffer Colors { vec4 colors[]; };
layout(std430, binding = 8) readonly buffer EmitterIndices { uint emitter_indices[]; };
layout(std430, binding = 9) readonly buffer Velocities { vec4 velocities[]; };
layout(std430, binding = 10) readonly buffer Rotations { vec4 rotations[]; };

uniform mat4 mvp;
uniform float line_scale;
uniform int line_length_mode;
uniform vec4 color;
uniform int use_color_buffer;
uniform int use_radius;
uniform int use_hpb;
uniform vec3 forced_up;

uniform int emitter_line_modes_count;
uniform int emitter_line_modes[64];
uniform int emitter_fixed_lengths_count;
uniform float emitter_line_fixed[64];
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_colors_count;
uniform vec4 emitter_colors[64];
uniform int emitter_rotation_modes_count;
uniform int emitter_rotation_modes[64];
uniform int emitter_up_vectors_count;
uniform vec3 emitter_up_vectors[64];

uniform float line_min_length;
uniform float line_max_length;
uniform int emitter_line_min_count;
uniform float emitter_line_min[64];
uniform int emitter_line_max_count;
uniform float emitter_line_max[64];

mat3 rot_x(float a) { float c = cos(a), s = sin(a); return mat3(1.0,0.0,0.0, 0.0,c,-s, 0.0,s,c); }
mat3 rot_y(float a) { float c = cos(a), s = sin(a); return mat3(c,0.0,s, 0.0,1.0,0.0, -s,0.0,c); }
mat3 rot_z(float a) { float c = cos(a), s = sin(a); return mat3(c,-s,0.0, s,c,0.0, 0.0,0.0,1.0); }

mat3 orient_from_up(vec3 up_ref) {
    float up_len_sq = dot(up_ref, up_ref);
    vec3 up = (up_len_sq > 1e-12) ? (up_ref * inversesqrt(up_len_sq)) : vec3(0.0, 0.0, 1.0);
    vec3 ref = (abs(up.z) < 0.999) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec3 right = normalize(cross(up, ref));
    vec3 forward = normalize(cross(right, up));
    return mat3(right, forward, up);
}
"""

_ARROW_OUTLINE_BODY = """
flat out vec4 v_color;

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    vec3 blender_pos = positions[particle_idx].xyz;
    vec3 blender_vel = velocities[particle_idx].xyz;

    float lenSq = dot(blender_vel, blender_vel);
    vec3 dir = (lenSq <= 1e-18)
        ? vec3(0.0, 0.0, 1.0)
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

    int rot_mode = use_hpb;
    if (emitter_rotation_modes_count > 0) {
        uint ri = min(emitter_idx, uint(max(emitter_rotation_modes_count - 1, 0)));
        rot_mode = emitter_rotation_modes[ri];
    }
    vec3 perp = vec3(0.0, 0.0, 1.0);
    if (rot_mode == 1) {
        vec3 up_ref = forced_up;
        if (emitter_up_vectors_count > 0) {
            uint ui = min(emitter_idx, uint(max(emitter_up_vectors_count - 1, 0)));
            up_ref = emitter_up_vectors[ui];
        }
        mat3 up_basis = orient_from_up(up_ref);
        vec3 dir_or_hpb = rotations[particle_idx].xyz;
        vec3 hpb = vec3(dir_or_hpb.y, dir_or_hpb.z, dir_or_hpb.x);
        mat3 hpb_rot = rot_z(hpb.z) * rot_x(hpb.x) * rot_y(hpb.y);
        mat3 rot = up_basis * hpb_rot;
        dir = normalize(rot * vec3(0.0, 1.0, 0.0));
        perp = normalize(rot * vec3(0.0, 0.0, 1.0));
    } else if (rot_mode == 2) {
        vec3 velocity = velocities[particle_idx].xyz;
        float velLenSq = dot(velocity, velocity);
        vec3 forward = (velLenSq <= 1e-18) ? vec3(0.0, 0.0, 1.0) : velocity *inversesqrt(velLenSq);
        vec3 ref = (abs(forward.z) < 0.999) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(forward, ref));
        vec3 up = normalize(cross(right, forward));
        dir = forward;
        perp = up;
    } else {
        dir = vec3(0.0, 1.0, 0.0);
        perp = vec3(0.0, 0.0, 1.0);
    }

    vec3 tail = blender_pos - dir * (lineLen * 0.5);
    vec3 endPos = tail + dir * lineLen;

    float headLen = max(lineLen * 0.25, 1e-6);
    vec3 shaftEnd = endPos - dir * headLen;

    float baseWidth = max(particle_radius * 0.5, lineLen * 0.05);
    float shaft_hw = baseWidth;
    float head_hw = baseWidth * 1.6;

    vec3 start_left  = tail - perp * shaft_hw;
    vec3 start_right = tail + perp * shaft_hw;
    vec3 end_left    = shaftEnd - perp * shaft_hw;
    vec3 end_right   = shaftEnd + perp * shaft_hw;

    vec3 head_left   = shaftEnd - perp * head_hw;
    vec3 head_right  = shaftEnd + perp * head_hw;
    vec3 tip          = endPos;

    vec3 world;
    if (gl_VertexID == 0)      world = start_left;
    else if (gl_VertexID == 1) world = start_right;
    else if (gl_VertexID == 2) world = start_right;
    else if (gl_VertexID == 3) world = end_right;
    else if (gl_VertexID == 4) world = end_right;
    else if (gl_VertexID == 5) world = end_left;
    else if (gl_VertexID == 6) world = end_left;
    else if (gl_VertexID == 7) world = start_left;
    else if (gl_VertexID == 8) world = head_left;
    else if (gl_VertexID == 9) world = head_right;
    else if (gl_VertexID == 10) world = head_right;
    else if (gl_VertexID == 11) world = tip;
    else if (gl_VertexID == 12) world = tip;
    else                        world = head_left;

    gl_Position = mvp * vec4(world, 1.0);
    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint ci = min(emitter_idx, uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[ci];
    } else {
        v_color = vec4(0.0);
    }
}
"""

_ARROW_FILLED_BODY = """
flat out vec4 v_color;
out vec4 v_param;

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    vec3 blender_pos = positions[particle_idx].xyz;
    vec3 blender_vel = velocities[particle_idx].xyz;

    float lenSq = dot(blender_vel, blender_vel);
    vec3 dir = (lenSq <= 1e-18)
        ? vec3(0.0, 0.0, 1.0)
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

    int rot_mode = use_hpb;
    if (emitter_rotation_modes_count > 0) {
        uint ri = min(emitter_idx, uint(max(emitter_rotation_modes_count - 1, 0)));
        rot_mode = emitter_rotation_modes[ri];
    }
    vec3 perp = vec3(0.0, 0.0, 1.0);
    if (rot_mode == 1) {
        vec3 up_ref = forced_up;
        if (emitter_up_vectors_count > 0) {
            uint ui = min(emitter_idx, uint(max(emitter_up_vectors_count - 1, 0)));
            up_ref = emitter_up_vectors[ui];
        }
        mat3 up_basis = orient_from_up(up_ref);
        vec3 dir_or_hpb = rotations[particle_idx].xyz;
        vec3 hpb = vec3(dir_or_hpb.y, dir_or_hpb.z, dir_or_hpb.x);
        mat3 hpb_rot = rot_z(hpb.z) * rot_x(hpb.x) * rot_y(hpb.y);
        mat3 rot = up_basis * hpb_rot;
        dir = normalize(rot * vec3(0.0, 1.0, 0.0));
        perp = normalize(rot * vec3(0.0, 0.0, 1.0));
    } else if (rot_mode == 2) {
        vec3 velocity = velocities[particle_idx].xyz;
        float velLenSq = dot(velocity, velocity);
        vec3 forward = (velLenSq <= 1e-18) ? vec3(0.0, 0.0, 1.0) : velocity *inversesqrt(velLenSq);
        vec3 ref = (abs(forward.z) < 0.999) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(forward, ref));
        vec3 up = normalize(cross(right, forward));
        dir = forward;
        perp = up;
    } else {
        dir = vec3(0.0, 1.0, 0.0);
        perp = vec3(0.0, 0.0, 1.0);
    }

    vec3 tail = blender_pos - dir * (lineLen * 0.5);
    vec3 endPos = tail + dir * lineLen;

    float headLen = max(lineLen * 0.25, 1e-6);
    vec3 shaftEnd = endPos - dir * headLen;

    float baseWidth = max(particle_radius * 0.5, lineLen * 0.05);
    float shaft_hw = baseWidth;
    float head_hw = baseWidth * 1.6;

    vec3 start_left  = tail - perp * shaft_hw;
    vec3 start_right = tail + perp * shaft_hw;
    vec3 end_left    = shaftEnd - perp * shaft_hw;
    vec3 end_right   = shaftEnd + perp * shaft_hw;

    vec3 head_left   = shaftEnd - perp * head_hw;
    vec3 head_right  = shaftEnd + perp * head_hw;
    vec3 tip          = endPos;

    vec3 world;
    if (gl_VertexID == 0)      world = start_left;
    else if (gl_VertexID == 1) world = start_right;
    else if (gl_VertexID == 2) world = end_right;
    else if (gl_VertexID == 3) world = start_left;
    else if (gl_VertexID == 4) world = end_right;
    else if (gl_VertexID == 5) world = end_left;
    else if (gl_VertexID == 6) world = head_left;
    else if (gl_VertexID == 7) world = head_right;
    else                        world = tip;

    if (gl_VertexID == 0) v_param = vec4(0.0, 0.0, 0.0, 0.0);
    else if (gl_VertexID == 1) v_param = vec4(1.0, 0.0, 0.0, 0.0);
    else if (gl_VertexID == 2) v_param = vec4(1.0, 1.0, 0.0, 0.0);
    else if (gl_VertexID == 3) v_param = vec4(0.0, 0.0, 0.0, 0.0);
    else if (gl_VertexID == 4) v_param = vec4(1.0, 1.0, 0.0, 0.0);
    else if (gl_VertexID == 5) v_param = vec4(0.0, 1.0, 0.0, 0.0);
    else if (gl_VertexID == 6) v_param = vec4(1.0, 0.0, 0.0, 1.0);
    else if (gl_VertexID == 7) v_param = vec4(0.0, 1.0, 0.0, 1.0);
    else v_param = vec4(0.0, 0.0, 1.0, 1.0);

    gl_Position = mvp * vec4(world, 1.0);
    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint ci = min(emitter_idx, uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[ci];
    } else {
        v_color = vec4(0.0);
    }
}
"""

_ARROW_OUTLINE_VERT = _ARROW_SSBO_HEADER + _ARROW_OUTLINE_BODY
_ARROW_FILLED_VERT = _ARROW_SSBO_HEADER + _ARROW_FILLED_BODY

_ARROW_OUTLINE_FRAG = """\
#version 330 core
flat in vec4 v_color;
out vec4 outColor;
uniform vec4 color;
void main() {
    vec4 final_color = (v_color.a > 0.0) ? v_color : color;
    outColor = final_color;
}
"""

_ARROW_FILLED_FRAG = """\
#version 330 core
flat in vec4 v_color;
in vec4 v_param;
out vec4 outColor;
uniform vec4 color;
void main() {
    vec4 final_color = (v_color.a > 0.0) ? v_color : color;
    const float vignette_strength = 0.12;
    const float vw_shaft = 0.12;
    float vig = 0.0;
    if (v_param.w < 0.5) {
        float cx = v_param.x * 2.0 - 1.0;
        float cy = v_param.y * 2.0 - 1.0;
        float lateral = smoothstep(1.0 - vw_shaft, 1.0, abs(cx));
        float tail = 1.0 - smoothstep(-1.0, -1.0 + vw_shaft, cy);
        vig = max(lateral, tail);
    } else {
        vec3 b = v_param.xyz;
        float m_st = min(b.x, b.y);
        float suppress_base = smoothstep(0.04, 0.10, b.z);
        float w = max(0.04, fwidth(m_st) * 2.5);
        vig = (1.0 - smoothstep(0.0, w, m_st)) * suppress_base;
    }
    final_color.rgb *= 1.0 - vignette_strength * vig;
    outColor = final_color;
}
"""


class ArrowOpenGLRenderer(VelIndirectOpenGLBase):
    def __init__(self, bridge) -> None:
        super().__init__(
            bridge,
            gl_primitive=_GL_LINES,
            verts_per_instance=14,
            vertex_shader_src=_ARROW_OUTLINE_VERT,
            fragment_shader_src=_ARROW_OUTLINE_FRAG,
        )

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        return super().draw(context, pipeline, scene, params)


class ArrowFilledOpenGLRenderer(VelIndirectOpenGLBase):
    def __init__(self, bridge) -> None:
        super().__init__(
            bridge,
            gl_primitive=_GL_TRIANGLES,
            verts_per_instance=9,
            vertex_shader_src=_ARROW_FILLED_VERT,
            fragment_shader_src=_ARROW_FILLED_FRAG,
        )

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        return super().draw(context, pipeline, scene, params)
