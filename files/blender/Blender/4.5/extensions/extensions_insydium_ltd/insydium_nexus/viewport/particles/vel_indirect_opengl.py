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

"""Shared OpenGL indirect draw for velocity-based modes (lines, arrows).

Uses draw-mode prefix + binned indices, EMITTER_INDEX SSBO, and
glDrawArraysIndirect like circle/sphere/axis paths.
"""

from __future__ import annotations

import numpy as np

from ..core.buffer_state import BufferExport, buf_identity
from .indirect_opengl_base import IndirectOpenGLBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_FALSE,
        GL_FLOAT,
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
        glUniform4f,
        glUniform4fv,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribPointer,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False

# Enough dummy vertices for arrow outline (14).
_DUMMY_VERT_COUNT = 16
_DUMMY_VERTS = np.zeros(_DUMMY_VERT_COUNT * 3, dtype=np.float32)


class VelIndirectOpenGLBase(IndirectOpenGLBase):
    _MAX_EMITTER = 64

    def __init__(
        self,
        bridge,
        *,
        gl_primitive: int,
        verts_per_instance: int,
        vertex_shader_src: str,
        fragment_shader_src: str,
    ) -> None:
        super().__init__(bridge)
        self._gl_primitive = int(gl_primitive)
        self._verts_per_instance = int(verts_per_instance)
        self._vertex_shader_src = vertex_shader_src
        self._fragment_shader_src = fragment_shader_src

        self._prefix_handle: int | None = None
        self._binned_handle: int | None = None
        self._prefix_vbo: int | None = None
        self._binned_vbo: int | None = None
        self._emit_idx_vbo: int | None = None
        self._pos_vbo: int | None = None
        self._vel_vbo: int | None = None
        self._vel_handle: object | None = None
        self._rad_vbo: int | None = None
        self._radius_handle: object | None = None
        self._rot_vbo: int | None = None
        self._rot_handle: object | None = None
        self._color_vbo: int | None = None
        self._color_handle: object | None = None
        self._mesh_vbo: int | None = None
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
        self._rad_vbo = None
        self._radius_handle = None
        self._rot_vbo = None
        self._rot_handle = None
        self._color_vbo = None
        self._color_handle = None
        super()._free_resources()

    def _ensure_import(
        self,
        pos: BufferExport,
        vel: BufferExport,
        prefix: BufferExport,
        binned: BufferExport,
        emit_idx: BufferExport,
        radius: BufferExport | None = None,
        rot: BufferExport | None = None,
        color: BufferExport | None = None,
    ) -> bool:
        pos_id = buf_identity(pos)
        prefix_id = buf_identity(prefix)
        binned_id = buf_identity(binned)
        vel_id = buf_identity(vel)
        radius_id = buf_identity(radius)
        rot_id = buf_identity(rot)
        color_id = buf_identity(color)
        if (
            self._imported
            and self._handle == pos_id
            and self._prefix_handle == prefix_id
            and self._binned_handle == binned_id
            and self._vel_handle == vel_id
            and self._radius_handle == radius_id
            and self._rot_handle == rot_id
            and self._color_handle == color_id
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
        self._rad_vbo = self._import(radius)
        self._rot_vbo = self._import(rot)
        self._color_vbo = self._import(color)
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
            glBindBuffer(GL_ARRAY_BUFFER, mesh)
            glBufferData(GL_ARRAY_BUFFER, _DUMMY_VERTS.nbytes, _DUMMY_VERTS, GL_STATIC_DRAW)
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

        program = self._bridge.compile_program(self._vertex_shader_src, self._fragment_shader_src)
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
        self._radius_handle = radius_id
        self._rot_handle = rot_id
        self._color_handle = color_id
        self._imported = True
        self._has_radius = self._rad_vbo is not None
        self._uniforms = {
            "mvp": glGetUniformLocation(program, "mvp"),
            "view": glGetUniformLocation(program, "view"),
            "color": glGetUniformLocation(program, "color"),
            "line_scale": glGetUniformLocation(program, "line_scale"),
            "line_length_mode": glGetUniformLocation(program, "line_length_mode"),
            "use_color_buffer": glGetUniformLocation(program, "use_color_buffer"),
            "use_radius": glGetUniformLocation(program, "use_radius"),
            "emitter_line_modes_count": glGetUniformLocation(program, "emitter_line_modes_count"),
            "emitter_line_modes": glGetUniformLocation(program, "emitter_line_modes"),
            "emitter_fixed_lengths_count": glGetUniformLocation(
                program, "emitter_fixed_lengths_count"
            ),
            "emitter_line_fixed": glGetUniformLocation(program, "emitter_line_fixed"),
            "emitter_sizes_count": glGetUniformLocation(program, "emitter_sizes_count"),
            "emitter_sizes": glGetUniformLocation(program, "emitter_sizes"),
            "emitter_colors_count": glGetUniformLocation(program, "emitter_colors_count"),
            "emitter_colors": glGetUniformLocation(program, "emitter_colors"),
            "use_hpb": glGetUniformLocation(program, "use_hpb"),
            "forced_up": glGetUniformLocation(program, "forced_up"),
            "emitter_rotation_modes_count": glGetUniformLocation(
                program, "emitter_rotation_modes_count"
            ),
            "emitter_rotation_modes": glGetUniformLocation(program, "emitter_rotation_modes"),
            "emitter_up_vectors_count": glGetUniformLocation(program, "emitter_up_vectors_count"),
            "emitter_up_vectors": glGetUniformLocation(program, "emitter_up_vectors"),
            "line_min_length": glGetUniformLocation(program, "line_min_length"),
            "line_max_length": glGetUniformLocation(program, "line_max_length"),
            "emitter_line_min_count": glGetUniformLocation(program, "emitter_line_min_count"),
            "emitter_line_min": glGetUniformLocation(program, "emitter_line_min"),
            "emitter_line_max_count": glGetUniformLocation(program, "emitter_line_max_count"),
            "emitter_line_max": glGetUniformLocation(program, "emitter_line_max"),
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
        vel = self.fetch_gpu_buffer(pipeline, "velocity")
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

        rad = self.fetch_gpu_buffer(pipeline, "radius")
        rot = self.fetch_gpu_buffer(pipeline, "rotation")
        color = self.fetch_gpu_buffer(pipeline, "color")
        if not self._ensure_import(
            pos,
            vel,
            prefix_buf,
            binned_buf,
            emit_idx,
            rad if rad and rad.valid else None,
            rot if rot and rot.valid else None,
            color,
        ):
            return False
        use_color = self._color_vbo is not None

        mode_index = self.mode_bin_index(params.display_shape)
        saved = self._bridge.save_state_for_particle_draw()
        try:
            self._dispatch_compute(
                self._prefix_vbo, mode_index, self._verts_per_instance, prefix_buf.size // 4
            )

            glUseProgram(self._program)
            glUniformMatrix4fv(self._uniforms["mvp"], 1, True, mvp)
            vloc = self._uniforms.get("view")
            if vloc is not None and vloc >= 0:
                glUniformMatrix4fv(vloc, 1, True, view)
            glUniform4f(self._uniforms["color"], *params.color)
            glUniform1f(self._uniforms["line_scale"], float(params.line_fixed_length))
            glUniform1i(self._uniforms["line_length_mode"], int(params.line_length_mode))
            glUniform1i(self._uniforms["use_color_buffer"], 1 if use_color else 0)
            glUniform1i(self._uniforms["use_radius"], 1 if self._has_radius else 0)
            rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
            use_hpb = rotation_mode == "UP_VECTOR" and self._rot_vbo is not None
            use_tangential = rotation_mode == "TANGENTIAL"
            use_hpb_mode = 1 if use_hpb else (2 if use_tangential else 0)
            uh = self._uniforms.get("use_hpb")
            if uh is not None and uh >= 0:
                glUniform1i(uh, use_hpb_mode)
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
            fu = self._uniforms.get("forced_up")
            if fu is not None and fu >= 0:
                glUniform3f(fu, ux, uy, uz)

            line_modes = tuple(
                int(x) for x in params.emitter_line_length_modes[: self._MAX_EMITTER]
            )
            line_fixed = tuple(
                float(x) for x in params.emitter_line_fixed_lengths[: self._MAX_EMITTER]
            )
            sizes = tuple(float(s) for s in params.emitter_point_sizes[: self._MAX_EMITTER])
            colors = tuple(
                tuple(float(c) for c in rgba[:4])
                for rgba in params.emitter_colors[: self._MAX_EMITTER]
            )

            glUniform1i(self._uniforms["emitter_line_modes_count"], len(line_modes))
            lm = self._uniforms["emitter_line_modes"]
            if line_modes and lm is not None and lm >= 0:
                glUniform1iv(lm, len(line_modes), list(line_modes))

            glUniform1i(self._uniforms["emitter_fixed_lengths_count"], len(line_fixed))
            lf = self._uniforms["emitter_line_fixed"]
            if line_fixed and lf is not None and lf >= 0:
                glUniform1fv(lf, len(line_fixed), list(line_fixed))

            glUniform1f(
                self._uniforms["line_min_length"],
                float(getattr(params, "line_min_length", 0.0)),
            )
            glUniform1f(
                self._uniforms["line_max_length"],
                float(getattr(params, "line_max_length", 0.0)),
            )

            line_min = tuple(
                float(x)
                for x in getattr(params, "emitter_line_min_lengths", ())[: self._MAX_EMITTER]
            )
            glUniform1i(self._uniforms["emitter_line_min_count"], len(line_min))
            lmin = self._uniforms["emitter_line_min"]
            if line_min and lmin is not None and lmin >= 0:
                glUniform1fv(lmin, len(line_min), list(line_min))

            line_max = tuple(
                float(x)
                for x in getattr(params, "emitter_line_max_lengths", ())[: self._MAX_EMITTER]
            )
            glUniform1i(self._uniforms["emitter_line_max_count"], len(line_max))
            lmax = self._uniforms["emitter_line_max"]
            if line_max and lmax is not None and lmax >= 0:
                glUniform1fv(lmax, len(line_max), list(line_max))

            glUniform1i(self._uniforms["emitter_sizes_count"], len(sizes))
            sz_u = self._uniforms["emitter_sizes"]
            if sizes and sz_u is not None and sz_u >= 0:
                glUniform1fv(sz_u, len(sizes), list(sizes))

            glUniform1i(self._uniforms["emitter_colors_count"], len(colors))
            ec = self._uniforms["emitter_colors"]
            if colors and ec is not None and ec >= 0:
                flat = [c for rgba in colors for c in rgba]
                glUniform4fv(ec, len(colors), flat)

            rot_modes = tuple(int(x) for x in params.emitter_rotation_modes[: self._MAX_EMITTER])
            rm_c = self._uniforms.get("emitter_rotation_modes_count")
            if rm_c is not None and rm_c >= 0:
                glUniform1i(rm_c, len(rot_modes))
            rm_u = self._uniforms.get("emitter_rotation_modes")
            if rot_modes and rm_u is not None and rm_u >= 0:
                glUniform1iv(rm_u, len(rot_modes), list(rot_modes))

            up_vecs = tuple(params.emitter_rotation_up_vectors[: self._MAX_EMITTER])
            uv_c = self._uniforms.get("emitter_up_vectors_count")
            if uv_c is not None and uv_c >= 0:
                glUniform1i(uv_c, len(up_vecs))
            uv_u = self._uniforms.get("emitter_up_vectors")
            if up_vecs and uv_u is not None and uv_u >= 0:
                flat_uv = [c for v in up_vecs for c in v]
                glUniform3fv(uv_u, len(up_vecs), flat_uv)

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
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 9, self._vel_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 10, self._rot_vbo if self._rot_vbo else 0)

            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
            glDrawArraysIndirect(self._gl_primitive, None)
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False
        finally:
            glBindVertexArray(0)
            self._bridge.restore_state(saved)
        return True
