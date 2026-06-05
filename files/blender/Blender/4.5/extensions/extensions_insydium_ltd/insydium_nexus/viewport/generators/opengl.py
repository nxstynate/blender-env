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

"""OpenGL multi-layer mesh-instancing renderer for NX_GENERATOR.

Each frame:
1. Fetch zero-copy particle buffers (positions, ids, plus the per-source ones).
2. Dispatch a compute classifier that hashes each particle's id, picks a layer
   from the cumulative spawn-weight array, and writes (a) sorted-by-layer
   ``binned_indices``, (b) ``layer_offsets[N+1]`` prefix array, and (c) one
   ``DrawElementsIndirectCommand`` per layer.
3. Per enabled layer: bind that layer's mesh VAO, set per-layer uniforms, issue
   ``glDrawElementsIndirect`` at the layer's command offset. The vertex shader
   reads ``binned_indices[layer_offsets[u_layer_idx] + gl_InstanceID]`` to find
   the actual particle.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import numpy as np

from ..core.buffer_state import buf_identity
from ..particles.opengl_base import OpenGLModeBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_COMMAND_BARRIER_BIT,
        GL_COMPILE_STATUS,
        GL_COMPUTE_SHADER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_DYNAMIC_DRAW,
        GL_ELEMENT_ARRAY_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_LINK_STATUS,
        GL_SHADER_STORAGE_BARRIER_BIT,
        GL_SHADER_STORAGE_BUFFER,
        GL_STATIC_DRAW,
        GL_TRIANGLES,
        GL_UNSIGNED_INT,
        glAttachShader,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBufferData,
        glCompileShader,
        glCreateProgram,
        glCreateShader,
        glDeleteBuffers,
        glDeleteProgram,
        glDeleteShader,
        glDeleteVertexArrays,
        glDispatchCompute,
        glDrawElementsIndirect,
        glEnableVertexAttribArray,
        glGenBuffers,
        glGenVertexArrays,
        glGetProgramiv,
        glGetShaderiv,
        glGetUniformLocation,
        glLinkProgram,
        glMemoryBarrier,
        glShaderSource,
        glUniform1fv,
        glUniform1i,
        glUniform1ui,
        glUniform1uiv,
        glUniform3f,
        glUniform4f,
        glUniformMatrix3fv,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribPointer,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False


_MAX_LAYERS = 16
# DrawElementsIndirectCommand layout:
#   uint count, uint instanceCount, uint firstIndex, int baseVertex, uint baseInstance
_INDIRECT_CMD_BYTES = 20


@dataclass
class _LayerMesh:
    """Static mesh resources owned by the renderer for one layer."""

    mesh_vbo: int
    mesh_ibo: int
    vao: int
    revision_key: tuple
    index_count: int


class GeneratorOpenGLRenderer(OpenGLModeBase):
    _VS = """\
#version 430 core
layout(location = 0) in vec3 a_mesh_local;
layout(location = 1) in vec3 a_corner_normal;
layout(location = 2) in vec3 a_smooth_normal;

layout(std430, binding = 3)  readonly buffer Positions    { vec4 positions[]; };
layout(std430, binding = 6)  readonly buffer Radii        { float radii[]; };
layout(std430, binding = 7)  readonly buffer Colors       { vec4 colors[]; };
layout(std430, binding = 9)  readonly buffer ParticleIds  { int particle_ids[]; };
layout(std430, binding = 10) readonly buffer Rotations    { vec4 rotations[]; };
layout(std430, binding = 11) readonly buffer Scales       { vec4 scales[]; };
layout(std430, binding = 12) readonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 13) readonly buffer LayerOffsets { uint layer_offsets[]; };

uniform mat4 u_mvp;
uniform vec4 u_mesh_color;
uniform vec4 u_custom_color;
uniform vec3 u_mesh_scale;
uniform vec3 u_custom_scale;
uniform mat3 u_mesh_rotation;
uniform vec3 u_custom_rotation;
uniform int  u_layer_idx;
uniform int  u_scale_source_id;
uniform int  u_color_source_id;
uniform int  u_rotation_source_id;
uniform vec3 u_scale_variation;
uniform vec3 u_color_variation;
uniform vec3 u_rotation_variation;
// 1 → keep three independent jitter samples; 0 → broadcast j.x to all axes.
uniform int  u_scale_variation_per_axis;
uniform int  u_color_variation_per_axis;
uniform int  u_rotation_variation_per_axis;
// 0 = DEFAULT (corner normal), 1 = FLAT (derivative), 2 = SMOOTH (vertex normal).
uniform int  u_shading_mode;

flat out vec4 v_color;
out vec3 v_world_pos;
out vec3 v_corner_normal;
out vec3 v_smooth_normal;
flat out int v_shading_mode;

mat3 rot_x(float a) { float c = cos(a), s = sin(a); return mat3(1.0,0.0,0.0, 0.0,c,-s, 0.0,s,c); }
mat3 rot_y(float a) { float c = cos(a), s = sin(a); return mat3(c,0.0,s, 0.0,1.0,0.0, -s,0.0,c); }
mat3 rot_z(float a) { float c = cos(a), s = sin(a); return mat3(c,-s,0.0, s,c,0.0, 0.0,0.0,1.0); }

uint pcg_hash(uint x) {
    uint state = x * 747796405u + 2891336453u;
    uint word  = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

float hash01(uint x) { return float(pcg_hash(x)) * (1.0 / 4294967295.0); }

void main() {
    // Resolve which particle this instance corresponds to via the layer's
    // slice of the binned indices buffer.
    uint base = layer_offsets[uint(u_layer_idx)];
    uint particle_idx = binned[base + uint(gl_InstanceID)];

    vec3 part = positions[particle_idx].xyz;
    uint pid = uint(particle_ids[particle_idx]);

    // Stable per-particle jitter seeds keyed on particle id.
    vec3 j_scale = vec3(
        hash01(pid * 11u + 1u),
        hash01(pid * 11u + 2u),
        hash01(pid * 11u + 3u)
    ) * 2.0 - 1.0;

    vec3 j_color = vec3(
        hash01(pid * 11u + 4u),
        hash01(pid * 11u + 5u),
        hash01(pid * 11u + 6u)
    ) * 2.0 - 1.0;

    vec3 j_rot = vec3(
        hash01(pid * 11u + 7u),
        hash01(pid * 11u + 8u),
        hash01(pid * 11u + 9u)
    ) * 2.0 - 1.0;
    
    if (u_scale_variation_per_axis == 0) j_scale = vec3(j_scale.x);
    if (u_color_variation_per_axis == 0) j_color = vec3(j_color.x);
    if (u_rotation_variation_per_axis == 0) j_rot = vec3(j_rot.x);

    // --- Rotation ---
    mat3 base_rot;
    if (u_rotation_source_id == 1) {
        vec3 raw_hpb = rotations[particle_idx].xyz;
        vec3 hpb = vec3(raw_hpb.y, raw_hpb.z, raw_hpb.x);
        base_rot = rot_z(hpb.z) * rot_x(hpb.x) * rot_y(hpb.y);
    } else if (u_rotation_source_id == 2) {
        // Blender Euler XYZ: apply X, then Y, then Z.
        base_rot = rot_z(u_custom_rotation.z)
                 * rot_y(u_custom_rotation.y)
                 * rot_x(u_custom_rotation.x);
    } else {
        base_rot = u_mesh_rotation;
    }
    vec3 jitter_e = j_rot * (u_rotation_variation * 6.28318530718);
    mat3 jitter_rot = rot_z(jitter_e.z) * rot_y(jitter_e.y) * rot_x(jitter_e.x);
    mat3 rot = jitter_rot * base_rot;

    // --- Scale ---
    vec3 base_scale;
    if (u_scale_source_id == 1) {
        base_scale = vec3(radii[particle_idx]);
    } else if (u_scale_source_id == 2) {
        base_scale = scales[particle_idx].xyz;
    } else if (u_scale_source_id == 3) {
        base_scale = u_custom_scale;
    } else {
        base_scale = u_mesh_scale;
    }
    vec3 scale_vec = base_scale * (vec3(1.0) + j_scale * u_scale_variation);

    vec3 local = rot * (scale_vec * a_mesh_local);
    vec3 world_pos = part + local;
    gl_Position = u_mvp * vec4(world_pos, 1.0);
    v_world_pos = world_pos;

    // Normals follow the rotation (rot is orthonormal here).
    v_corner_normal = rot * a_corner_normal;
    v_smooth_normal = rot * a_smooth_normal;
    v_shading_mode  = u_shading_mode;

    // --- Colour ---
    vec4 base_color;
    if (u_color_source_id == 1) {
        base_color = vec4(colors[particle_idx].rgb, 1.0);
    } else if (u_color_source_id == 2) {
        base_color = u_custom_color;
    } else {
        base_color = u_mesh_color;
    }
    vec3 jittered_rgb = clamp(base_color.rgb + j_color * u_color_variation, 0.0, 1.0);
    v_color = vec4(jittered_rgb, base_color.a);
}
"""

    _FS = """\
#version 330 core
flat in vec4 v_color;
in vec3 v_world_pos;
in vec3 v_corner_normal;
in vec3 v_smooth_normal;
flat in int v_shading_mode;

uniform vec3 u_camera_pos;

out vec4 frag;

void main() {
    // Headlight lambert (two-sided) + 0.25 ambient floor.
    //   0 = DEFAULT — corner normal (honours per-polygon smooth/flat).
    //   1 = FLAT    — derivative-based face normal.
    //   2 = SMOOTH  — vertex-averaged smooth normal.
    vec3 N;
    if (v_shading_mode == 1) {
        N = normalize(cross(dFdx(v_world_pos), dFdy(v_world_pos)));
    } else if (v_shading_mode == 2) {
        N = normalize(v_smooth_normal);
    } else {
        N = normalize(v_corner_normal);
    }
    vec3 V = normalize(u_camera_pos - v_world_pos);
    float NdotV = abs(dot(N, V)); // two-sided

    float ambient = 0.25;
    float lit = ambient + (1.0 - ambient) * NdotV;
    frag = vec4(v_color.rgb * lit, v_color.a);
}
"""

    _COMPUTE_SRC = """\
#version 430 core
layout(local_size_x = 64) in;

layout(std430, binding = 0) readonly buffer ParticleIds { int particle_ids[]; };
layout(std430, binding = 1) writeonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 2) writeonly buffer LayerOffsets { uint layer_offsets[]; };
struct DrawElementsIndirectCommand {
    uint count;
    uint instance_count;
    uint first_index;
    int  base_vertex;
    uint base_instance;
};
layout(std430, binding = 3) writeonly buffer IndirectCommands {
    DrawElementsIndirectCommand cmds[];
};
layout(std430, binding = 4) readonly buffer EmitterIndices { int emitter_indices[]; };

uniform uint  u_particle_count;
uniform uint  u_num_layers;
uniform float u_cumulative[16];
uniform uint  u_index_counts[16];
uniform uint  u_emitter_mask;  // bit i = include emitter i

shared uint s_counts[16];
shared uint s_offsets[16];
shared uint s_running[16];

uint pcg_hash(uint x) {
    uint state = x * 747796405u + 2891336453u;
    uint word  = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

uint classify(uint pid) {
    float r = float(pcg_hash(pid)) * (1.0 / 4294967295.0);
    for (uint j = 0u; j < u_num_layers; ++j) {
        if (r < u_cumulative[j]) return j;
    }
    return u_num_layers - 1u;
}

bool emitter_allowed(uint i) {
    int ei = emitter_indices[i];
    if (ei < 0 || ei >= 32) return false;
    return ((u_emitter_mask >> uint(ei)) & 1u) != 0u;
}

void main() {
    uint lid = gl_LocalInvocationID.x;

    if (lid < 16u) { s_counts[lid] = 0u; s_running[lid] = 0u; }
    barrier();

    // Phase 1: classify + count
    for (uint i = lid; i < u_particle_count; i += gl_WorkGroupSize.x) {
        if (!emitter_allowed(i)) continue;
        uint layer = classify(uint(particle_ids[i]));
        atomicAdd(s_counts[layer], 1u);
    }
    barrier();

    // Phase 2: prefix-sum + write public outputs (single thread)
    if (lid == 0u) {
        uint sum = 0u;
        for (uint i = 0u; i < u_num_layers; ++i) {
            s_offsets[i] = sum;
            layer_offsets[i] = sum;
            cmds[i].count = u_index_counts[i];
            cmds[i].instance_count = s_counts[i];
            cmds[i].first_index = 0u;
            cmds[i].base_vertex = 0;
            cmds[i].base_instance = 0u;
            sum += s_counts[i];
        }
        layer_offsets[u_num_layers] = sum;
    }
    barrier();

    // Phase 3: scatter
    for (uint i = lid; i < u_particle_count; i += gl_WorkGroupSize.x) {
        if (!emitter_allowed(i)) continue;
        uint layer = classify(uint(particle_ids[i]));
        uint slot = atomicAdd(s_running[layer], 1u);
        binned[s_offsets[layer] + slot] = i;
    }
}
"""

    def __init__(self, bridge):
        super().__init__(bridge)
        # Per-layer mesh resources, keyed by mesh_revision_key.
        self._mesh_slots: dict[tuple, _LayerMesh] = {}
        # Zero-copy imports (refreshed as a group when any handle changes).
        self._pos_vbo: int | None = None
        self._color_vbo: int | None = None
        self._color_handle: object | None = None
        self._radius_vbo: int | None = None
        self._radius_handle: object | None = None
        self._scale_vbo: int | None = None
        self._scale_handle: object | None = None
        self._rot_vbo: int | None = None
        self._rot_handle: object | None = None
        self._pid_vbo: int | None = None
        self._pid_handle: object | None = None
        self._emit_idx_vbo: int | None = None
        self._emit_idx_handle: object | None = None
        # Compute classifier resources.
        self._compute_program: int | None = None
        self._compute_uniforms: dict[str, int] = {}
        self._binned_ssbo: int | None = None
        self._binned_capacity: int = 0
        self._layer_offsets_ssbo: int | None = None
        self._indirect_cmd_buffer: int | None = None

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def _free_mesh_slots(self) -> None:
        if not _GL_OK:
            self._mesh_slots = {}
            return
        for slot in self._mesh_slots.values():
            try:
                glDeleteVertexArrays(1, [slot.vao])
            except Exception:
                pass
            try:
                glDeleteBuffers(1, [slot.mesh_vbo])
            except Exception:
                pass
            try:
                glDeleteBuffers(1, [slot.mesh_ibo])
            except Exception:
                pass
        self._mesh_slots = {}

    def _free_imported(self) -> None:
        for vbo, mem, keep_handle in self._buffers:
            try:
                self._bridge.free_buffer(vbo, mem, keep_handle)
            except Exception:
                pass
        self._buffers = []
        self._pos_vbo = None
        self._color_vbo = None
        self._color_handle = None
        self._radius_vbo = None
        self._radius_handle = None
        self._scale_vbo = None
        self._scale_handle = None
        self._rot_vbo = None
        self._rot_handle = None
        self._pid_vbo = None
        self._pid_handle = None
        self._emit_idx_vbo = None
        self._emit_idx_handle = None
        self._handle = None
        self._imported = False

    def _free_compute_resources(self) -> None:
        if not _GL_OK:
            self._compute_program = None
            self._compute_uniforms = {}
            self._binned_ssbo = None
            self._binned_capacity = 0
            self._layer_offsets_ssbo = None
            self._indirect_cmd_buffer = None
            return
        for buf in (self._binned_ssbo, self._layer_offsets_ssbo, self._indirect_cmd_buffer):
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
        self._compute_program = None
        self._compute_uniforms = {}
        self._binned_ssbo = None
        self._binned_capacity = 0
        self._layer_offsets_ssbo = None
        self._indirect_cmd_buffer = None

    def _free_resources(self) -> None:
        self._free_mesh_slots()
        self._free_imported()
        self._free_compute_resources()
        super()._free_resources()

    # ------------------------------------------------------------------
    # Lazy resource setup
    # ------------------------------------------------------------------

    def _ensure_program(self) -> bool:
        if self._program is not None:
            return True
        program = self._bridge.compile_program(self._VS, self._FS)
        if program is None:
            return False
        self._program = program
        self._uniforms = {
            "u_mvp": glGetUniformLocation(program, "u_mvp"),
            "u_mesh_color": glGetUniformLocation(program, "u_mesh_color"),
            "u_custom_color": glGetUniformLocation(program, "u_custom_color"),
            "u_mesh_scale": glGetUniformLocation(program, "u_mesh_scale"),
            "u_custom_scale": glGetUniformLocation(program, "u_custom_scale"),
            "u_mesh_rotation": glGetUniformLocation(program, "u_mesh_rotation"),
            "u_custom_rotation": glGetUniformLocation(program, "u_custom_rotation"),
            "u_layer_idx": glGetUniformLocation(program, "u_layer_idx"),
            "u_scale_source_id": glGetUniformLocation(program, "u_scale_source_id"),
            "u_color_source_id": glGetUniformLocation(program, "u_color_source_id"),
            "u_rotation_source_id": glGetUniformLocation(program, "u_rotation_source_id"),
            "u_scale_variation": glGetUniformLocation(program, "u_scale_variation"),
            "u_color_variation": glGetUniformLocation(program, "u_color_variation"),
            "u_rotation_variation": glGetUniformLocation(program, "u_rotation_variation"),
            "u_scale_variation_per_axis": glGetUniformLocation(
                program, "u_scale_variation_per_axis"
            ),
            "u_color_variation_per_axis": glGetUniformLocation(
                program, "u_color_variation_per_axis"
            ),
            "u_rotation_variation_per_axis": glGetUniformLocation(
                program, "u_rotation_variation_per_axis"
            ),
            "u_shading_mode": glGetUniformLocation(program, "u_shading_mode"),
            "u_camera_pos": glGetUniformLocation(program, "u_camera_pos"),
        }
        return True

    def _ensure_compute_program(self) -> bool:
        if self._compute_program is not None:
            return True
        try:
            sh = glCreateShader(GL_COMPUTE_SHADER)
            glShaderSource(sh, self._COMPUTE_SRC)
            glCompileShader(sh)
            if not glGetShaderiv(sh, GL_COMPILE_STATUS):
                glDeleteShader(sh)
                return False
            prog = glCreateProgram()
            glAttachShader(prog, sh)
            glLinkProgram(prog)
            glDeleteShader(sh)
            if not glGetProgramiv(prog, GL_LINK_STATUS):
                glDeleteProgram(prog)
                return False
            self._compute_program = prog
            self._compute_uniforms = {
                "u_particle_count": glGetUniformLocation(prog, "u_particle_count"),
                "u_num_layers": glGetUniformLocation(prog, "u_num_layers"),
                "u_cumulative": glGetUniformLocation(prog, "u_cumulative"),
                "u_index_counts": glGetUniformLocation(prog, "u_index_counts"),
                "u_emitter_mask": glGetUniformLocation(prog, "u_emitter_mask"),
            }
            return True
        except Exception:
            return False

    def _ensure_indirect_buffers(self, particle_count: int) -> bool:
        """Allocate / grow the binned-indices, layer-offsets and indirect-cmd
        buffers. Binned-indices grows with particle_count; the others are fixed."""
        try:
            if self._layer_offsets_ssbo is None:
                gen = glGenBuffers(1)
                self._layer_offsets_ssbo = gen[0] if isinstance(gen, (list, tuple)) else gen
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._layer_offsets_ssbo)
                glBufferData(
                    GL_SHADER_STORAGE_BUFFER, 4 * (_MAX_LAYERS + 1), None, GL_DYNAMIC_DRAW
                )
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

            if self._indirect_cmd_buffer is None:
                gen = glGenBuffers(1)
                self._indirect_cmd_buffer = gen[0] if isinstance(gen, (list, tuple)) else gen
                glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd_buffer)
                glBufferData(
                    GL_DRAW_INDIRECT_BUFFER,
                    _INDIRECT_CMD_BYTES * _MAX_LAYERS,
                    None,
                    GL_DYNAMIC_DRAW,
                )
                glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)

            if self._binned_ssbo is None or particle_count > self._binned_capacity:
                if self._binned_ssbo is not None:
                    glDeleteBuffers(1, [self._binned_ssbo])
                gen = glGenBuffers(1)
                self._binned_ssbo = gen[0] if isinstance(gen, (list, tuple)) else gen
                # Round capacity up to next 1024 to reduce realloc churn.
                cap = max(1024, ((particle_count + 1023) // 1024) * 1024)
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._binned_ssbo)
                glBufferData(GL_SHADER_STORAGE_BUFFER, 4 * cap, None, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
                self._binned_capacity = cap
            return True
        except Exception:
            return False

    def _ensure_layer_mesh(self, layer) -> _LayerMesh | None:
        """Return the cached mesh slot for *layer*, building it on miss."""
        slot = self._mesh_slots.get(layer.mesh_revision_key)
        if slot is not None:
            return slot

        pos = np.ascontiguousarray(layer.mesh_vertices, dtype=np.float32).reshape(-1, 3)
        inds = np.ascontiguousarray(layer.mesh_indices, dtype=np.uint32)
        if pos.size == 0 or inds.size == 0:
            return None
        cn = np.ascontiguousarray(layer.mesh_corner_normals, dtype=np.float32).reshape(-1, 3)
        sn = np.ascontiguousarray(layer.mesh_smooth_normals, dtype=np.float32).reshape(-1, 3)
        interleaved = np.empty((pos.shape[0], 9), dtype=np.float32)
        interleaved[:, 0:3] = pos
        interleaved[:, 3:6] = cn
        interleaved[:, 6:9] = sn
        verts = interleaved.ravel()

        try:
            vbo_gen = glGenBuffers(1)
            mesh_vbo = vbo_gen[0] if isinstance(vbo_gen, (list, tuple)) else vbo_gen
            glBindBuffer(GL_ARRAY_BUFFER, mesh_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)

            ibo_gen = glGenBuffers(1)
            mesh_ibo = ibo_gen[0] if isinstance(ibo_gen, (list, tuple)) else ibo_gen
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, mesh_ibo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)

            vao_gen = glGenVertexArrays(1)
            vao = vao_gen[0] if isinstance(vao_gen, (list, tuple)) else vao_gen
            glBindVertexArray(vao)
            glBindBuffer(GL_ARRAY_BUFFER, mesh_vbo)
            # Interleaved layout: pos (loc 0, offset 0), corner_normal (loc 1,
            # offset 12), smooth_normal (loc 2, offset 24). Stride 36.
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 36, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 36, ctypes.c_void_p(12))
            glEnableVertexAttribArray(1)
            glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 36, ctypes.c_void_p(24))
            glEnableVertexAttribArray(2)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, mesh_ibo)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        except Exception:
            return None

        slot = _LayerMesh(
            mesh_vbo=mesh_vbo,
            mesh_ibo=mesh_ibo,
            vao=vao,
            revision_key=layer.mesh_revision_key,
            index_count=int(layer.index_count),
        )
        self._mesh_slots[layer.mesh_revision_key] = slot
        return slot

    def _ensure_import(self, pos, color, radius, scale, rotation, pid, emit_idx) -> bool:
        """Refresh zero-copy imports as a group when any handle changes."""
        pos_id = buf_identity(pos)
        color_id = buf_identity(color)
        radius_id = buf_identity(radius)
        scale_id = buf_identity(scale)
        rot_id = buf_identity(rotation)
        pid_id = buf_identity(pid)
        emit_id = buf_identity(emit_idx)
        if (
            self._imported
            and self._handle == pos_id
            and self._color_handle == color_id
            and self._radius_handle == radius_id
            and self._scale_handle == scale_id
            and self._rot_handle == rot_id
            and self._pid_handle == pid_id
            and self._emit_idx_handle == emit_id
        ):
            return True

        if self._imported:
            self._free_imported()

        self._pos_vbo = self._import(pos)
        if self._pos_vbo is None:
            self._free_imported()
            return False
        self._pid_vbo = self._import(pid)
        if self._pid_vbo is None:
            self._free_imported()
            return False
        self._emit_idx_vbo = self._import(emit_idx)
        if self._emit_idx_vbo is None:
            self._free_imported()
            return False
        self._color_vbo = self._import(color)
        self._radius_vbo = self._import(radius)
        self._scale_vbo = self._import(scale)
        self._rot_vbo = self._import(rotation)

        self._handle = pos_id
        self._color_handle = color_id
        self._radius_handle = radius_id
        self._scale_handle = scale_id
        self._rot_handle = rot_id
        self._pid_handle = pid_id
        self._emit_idx_handle = emit_id
        self._imported = True
        return True

    # ------------------------------------------------------------------
    # Per-frame draw
    # ------------------------------------------------------------------

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        if params.particle_count <= 0:
            return False

        # Filter to enabled layers with a usable index count.
        enabled = [layer for layer in params.layers if layer.enabled and layer.index_count > 0]
        if not enabled:
            return True
        if len(enabled) > _MAX_LAYERS:
            enabled = enabled[:_MAX_LAYERS]

        prep = self._prepare_draw(context, pipeline, params)
        if prep is None:
            return False
        mvp, _view = prep

        # Position + particle-id are required for the classifier; fail fast if
        # the particle id buffer isn't exposed for this pipeline.
        pos = self.fetch_gpu_buffer(pipeline, "position")
        if pos is None or not pos.valid:
            return False
        pid = self.fetch_gpu_buffer(pipeline, "id")
        if pid is None or not pid.valid:
            return False

        emitter_mask = int(getattr(params, "emitter_filter_mask", 0)) & 0xFFFFFFFF
        if emitter_mask == 0:
            return True
        emit_idx = self.fetch_gpu_buffer(pipeline, "emitter_index")
        if emit_idx is None or not emit_idx.valid:
            return True

        # Take the union of all layers' source needs so we only fetch / import
        # the optional buffers when at least one layer wants them.
        need_color = any(layer.color_source_id == 1 for layer in enabled)
        need_radius = any(layer.scale_source_id == 1 for layer in enabled)
        need_scale_buf = any(layer.scale_source_id == 2 for layer in enabled)
        need_rotation = any(layer.rotation_source_id == 1 for layer in enabled)

        color = self.fetch_gpu_buffer(pipeline, "color") if need_color else None
        radius = self.fetch_gpu_buffer(pipeline, "radius") if need_radius else None
        scale_buf = self.fetch_gpu_buffer(pipeline, "scale") if need_scale_buf else None
        rotation = self.fetch_gpu_buffer(pipeline, "rotation") if need_rotation else None

        if not self._ensure_program():
            return False
        if not self._ensure_compute_program():
            return False
        if not self._ensure_indirect_buffers(int(params.particle_count)):
            return False
        if not self._ensure_import(pos, color, radius, scale_buf, rotation, pid, emit_idx):
            return False

        # Build per-layer mesh slots. Skip layers whose mesh fails.
        slots: list[_LayerMesh] = []
        keep: list = []
        for layer in enabled:
            slot = self._ensure_layer_mesh(layer)
            if slot is None:
                continue
            slots.append(slot)
            keep.append(layer)
        enabled = keep
        if not enabled:
            return True

        # Cumulative spawn weights normalised to [0, 1).
        weights = [max(0.0, layer.spawn_chance) for layer in enabled]
        total = sum(weights) or 1.0
        cumulative = [0.0] * _MAX_LAYERS
        running = 0.0
        for i, w in enumerate(weights):
            running += w / total
            cumulative[i] = running
        cumulative[len(enabled) - 1] = 1.0  # epsilon-safe upper bound

        index_counts = [0] * _MAX_LAYERS
        for i, slot in enumerate(slots):
            index_counts[i] = slot.index_count

        # Dispatch the classifier compute shader.
        glUseProgram(self._compute_program)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, self._pid_vbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, self._binned_ssbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, self._layer_offsets_ssbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._indirect_cmd_buffer)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, self._emit_idx_vbo)
        glUniform1ui(self._compute_uniforms["u_particle_count"], int(params.particle_count))
        glUniform1ui(self._compute_uniforms["u_num_layers"], len(enabled))
        if self._compute_uniforms["u_emitter_mask"] >= 0:
            glUniform1ui(self._compute_uniforms["u_emitter_mask"], emitter_mask)
        if self._compute_uniforms["u_cumulative"] >= 0:
            glUniform1fv(self._compute_uniforms["u_cumulative"], _MAX_LAYERS, cumulative)
        if self._compute_uniforms["u_index_counts"] >= 0:
            glUniform1uiv(self._compute_uniforms["u_index_counts"], _MAX_LAYERS, index_counts)
        glDispatchCompute(1, 1, 1)
        glMemoryBarrier(GL_COMMAND_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT)

        # Camera position in world space — used by the FS for headlight shading.
        try:
            cam_pos = context.region_data.view_matrix.inverted().translation
            cam_x, cam_y, cam_z = float(cam_pos.x), float(cam_pos.y), float(cam_pos.z)
        except Exception:
            cam_x = cam_y = cam_z = 0.0

        # Per-layer draw via indirect.
        saved = self._bridge.save_state_for_particle_draw()
        try:
            glUseProgram(self._program)
            glUniformMatrix4fv(self._uniforms["u_mvp"], 1, True, mvp)
            glUniform3f(self._uniforms["u_camera_pos"], cam_x, cam_y, cam_z)

            # Common SSBO bindings (constant across layers).
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._pos_vbo)
            glBindBufferBase(
                GL_SHADER_STORAGE_BUFFER, 6, self._radius_vbo if self._radius_vbo else 0
            )
            glBindBufferBase(
                GL_SHADER_STORAGE_BUFFER, 7, self._color_vbo if self._color_vbo else 0
            )
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 9, self._pid_vbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 10, self._rot_vbo if self._rot_vbo else 0)
            glBindBufferBase(
                GL_SHADER_STORAGE_BUFFER, 11, self._scale_vbo if self._scale_vbo else 0
            )
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 12, self._binned_ssbo)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 13, self._layer_offsets_ssbo)

            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd_buffer)
            for layer_idx, (layer, slot) in enumerate(zip(enabled, slots)):
                # Resolve runtime sources — missing optional buffers fall back to mesh.
                eff_scale = layer.scale_source_id
                if eff_scale == 1 and self._radius_vbo is None:
                    eff_scale = 0
                elif eff_scale == 2 and self._scale_vbo is None:
                    eff_scale = 0
                eff_color = layer.color_source_id
                if eff_color == 1 and self._color_vbo is None:
                    eff_color = 0
                eff_rot = layer.rotation_source_id
                if eff_rot == 1 and self._rot_vbo is None:
                    eff_rot = 0

                glUniform1i(self._uniforms["u_layer_idx"], layer_idx)
                glUniform4f(self._uniforms["u_mesh_color"], *layer.mesh_color)
                glUniform4f(self._uniforms["u_custom_color"], *layer.custom_color)
                glUniform3f(self._uniforms["u_mesh_scale"], *layer.mesh_scale)
                glUniform3f(self._uniforms["u_custom_scale"], *layer.custom_scale)
                glUniformMatrix3fv(self._uniforms["u_mesh_rotation"], 1, True, layer.mesh_rotation)
                glUniform3f(self._uniforms["u_custom_rotation"], *layer.custom_rotation)
                glUniform1i(self._uniforms["u_scale_source_id"], eff_scale)
                glUniform1i(self._uniforms["u_color_source_id"], eff_color)
                glUniform1i(self._uniforms["u_rotation_source_id"], eff_rot)
                glUniform3f(self._uniforms["u_scale_variation"], *layer.scale_variation)
                glUniform3f(self._uniforms["u_color_variation"], *layer.color_variation)
                glUniform3f(self._uniforms["u_rotation_variation"], *layer.rotation_variation)
                glUniform1i(
                    self._uniforms["u_scale_variation_per_axis"],
                    1 if layer.scale_variation_per_axis else 0,
                )
                glUniform1i(
                    self._uniforms["u_color_variation_per_axis"],
                    1 if layer.color_variation_per_axis else 0,
                )
                glUniform1i(
                    self._uniforms["u_rotation_variation_per_axis"],
                    1 if layer.rotation_variation_per_axis else 0,
                )
                glUniform1i(self._uniforms["u_shading_mode"], int(layer.shading_mode_id))

                glBindVertexArray(slot.vao)
                glDrawElementsIndirect(
                    GL_TRIANGLES,
                    GL_UNSIGNED_INT,
                    ctypes.c_void_p(layer_idx * _INDIRECT_CMD_BYTES),
                )
            glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        except Exception:
            self._free_resources()
            return False
        finally:
            glBindVertexArray(0)
            self._bridge.restore_state(saved)

        return True
