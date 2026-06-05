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

"""OpenGL zero-copy point renderer with draw-mode indirect binning."""

from __future__ import annotations

import numpy as np

from ...core.buffer_state import BufferExport, buf_identity
from ..indirect_opengl_base import IndirectOpenGLBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_POINTS,
        GL_PROGRAM_POINT_SIZE,
        GL_SHADER_STORAGE_BUFFER,
        GL_STATIC_DRAW,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBufferData,
        glDeleteBuffers,
        glDisable,
        glDrawArraysIndirect,
        glEnable,
        glEnableVertexAttribArray,
        glGenBuffers,
        glGenVertexArrays,
        glGetUniformLocation,
        glIsEnabled,
        glUniform1f,
        glUniform1fv,
        glUniform1i,
        glUniform4f,
        glUniform4fv,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribPointer,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False

_VERTS_PER_INSTANCE = 1


class PointOpenGLRenderer(IndirectOpenGLBase):
    _MAX_EMITTER_SIZES = 64
    _MAX_EMITTER_COLORS = 64

    def __init__(self, bridge):
        super().__init__(bridge)
        self._mesh_vbo: int | None = None
        self._prefix_handle: int | None = None
        self._binned_handle: int | None = None
        self._color_handle: object | None = None
        self._prefix_vbo: int | None = None
        self._binned_vbo: int | None = None
        self._emit_idx_vbo: int | None = None
        self._pos_vbo: int | None = None
        self._color_vbo: int | None = None

    def _free_resources(self) -> None:
        if _GL_OK and self._mesh_vbo is not None:
            try:
                glDeleteBuffers(1, [self._mesh_vbo])
            except Exception:
                pass
        self._free_indirect_resources()
        self._mesh_vbo = None
        self._prefix_handle = None
        self._binned_handle = None
        self._color_handle = None
        self._prefix_vbo = None
        self._binned_vbo = None
        self._emit_idx_vbo = None
        self._pos_vbo = None
        self._color_vbo = None
        super()._free_resources()

    def _ensure_import(
        self,
        pos: BufferExport,
        prefix: BufferExport,
        binned: BufferExport,
        emit_idx: BufferExport,
        color: BufferExport | None = None,
    ) -> bool:
        pos_id = buf_identity(pos)
        prefix_id = buf_identity(prefix)
        binned_id = buf_identity(binned)
        color_id = buf_identity(color)
        if (
            self._imported
            and self._handle == pos_id
            and self._prefix_handle == prefix_id
            and self._binned_handle == binned_id
            and self._color_handle == color_id
            and self._emit_idx_vbo is not None
        ):
            return True
        if self._imported:
            self._free_resources()

        self._pos_vbo = self._import(pos)
        self._prefix_vbo = self._import(prefix)
        self._binned_vbo = self._import(binned)
        self._emit_idx_vbo = self._import(emit_idx)
        self._color_vbo = self._import(color)
        if None in (self._pos_vbo, self._prefix_vbo, self._binned_vbo, self._emit_idx_vbo):
            self._free_resources()
            return False

        try:
            mesh_gen = glGenBuffers(1)
            mesh = mesh_gen[0] if isinstance(mesh_gen, (list, tuple)) else mesh_gen
            dummy = np.zeros(3, dtype=np.float32)
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
layout(std430, binding = 7) readonly buffer Colors { vec4 colors[]; };
layout(std430, binding = 8) readonly buffer EmitterIndices { uint emitter_indices[]; };

uniform mat4 mvp;
uniform float point_size;
uniform vec4 color;
uniform int use_color_buffer;
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_colors_count;
uniform vec4 emitter_colors[64];

flat out vec4 v_color;

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    gl_Position = mvp * vec4(positions[particle_idx].xyz, 1.0);

    float size = point_size;
    if (emitter_sizes_count > 0) {
        uint idx = min(emitter_idx, uint(max(emitter_sizes_count - 1, 0)));
        size = emitter_sizes[idx];
    }
    gl_PointSize = size;

    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint idx = min(emitter_idx, uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[idx];
    } else {
        v_color = color;
    }
}
"""
        fs_src = """\
#version 330 core
flat in vec4 v_color;
out vec4 FragColor;
void main() {
    vec2 centered = gl_PointCoord * 2.0 - 1.0;
    if (dot(centered, centered) > 1.0) discard;
    FragColor = v_color;
}
"""
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
        self._color_handle = color_id
        self._imported = True
        self._uniforms = {
            "mvp": glGetUniformLocation(program, "mvp"),
            "color": glGetUniformLocation(program, "color"),
            "point_size": glGetUniformLocation(program, "point_size"),
            "use_color_buffer": glGetUniformLocation(program, "use_color_buffer"),
            "emitter_sizes_count": glGetUniformLocation(program, "emitter_sizes_count"),
            "emitter_sizes": glGetUniformLocation(program, "emitter_sizes"),
            "emitter_colors_count": glGetUniformLocation(program, "emitter_colors_count"),
            "emitter_colors": glGetUniformLocation(program, "emitter_colors"),
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
        if pos is None or not pos.valid:
            return False
        mode_buffers = self.fetch_draw_mode_buffers(pipeline)
        emit_idx = self.fetch_gpu_buffer(pipeline, "emitter_index")
        if mode_buffers is None or emit_idx is None or not emit_idx.valid:
            return False
        prefix_buf, binned_buf = mode_buffers
        color = self.fetch_gpu_buffer(pipeline, "color")
        if not self._ensure_import(pos, prefix_buf, binned_buf, emit_idx, color):
            return False
        use_color = self._color_vbo is not None

        mode_index = self.mode_bin_index(params.display_shape)
        saved = self._bridge.save_state_for_particle_draw()
        prev_point = None
        try:
            prev_point = glIsEnabled(GL_PROGRAM_POINT_SIZE)
            if not prev_point:
                glEnable(GL_PROGRAM_POINT_SIZE)

            self._dispatch_compute(
                self._prefix_vbo, mode_index, _VERTS_PER_INSTANCE, prefix_buf.size // 4
            )

            glUseProgram(self._program)
            glUniformMatrix4fv(self._uniforms["mvp"], 1, True, mvp)
            glUniform4f(self._uniforms["color"], *params.color)
            glUniform1f(self._uniforms["point_size"], float(params.size))
            glUniform1i(self._uniforms["use_color_buffer"], 1 if use_color else 0)

            sizes = tuple(float(s) for s in params.emitter_point_sizes[: self._MAX_EMITTER_SIZES])
            colors = tuple(
                tuple(float(c) for c in rgba[:4])
                for rgba in params.emitter_colors[: self._MAX_EMITTER_COLORS]
            )
            glUniform1i(self._uniforms["emitter_sizes_count"], len(sizes))
            su = self._uniforms["emitter_sizes"]
            if sizes and su is not None and su >= 0:
                glUniform1fv(su, len(sizes), list(sizes))
            glUniform1i(self._uniforms["emitter_colors_count"], len(colors))
            cu = self._uniforms["emitter_colors"]
            if colors and cu is not None and cu >= 0:
                flat = [c for rgba in colors for c in rgba]
                glUniform4fv(cu, len(colors), flat)

            glBindVertexArray(self._vao)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._pos_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, self._binned_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, self._draw_state_ssbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, self._color_vbo if use_color else 0)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 8, self._emit_idx_vbo)

            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
            glDrawArraysIndirect(GL_POINTS, None)
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False
        finally:
            glBindVertexArray(0)
            if prev_point is not None and not prev_point:
                try:
                    glDisable(GL_PROGRAM_POINT_SIZE)
                except Exception:
                    pass
            self._bridge.restore_state(saved)
        return True
