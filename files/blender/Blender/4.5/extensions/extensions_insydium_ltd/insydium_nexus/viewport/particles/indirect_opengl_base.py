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

"""Shared infrastructure for OpenGL indirect draw particle renderers.

Provides the single-dispatch compute shader (DrawArraysIndirect path),
the indirect command + draw-state SSBO lifecycle, and the canonical
draw-mode bin index mapping.
"""

from __future__ import annotations

from .opengl_base import OpenGLModeBase

try:
    from OpenGL.GL import (
        GL_COMMAND_BARRIER_BIT,
        GL_COMPILE_STATUS,
        GL_COMPUTE_SHADER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_DYNAMIC_DRAW,
        GL_LINK_STATUS,
        GL_SHADER_STORAGE_BARRIER_BIT,
        GL_SHADER_STORAGE_BUFFER,
        glAttachShader,
        glBindBuffer,
        glBindBufferBase,
        glBufferData,
        glCompileShader,
        glCreateProgram,
        glCreateShader,
        glDeleteBuffers,
        glDeleteProgram,
        glDeleteShader,
        glDispatchCompute,
        glGenBuffers,
        glGetProgramiv,
        glGetShaderiv,
        glGetUniformLocation,
        glLinkProgram,
        glMemoryBarrier,
        glShaderSource,
        glUniform1ui,
        glUseProgram,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False

_COMPUTE_SRC = """
#version 430 core
layout(local_size_x = 1) in;
layout(std430, binding = 0) readonly buffer PrefixBuffer { uint prefix[]; };
struct DrawArraysIndirectCommand {
    uint count;
    uint instanceCount;
    uint first;
    uint baseInstance;
};
layout(std430, binding = 1) writeonly buffer DrawCommandBuffer {
    DrawArraysIndirectCommand cmd;
};
layout(std430, binding = 2) writeonly buffer DrawStateBuffer {
    uint start_index;
};
uniform uint mode_index;
uniform uint verts_per_instance;
uniform uint prefix_count;
void main() {
    if (mode_index >= prefix_count) {
        cmd.count = 0u;
        cmd.instanceCount = 0u;
        cmd.first = 0u;
        cmd.baseInstance = 0u;
        start_index = 0u;
        return;
    }
    uint end_val = prefix[mode_index];
    uint start_val = (mode_index == 0u) ? 0u : prefix[mode_index - 1u];
    if (end_val < start_val) {
        end_val = start_val;
    }
    cmd.count = verts_per_instance;
    cmd.instanceCount = end_val - start_val;
    cmd.first = 0u;
    cmd.baseInstance = 0u;
    start_index = start_val;
}
"""


FLAT_COLOR_FRAG = """\
#version 330 core
flat in vec4 v_color;
out vec4 FragColor;
void main() { FragColor = v_color; }
"""

LIT_FLAT_FRAG = """\
#version 330 core
flat in vec3 v_n_view;
flat in vec3 v_L_view;
in vec3 v_pos_view;
flat in vec4 v_color;
out vec4 FragColor;
void main() {
    vec3 N = normalize(v_n_view);
    vec3 L = v_L_view;
    vec3 V = normalize(-v_pos_view);
    vec3 H = normalize(L + V);
    float diff = max(dot(N, L), 0.0);
    float spec = pow(max(dot(N, H), 0.0), 48.0);
    vec3 rgb = v_color.rgb * (0.12 + 0.58 * diff) + vec3(1.0) * 0.25 * spec;
    FragColor = vec4(rgb, v_color.a);
}
"""

LIT_SMOOTH_FRAG = """\
#version 330 core
in vec3 v_n_view;
in vec3 v_pos_view;
flat in vec3 v_L_view;
flat in vec4 v_color;
out vec4 FragColor;
void main() {
    vec3 N = normalize(v_n_view);
    vec3 L = v_L_view;
    vec3 V = normalize(-v_pos_view);
    vec3 H = normalize(L + V);
    float diff = max(dot(N, L), 0.0);
    float spec = pow(max(dot(N, H), 0.0), 48.0);
    vec3 rgb = v_color.rgb * (0.12 + 0.58 * diff) + vec3(1.0) * 0.25 * spec;
    FragColor = vec4(rgb, v_color.a);
}
"""


class IndirectOpenGLBase(OpenGLModeBase):
    """Mixin infrastructure for glDrawArraysIndirect particle renderers.

    Subclasses gain:
      - ``DRAW_MODE_BIN_INDEX`` — canonical mode → prefix buffer index mapping
      - ``_ensure_compute_program()`` — lazily compile the dispatch compute shader
      - ``_ensure_indirect_buffers()`` — allocate _indirect_cmd / _draw_state_ssbo
      - ``_free_indirect_resources()`` — release the above (call from _free_resources)
      - ``_dispatch_compute(prefix_vbo, mode_index, verts_per_instance, prefix_count)``
      - ``mode_bin_index(display_shape)`` — look up a mode's bin index
    """

    DRAW_MODE_BIN_INDEX: dict[str, int] = {
        "POINTS": 0,
        "SQUARE": 1,
        "DIRECTION": 2,
        "BOX3D": 3,
        "BOX3D_FILLED": 4,
        "CIRCLE": 5,
        "CIRCLE_FILLED": 6,
        "PYRAMID": 7,
        "PYRAMID_FILLED": 8,
        "ARROW": 9,
        "ARROW_FILLED": 10,
        "SPHERE": 11,
        "AXIS": 12,
        "NONE": 13,
        "SSF": 14,
    }

    def __init__(self, bridge) -> None:
        super().__init__(bridge)
        self._draw_state_ssbo: int | None = None
        self._indirect_cmd: int | None = None
        self._compute_program: int | None = None
        self._compute_mode_loc: int = -1
        self._compute_verts_loc: int = -1
        self._compute_prefix_count_loc: int = -1

    def _ensure_compute_program(self) -> bool:
        """Lazily compile the shared indirect dispatch compute shader."""
        if self._compute_program is not None:
            return True
        try:
            shader = glCreateShader(GL_COMPUTE_SHADER)
            glShaderSource(shader, _COMPUTE_SRC)
            glCompileShader(shader)
            if not glGetShaderiv(shader, GL_COMPILE_STATUS):
                glDeleteShader(shader)
                return False
            prog = glCreateProgram()
            glAttachShader(prog, shader)
            glLinkProgram(prog)
            glDeleteShader(shader)
            if not glGetProgramiv(prog, GL_LINK_STATUS):
                glDeleteProgram(prog)
                return False
            self._compute_program = prog
            self._compute_mode_loc = glGetUniformLocation(prog, "mode_index")
            self._compute_verts_loc = glGetUniformLocation(prog, "verts_per_instance")
            self._compute_prefix_count_loc = glGetUniformLocation(prog, "prefix_count")
            return True
        except Exception:
            return False

    def _ensure_indirect_buffers(self) -> bool:
        """Allocate the indirect draw command buffer and draw-state SSBO."""
        if self._indirect_cmd is not None and self._draw_state_ssbo is not None:
            return True
        try:
            cmd_gen = glGenBuffers(1)
            self._indirect_cmd = cmd_gen[0] if isinstance(cmd_gen, (list, tuple)) else cmd_gen
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
            glBufferData(GL_DRAW_INDIRECT_BUFFER, 16, None, GL_DYNAMIC_DRAW)
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)

            state_gen = glGenBuffers(1)
            self._draw_state_ssbo = (
                state_gen[0] if isinstance(state_gen, (list, tuple)) else state_gen
            )
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._draw_state_ssbo)
            glBufferData(GL_SHADER_STORAGE_BUFFER, 4, None, GL_DYNAMIC_DRAW)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
            return True
        except Exception:
            return False

    def _free_indirect_resources(self) -> None:
        """Release the compute program and indirect buffers. Call from _free_resources()."""
        if _GL_OK:
            for buf in (self._draw_state_ssbo, self._indirect_cmd):
                if buf is not None:
                    try:
                        glDeleteBuffers(1, [buf])
                    except Exception:
                        pass
            if self._compute_program is not None:
                try:
                    glDeleteProgram(self._compute_program)
                except Exception:
                    pass
        self._draw_state_ssbo = None
        self._indirect_cmd = None
        self._compute_program = None
        self._compute_mode_loc = -1
        self._compute_verts_loc = -1
        self._compute_prefix_count_loc = -1

    def _dispatch_compute(
        self,
        prefix_vbo: int,
        mode_index: int,
        verts_per_instance: int,
        prefix_count: int,
    ) -> None:
        """Bind, dispatch, and barrier the indirect draw compute shader."""
        glUseProgram(self._compute_program)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, prefix_vbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, self._indirect_cmd)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, self._draw_state_ssbo)
        glUniform1ui(self._compute_mode_loc, int(mode_index))
        glUniform1ui(self._compute_verts_loc, int(verts_per_instance))
        glUniform1ui(self._compute_prefix_count_loc, int(prefix_count))
        glDispatchCompute(1, 1, 1)
        glMemoryBarrier(GL_COMMAND_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT)

    def mode_bin_index(self, display_shape: str) -> int:
        """Return the prefix buffer bin index for the given display shape."""
        key = str(display_shape or "").strip().upper()
        aliases = {
            "CIRCLEFILLED": "CIRCLE_FILLED",
            "BOX3DOUTLINE": "BOX3D",
            "BOX3DFILLED": "BOX3D_FILLED",
            "PYRAMIDOUTLINE": "PYRAMID",
            "PYRAMIDFILLED": "PYRAMID_FILLED",
        }
        key = aliases.get(key, key)
        return int(self.DRAW_MODE_BIN_INDEX.get(key, 0))
