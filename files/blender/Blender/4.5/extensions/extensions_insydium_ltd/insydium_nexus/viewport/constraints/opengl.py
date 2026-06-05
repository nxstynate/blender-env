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

"""OpenGL constraint overlay (Python-side, zero-copy via GL_EXT_external_objects).

Mirrors the Vulkan ``vk_constraints`` pipeline but lives entirely in Python:
imports Theron's external constraint, id-LUT, and particle-id buffers as
GL SSBOs, packs the per-emitter palette into a host-allocated SSBO, and
issues a single ``glDrawArraysInstanced(GL_LINES, …)`` per frame against
the same vertex shader the Vulkan/Metal paths use.

The shader logic (linear-probing hash, ``ParticleConstraintsBuffer`` header
with ``_capacity``/``_count``, ``broken``/palette-alpha discard) is kept in
sync with ``viewport/backend/shaders/constraints/constraints_indirect.vert``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..core.buffer_state import BufferExport, buf_identity
from ..particles.opengl_base import OpenGLModeBase

if TYPE_CHECKING:
    from ..registry import ConstraintDrawParams

try:
    from OpenGL.GL import (
        GL_DYNAMIC_DRAW,
        GL_LINES,
        GL_SHADER_STORAGE_BUFFER,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBufferData,
        glDeleteBuffers,
        glDrawArraysInstanced,
        glGenBuffers,
        glGenVertexArrays,
        glGetUniformLocation,
        glUniform1ui,
        glUniformMatrix4fv,
        glUseProgram,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False


def _gl_id(generated):
    """Normalise the return of glGen* across PyOpenGL versions."""
    if isinstance(generated, (list, tuple)):
        return int(generated[0])
    if hasattr(generated, "__len__"):
        try:
            return int(generated[0])
        except Exception:
            return int(generated)
    return int(generated)


_VERT_SRC = """\
#version 430 core

layout(std430, binding = 0) readonly buffer Positions      { vec4 positions[]; };
layout(std430, binding = 1) readonly buffer EmitterIndices { uint emitter_indices[]; };

struct ParticleConstraint {
    int   fromId;
    int   toId;
    int   type;
    int   next;
    float relaxLen;
    float opts;
    int   broken;
};
layout(std430, binding = 2) readonly buffer ConstraintsBuffer {
    int  c_capacity;
    int  c_count;
    ParticleConstraint constraints[];
};
layout(std430, binding = 3) readonly buffer IdLut          { int id_lut[]; };

struct EmitterConstraintPalette {
    vec4 colors[4];
    vec4 enable_pad;
};
layout(std430, binding = 4) readonly buffer EmitterPalette {
    EmitterConstraintPalette emitter_palette[];
};

layout(std430, binding = 5) readonly buffer ParticleIds    { int particle_ids[]; };

uniform mat4 u_mvp;
uniform uint u_lut_capacity;

flat out vec4 v_color;

const int INVALID_PARTICLE = -1;

uint particle_id_to_hash(uint id, uint capacity) {
    uint state = id * 747796405u + 2891336453u;
    uint word  = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return ((word >> 22u) ^ word) % capacity;
}

int find_particle_index_from_id(int id, uint capacity) {
    if (id < 0 || capacity == 0u) return INVALID_PARTICLE;
    uint slot  = particle_id_to_hash(uint(id), capacity);
    int  guard = int(capacity);
    while (guard > 0 && id_lut[slot] != -1) {
        int idx = id_lut[slot];
        if (particle_ids[idx] == id) return idx;
        slot = (slot + 1u) % capacity;
        guard -= 1;
    }
    return INVALID_PARTICLE;
}

void emit_degenerate() {
    gl_Position = vec4(0.0);
    v_color = vec4(0.0);
}

void main() {
    if (gl_InstanceID >= c_count) { emit_degenerate(); return; }

    ParticleConstraint c = constraints[gl_InstanceID];
    if (c.broken == 1) { emit_degenerate(); return; }

    int from_idx = find_particle_index_from_id(c.fromId, u_lut_capacity);
    int to_idx   = find_particle_index_from_id(c.toId,   u_lut_capacity);
    if (from_idx == INVALID_PARTICLE || to_idx == INVALID_PARTICLE) {
        emit_degenerate();
        return;
    }

    uint emitter = emitter_indices[from_idx];
    EmitterConstraintPalette palette = emitter_palette[emitter];
    if (palette.enable_pad.x < 0.5) { emit_degenerate(); return; }

    int type_idx = clamp(c.type, 0, 3);
    vec4 col = palette.colors[type_idx];
    if (col.a <= 0.0) { emit_degenerate(); return; }

    vec3 world = (gl_VertexID == 0)
        ? positions[from_idx].xyz
        : positions[to_idx].xyz;
    gl_Position = u_mvp * vec4(world, 1.0);
    v_color = col;
}
"""

_FRAG_SRC = """\
#version 430 core
flat in vec4 v_color;
out vec4 FragColor;
void main() { FragColor = v_color; }
"""


# 4 vec4 colours + 1 vec4 enable_pad. Sim emits ParticleConstraint.type in
# {BIRTH=0, DIST=1, CUSTOM=2, VISCOSITY=3}; if more types are added later
# this constant + the GLSL/MSL ``colors[N]`` arrays + the per-emitter palette
# panel all grow together.
_FLOATS_PER_PALETTE = 20


class ConstraintsOpenGLRenderer(OpenGLModeBase):
    """OpenGL constraint overlay using GL_EXT_external_objects buffer imports."""

    def __init__(self) -> None:
        from ..bridges import get_opengl_bridge

        super().__init__(get_opengl_bridge())
        self._pos_vbo: int | None = None
        self._pos_handle: object | None = None
        self._emit_idx_vbo: int | None = None
        self._emit_idx_handle: object | None = None
        self._pid_vbo: int | None = None
        self._pid_handle: object | None = None
        self._cons_vbo: int | None = None
        self._cons_handle: object | None = None
        self._lut_vbo: int | None = None
        self._lut_handle: object | None = None
        # Host-uploaded SSBO; persists across frames, freed in shutdown only.
        self._palette_vbo: int | None = None

    def _free_resources(self) -> None:
        # Imported buffers + program + vao are released by the base class via
        # ``self._buffers``, ``self._program``, ``self._vao``.  We only have to
        # null the named handle/vbo refs that mirror them.
        self._pos_vbo = None
        self._pos_handle = None
        self._emit_idx_vbo = None
        self._emit_idx_handle = None
        self._pid_vbo = None
        self._pid_handle = None
        self._cons_vbo = None
        self._cons_handle = None
        self._lut_vbo = None
        self._lut_handle = None
        super()._free_resources()

    def _release_imported_buffers(self) -> None:
        """Release only the imported SSBOs, keeping the shader program + VAO."""
        if _GL_OK:
            for vbo, mem, keep_handle in self._buffers:
                self._bridge.free_buffer(vbo, mem, keep_handle)
        self._buffers = []
        self._pos_vbo = None
        self._pos_handle = None
        self._emit_idx_vbo = None
        self._emit_idx_handle = None
        self._pid_vbo = None
        self._pid_handle = None
        self._cons_vbo = None
        self._cons_handle = None
        self._lut_vbo = None
        self._lut_handle = None
        self._imported = False

    def shutdown(self) -> None:
        super().shutdown()
        if _GL_OK and self._palette_vbo is not None:
            try:
                glDeleteBuffers(1, [self._palette_vbo])
            except Exception:
                pass
            self._palette_vbo = None

    def _ensure_program(self) -> bool:
        if self._program is not None:
            return True
        if not _GL_OK or not self._bridge.load():
            return False
        prog = self._bridge.compile_program(_VERT_SRC, _FRAG_SRC)
        if prog is None:
            return False
        self._program = int(prog)
        # OpenGL requires a bound VAO for glDrawArrays*, even when the vertex
        # shader sources its data entirely from SSBOs.
        self._vao = _gl_id(glGenVertexArrays(1))
        return True

    def _ensure_palette_vbo(self) -> int | None:
        if self._palette_vbo is None:
            if not _GL_OK:
                return None
            self._palette_vbo = _gl_id(glGenBuffers(1))
        return self._palette_vbo

    def _upload_palette(self, params: "ConstraintDrawParams") -> int | None:
        vbo = self._ensure_palette_vbo()
        if vbo is None:
            return None
        emitter_count = max(
            1,
            len(params.emitter_constraint_palettes),
            len(params.emitter_display_constraints),
        )
        floats = np.zeros((emitter_count, _FLOATS_PER_PALETTE), dtype=np.float32)
        for i in range(emitter_count):
            palette = (
                params.emitter_constraint_palettes[i]
                if i < len(params.emitter_constraint_palettes)
                else ()
            )
            for slot in range(4):
                rgba = palette[slot] if slot < len(palette) else (0.0, 0.0, 0.0, 0.0)
                floats[i, slot * 4 : slot * 4 + 4] = rgba
            enabled = i < len(params.emitter_display_constraints) and bool(
                params.emitter_display_constraints[i]
            )
            floats[i, 16] = 1.0 if enabled else 0.0  # enable_pad.x
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, vbo)
        glBufferData(GL_SHADER_STORAGE_BUFFER, floats.nbytes, floats.tobytes(), GL_DYNAMIC_DRAW)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
        return vbo

    def _ensure_import(
        self,
        pos: BufferExport,
        emit_idx: BufferExport,
        pid: BufferExport,
        cons: BufferExport,
        lut: BufferExport,
    ) -> bool:
        pos_id = buf_identity(pos)
        emit_id = buf_identity(emit_idx)
        pid_id = buf_identity(pid)
        cons_id = buf_identity(cons)
        lut_id = buf_identity(lut)
        if (
            self._imported
            and self._pos_handle == pos_id
            and self._emit_idx_handle == emit_id
            and self._pid_handle == pid_id
            and self._cons_handle == cons_id
            and self._lut_handle == lut_id
        ):
            return True
        if self._imported:
            self._release_imported_buffers()

        self._pos_vbo = self._import(pos)
        self._emit_idx_vbo = self._import(emit_idx)
        self._pid_vbo = self._import(pid)
        self._cons_vbo = self._import(cons)
        self._lut_vbo = self._import(lut)
        if None in (
            self._pos_vbo,
            self._emit_idx_vbo,
            self._pid_vbo,
            self._cons_vbo,
            self._lut_vbo,
        ):
            self._release_imported_buffers()
            return False

        self._pos_handle = pos_id
        self._emit_idx_handle = emit_id
        self._pid_handle = pid_id
        self._cons_handle = cons_id
        self._lut_handle = lut_id
        self._imported = True
        return True

    def draw(self, context, pipeline, scene, params) -> bool:  # noqa: ARG002
        """``NexusRenderer`` entry point — forwards to :meth:`stage`.

        Constraint stagers expose ``stage(context, pipeline, params)``; the
        ``scene`` argument from the registry's draw signature is unused here.
        """
        return self.stage(context, pipeline, params)

    def stage(self, context, pipeline, params: "ConstraintDrawParams") -> bool:
        if not _GL_OK or not self._bridge.load():
            return False
        if not params.overlay_enabled or pipeline is None:
            return True

        positions = self.fetch_gpu_buffer(int(pipeline), "position")
        emitter_idx = self.fetch_gpu_buffer(int(pipeline), "emitter_index")
        particle_ids = self.fetch_gpu_buffer(int(pipeline), "id")
        constraints_buf = self.fetch_constraints_buffer(int(pipeline))
        lut_pair = self.fetch_id_lut_buffer(int(pipeline))

        bufs = (positions, emitter_idx, particle_ids, constraints_buf)
        if any(b is None or not b.valid for b in bufs) or lut_pair is None:
            return True
        lut_buf, lut_capacity = lut_pair

        if not self._ensure_program():
            return False
        if not self._ensure_import(positions, emitter_idx, particle_ids, constraints_buf, lut_buf):
            return True

        palette_vbo = self._upload_palette(params)
        if palette_vbo is None:
            return True

        # Buffer capacity = (size_bytes - 8 byte header) / 28 byte stride.
        # Matches the C-side derivation in nexus_use_external_constraint_buffer.
        capacity = max(0, (constraints_buf.size - 8) // 28)
        if capacity == 0:
            return True

        mvp_view = self.get_mvp_view(context)
        if mvp_view is None:
            return True
        mvp_list, _view_list = mvp_view

        # Blender's draw handler runs with depth test off; particle renderers
        # use save_state_for_particle_draw which enables LEQUAL + depth writes.
        # We follow the same pattern so constraints occlude correctly and we
        # don't leak GL state on exit.
        saved = self._bridge.save_state_for_particle_draw()
        try:
            glUseProgram(self._program)
            glBindVertexArray(self._vao)

            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, self._pos_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, self._emit_idx_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, self._cons_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._lut_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, palette_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, self._pid_vbo)

            loc_mvp = glGetUniformLocation(self._program, "u_mvp")
            loc_lut = glGetUniformLocation(self._program, "u_lut_capacity")
            # Blender hands us row-major matrices; let GL transpose to its
            # column-major layout via the third arg.
            if loc_mvp >= 0:
                glUniformMatrix4fv(loc_mvp, 1, True, mvp_list)
            if loc_lut >= 0:
                glUniform1ui(loc_lut, int(lut_capacity))

            glDrawArraysInstanced(GL_LINES, 0, 2, int(capacity))

            for binding in range(6):
                glBindBufferBase(GL_SHADER_STORAGE_BUFFER, binding, 0)
        finally:
            self._bridge.restore_state(saved)
        return True


def make_opengl_stager():
    return ConstraintsOpenGLRenderer()
