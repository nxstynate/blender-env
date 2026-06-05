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

"""OpenGL zero-copy axis renderer (indirect binned draw)."""

from __future__ import annotations

import numpy as np

from ...core.buffer_state import BufferExport, buf_identity
from ..indirect_opengl_base import FLAT_COLOR_FRAG, IndirectOpenGLBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_LINES,
        GL_SHADER_STORAGE_BUFFER,
        GL_STATIC_DRAW,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBufferData,
        glDeleteBuffers,
        glDrawArraysIndirect,
        glEnableVertexAttribArray,
        glGenBuffers,
        glGenVertexArrays,
        glGetUniformLocation,
        glUniform1f,
        glUniform1fv,
        glUniform1i,
        glUniform1iv,
        glUniform3f,
        glUniform3fv,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribPointer,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False

_VERTS_PER_INSTANCE = 6  # 3 axes × 2 endpoints


class AxisOpenGLRenderer(IndirectOpenGLBase):
    _MAX_EMITTER = 64

    def __init__(self, bridge):
        super().__init__(bridge)
        self._mesh_vbo: int | None = None
        self._prefix_handle: int | None = None
        self._binned_handle: int | None = None
        self._prefix_vbo: int | None = None
        self._binned_vbo: int | None = None
        self._emit_idx_vbo: int | None = None
        self._pos_vbo: int | None = None
        self._vel_vbo: int | None = None
        self._vel_handle: object | None = None
        self._rot_vbo: int | None = None
        self._rot_handle: object | None = None
        self._rad_vbo: int | None = None
        self._radius_handle: object | None = None
        self._has_radius = False

    def _free_resources(self) -> None:
        if _GL_OK and self._mesh_vbo is not None:
            try:
                glDeleteBuffers(1, [self._mesh_vbo])
            except Exception:
                pass
        self._free_indirect_resources()
        self._mesh_vbo = None
        self._has_radius = False
        self._prefix_handle = None
        self._binned_handle = None
        self._prefix_vbo = None
        self._binned_vbo = None
        self._emit_idx_vbo = None
        self._pos_vbo = None
        self._vel_vbo = None
        self._vel_handle = None
        self._rot_vbo = None
        self._rot_handle = None
        self._rad_vbo = None
        self._radius_handle = None
        super()._free_resources()

    def _ensure_import(
        self,
        pos: BufferExport,
        vel: BufferExport,
        rot: BufferExport | None,
        prefix: BufferExport,
        binned: BufferExport,
        emit_idx: BufferExport,
        radius: BufferExport | None = None,
    ) -> bool:
        pos_id = buf_identity(pos)
        prefix_id = buf_identity(prefix)
        binned_id = buf_identity(binned)
        vel_id = buf_identity(vel)
        radius_id = buf_identity(radius)
        rot_id = buf_identity(rot)
        if (
            self._imported
            and self._handle == pos_id
            and self._prefix_handle == prefix_id
            and self._binned_handle == binned_id
            and self._vel_handle == vel_id
            and self._rot_handle == rot_id
            and self._radius_handle == radius_id
            and self._emit_idx_vbo is not None
        ):
            return True
        if self._imported:
            self._free_resources()

        self._pos_vbo = self._import(pos)
        self._vel_vbo = self._import(vel)
        self._prefix_vbo = self._import(prefix)
        self._binned_vbo = self._import(binned)
        self._emit_idx_vbo = self._import(emit_idx)
        self._rot_vbo = self._import(rot)
        self._rad_vbo = self._import(radius)
        if None in (
            self._pos_vbo,
            self._vel_vbo,
            self._prefix_vbo,
            self._binned_vbo,
            self._emit_idx_vbo,
        ):
            self._free_resources()
            return False

        try:
            mesh_gen = glGenBuffers(1)
            mesh = mesh_gen[0] if isinstance(mesh_gen, (list, tuple)) else mesh_gen
            dummy = np.zeros(8 * 3, dtype=np.float32)
            glBindBuffer(GL_ARRAY_BUFFER, mesh)
            glBufferData(GL_ARRAY_BUFFER, dummy.nbytes, dummy, GL_STATIC_DRAW)
            self._mesh_vbo = mesh

            vao_gen = glGenVertexArrays(1)
            vao = vao_gen[0] if isinstance(vao_gen, (list, tuple)) else vao_gen
            glBindVertexArray(vao)
            glBindBuffer(GL_ARRAY_BUFFER, mesh)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
            glEnableVertexAttribArray(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False

        vs_src = """
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
uniform int use_hpb;
uniform vec3 forced_up;
uniform int use_radius;
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_rotation_modes_count;
uniform int emitter_rotation_modes[64];
uniform int emitter_up_vectors_count;
uniform vec3 emitter_up_vectors[64];

flat out vec4 v_color;

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

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    vec3 blender_pos = positions[particle_idx].xyz;
    float size = use_radius != 0 ? radii[particle_idx] : 1.0;
    if (use_radius == 0 && emitter_sizes_count > 0) {
        uint i = min(emitter_idx, uint(max(emitter_sizes_count - 1, 0)));
        size = emitter_sizes[i];
    }
    size = max(size, 1e-6);

    int axis = gl_VertexID / 2;
    int endpoint = gl_VertexID % 2;

    vec3 axis_dir;
    vec4 axis_color;
    int rot_mode = use_hpb;
    if (emitter_rotation_modes_count > 0) {
        uint ri = min(emitter_idx, uint(max(emitter_rotation_modes_count - 1, 0)));
        rot_mode = emitter_rotation_modes[ri];
    }
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
        if (axis == 0) {
            axis_dir = normalize(rot * vec3(0.0, 1.0, 0.0));
            axis_color = vec4(0.0, 1.0, 0.0, 1.0);
        } else if (axis == 1) {
            axis_dir = normalize(rot * vec3(-1.0, 0.0, 0.0));
            axis_color = vec4(1.0, 0.0, 0.0, 1.0);
        } else {
            axis_dir = normalize(rot * vec3(0.0, 0.0, 1.0));
            axis_color = vec4(0.0, 0.0, 1.0, 1.0);
        }
    } else if (rot_mode == 2) {
        vec3 velocity = velocities[particle_idx].xyz;
        float lenSq = dot(velocity, velocity);
        vec3 forward = (lenSq <= 1e-18) ? vec3(0.0, 0.0, 1.0) : velocity * inversesqrt(lenSq);
        vec3 ref = (abs(forward.z) < 0.999) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(forward, ref));
        vec3 up = cross(right, forward);
        if (axis == 0) {
            axis_dir = forward;
            axis_color = vec4(0.0, 1.0, 0.0, 1.0);
        } else if (axis == 1) {
            axis_dir = right;
            axis_color = vec4(1.0, 0.0, 0.0, 1.0);
        } else {
            axis_dir = up;
            axis_color = vec4(0.0, 0.0, 1.0, 1.0);
        }
    } else {
        if (axis == 0) {
            axis_dir = vec3(0.0, 1.0, 0.0);
            axis_color = vec4(0.0, 1.0, 0.0, 1.0);
        } else if (axis == 1) {
            axis_dir = vec3(-1.0, 0.0, 0.0);
            axis_color = vec4(1.0, 0.0, 0.0, 1.0);
        } else {
            axis_dir = vec3(0.0, 0.0, 1.0);
            axis_color = vec4(0.0, 0.0, 1.0, 1.0);
        }
    }

    vec3 world = blender_pos + (endpoint == 1 ? axis_dir * size : vec3(0.0));
    gl_Position = mvp * vec4(world, 1.0);
    v_color = axis_color;
}
"""
        fs_src = FLAT_COLOR_FRAG
        program = self._bridge.compile_program(vs_src, fs_src)
        if program is None:
            self._free_resources()
            return False
        if not self._ensure_compute_program() or not self._ensure_indirect_buffers():
            self._free_resources()
            return False

        self._vao = vao
        self._program = program
        self._handle = pos_id
        self._prefix_handle = prefix_id
        self._binned_handle = binned_id
        self._vel_handle = vel_id
        self._rot_handle = rot_id
        self._radius_handle = radius_id
        self._imported = True
        self._has_radius = self._rad_vbo is not None
        self._uniforms = {
            "mvp": glGetUniformLocation(program, "mvp"),
            "use_hpb": glGetUniformLocation(program, "use_hpb"),
            "forced_up": glGetUniformLocation(program, "forced_up"),
            "use_radius": glGetUniformLocation(program, "use_radius"),
            "emitter_sizes_count": glGetUniformLocation(program, "emitter_sizes_count"),
            "emitter_sizes": glGetUniformLocation(program, "emitter_sizes"),
            "emitter_rotation_modes_count": glGetUniformLocation(
                program, "emitter_rotation_modes_count"
            ),
            "emitter_rotation_modes": glGetUniformLocation(program, "emitter_rotation_modes"),
            "emitter_up_vectors_count": glGetUniformLocation(program, "emitter_up_vectors_count"),
            "emitter_up_vectors": glGetUniformLocation(program, "emitter_up_vectors"),
        }
        return True

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        prep = self._prepare_draw(context, pipeline, params)
        if prep is None:
            return False
        mvp, _view = prep

        pos = self.fetch_gpu_buffer(pipeline, "position")
        vel = self.fetch_gpu_buffer(pipeline, "velocity")
        rot = self.fetch_gpu_buffer(pipeline, "rotation")
        emit_idx = self.fetch_gpu_buffer(pipeline, "emitter_index")
        mode_buffers = self.fetch_draw_mode_buffers(pipeline)
        if (
            pos is None
            or not pos.valid
            or vel is None
            or not vel.valid
            or emit_idx is None
            or not emit_idx.valid
            or mode_buffers is None
        ):
            return False
        prefix_buf, binned_buf = mode_buffers

        rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
        use_hpb = rotation_mode == "UP_VECTOR" and rot is not None and rot.valid
        use_tangential = rotation_mode == "TANGENTIAL"
        use_hpb_mode = 1 if use_hpb else (2 if use_tangential else 0)

        rot_buf = rot if rot and rot.valid else None
        rad = self.fetch_gpu_buffer(pipeline, "radius")
        if not self._ensure_import(
            pos,
            vel,
            rot_buf,
            prefix_buf,
            binned_buf,
            emit_idx,
            rad if rad and rad.valid else None,
        ):
            return False

        saved = self._bridge.save_state_for_particle_draw()
        try:
            self._dispatch_compute(
                self._prefix_vbo,
                self.mode_bin_index(params.display_shape),
                _VERTS_PER_INSTANCE,
                prefix_buf.size // 4,
            )

            glUseProgram(self._program)
            glUniformMatrix4fv(self._uniforms["mvp"], 1, True, mvp)
            glUniform1i(self._uniforms["use_hpb"], use_hpb_mode)
            glUniform1i(self._uniforms["use_radius"], 1 if self._has_radius else 0)
            up_mode = str(getattr(params, "rotation_up_vector", "Y_POS"))
            up_map = {
                "X_POS": (1.0, 0.0, 0.0),
                "X_NEG": (-1.0, 0.0, 0.0),
                "Y_POS": (0.0, 1.0, 0.0),
                "Y_NEG": (0.0, -1.0, 0.0),
                "Z_POS": (0.0, 0.0, 1.0),
                "Z_NEG": (0.0, 0.0, -1.0),
            }
            ux, uy, uz = up_map.get(up_mode, (0.0, 1.0, 0.0))
            glUniform3f(self._uniforms["forced_up"], ux, uy, uz)

            sizes = tuple(float(s) for s in params.emitter_point_sizes[: self._MAX_EMITTER])
            glUniform1i(self._uniforms["emitter_sizes_count"], len(sizes))
            su = self._uniforms["emitter_sizes"]
            if (not self._has_radius) and sizes and su is not None and su >= 0:
                glUniform1fv(su, len(sizes), list(sizes))

            rot_modes = tuple(int(x) for x in params.emitter_rotation_modes[: self._MAX_EMITTER])
            glUniform1i(self._uniforms["emitter_rotation_modes_count"], len(rot_modes))
            rm_u = self._uniforms["emitter_rotation_modes"]
            if rot_modes and rm_u is not None and rm_u >= 0:
                glUniform1iv(rm_u, len(rot_modes), list(rot_modes))

            up_vecs = tuple(params.emitter_rotation_up_vectors[: self._MAX_EMITTER])
            glUniform1i(self._uniforms["emitter_up_vectors_count"], len(up_vecs))
            uv_u = self._uniforms["emitter_up_vectors"]
            if up_vecs and uv_u is not None and uv_u >= 0:
                flat_uv = [c for v in up_vecs for c in v]
                glUniform3fv(uv_u, len(up_vecs), flat_uv)

            glBindVertexArray(self._vao)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._pos_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, self._binned_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, self._draw_state_ssbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 6, self._rad_vbo if self._has_radius else 0)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, 0)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 8, self._emit_idx_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 9, self._vel_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 10, self._rot_vbo if self._rot_vbo else 0)

            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
            glDrawArraysIndirect(GL_LINES, None)
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False
        finally:
            glBindVertexArray(0)
            self._bridge.restore_state(saved)
        return True
