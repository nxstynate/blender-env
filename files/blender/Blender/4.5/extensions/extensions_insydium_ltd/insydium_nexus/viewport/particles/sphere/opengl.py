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

"""OpenGL zero-copy sphere renderer with draw-mode indirect binning."""

from __future__ import annotations

import ctypes as _ct

import numpy as np

from ...core.buffer_state import BufferExport, buf_identity
from ..indirect_opengl_base import LIT_SMOOTH_FRAG, IndirectOpenGLBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_SHADER_STORAGE_BUFFER,
        GL_STATIC_DRAW,
        GL_STREAM_DRAW,
        GL_TRIANGLES,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBufferData,
        glBufferSubData,
        glDeleteBuffers,
        glDrawArraysIndirect,
        glEnableVertexAttribArray,
        glGenBuffers,
        glGenVertexArrays,
        glGetUniformLocation,
        glUniform1f,
        glUniform1fv,
        glUniform1i,
        glUniform4f,
        glUniform4fv,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribDivisor,
        glVertexAttribPointer,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False

_SPHERE_TPL = np.zeros(192 * 5, dtype=np.float32)
_VERTS_PER_INSTANCE = 192  # 8 slices × 5 stacks sphere tessellation


class SphereOpenGLRenderer(IndirectOpenGLBase):
    _MAX_EMITTER_SIZES = 64
    _MAX_EMITTER_COLORS = 64

    def __init__(self, bridge):
        super().__init__(bridge)
        self._tpl_vbo: int | None = None
        self._uniform_size_vbo: int | None = None
        self._has_radius = False
        self._prefix_handle: int | None = None
        self._binned_handle: int | None = None
        self._prefix_vbo: int | None = None
        self._binned_vbo: int | None = None
        self._emit_idx_vbo: int | None = None
        self._pos_vbo: int | None = None
        self._rad_vbo: int | None = None
        self._radius_handle: object | None = None
        self._color_vbo: int | None = None
        self._color_handle: object | None = None

    def _free_resources(self) -> None:
        if _GL_OK:
            for buf in (self._tpl_vbo, self._uniform_size_vbo):
                if buf is not None:
                    try:
                        glDeleteBuffers(1, [buf])
                    except Exception:
                        pass
        self._free_indirect_resources()
        self._tpl_vbo = None
        self._uniform_size_vbo = None
        self._has_radius = False
        self._prefix_handle = None
        self._binned_handle = None
        self._prefix_vbo = None
        self._binned_vbo = None
        self._emit_idx_vbo = None
        self._pos_vbo = None
        self._rad_vbo = None
        self._radius_handle = None
        self._color_vbo = None
        self._color_handle = None
        super()._free_resources()

    def _ensure_import(
        self,
        pos: BufferExport,
        prefix: BufferExport,
        binned: BufferExport,
        emit_idx: BufferExport,
        radius: BufferExport | None = None,
        color: BufferExport | None = None,
    ) -> bool:
        pos_id = buf_identity(pos)
        prefix_id = buf_identity(prefix)
        binned_id = buf_identity(binned)
        radius_id = buf_identity(radius)
        color_id = buf_identity(color)
        if (
            self._imported
            and self._handle == pos_id
            and self._prefix_handle == prefix_id
            and self._binned_handle == binned_id
            and self._radius_handle == radius_id
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
        self._rad_vbo = self._import(radius)
        self._color_vbo = self._import(color)
        if None in (self._pos_vbo, self._prefix_vbo, self._binned_vbo, self._emit_idx_vbo):
            self._free_resources()
            return False

        try:
            tbuf_gen = glGenBuffers(1)
            tbuf = tbuf_gen[0] if isinstance(tbuf_gen, (list, tuple)) else tbuf_gen
            glBindBuffer(GL_ARRAY_BUFFER, tbuf)
            glBufferData(GL_ARRAY_BUFFER, _SPHERE_TPL.nbytes, _SPHERE_TPL, GL_STATIC_DRAW)
            self._tpl_vbo = tbuf

            vao_gen = glGenVertexArrays(1)
            vao = vao_gen[0] if isinstance(vao_gen, (list, tuple)) else vao_gen
            glBindVertexArray(vao)
            stride = 5 * 4
            glBindBuffer(GL_ARRAY_BUFFER, tbuf)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, _ct.c_void_p(12))
            glEnableVertexAttribArray(1)

            glBindBuffer(GL_ARRAY_BUFFER, self._pos_vbo)
            glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 16, None)
            glEnableVertexAttribArray(2)
            glVertexAttribDivisor(2, 1)

            if self._rad_vbo is not None:
                glBindBuffer(GL_ARRAY_BUFFER, self._rad_vbo)
                glVertexAttribPointer(3, 1, GL_FLOAT, GL_FALSE, 4, None)
                glEnableVertexAttribArray(3)
                glVertexAttribDivisor(3, 1)
            else:
                usbuf_gen = glGenBuffers(1)
                usbuf = usbuf_gen[0] if isinstance(usbuf_gen, (list, tuple)) else usbuf_gen
                glBindBuffer(GL_ARRAY_BUFFER, usbuf)
                glBufferData(GL_ARRAY_BUFFER, 4, np.array([1.0], dtype=np.float32), GL_STREAM_DRAW)
                glVertexAttribPointer(3, 1, GL_FLOAT, GL_FALSE, 4, None)
                glEnableVertexAttribArray(3)
                glVertexAttribDivisor(3, 0)
                self._uniform_size_vbo = usbuf

            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False

        vs_src = """
#version 430 core
layout(location = 0) in vec3 _tpl_pos;
layout(location = 1) in vec2 _tpl_uv;

layout(std430, binding = 3) readonly buffer Positions { vec4 positions[]; };
layout(std430, binding = 4) readonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 5) readonly buffer DrawState { uint start_index; };
layout(std430, binding = 6) readonly buffer Radii { float radii[]; };
layout(std430, binding = 7) readonly buffer Colors { vec4 colors[]; };
layout(std430, binding = 8) readonly buffer EmitterIndices { uint emitter_indices[]; };

uniform mat4 mvp;
uniform mat4 view;
uniform float quad_size;
uniform int use_radius;
uniform vec4 color;
uniform int use_color_buffer;
uniform int emitter_sizes_count;
uniform float emitter_sizes[64];
uniform int emitter_colors_count;
uniform vec4 emitter_colors[64];

out vec3 v_n_view;
out vec3 v_pos_view;
flat out vec3 v_L_view;
flat out vec4 v_color;

const float PI = 3.14159265359;
const int SLICES = 8;
const int STACKS = 5;

vec3 sphere_pt(int stack_idx, int slice_idx) {
    float phi   = float(stack_idx) * PI / float(STACKS);
    float theta = float(slice_idx) * 2.0 * PI / float(SLICES);
    float sp = sin(phi);
    float cp = cos(phi);
    float st = sin(theta);
    float ct = cos(theta);
    return vec3(sp * ct, sp * st, cp);
}

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    int tri  = gl_VertexID / 3;
    int vert = gl_VertexID % 3;
    int north_cap  = SLICES;
    int band_tris  = (STACKS - 2) * 2 * SLICES;
    int south_start = north_cap + band_tris;

    vec3 local;
    if (tri < north_cap) {
        int slice = tri;
        if (vert == 0)      local = sphere_pt(0, 0);
        else if (vert == 1) local = sphere_pt(1, slice);
        else                local = sphere_pt(1, (slice + 1) % SLICES);
    } else if (tri < south_start) {
        int t        = tri - north_cap;
        int band     = t / (2 * SLICES);
        int local_t  = t % (2 * SLICES);
        int slice    = local_t / 2;
        int tri_type = local_t % 2;
        int ring1    = band + 1;
        int ring2    = band + 2;
        if (tri_type == 0) {
            if (vert == 0)      local = sphere_pt(ring1, slice);
            else if (vert == 1) local = sphere_pt(ring2, slice);
            else                local = sphere_pt(ring2, (slice + 1) % SLICES);
        } else {
            if (vert == 0)      local = sphere_pt(ring1, slice);
            else if (vert == 1) local = sphere_pt(ring2, (slice + 1) % SLICES);
            else                local = sphere_pt(ring1, (slice + 1) % SLICES);
        }
    } else {
        int slice = tri - south_start;
        if (vert == 0)      local = sphere_pt(STACKS, 0);
        else if (vert == 1) local = sphere_pt(STACKS - 1, (slice + 1) % SLICES);
        else                local = sphere_pt(STACKS - 1, slice);
    }

    vec3 n_world = local;
    vec3 blender_pos = positions[particle_idx].xyz;
    float r = use_radius != 0 ? radii[particle_idx] : quad_size;
    if (use_radius == 0 && emitter_sizes_count > 0) {
        uint i = min(emitter_idx, uint(max(emitter_sizes_count - 1, 0)));
        r = emitter_sizes[i];
    }
    if (use_radius != 0 && (r != r || r < 0.0 || r > 1.0e6)) r = 1.0;
    vec3 world = blender_pos + local * r;

    mat3 R = mat3(view);
    v_n_view   = normalize(R * n_world);
    v_pos_view = (view * vec4(world, 1.0)).xyz;
    v_L_view   = normalize(R * normalize(vec3(0.45, 0.75, 0.4)));

    if (use_color_buffer != 0) {
        v_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (emitter_colors_count > 0) {
        uint i = min(emitter_idx, uint(max(emitter_colors_count - 1, 0)));
        v_color = emitter_colors[i];
    } else {
        v_color = color;
    }

    gl_Position = mvp * vec4(world, 1.0);
}
"""
        fs_src = LIT_SMOOTH_FRAG
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
        self._radius_handle = radius_id
        self._color_handle = color_id
        self._imported = True
        self._has_radius = self._rad_vbo is not None
        self._uniforms = {
            "mvp": glGetUniformLocation(program, "mvp"),
            "view": glGetUniformLocation(program, "view"),
            "color": glGetUniformLocation(program, "color"),
            "quad_size": glGetUniformLocation(program, "quad_size"),
            "use_radius": glGetUniformLocation(program, "use_radius"),
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
        mvp, view = prep

        pos = self.fetch_gpu_buffer(pipeline, "position")
        emit_idx = self.fetch_gpu_buffer(pipeline, "emitter_index")
        mode_buffers = self.fetch_draw_mode_buffers(pipeline)
        if (
            pos is None
            or not pos.valid
            or emit_idx is None
            or not emit_idx.valid
            or mode_buffers is None
        ):
            return False
        prefix_buf, binned_buf = mode_buffers

        rad = self.fetch_gpu_buffer(pipeline, "radius")
        color = self.fetch_gpu_buffer(pipeline, "color")
        if not self._ensure_import(
            pos,
            prefix_buf,
            binned_buf,
            emit_idx,
            rad if rad and rad.valid else None,
            color,
        ):
            return False
        use_color = self._color_vbo is not None

        saved = self._bridge.save_state_for_particle_draw()
        try:
            if not self._has_radius and self._uniform_size_vbo is not None:
                glBindBuffer(GL_ARRAY_BUFFER, self._uniform_size_vbo)
                glBufferSubData(
                    GL_ARRAY_BUFFER, 0, 4, np.array([float(params.size)], dtype=np.float32)
                )
                glBindBuffer(GL_ARRAY_BUFFER, 0)

            self._dispatch_compute(
                self._prefix_vbo,
                self.mode_bin_index(params.display_shape),
                _VERTS_PER_INSTANCE,
                prefix_buf.size // 4,
            )

            glUseProgram(self._program)
            glUniformMatrix4fv(self._uniforms["mvp"], 1, True, mvp)
            glUniformMatrix4fv(self._uniforms["view"], 1, True, view)
            glUniform4f(self._uniforms["color"], *params.color)
            glUniform1f(self._uniforms["quad_size"], float(params.size))
            glUniform1i(self._uniforms["use_radius"], 1 if self._has_radius else 0)
            glUniform1i(self._uniforms["use_color_buffer"], 1 if use_color else 0)

            sizes = tuple(float(s) for s in params.emitter_point_sizes[: self._MAX_EMITTER_SIZES])
            colors = tuple(
                tuple(float(c) for c in rgba[:4])
                for rgba in params.emitter_colors[: self._MAX_EMITTER_COLORS]
            )
            glUniform1i(self._uniforms["emitter_sizes_count"], len(sizes))
            if (
                sizes
                and self._uniforms["emitter_sizes"] is not None
                and self._uniforms["emitter_sizes"] >= 0
            ):
                glUniform1fv(self._uniforms["emitter_sizes"], len(sizes), list(sizes))
            glUniform1i(self._uniforms["emitter_colors_count"], len(colors))
            if (
                colors
                and self._uniforms["emitter_colors"] is not None
                and self._uniforms["emitter_colors"] >= 0
            ):
                flat = [c for rgba in colors for c in rgba]
                glUniform4fv(self._uniforms["emitter_colors"], len(colors), flat)

            glBindVertexArray(self._vao)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._pos_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, self._binned_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, self._draw_state_ssbo)
            if self._has_radius and self._rad_vbo is not None:
                glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 6, self._rad_vbo)
            else:
                glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 6, 0)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, self._color_vbo if use_color else 0)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 8, self._emit_idx_vbo)

            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
            glDrawArraysIndirect(GL_TRIANGLES, None)
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False
        finally:
            glBindVertexArray(0)
            self._bridge.restore_state(saved)
        return True
