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

"""Shared infrastructure for OpenGL zero-copy particle mode renderers."""

from __future__ import annotations

from typing import Any

from ..bridges.opengl import OpenGLBridge
from ..core.buffer_state import BufferExport
from ..core.particle_renderer import ParticleRenderer

try:
    from OpenGL.GL import (
        glDeleteProgram,
        glDeleteVertexArrays,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False


class OpenGLModeBase(ParticleRenderer):
    """Base for OpenGL zero-copy particle mode renderers.

    Each subclass owns its own VAO, shader program, and imported VBOs.
    The bridge handles extension resolution and buffer import.
    """

    def __init__(self, bridge: OpenGLBridge) -> None:
        self._bridge = bridge
        self._vao: int | None = None
        self._program: int | None = None
        self._handle: int | None = None
        self._imported = False
        self._buffers: list[tuple[int, int, int | None]] = []
        self._uniforms: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def _free_resources(self) -> None:
        if not _GL_OK:
            self._vao = None
            self._program = None
            self._buffers = []
            self._handle = None
            self._imported = False
            return
        if self._vao is not None:
            try:
                glDeleteVertexArrays(1, [self._vao])
            except Exception:
                pass
            self._vao = None
        if self._program is not None:
            try:
                glDeleteProgram(self._program)
            except Exception:
                pass
            self._program = None
        for vbo, mem, keep_handle in self._buffers:
            self._bridge.free_buffer(vbo, mem, keep_handle)
        self._buffers = []
        self._handle = None
        self._imported = False
        self._uniforms = {}

    def shutdown(self) -> None:
        self._free_resources()

    # ------------------------------------------------------------------
    # Buffer import helper
    # ------------------------------------------------------------------

    def _import(self, buf: BufferExport | None) -> int | None:
        """Import *buf* via the bridge; track for cleanup, return the VBO id."""
        if buf is None or not buf.valid:
            return None
        result = self._bridge.import_buffer(buf.handle, buf.size)
        buf.consume()
        if result is None:
            return None
        vbo, mem, keep_handle = result
        self._buffers.append((vbo, mem, keep_handle))
        return vbo

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------

    def _prepare_draw(self, context, pipeline, params):
        """Common pre-draw: check bridge and matrices.

        Returns ``(mvp, view)`` or ``None``.
        """
        if not self._bridge.load():
            return None

        matrices = self.get_mvp_view(context)
        if matrices is None:
            return None
        return matrices
