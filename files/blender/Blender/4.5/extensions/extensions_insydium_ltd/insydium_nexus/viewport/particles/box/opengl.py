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

"""OpenGL zero-copy box renderers (indirect binned draw)."""

from __future__ import annotations

from ..indirect_opengl_base import FLAT_COLOR_FRAG, LIT_FLAT_FRAG
from ..mesh_indirect_opengl import MeshIndirectOpenGLBase

try:
    from OpenGL.GL import GL_LINES as _GL_LINES
    from OpenGL.GL import GL_TRIANGLES as _GL_TRIANGLES

    _GL_OK = True
except ImportError:
    _GL_LINES = 0
    _GL_TRIANGLES = 0
    _GL_OK = False

_BOX_HEADER = """
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
uniform mat4 view;
uniform float quad_size;
uniform int use_radius;
uniform vec4 color;
uniform int use_color_buffer;
uniform int use_hpb;
uniform vec3 forced_up;
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_colors_count;
uniform vec4 emitter_colors[64];
uniform int emitter_rotation_modes_count;
uniform int emitter_rotation_modes[64];
uniform int emitter_up_vectors_count;
uniform vec3 emitter_up_vectors[64];

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
vec3 corner_from_id(int cid) {
    float x = (cid & 1) != 0 ? 1.0 : -1.0;
    float y = (cid & 2) != 0 ? 1.0 : -1.0;
    float z = (cid & 4) != 0 ? 1.0 : -1.0;
    return vec3(x, y, z);
}
"""

_BOX_WIRE = (
    _BOX_HEADER
    + """
flat out vec4 v_color;
void main() {
    const int EDGES[24] = int[](0,1,1,3,3,2,2,0,4,5,5,7,7,6,6,4,0,4,1,5,2,6,3,7);
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];
    int eid = EDGES[gl_VertexID];
    vec3 blender_pos = positions[particle_idx].xyz;
    float r = use_radius != 0 ? radii[particle_idx] : quad_size;
    if (use_radius == 0 && emitter_sizes_count > 0) {
        uint i = min(emitter_idx,
            uint(max(emitter_sizes_count - 1, 0)));
        r = emitter_sizes[i];
    }
    if (r != r || r < 0.0 || r > 1.0e6) r = 1.0;
    vec3 local = corner_from_id(eid);
    int rot_mode = use_hpb;
    if (emitter_rotation_modes_count > 0) {
        uint ri = min(emitter_idx,
            uint(max(emitter_rotation_modes_count - 1, 0)));
        rot_mode = emitter_rotation_modes[ri];
    }
    if (rot_mode == 1) {
        vec3 up_ref = forced_up;
        if (emitter_up_vectors_count > 0) {
            uint ui = min(emitter_idx,
                uint(max(emitter_up_vectors_count - 1, 0)));
            up_ref = emitter_up_vectors[ui];
        }
        vec4 pr = rotations[particle_idx];
        vec3 hpb = vec3(pr.y, pr.z, pr.x);
        mat3 rot_mat = orient_from_up(up_ref)
            * rot_z(hpb.z) * rot_x(hpb.x) * rot_y(hpb.y);
        local = rot_mat * local;
    } else if (rot_mode == 2) {
        vec3 vel = velocities[particle_idx].xyz;
        float len_sq = dot(vel, vel);
        vec3 forward = (len_sq > 1e-18)
            ? (vel * inversesqrt(len_sq))
            : vec3(0.0, 0.0, 1.0);
        vec3 ref = (abs(forward.z) < 0.999)
            ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(forward, ref));
        vec3 up = cross(right, forward);
        local = mat3(right, forward, up) * local;
    }
    vec3 world = blender_pos + local * r;
    gl_Position = mvp * vec4(world, 1.0);
    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint i = min(emitter_idx,
            uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[i];
    } else {
        v_color = color;
    }
}
"""
)

_BOX_FILLED = (
    _BOX_HEADER
    + """
flat out vec3 v_n_view;
flat out vec3 v_L_view;
out vec3 v_pos_view;
flat out vec4 v_color;
vec3 face_normal(int face) {
    if (face == 0) return vec3(0.0, 0.0, 1.0);
    if (face == 1) return vec3(0.0, 0.0, -1.0);
    if (face == 2) return vec3(1.0, 0.0, 0.0);
    if (face == 3) return vec3(-1.0, 0.0, 0.0);
    if (face == 4) return vec3(0.0, 1.0, 0.0);
    return vec3(0.0, -1.0, 0.0);
}
void main() {
    const int CIDS[36] = int[](
        4,5,7,4,7,6, 0,3,1,0,2,3,
        1,7,5,1,3,7, 0,4,6,0,6,2,
        2,3,6,3,6,7, 0,1,5,0,5,4);
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];
    int cid = CIDS[gl_VertexID];
    int face = gl_VertexID / 6;
    vec3 blender_pos = positions[particle_idx].xyz;
    float r = use_radius != 0 ? radii[particle_idx] : quad_size;
    if (use_radius == 0 && emitter_sizes_count > 0) {
        uint i = min(emitter_idx,
            uint(max(emitter_sizes_count - 1, 0)));
        r = emitter_sizes[i];
    }
    if (r != r || r < 0.0 || r > 1.0e6) r = 1.0;
    vec3 local = corner_from_id(cid);
    vec3 n_world = face_normal(face);
    int rot_mode = use_hpb;
    if (emitter_rotation_modes_count > 0) {
        uint ri = min(emitter_idx,
            uint(max(emitter_rotation_modes_count - 1, 0)));
        rot_mode = emitter_rotation_modes[ri];
    }
    if (rot_mode == 1) {
        vec3 up_ref = forced_up;
        if (emitter_up_vectors_count > 0) {
            uint ui = min(emitter_idx,
                uint(max(emitter_up_vectors_count - 1, 0)));
            up_ref = emitter_up_vectors[ui];
        }
        vec4 pr = rotations[particle_idx];
        vec3 hpb = vec3(pr.y, pr.z, pr.x);
        mat3 rot_mat = orient_from_up(up_ref)
            * rot_z(hpb.z) * rot_x(hpb.x) * rot_y(hpb.y);
        local = rot_mat * local;
        n_world = rot_mat * n_world;
    } else if (rot_mode == 2) {
        vec3 vel = velocities[particle_idx].xyz;
        float len_sq = dot(vel, vel);
        vec3 forward = (len_sq > 1e-18)
            ? (vel * inversesqrt(len_sq))
            : vec3(0.0, 0.0, 1.0);
        vec3 ref = (abs(forward.z) < 0.999)
            ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(forward, ref));
        vec3 up = cross(right, forward);
        mat3 rot_mat = mat3(right, forward, up);
        local = rot_mat * local;
        n_world = rot_mat * n_world;
    }
    vec3 world = blender_pos + local * r;
    mat3 R = mat3(view);
    v_n_view = normalize(R * n_world);
    v_pos_view = (view * vec4(world, 1.0)).xyz;
    v_L_view = normalize(R * normalize(vec3(0.45, 0.75, 0.4)));
    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint i = min(emitter_idx,
            uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[i];
    } else {
        v_color = color;
    }
    gl_Position = mvp * vec4(world, 1.0);
}
"""
)


class Box3DOpenGLRenderer(MeshIndirectOpenGLBase):
    def __init__(self, bridge):
        super().__init__(
            bridge,
            gl_primitive=_GL_LINES,
            verts_per_instance=24,
            vs_src=_BOX_WIRE,
            fs_src=FLAT_COLOR_FRAG,
        )

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        return super().draw(context, pipeline, scene, params)


class Box3DFilledOpenGLRenderer(MeshIndirectOpenGLBase):
    def __init__(self, bridge):
        super().__init__(
            bridge,
            gl_primitive=_GL_TRIANGLES,
            verts_per_instance=36,
            vs_src=_BOX_FILLED,
            fs_src=LIT_FLAT_FRAG,
        )

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        return super().draw(context, pipeline, scene, params)
