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
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""OpenGL zero-copy NX_TRAIL backend.

The 16-byte trail-buffer header is folded into each SSBO's std430 struct
so we can ``glBindBufferBase`` at offset 0
"""

from __future__ import annotations

import ctypes

import numpy as np

from ..core.buffer_state import BufferExport, buf_identity
from ..particles.opengl_base import OpenGLModeBase

try:
    from OpenGL.GL import (
        GL_ALL_BARRIER_BITS,
        GL_BLEND,
        GL_COMMAND_BARRIER_BIT,
        GL_COMPILE_STATUS,
        GL_COMPUTE_SHADER,
        GL_DRAW_INDIRECT_BUFFER,
        GL_DYNAMIC_DRAW,
        GL_FRAGMENT_SHADER,
        GL_FUNC_ADD,
        GL_LINES,
        GL_LINK_STATUS,
        GL_ONE,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_SHADER_STORAGE_BARRIER_BIT,
        GL_SHADER_STORAGE_BUFFER,
        GL_SRC_ALPHA,
        GL_TRIANGLES,
        GL_VERTEX_SHADER,
        GL_ZERO,
        glAttachShader,
        glBindBuffer,
        glBindBufferBase,
        glBindVertexArray,
        glBlendEquationSeparate,
        glBlendFuncSeparate,
        glBufferData,
        glBufferSubData,
        glCompileShader,
        glCreateProgram,
        glCreateShader,
        glDeleteBuffers,
        glDeleteProgram,
        glDeleteShader,
        glDispatchCompute,
        glDrawArraysIndirect,
        glEnable,
        glGenBuffers,
        glGenVertexArrays,
        glGetProgramInfoLog,
        glGetProgramiv,
        glGetShaderInfoLog,
        glGetShaderiv,
        glGetUniformLocation,
        glLinkProgram,
        glMemoryBarrier,
        glShaderSource,
        glUniform1i,
        glUniform1ui,
        glUniform4f,
        glUniformMatrix4fv,
        glUseProgram,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False


# ---------------------------------------------------------------------------
# Trail constants
# ---------------------------------------------------------------------------

_TRAIL_SEGMENT_HEAD_MASK = 0x3FFFFFFF
_TRAIL_TUBE_SIDES = 8
_LINE_VERTS_PER_EDGE = 2
_TUBE_TRI_VERTS_PER_SIDE = 6
_TUBE_VERTS_PER_EDGE = _TRAIL_TUBE_SIDES * _TUBE_TRI_VERTS_PER_SIDE
_TUBE_VERTEX_HARD_CAP = (2**31 - 1) // 2
_PALETTE_FLOATS_PER_ENTRY = 12

_TRAIL_PASS_LINE = 0
_TRAIL_PASS_TUBE = 1

_RADIUS_THICKNESS_MODES = frozenset({"RADIUS_CURRENT"})

# Must match nexus_stage_trail_palette() in viewport/bridges/native.py.
_THICKNESS_MODE_MAP = {
    "NONE": 0,
    "VALUE": 1,
    "SPLINE": 2,
    "RADIUS_CURRENT": 3,
    "RADIUS_VARIABLE": 4,
}
_COLOR_MODE_MAP = {"STANDARD": 0, "GRADIENT": 1}
_TRAIL_COLOR_MODE_MAP = {"PARTICLE": 0, "PER_VERTEX": 1}


# ---------------------------------------------------------------------------
# GLSL shaders
# ---------------------------------------------------------------------------

_COMPUTE_SRC = """\
#version 430 core

layout(local_size_x = 64) in;

struct ParticleTrailPoint {
    float px;
    float py;
    float pz;
    uint  packedFlags;
};

struct ParticleTrailSegment {
    int particleIndex;
    int numPoints;
    int emitterIndex;
    int meta;
};

struct EmitterTrailPalette {
    vec4 color;
    vec4 params0;   // x=enabled, y=color_mode, z=trail_color_mode, w=no_data
    vec4 params1;   // x=thickness_mode, y=thickness_value, z=variation, w=spline_max
};

struct DrawArraysIndirectCommand {
    uint count;
    uint instanceCount;
    uint first;
    uint baseInstance;
};

layout(std430, binding = 0) readonly buffer HistoryBuffer {
    int h_header[4];
    ParticleTrailPoint history[];
};
layout(std430, binding = 1) readonly buffer TopologyBuffer {
    int t_capacity;
    int t_count;
    int t_topologyMode;
    int t_reserved;
    ParticleTrailSegment segments[];
};
layout(std430, binding = 3) readonly buffer ThicknessBuffer {
    int th_header[4];
    float thick[];
};
layout(std430, binding = 4) readonly buffer PaletteBuffer {
    EmitterTrailPalette palettes[];
};
layout(std430, binding = 5) buffer HeadSlotsBuffer {
    int headSlots[];
};
layout(std430, binding = 6) readonly buffer RadiusBuffer {
    float radius[];
};
layout(std430, binding = 7) buffer VisibleSegmentsBuffer {
    int visibleSegments[];
};
layout(std430, binding = 8) buffer DrawCommandBuffer {
    DrawArraysIndirectCommand drawArgs;
};

uniform int  u_slotsPerParticle;
uniform int  u_segmentCount;
uniform uint u_vertexCountPerInstance;
uniform int  u_paletteCount;
uniform int  u_drawPass;
uniform int  u_hasThicknessBuffer;
uniform int  u_hasRadiusBuffer;
uniform int  u_radiusCount;
uniform int  u_historyCapacity;
uniform int  u_topologyCapacity;
uniform int  u_thicknessCapacity;

const uint ALIVE_BIT             = 1u;
const int  SAMPLE_INDEX_SHIFT    = 8;
const int  TRAIL_SEGMENT_HEAD_MASK = 0x3FFFFFFF;
const int  TRAIL_SEGMENT_KIND_LINK = 0x40000000;
const int  TRAIL_SEGMENT_TO_LIVE   = 0xFFFF;
const int  TRAIL_PASS_LINE       = 0;
const int  TRAIL_PASS_TUBE       = 1;

bool  pal_enabled(EmitterTrailPalette p)    { return p.params0.x >= 0.5; }
bool  pal_no_data(EmitterTrailPalette p)    { return p.params0.w >= 0.5; }
int   pal_thickness_mode(EmitterTrailPalette p) {
    return pal_no_data(p) ? 0 : int(p.params1.x + 0.5);
}
float pal_thickness_value(EmitterTrailPalette p) { return p.params1.y; }

int slot_for(int headSlot, int pt, int slots) {
    return (headSlot - pt + slots) % slots;
}

bool segment_has_stored_thickness(int base, int headSlot, int pointCount) {
    bool sawAlive = false;
    int count = min(pointCount, u_slotsPerParticle);
    for (int pt = 0; pt < count; ++pt) {
        int idx = base + slot_for(headSlot, pt, u_slotsPerParticle);
        if (idx < 0 || idx >= u_historyCapacity || idx >= u_thicknessCapacity) return false;
        if ((history[idx].packedFlags & ALIVE_BIT) == 0u) continue;
        sawAlive = true;
        if (thick[idx] < 0.0) return false;
    }
    return sawAlive;
}

bool segment_source_enabled(ParticleTrailSegment seg) {
    if (u_paletteCount <= 0) return true;
    int src = seg.emitterIndex & 0xFFFF;
    if (src < 0 || src >= u_paletteCount) return false;
    return pal_enabled(palettes[src]);
}

bool segment_has_stored_thickness_link(int fromIdx, int toIdx) {
    if (fromIdx < 0 || fromIdx >= u_historyCapacity ||
        fromIdx >= u_thicknessCapacity) return false;
    if (toIdx < 0 || toIdx >= u_historyCapacity || toIdx >= u_thicknessCapacity) return false;
    if ((history[fromIdx].packedFlags & ALIVE_BIT) == 0u) return false;
    if ((history[toIdx].packedFlags & ALIVE_BIT) == 0u) return false;
    return thick[fromIdx] >= 0.0 && thick[toIdx] >= 0.0;
}

bool segment_resolves_to_tube_link(ParticleTrailSegment seg, int fromIdx, int toIdx,
                                   int fromRow, int toRow) {
    if (u_paletteCount <= 0) return false;
    int fromSrc = seg.emitterIndex & 0xFFFF;
    int toSrc = (seg.emitterIndex >> 16) & 0xFFFF;
    if (fromSrc < 0 || fromSrc >= u_paletteCount) return false;
    EmitterTrailPalette pal = palettes[fromSrc];
    if (!pal_enabled(pal)) return false;
    int mode = pal_thickness_mode(pal);
    if (mode == 0) return false;
    if (mode == 1) {
        if (u_hasThicknessBuffer != 0 &&
            segment_has_stored_thickness_link(fromIdx, toIdx)) {
            return true;
        }
        return pal_thickness_value(pal) > 0.0;
    }
    if (mode == 2 || mode == 4) {
        return u_hasThicknessBuffer != 0 &&
               segment_has_stored_thickness_link(fromIdx, toIdx);
    }
    if (mode == 3) {
        if (u_hasRadiusBuffer == 0) return false;
        int hpc = (u_slotsPerParticle > 0)
            ? u_historyCapacity / (u_paletteCount * u_slotsPerParticle)
            : 0;
        int fromParticle = fromRow - fromSrc * hpc;
        int toParticle = toRow - toSrc * hpc;
        if (fromParticle < 0 || fromParticle >= u_radiusCount) return false;
        if (toParticle < 0 || toParticle >= u_radiusCount) return false;
        return radius[fromParticle] > 0.0 && radius[toParticle] > 0.0;
    }
    return false;
}

bool segment_resolves_to_tube_link_live(ParticleTrailSegment seg, int fromIdx, int fromRow) {
    if (u_paletteCount <= 0) return false;
    int fromSrc = seg.emitterIndex & 0xFFFF;
    if (fromSrc < 0 || fromSrc >= u_paletteCount) return false;
    EmitterTrailPalette pal = palettes[fromSrc];
    if (!pal_enabled(pal)) return false;
    int mode = pal_thickness_mode(pal);
    if (mode == 0) return false;
    bool fromStored = u_hasThicknessBuffer != 0 &&
                      fromIdx >= 0 && fromIdx < u_historyCapacity &&
                      fromIdx < u_thicknessCapacity &&
                      (history[fromIdx].packedFlags & ALIVE_BIT) != 0u &&
                      thick[fromIdx] >= 0.0;
    if (mode == 1) {
        return fromStored || pal_thickness_value(pal) > 0.0;
    }
    if (mode == 2 || mode == 4) {
        return fromStored;
    }
    if (mode == 3) {
        if (u_hasRadiusBuffer == 0) return false;
        int hpc = (u_slotsPerParticle > 0)
            ? u_historyCapacity / (u_paletteCount * u_slotsPerParticle)
            : 0;
        int fromParticle = fromRow - fromSrc * hpc;
        if (fromParticle < 0 || fromParticle >= u_radiusCount) return false;
        return radius[fromParticle] > 0.0;
    }
    return false;
}

bool segment_resolves_to_tube(ParticleTrailSegment seg, int base, int headSlot, int pointCount) {
    if (u_paletteCount <= 0) return false;
    if (seg.emitterIndex < 0 || seg.emitterIndex >= u_paletteCount) return false;
    EmitterTrailPalette pal = palettes[seg.emitterIndex];
    if (!pal_enabled(pal)) return false;
    int mode = pal_thickness_mode(pal);
    if (mode == 0) return false;
    if (mode == 1) {
        if (u_hasThicknessBuffer != 0 &&
            segment_has_stored_thickness(base, headSlot, pointCount)) {
            return true;
        }
        return pal_thickness_value(pal) > 0.0;
    }
    if (mode == 2 || mode == 4) {
        return u_hasThicknessBuffer != 0 &&
               segment_has_stored_thickness(base, headSlot, pointCount);
    }
    if (mode == 3) {
        return u_hasRadiusBuffer != 0 &&
               seg.particleIndex >= 0 &&
               seg.particleIndex < u_radiusCount &&
               radius[seg.particleIndex] > 0.0;
    }
    return false;
}

void main() {
    uint gid = gl_GlobalInvocationID.x;

    // Thread 0 seeds the indirect-draw vertex count once per dispatch.
    if (gid == 0u) {
        drawArgs.count        = u_vertexCountPerInstance;
        drawArgs.first        = 0u;
        drawArgs.baseInstance = 0u;
    }

    if (u_slotsPerParticle <= 0) return;
    if (int(gid) >= u_segmentCount || int(gid) >= u_topologyCapacity) return;

    // Clamp against the live topology count so we skip empty/stale slots
    // then derive pointCount from the alive history slots
    int liveCount = min(max(t_count, 0), min(u_segmentCount, u_topologyCapacity));
    if (int(gid) >= liveCount) return;

    ParticleTrailSegment seg = segments[gid];
    if (!segment_source_enabled(seg)) return;

    bool isLink = (seg.meta & TRAIL_SEGMENT_KIND_LINK) != 0;
    if (isLink) {
        int fromRow = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
        int toSrc = (seg.emitterIndex >> 16) & 0xFFFF;
        bool toLive = (toSrc == TRAIL_SEGMENT_TO_LIVE);
        int toRow = seg.numPoints;
        if (fromRow < 0 || (!toLive && toRow < 0)) return;

        int fromBase = fromRow * u_slotsPerParticle;
        if (fromBase < 0 || fromBase + u_slotsPerParticle > u_historyCapacity) return;

        int fromHead = -1;
        int fromBest = -1;
        for (int s = 0; s < u_slotsPerParticle; ++s) {
            uint flags = history[fromBase + s].packedFlags;
            if ((flags & ALIVE_BIT) == 0u) continue;
            int sampleIndex = int(flags >> uint(SAMPLE_INDEX_SHIFT));
            if (sampleIndex > fromBest) {
                fromBest = sampleIndex;
                fromHead = s;
            }
        }
        if (fromHead < 0) return;

        int toHead = 0;
        bool wantsTube = false;
        int fromIdx = fromBase + fromHead;
        if (!toLive) {
            int toBase = toRow * u_slotsPerParticle;
            if (toBase < 0 || toBase + u_slotsPerParticle > u_historyCapacity) return;

            int toBest = -1;
            toHead = -1;
            for (int s = 0; s < u_slotsPerParticle; ++s) {
                uint flags = history[toBase + s].packedFlags;
                if ((flags & ALIVE_BIT) == 0u) continue;
                int sampleIndex = int(flags >> uint(SAMPLE_INDEX_SHIFT));
                if (sampleIndex > toBest) {
                    toBest = sampleIndex;
                    toHead = s;
                }
            }
            if (toHead < 0) return;

            int toIdx = toBase + toHead;
            wantsTube = segment_resolves_to_tube_link(seg, fromIdx, toIdx, fromRow, toRow);
        } else {
            wantsTube = segment_resolves_to_tube_link_live(seg, fromIdx, fromRow);
        }

        bool passMatch = (u_drawPass == TRAIL_PASS_TUBE) ? wantsTube : !wantsTube;
        if (!passMatch) return;

        uint outIndex = atomicAdd(drawArgs.instanceCount, 1u);
        if (outIndex >= uint(u_segmentCount)) return;
        visibleSegments[outIndex] = int(gid);
        headSlots[outIndex] = (u_slotsPerParticle > 0x10000)
            ? -1
            : (((fromHead & 0xFFFF) << 16) | (toHead & 0xFFFF));
        return;
    }

    if (seg.numPoints <= 1) return;

    int slotIndex = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
    int base = slotIndex * u_slotsPerParticle;
    if (slotIndex < 0 || base < 0 ||
        base + u_slotsPerParticle > u_historyCapacity) return;

    int headSlot = -1;
    int bestSample = -1;
    int aliveCount = 0;
    for (int s = 0; s < u_slotsPerParticle; ++s) {
        uint flags = history[base + s].packedFlags;
        if ((flags & ALIVE_BIT) == 0u) continue;
        aliveCount++;
        int si = int(flags >> uint(SAMPLE_INDEX_SHIFT));
        if (si > bestSample) {
            bestSample = si;
            headSlot   = s;
        }
    }
    if (headSlot < 0) return;

    int pointCount = min(seg.numPoints, aliveCount);
    pointCount = min(pointCount, u_slotsPerParticle);
    if (pointCount <= 1) return;

    bool wantsTube = segment_resolves_to_tube(seg, base, headSlot, pointCount);
    bool passMatch = (u_drawPass == TRAIL_PASS_TUBE) ? wantsTube : !wantsTube;
    if (!passMatch) return;

    uint outIndex = atomicAdd(drawArgs.instanceCount, 1u);
    if (outIndex >= uint(u_segmentCount)) return;
    visibleSegments[outIndex] = int(gid);
    headSlots[outIndex]       = headSlot;
}
"""


_TRAIL_SHARED_STRUCTS = """\
struct ParticleTrailPoint {
    float px;
    float py;
    float pz;
    uint  packedFlags;
};
struct ParticleTrailSegment {
    int particleIndex;
    int numPoints;
    int emitterIndex;
    int meta;
};
struct EmitterTrailPalette {
    vec4 color;
    vec4 params0;
    vec4 params1;
};
"""

_TRAIL_SHARED_HELPERS = """\
bool pal_enabled(EmitterTrailPalette p)          { return p.params0.x >= 0.5; }
int  pal_color_mode(EmitterTrailPalette p)       { return int(p.params0.y + 0.5); }
int  pal_trail_color_mode(EmitterTrailPalette p) { return int(p.params0.z + 0.5); }
bool pal_no_data(EmitterTrailPalette p)          { return p.params0.w >= 0.5; }

bool source_enabled(int ei) {
    if (u_paletteCount <= 0) return true;
    int src = ei & 0xFFFF;
    if (src < 0 || src >= u_paletteCount) return false;
    return pal_enabled(palettes[src]);
}

vec4 resolve_color(int idx, int ei) {
    if (u_paletteCount > 0 && ei >= 0 && ei < u_paletteCount) {
        EmitterTrailPalette p = palettes[ei];
        if (pal_enabled(p)) {
            bool stored = !pal_no_data(p) &&
                          (pal_color_mode(p) == 1 ||
                           pal_trail_color_mode(p) == 0 ||
                           pal_trail_color_mode(p) == 1);
            if (stored && u_useColorBuffer != 0
                && idx >= 0 && idx < u_colorCapacity) {
                vec4 c = colors[idx];
                if (pal_color_mode(p) != 1) c.a = 1.0;
                return c;
            }
            return p.color;
        }
    }
    if (u_useColorBuffer != 0 && idx >= 0 && idx < u_colorCapacity) return colors[idx];
    return u_defaultColor;
}

int slot_for(int headSlot, int pt, int slots) {
    return (headSlot - pt + slots) % slots;
}
"""


_LINE_VS_SRC = (
    """\
#version 430 core

"""
    + _TRAIL_SHARED_STRUCTS
    + """\

layout(std430, binding = 0) readonly buffer HistoryBuffer {
    int h_header[4];
    ParticleTrailPoint history[];
};
layout(std430, binding = 1) readonly buffer TopologyBuffer {
    int t_capacity;
    int t_count;
    int t_topologyMode;
    int t_reserved;
    ParticleTrailSegment segments[];
};
layout(std430, binding = 2) readonly buffer ColorBuffer {
    int c_header[4];
    vec4 colors[];
};
layout(std430, binding = 4) readonly buffer PaletteBuffer {
    EmitterTrailPalette palettes[];
};
layout(std430, binding = 5) readonly buffer HeadSlotsBuffer {
    int headSlots[];
};
layout(std430, binding = 7) readonly buffer VisibleSegmentsBuffer {
    int visibleSegments[];
};
layout(std430, binding = 9) readonly buffer LiveEndpointBuffer {
    float liveEndpoint[];
};

uniform mat4 u_mvp;
uniform vec4 u_defaultColor;
uniform int  u_slotsPerParticle;
uniform int  u_historyCapacity;
uniform int  u_useColorBuffer;
uniform int  u_paletteCount;
uniform int  u_topologyCapacity;
uniform int  u_colorCapacity;

out vec4 v_color;

const uint ALIVE_BIT               = 1u;
const int  LINE_VERTS_PER_EDGE     = 2;
const int  TRAIL_SEGMENT_HEAD_MASK = 0x3FFFFFFF;
const int  TRAIL_SEGMENT_KIND_LINK = 0x40000000;
const int  TRAIL_SEGMENT_TO_LIVE   = 0xFFFF;

"""
    + _TRAIL_SHARED_HELPERS
    + """\

void emit_degenerate() {
    gl_Position = vec4(0.0);
    v_color = vec4(0.0);
}

void main() {
    // Topology header's count is not maintained by the sim — clamp against
    // capacity instead.  Empty slots already get filtered out by the compute
    // prepass's numPoints check before being written to visibleSegments.
    int segIndex = visibleSegments[gl_InstanceID];
    if (u_slotsPerParticle <= 0 || segIndex < 0 || segIndex >= u_topologyCapacity) {
        emit_degenerate(); return;
    }

    ParticleTrailSegment seg = segments[segIndex];
    if (!source_enabled(seg.emitterIndex)) { emit_degenerate(); return; }

    bool isLink = (seg.meta & TRAIL_SEGMENT_KIND_LINK) != 0;
    if (isLink) {
        int edgeIdx = gl_VertexID / LINE_VERTS_PER_EDGE;
        int endpoint = gl_VertexID % LINE_VERTS_PER_EDGE;
        if (edgeIdx != 0) { emit_degenerate(); return; }

        int fromSrc = seg.emitterIndex & 0xFFFF;
        int toSrc = (seg.emitterIndex >> 16) & 0xFFFF;
        bool toLive = (toSrc == TRAIL_SEGMENT_TO_LIVE);
        int fromRow = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
        int toRow = seg.numPoints;
        if (fromRow < 0 || toRow < 0) { emit_degenerate(); return; }

        int fromBase = fromRow * u_slotsPerParticle;
        int toBase = toRow * u_slotsPerParticle;
        if (fromBase < 0 || fromBase + u_slotsPerParticle > u_historyCapacity) {
            emit_degenerate(); return;
        }
        if (!toLive && (toBase < 0 || toBase + u_slotsPerParticle > u_historyCapacity)) {
            emit_degenerate(); return;
        }

        int packedHead = headSlots[gl_InstanceID];
        if (packedHead < 0) { emit_degenerate(); return; }
        int fromHead = (packedHead >> 16) & 0xFFFF;
        int toHead = packedHead & 0xFFFF;
        if (fromHead < 0 || fromHead >= u_slotsPerParticle ||
            toHead < 0 || toHead >= u_slotsPerParticle) {
            emit_degenerate(); return;
        }

        if (toLive && endpoint == 1) {
            int li = toRow;
            gl_Position = u_mvp * vec4(liveEndpoint[li * 8 + 0],
                                       liveEndpoint[li * 8 + 1],
                                       liveEndpoint[li * 8 + 2], 1.0);
            v_color = vec4(liveEndpoint[li * 8 + 4],
                           liveEndpoint[li * 8 + 5],
                           liveEndpoint[li * 8 + 6],
                           liveEndpoint[li * 8 + 7]);
            return;
        }

        int idx = (endpoint == 0) ? (fromBase + fromHead) : (toBase + toHead);
        ParticleTrailPoint pt = history[idx];
        if ((pt.packedFlags & ALIVE_BIT) == 0u) { emit_degenerate(); return; }

        gl_Position = u_mvp * vec4(pt.px, pt.py, pt.pz, 1.0);
        v_color = resolve_color(idx, (endpoint == 0) ? fromSrc : toSrc);
        return;
    }

    int nEdges = seg.numPoints - 1;
    int edgeIdx = gl_VertexID / LINE_VERTS_PER_EDGE;
    int endpoint = gl_VertexID % LINE_VERTS_PER_EDGE;
    if (edgeIdx >= nEdges || nEdges <= 0) { emit_degenerate(); return; }

    int slotIndex = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
    int base = slotIndex * u_slotsPerParticle;
    int head = headSlots[gl_InstanceID];
    if (slotIndex < 0 || base < 0 || base + u_slotsPerParticle > u_historyCapacity
        || head < 0 || head >= u_slotsPerParticle) {
        emit_degenerate(); return;
    }
    int slot = slot_for(head, edgeIdx + endpoint, u_slotsPerParticle);
    int idx = base + slot;
    ParticleTrailPoint pt = history[idx];
    if ((pt.packedFlags & ALIVE_BIT) == 0u) { emit_degenerate(); return; }

    gl_Position = u_mvp * vec4(pt.px, pt.py, pt.pz, 1.0);
    v_color = resolve_color(idx, seg.emitterIndex);
}
"""
)


_LINE_FS_SRC = """\
#version 430 core
in vec4 v_color;
out vec4 FragColor;
void main() {
    if (v_color.a <= 0.0) discard;
    FragColor = v_color;
}
"""


_TUBE_VS_SRC = (
    """\
#version 430 core

"""
    + _TRAIL_SHARED_STRUCTS
    + """\

layout(std430, binding = 0) readonly buffer HistoryBuffer {
    int h_header[4];
    ParticleTrailPoint history[];
};
layout(std430, binding = 1) readonly buffer TopologyBuffer {
    int t_capacity;
    int t_count;
    int t_topologyMode;
    int t_reserved;
    ParticleTrailSegment segments[];
};
layout(std430, binding = 2) readonly buffer ColorBuffer {
    int c_header[4];
    vec4 colors[];
};
layout(std430, binding = 3) readonly buffer ThicknessBuffer {
    int th_header[4];
    float thick[];
};
layout(std430, binding = 4) readonly buffer PaletteBuffer {
    EmitterTrailPalette palettes[];
};
layout(std430, binding = 5) readonly buffer HeadSlotsBuffer {
    int headSlots[];
};
layout(std430, binding = 6) readonly buffer RadiusBuffer {
    float radius[];
};
layout(std430, binding = 7) readonly buffer VisibleSegmentsBuffer {
    int visibleSegments[];
};
layout(std430, binding = 9) readonly buffer LiveEndpointBuffer {
    float liveEndpoint[];
};

uniform mat4 u_mvp;
uniform vec4 u_defaultColor;
uniform int  u_slotsPerParticle;
uniform int  u_historyCapacity;
uniform int  u_useColorBuffer;
uniform int  u_hasThicknessBuffer;
uniform int  u_hasRadiusBuffer;
uniform int  u_radiusCount;
uniform int  u_paletteCount;
uniform int  u_topologyCapacity;
uniform int  u_colorCapacity;
uniform int  u_thicknessCapacity;

out vec4 v_color;
out  float v_across;

const uint ALIVE_BIT                = 1u;
const int  TRAIL_TUBE_SIDES         = 8;
const int  TUBE_TRI_VERTS_PER_SIDE  = 6;
const int  TUBE_VERTS_PER_EDGE      = TRAIL_TUBE_SIDES * TUBE_TRI_VERTS_PER_SIDE;
const int  TRAIL_SEGMENT_HEAD_MASK  = 0x3FFFFFFF;
const int  TRAIL_SEGMENT_KIND_LINK  = 0x40000000;
const int  TRAIL_SEGMENT_TO_LIVE    = 0xFFFF;

int   pal_thickness_mode_local(EmitterTrailPalette p) {
    return (p.params0.w >= 0.5) ? 0 : int(p.params1.x + 0.5);
}
float pal_thickness_value_local(EmitterTrailPalette p) { return p.params1.y; }

"""
    + _TRAIL_SHARED_HELPERS
    + """\

float resolve_thickness(int mode, float val, int idx, int particleIndex) {
    if (mode == 0) return 0.0;
    float stored = -1.0;
    if (u_hasThicknessBuffer != 0 && idx >= 0 && idx < u_thicknessCapacity) {
        stored = thick[idx];
    }
    if (mode == 1) return stored >= 0.0 ? stored : val;
    if (mode == 2) return stored >= 0.0 ? stored : 0.0;
    if (mode == 3 && u_hasRadiusBuffer != 0
                  && particleIndex >= 0 && particleIndex < u_radiusCount) {
        return radius[particleIndex];
    }
    if (mode == 4) return stored >= 0.0 ? stored : 0.0;
    return 0.0;
}

float resolve_thickness_live(int mode, float val, float liveRadius) {
    if (mode == 0) return 0.0;
    if (mode == 1) return val;
    return liveRadius;
}

bool segment_has_stored_thickness_link(int fromIdx, int toIdx) {
    if (fromIdx < 0 || fromIdx >= u_historyCapacity ||
        fromIdx >= u_thicknessCapacity) return false;
    if (toIdx < 0 || toIdx >= u_historyCapacity || toIdx >= u_thicknessCapacity) return false;
    if ((history[fromIdx].packedFlags & ALIVE_BIT) == 0u) return false;
    if ((history[toIdx].packedFlags & ALIVE_BIT) == 0u) return false;
    return thick[fromIdx] >= 0.0 && thick[toIdx] >= 0.0;
}

bool segment_resolves_to_tube_link(ParticleTrailSegment seg, int fromIdx, int toIdx,
                                   int fromRow, int toRow) {
    if (u_paletteCount <= 0) return false;
    int fromSrc = seg.emitterIndex & 0xFFFF;
    int toSrc = (seg.emitterIndex >> 16) & 0xFFFF;
    if (fromSrc < 0 || fromSrc >= u_paletteCount) return false;
    EmitterTrailPalette pal = palettes[fromSrc];
    if (!pal_enabled(pal)) return false;
    int mode = pal_thickness_mode_local(pal);
    if (mode == 0) return false;
    if (mode == 1) {
        if (u_hasThicknessBuffer != 0 &&
            segment_has_stored_thickness_link(fromIdx, toIdx)) {
            return true;
        }
        return pal_thickness_value_local(pal) > 0.0;
    }
    if (mode == 2 || mode == 4) {
        return u_hasThicknessBuffer != 0 &&
               segment_has_stored_thickness_link(fromIdx, toIdx);
    }
    if (mode == 3) {
        if (u_hasRadiusBuffer == 0) return false;
        int hpc = (u_slotsPerParticle > 0)
            ? u_historyCapacity / (u_paletteCount * u_slotsPerParticle)
            : 0;
        int fromParticle = fromRow - fromSrc * hpc;
        int toParticle = toRow - toSrc * hpc;
        if (fromParticle < 0 || fromParticle >= u_radiusCount) return false;
        if (toParticle < 0 || toParticle >= u_radiusCount) return false;
        return radius[fromParticle] > 0.0 && radius[toParticle] > 0.0;
    }
    return false;
}

void emit_degenerate() {
    gl_Position = vec4(0.0);
    v_color = vec4(0.0);
    v_across = 0.0;
}

void main() {
    // Topology header's count is not maintained by the sim — clamp against
    // capacity instead.  Empty slots already get filtered out by the compute
    // prepass's numPoints check before being written to visibleSegments.
    int segIndex = visibleSegments[gl_InstanceID];
    if (u_slotsPerParticle <= 0 || segIndex < 0 || segIndex >= u_topologyCapacity) {
        emit_degenerate(); return;
    }

    ParticleTrailSegment seg = segments[segIndex];
    if (!source_enabled(seg.emitterIndex)) { emit_degenerate(); return; }

    bool isLink = (seg.meta & TRAIL_SEGMENT_KIND_LINK) != 0;
    if (isLink) {
        int edgeIdx = gl_VertexID / TUBE_VERTS_PER_EDGE;
        int local   = gl_VertexID % TUBE_VERTS_PER_EDGE;
        if (edgeIdx != 0) { emit_degenerate(); return; }

        int side     = local / TUBE_TRI_VERTS_PER_SIDE;
        int corner   = local % TUBE_TRI_VERTS_PER_SIDE;
        int endpoint = (corner == 1 || corner == 2 || corner == 4) ? 1 : 0;
        int ringOffset = (corner == 2 || corner == 4 || corner == 5) ? 1 : 0;
        int ringPos  = (side + ringOffset) % TRAIL_TUBE_SIDES;

        int fromSrc = seg.emitterIndex & 0xFFFF;
        int toSrc = (seg.emitterIndex >> 16) & 0xFFFF;
        bool toLive = (toSrc == TRAIL_SEGMENT_TO_LIVE);
        int fromRow = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
        int toRow = seg.numPoints;
        if (fromRow < 0 || (!toLive && toRow < 0)) { emit_degenerate(); return; }

        int fromBase = fromRow * u_slotsPerParticle;
        int toBase = toRow * u_slotsPerParticle;
        if (fromBase < 0 || fromBase + u_slotsPerParticle > u_historyCapacity) {
            emit_degenerate(); return;
        }
        if (!toLive && (toBase < 0 || toBase + u_slotsPerParticle > u_historyCapacity)) {
            emit_degenerate(); return;
        }

        int packedHead = headSlots[gl_InstanceID];
        if (packedHead < 0) { emit_degenerate(); return; }
        int fromHead = (packedHead >> 16) & 0xFFFF;
        int toHead = packedHead & 0xFFFF;
        if (fromHead < 0 || fromHead >= u_slotsPerParticle ||
            toHead < 0 || toHead >= u_slotsPerParticle) {
            emit_degenerate(); return;
        }

        int idxA = fromBase + fromHead;
        int idxB = toBase + toHead;

        if (!toLive && !segment_resolves_to_tube_link(seg, idxA, idxB, fromRow, toRow)) {
            emit_degenerate(); return;
        }

        ParticleTrailPoint pA = history[idxA];
        if ((pA.packedFlags & ALIVE_BIT) == 0u) { emit_degenerate(); return; }

        vec3 posA = vec3(pA.px, pA.py, pA.pz);
        vec3 posB;
        if (toLive) {
            posB = vec3(liveEndpoint[toRow * 8 + 0],
                        liveEndpoint[toRow * 8 + 1],
                        liveEndpoint[toRow * 8 + 2]);
        } else {
            ParticleTrailPoint pB = history[idxB];
            if ((pB.packedFlags & ALIVE_BIT) == 0u) { emit_degenerate(); return; }
            posB = vec3(pB.px, pB.py, pB.pz);
        }

        vec3 axis = posB - posA;
        float axLen = length(axis);
        if (axLen < 1e-8) axis = vec3(0.0, 0.0, 1.0);
        else              axis /= axLen;

        vec3 ref = (abs(axis.z) < 0.9) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
        vec3 normal   = normalize(cross(ref, axis));
        vec3 binormal = cross(axis, normal);

        float halfThick = 0.0;
        if (u_paletteCount > 0 && fromSrc >= 0 && fromSrc < u_paletteCount) {
            EmitterTrailPalette pal = palettes[fromSrc];
            int tmode = pal_thickness_mode_local(pal);
            float tval = pal_thickness_value_local(pal);
            int hpc = (u_slotsPerParticle > 0)
                ? u_historyCapacity / (u_paletteCount * u_slotsPerParticle)
                : 0;
            if (endpoint == 0) {
                int fromParticle = fromRow - fromSrc * hpc;
                halfThick = resolve_thickness(tmode, tval, idxA, fromParticle) * 0.5;
            } else if (toLive) {
                halfThick = resolve_thickness_live(tmode, tval, liveEndpoint[toRow * 8 + 3]) * 0.5;
            } else {
                int toParticle = toRow - toSrc * hpc;
                halfThick = resolve_thickness(tmode, tval, idxB, toParticle) * 0.5;
            }
        }
        if (halfThick <= 0.0) { emit_degenerate(); return; }

        float angle = 6.28318530718 * float(ringPos) / float(TRAIL_TUBE_SIDES);
        vec3 radial = cos(angle) * normal + sin(angle) * binormal;
        vec3 endPos = (endpoint == 0) ? posA : posB;
        vec3 wp = endPos + radial * halfThick;

        gl_Position = u_mvp * vec4(wp, 1.0);

        if (endpoint == 0) {
            v_color = resolve_color(idxA, fromSrc);
        } else if (toLive) {
            v_color = vec4(liveEndpoint[toRow * 8 + 4],
                           liveEndpoint[toRow * 8 + 5],
                           liveEndpoint[toRow * 8 + 6],
                           liveEndpoint[toRow * 8 + 7]);
        } else {
            v_color = resolve_color(idxB, toSrc);
        }
        v_across = cos(angle);
        return;
    }

    int nEdges = seg.numPoints - 1;
    if (nEdges <= 0) { emit_degenerate(); return; }

    int edgeIdx = gl_VertexID / TUBE_VERTS_PER_EDGE;
    int local   = gl_VertexID % TUBE_VERTS_PER_EDGE;
    if (edgeIdx >= nEdges) { emit_degenerate(); return; }

    int side     = local / TUBE_TRI_VERTS_PER_SIDE;
    int corner   = local % TUBE_TRI_VERTS_PER_SIDE;
    int endpoint = (corner == 1 || corner == 2 || corner == 4) ? 1 : 0;
    int ringOffset = (corner == 2 || corner == 4 || corner == 5) ? 1 : 0;
    int ringPos  = (side + ringOffset) % TRAIL_TUBE_SIDES;

    int slotIndex = seg.meta & TRAIL_SEGMENT_HEAD_MASK;
    int base = slotIndex * u_slotsPerParticle;
    int head = headSlots[gl_InstanceID];
    if (slotIndex < 0 || base < 0 || base + u_slotsPerParticle > u_historyCapacity
        || head < 0 || head >= u_slotsPerParticle) {
        emit_degenerate(); return;
    }

    int slotA = slot_for(head, edgeIdx,     u_slotsPerParticle);
    int slotB = slot_for(head, edgeIdx + 1, u_slotsPerParticle);
    int idxA  = base + slotA;
    int idxB  = base + slotB;

    ParticleTrailPoint pA = history[idxA];
    ParticleTrailPoint pB = history[idxB];
    if ((pA.packedFlags & ALIVE_BIT) == 0u || (pB.packedFlags & ALIVE_BIT) == 0u) {
        emit_degenerate(); return;
    }

    vec3 posA = vec3(pA.px, pA.py, pA.pz);
    vec3 posB = vec3(pB.px, pB.py, pB.pz);

    vec3 axis = posB - posA;
    float axLen = length(axis);
    if (axLen < 1e-8) axis = vec3(0.0, 0.0, 1.0);
    else              axis /= axLen;

    vec3 ref = (abs(axis.z) < 0.9) ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
    vec3 normal   = normalize(cross(ref, axis));
    vec3 binormal = cross(axis, normal);

    float halfThick = 0.0;
    if (u_paletteCount > 0 && seg.emitterIndex >= 0 && seg.emitterIndex < u_paletteCount) {
        EmitterTrailPalette pal = palettes[seg.emitterIndex];
        int tmode = pal_thickness_mode_local(pal);
        float tval = pal_thickness_value_local(pal);
        int useIdx = (endpoint == 0) ? idxA : idxB;
        halfThick = resolve_thickness(tmode, tval, useIdx, seg.particleIndex) * 0.5;
    }
    if (halfThick <= 0.0) { emit_degenerate(); return; }

    float angle = 6.28318530718 * float(ringPos) / float(TRAIL_TUBE_SIDES);
    vec3 radial = cos(angle) * normal + sin(angle) * binormal;
    vec3 endPos = (endpoint == 0) ? posA : posB;
    vec3 wp = endPos + radial * halfThick;

    gl_Position = u_mvp * vec4(wp, 1.0);

    int colorIdx = (endpoint == 0) ? idxA : idxB;
    v_color = resolve_color(colorIdx, seg.emitterIndex);
    v_across = cos(angle);
}
"""
)


_TUBE_FS_SRC = """\
#version 430 core
in vec4 v_color;
in   float v_across;
out  vec4 FragColor;
void main() {
    if (v_color.a <= 0.0) discard;
    float nx = v_across;
    float nz = sqrt(max(0.0, 1.0 - nx * nx));
    vec3 fakeN = vec3(nx, 0.0, nz);
    vec3 L = normalize(vec3(0.3, 0.5, 1.0));
    float diff = max(dot(fakeN, L), 0.0);
    float ambient = 0.25;
    vec3 lit = v_color.rgb * (ambient + (1.0 - ambient) * diff);
    vec3 H = normalize(L + vec3(0.0, 0.0, 1.0));
    float spec = pow(max(dot(fakeN, H), 0.0), 24.0) * 0.35;
    lit += vec3(spec);
    float rim = 1.0 - nz;
    lit *= (1.0 - rim * rim * 0.25);
    FragColor = vec4(lit, v_color.a);
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gl_id(generated):
    if isinstance(generated, (list, tuple)):
        return int(generated[0])
    if hasattr(generated, "__len__"):
        try:
            return int(generated[0])
        except Exception:
            return int(generated)
    return int(generated)


def _shader_info_log(shader: int) -> str:
    try:
        raw = glGetShaderInfoLog(shader)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)
    except Exception:
        return "<no info log>"


def _program_info_log(program: int) -> str:
    try:
        raw = glGetProgramInfoLog(program)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)
    except Exception:
        return "<no info log>"


def _compile_render(vs_src: str, fs_src: str, label: str) -> int | None:
    def _compile_stage(stage: int, src: str, stage_label: str) -> int | None:
        sh = glCreateShader(stage)
        glShaderSource(sh, src)
        glCompileShader(sh)
        if not glGetShaderiv(sh, GL_COMPILE_STATUS):
            print(
                f"nexus trails OpenGL: {label} {stage_label} compile failed:\n"
                + _shader_info_log(sh)
            )
            glDeleteShader(sh)
            return None
        return int(sh)

    vs = _compile_stage(GL_VERTEX_SHADER, vs_src, "VS")
    fs = _compile_stage(GL_FRAGMENT_SHADER, fs_src, "FS")
    if vs is None or fs is None:
        if vs is not None:
            glDeleteShader(vs)
        if fs is not None:
            glDeleteShader(fs)
        return None

    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    glDeleteShader(vs)
    glDeleteShader(fs)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        print(f"nexus trails OpenGL: {label} program link failed:\n" + _program_info_log(prog))
        glDeleteProgram(prog)
        return None
    return int(prog)


def _compile_compute(src: str) -> int | None:
    sh = glCreateShader(GL_COMPUTE_SHADER)
    glShaderSource(sh, src)
    glCompileShader(sh)
    if not glGetShaderiv(sh, GL_COMPILE_STATUS):
        print("nexus trails OpenGL: compute shader compile failed:\n" + _shader_info_log(sh))
        glDeleteShader(sh)
        return None
    prog = glCreateProgram()
    glAttachShader(prog, sh)
    glLinkProgram(prog)
    glDeleteShader(sh)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        print("nexus trails OpenGL: compute program link failed:\n" + _program_info_log(prog))
        glDeleteProgram(prog)
        return None
    return int(prog)


def _to_buffer_export(tup) -> BufferExport | None:
    if tup is None:
        return None
    handle, size, uid = tup
    return BufferExport(handle=int(handle), size=int(size), uid=int(uid))


def _fetch_trail_bundle(pipeline: int):
    from ...libs import theron

    fetch = getattr(theron, "get_trail_buffer_exports", None)
    if fetch is None:
        return None
    return fetch(pipeline)


def _fetch_radius_export(pipeline: int, params) -> tuple[int, int, int] | None:
    from ...libs import theron
    from ...libs.theron_bindings import TrParticleProperty

    needs_radius = False
    for i, mode in enumerate(params.source_thickness_modes):
        if mode not in _RADIUS_THICKNESS_MODES:
            continue
        if i < len(params.source_enabled_flags) and not params.source_enabled_flags[i]:
            continue
        if i < len(params.source_no_data_flags) and params.source_no_data_flags[i]:
            continue
        needs_radius = True
        break
    if not needs_radius:
        return None

    particle_count = theron.get_particle_count(pipeline)
    if particle_count <= 0:
        return None
    export = theron.get_particle_data_buffer_export(
        pipeline, TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS
    )
    if export is None:
        return None
    handle, size, uid = export
    live_size = min(int(size), particle_count * 4)
    if not handle or live_size <= 0:
        return None
    return (int(handle), int(live_size), int(uid))


def _line_vertex_count(max_pts: int) -> int:
    if max_pts <= 1:
        return 0
    n = (max_pts - 1) * _LINE_VERTS_PER_EDGE
    return min(n, _TUBE_VERTEX_HARD_CAP)


def _tube_vertex_count(max_pts: int) -> int:
    if max_pts <= 1:
        return 0
    n = (max_pts - 1) * _TUBE_VERTS_PER_EDGE
    return min(n, _TUBE_VERTEX_HARD_CAP)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class TrailsOpenGLRenderer(OpenGLModeBase):
    backend_id = "OPENGL"
    supports_lines = True

    def __init__(self, bridge) -> None:
        super().__init__(bridge)

        self._history_vbo: int | None = None
        self._topology_vbo: int | None = None
        self._color_vbo: int | None = None
        self._thickness_vbo: int | None = None
        self._radius_vbo: int | None = None
        self._live_endpoint_vbo: int | None = None

        self._history_id = None
        self._topology_id = None
        self._color_id = None
        self._thickness_id = None
        self._radius_id = None
        self._live_endpoint_id = None

        self._history_size = 0
        self._topology_size = 0
        self._color_size = 0
        self._thickness_size = 0
        self._radius_size = 0
        self._live_endpoint_size = 0

        self._compute_program: int | None = None
        self._line_program: int | None = None
        self._tube_program: int | None = None
        self._compute_locs: dict[str, int] = {}
        self._line_locs: dict[str, int] = {}
        self._tube_locs: dict[str, int] = {}

        self._palette_ssbo: int | None = None
        self._head_slots_ssbo: int | None = None
        self._visible_ssbo: int | None = None
        self._indirect_ssbo: int | None = None
        self._live_dummy_ssbo: int | None = None
        self._scratch_capacity = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _free_resources(self) -> None:
        # Don't chain to super()._free_resources(): it would delete the VAO
        # and self._program, which we keep alive across buffer reimports.
        if _GL_OK:
            for vbo, mem, keep_handle in self._buffers:
                self._bridge.free_buffer(vbo, mem, keep_handle)
        self._buffers = []
        self._history_vbo = None
        self._topology_vbo = None
        self._color_vbo = None
        self._thickness_vbo = None
        self._radius_vbo = None
        self._live_endpoint_vbo = None
        self._history_id = None
        self._topology_id = None
        self._color_id = None
        self._thickness_id = None
        self._radius_id = None
        self._live_endpoint_id = None
        self._history_size = 0
        self._topology_size = 0
        self._color_size = 0
        self._thickness_size = 0
        self._radius_size = 0
        self._live_endpoint_size = 0
        self._imported = False

    def shutdown(self) -> None:
        self._free_resources()
        if not _GL_OK:
            return
        if self._vao is not None:
            try:
                from OpenGL.GL import glDeleteVertexArrays

                glDeleteVertexArrays(1, [self._vao])
            except Exception:
                pass
            self._vao = None
        for attr in ("_compute_program", "_line_program", "_tube_program"):
            prog = getattr(self, attr)
            if prog is not None:
                try:
                    glDeleteProgram(prog)
                except Exception:
                    pass
                setattr(self, attr, None)
        for attr in (
            "_palette_ssbo",
            "_head_slots_ssbo",
            "_visible_ssbo",
            "_indirect_ssbo",
            "_live_dummy_ssbo",
        ):
            buf = getattr(self, attr)
            if buf is not None:
                try:
                    glDeleteBuffers(1, [buf])
                except Exception:
                    pass
                setattr(self, attr, None)
        self._scratch_capacity = 0

    def reset(self, pipeline=None) -> None:
        self._free_resources()

    def draw(self, context, pipeline, scene, params) -> bool:  # noqa: ARG002
        return self.stage(context, pipeline, params)

    # ------------------------------------------------------------------
    # Programs
    # ------------------------------------------------------------------

    def _ensure_programs(self) -> bool:
        if self._compute_program is None:
            prog = _compile_compute(_COMPUTE_SRC)
            if prog is None:
                return False
            self._compute_program = prog
            self._compute_locs = {
                name: glGetUniformLocation(prog, name)
                for name in (
                    "u_slotsPerParticle",
                    "u_segmentCount",
                    "u_vertexCountPerInstance",
                    "u_paletteCount",
                    "u_drawPass",
                    "u_hasThicknessBuffer",
                    "u_hasRadiusBuffer",
                    "u_radiusCount",
                    "u_historyCapacity",
                    "u_topologyCapacity",
                    "u_thicknessCapacity",
                )
            }
        if self._line_program is None:
            prog = _compile_render(_LINE_VS_SRC, _LINE_FS_SRC, "line")
            if prog is None:
                return False
            self._line_program = int(prog)
            self._line_locs = {
                name: glGetUniformLocation(prog, name)
                for name in (
                    "u_mvp",
                    "u_defaultColor",
                    "u_slotsPerParticle",
                    "u_historyCapacity",
                    "u_useColorBuffer",
                    "u_paletteCount",
                    "u_topologyCapacity",
                    "u_colorCapacity",
                )
            }
        if self._tube_program is None:
            prog = _compile_render(_TUBE_VS_SRC, _TUBE_FS_SRC, "tube")
            if prog is None:
                return False
            self._tube_program = int(prog)
            self._tube_locs = {
                name: glGetUniformLocation(prog, name)
                for name in (
                    "u_mvp",
                    "u_defaultColor",
                    "u_slotsPerParticle",
                    "u_historyCapacity",
                    "u_useColorBuffer",
                    "u_hasThicknessBuffer",
                    "u_hasRadiusBuffer",
                    "u_radiusCount",
                    "u_paletteCount",
                    "u_topologyCapacity",
                    "u_colorCapacity",
                    "u_thicknessCapacity",
                )
            }
        if self._vao is None:
            self._vao = _gl_id(glGenVertexArrays(1))
        return True

    # ------------------------------------------------------------------
    # Scratch + palette
    # ------------------------------------------------------------------

    def _ensure_scratch(self, segment_count: int) -> bool:
        # Round up to 1024 so resize doesn't ping-pong with small spikes.
        rounded = ((max(segment_count, 16) + 1023) // 1024) * 1024
        try:
            if self._palette_ssbo is None:
                self._palette_ssbo = _gl_id(glGenBuffers(1))
            if self._indirect_ssbo is None:
                self._indirect_ssbo = _gl_id(glGenBuffers(1))
                glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_ssbo)
                glBufferData(GL_DRAW_INDIRECT_BUFFER, 16, None, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
            if self._live_dummy_ssbo is None:
                self._live_dummy_ssbo = _gl_id(glGenBuffers(1))
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._live_dummy_ssbo)
                glBufferData(GL_SHADER_STORAGE_BUFFER, 64, bytes(64), GL_DYNAMIC_DRAW)
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
            if rounded != self._scratch_capacity:
                if self._head_slots_ssbo is not None:
                    glDeleteBuffers(1, [self._head_slots_ssbo])
                if self._visible_ssbo is not None:
                    glDeleteBuffers(1, [self._visible_ssbo])
                self._head_slots_ssbo = _gl_id(glGenBuffers(1))
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._head_slots_ssbo)
                glBufferData(GL_SHADER_STORAGE_BUFFER, rounded * 4, None, GL_DYNAMIC_DRAW)
                self._visible_ssbo = _gl_id(glGenBuffers(1))
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._visible_ssbo)
                glBufferData(GL_SHADER_STORAGE_BUFFER, rounded * 4, None, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
                self._scratch_capacity = rounded
            return True
        except Exception:
            return False

    def _upload_palette(self, params) -> int:
        count = int(params.source_count)
        if count <= 0 or self._palette_ssbo is None:
            return 0
        floats = np.zeros((count, _PALETTE_FLOATS_PER_ENTRY), dtype=np.float32)
        for i in range(count):
            color = (
                params.source_colors[i] if i < len(params.source_colors) else (0.0, 0.0, 0.0, 1.0)
            )
            floats[i, 0:4] = color

            enabled = (
                1.0
                if (i < len(params.source_enabled_flags) and params.source_enabled_flags[i])
                else 0.0
            )
            color_mode_str = (
                params.source_color_modes[i] if i < len(params.source_color_modes) else "STANDARD"
            )
            trail_mode_str = (
                params.source_trail_color_modes[i]
                if i < len(params.source_trail_color_modes)
                else "PARTICLE"
            )
            no_data = (
                1.0
                if (i < len(params.source_no_data_flags) and params.source_no_data_flags[i])
                else 0.0
            )
            floats[i, 4] = enabled
            floats[i, 5] = float(_COLOR_MODE_MAP.get(color_mode_str, 0))
            floats[i, 6] = float(_TRAIL_COLOR_MODE_MAP.get(trail_mode_str, 0))
            floats[i, 7] = no_data

            thickness_mode_str = (
                params.source_thickness_modes[i]
                if i < len(params.source_thickness_modes)
                else "NONE"
            )
            floats[i, 8] = float(_THICKNESS_MODE_MAP.get(thickness_mode_str, 0))
            floats[i, 9] = (
                float(params.source_thickness_values[i])
                if i < len(params.source_thickness_values)
                else 0.01
            )
            floats[i, 10] = (
                float(params.source_thickness_variations[i])
                if i < len(params.source_thickness_variations)
                else 0.0
            )
            floats[i, 11] = (
                float(params.source_spline_max_values[i])
                if i < len(params.source_spline_max_values)
                else 0.01
            )
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, self._palette_ssbo)
        glBufferData(GL_SHADER_STORAGE_BUFFER, floats.nbytes, floats.tobytes(), GL_DYNAMIC_DRAW)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)
        return count

    # ------------------------------------------------------------------
    # Buffer import + identity tracking
    # ------------------------------------------------------------------

    def _ensure_import(
        self,
        history: BufferExport,
        topology: BufferExport,
        color: BufferExport | None,
        thickness: BufferExport | None,
        radius: BufferExport | None,
        live_endpoint: BufferExport | None,
    ) -> bool:
        if not history.valid or not topology.valid:
            return False

        history_id = buf_identity(history)
        topology_id = buf_identity(topology)
        color_id = buf_identity(color)
        thickness_id = buf_identity(thickness)
        radius_id = buf_identity(radius)
        live_endpoint_id = buf_identity(live_endpoint)

        if (
            self._imported
            and self._history_id == history_id
            and self._topology_id == topology_id
            and self._color_id == color_id
            and self._thickness_id == thickness_id
            and self._radius_id == radius_id
            and self._live_endpoint_id == live_endpoint_id
        ):
            return True

        if self._imported:
            self._free_resources()

        self._history_vbo = self._import(history)
        self._topology_vbo = self._import(topology)
        self._color_vbo = self._import(color) if (color is not None and color.valid) else None
        self._thickness_vbo = (
            self._import(thickness) if (thickness is not None and thickness.valid) else None
        )
        self._radius_vbo = self._import(radius) if (radius is not None and radius.valid) else None
        self._live_endpoint_vbo = (
            self._import(live_endpoint)
            if (live_endpoint is not None and live_endpoint.valid)
            else None
        )
        if self._history_vbo is None or self._topology_vbo is None:
            self._free_resources()
            return False

        self._history_id = history_id
        self._topology_id = topology_id
        self._color_id = color_id
        self._thickness_id = thickness_id
        self._radius_id = radius_id
        self._live_endpoint_id = live_endpoint_id
        self._history_size = int(history.size)
        self._topology_size = int(topology.size)
        self._color_size = (
            int(color.size) if (color is not None and self._color_vbo is not None) else 0
        )
        self._thickness_size = (
            int(thickness.size)
            if (thickness is not None and self._thickness_vbo is not None)
            else 0
        )
        self._radius_size = (
            int(radius.size) if (radius is not None and self._radius_vbo is not None) else 0
        )
        self._live_endpoint_size = (
            int(live_endpoint.size)
            if (live_endpoint is not None and self._live_endpoint_vbo is not None)
            else 0
        )
        self._imported = True
        return True

    # ------------------------------------------------------------------
    # Capacity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _payload_capacity(size_bytes: int, element_bytes: int) -> int:
        from .constants import TRAIL_HEADER_BYTES

        if element_bytes <= 0 or size_bytes <= TRAIL_HEADER_BYTES:
            return 0
        return (size_bytes - TRAIL_HEADER_BYTES) // element_bytes

    def _topology_segment_capacity(self, topology_size: int, params) -> int:
        cap = self._payload_capacity(topology_size, 16)
        if cap > 0:
            return cap
        return max(1, int(params.source_count)) * max(1, int(params.history_capacity))

    # ------------------------------------------------------------------
    # MVP
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_mvp(context) -> list[float] | None:
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return None
        try:
            persp = region_data.perspective_matrix
            return [persp[i][j] for i in range(4) for j in range(4)]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Indirect-args reset (between compute passes)
    # ------------------------------------------------------------------

    def _reset_indirect_args(self) -> None:
        zeros = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_ssbo)
        glBufferSubData(GL_DRAW_INDIRECT_BUFFER, 0, 16, zeros)
        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)

    # ------------------------------------------------------------------
    # SSBO binding (shared across compute + render passes)
    # ------------------------------------------------------------------

    def _bind_ssbos(self, include_thickness: bool, include_radius: bool) -> None:
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, int(self._history_vbo))
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, int(self._topology_vbo))
        glBindBufferBase(
            GL_SHADER_STORAGE_BUFFER, 2, int(self._color_vbo) if self._color_vbo else 0
        )
        if include_thickness:
            glBindBufferBase(
                GL_SHADER_STORAGE_BUFFER,
                3,
                int(self._thickness_vbo) if self._thickness_vbo else 0,
            )
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, int(self._palette_ssbo))
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, int(self._head_slots_ssbo))
        if include_radius:
            glBindBufferBase(
                GL_SHADER_STORAGE_BUFFER,
                6,
                int(self._radius_vbo) if self._radius_vbo else 0,
            )
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, int(self._visible_ssbo))
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 8, int(self._indirect_ssbo))
        glBindBufferBase(
            GL_SHADER_STORAGE_BUFFER,
            9,
            int(self._live_endpoint_vbo)
            if self._live_endpoint_vbo
            else int(self._live_dummy_ssbo or 0),
        )

    # ------------------------------------------------------------------
    # Single pass (LINE or TUBE)
    # ------------------------------------------------------------------

    def _run_pass(
        self,
        *,
        draw_pass: int,
        vertex_count: int,
        segment_count: int,
        slots: int,
        history_cap: int,
        topology_cap: int,
        color_cap: int,
        thickness_cap: int,
        radius_count: int,
        palette_count: int,
        has_thickness: int,
        has_radius: int,
        use_color: int,
        mvp: list[float],
        default_color: tuple[float, float, float, float],
        program: int,
        prim: int,
        locs: dict[str, int],
        is_tube: bool,
    ) -> None:
        if vertex_count <= 0:
            return

        # 1) Compute prepass — head resolution + indirect args + visible list.
        self._reset_indirect_args()
        glUseProgram(self._compute_program)
        self._bind_ssbos(include_thickness=True, include_radius=True)

        cl = self._compute_locs
        if cl["u_slotsPerParticle"] >= 0:
            glUniform1i(cl["u_slotsPerParticle"], slots)
        if cl["u_segmentCount"] >= 0:
            glUniform1i(cl["u_segmentCount"], int(segment_count))
        if cl["u_vertexCountPerInstance"] >= 0:
            glUniform1ui(cl["u_vertexCountPerInstance"], int(vertex_count))
        if cl["u_paletteCount"] >= 0:
            glUniform1i(cl["u_paletteCount"], int(palette_count))
        if cl["u_drawPass"] >= 0:
            glUniform1i(cl["u_drawPass"], int(draw_pass))
        if cl["u_hasThicknessBuffer"] >= 0:
            glUniform1i(cl["u_hasThicknessBuffer"], int(has_thickness))
        if cl["u_hasRadiusBuffer"] >= 0:
            glUniform1i(cl["u_hasRadiusBuffer"], int(has_radius))
        if cl["u_radiusCount"] >= 0:
            glUniform1i(cl["u_radiusCount"], int(radius_count))
        if cl["u_historyCapacity"] >= 0:
            glUniform1i(cl["u_historyCapacity"], int(history_cap))
        if cl["u_topologyCapacity"] >= 0:
            glUniform1i(cl["u_topologyCapacity"], int(topology_cap))
        if cl["u_thicknessCapacity"] >= 0:
            glUniform1i(cl["u_thicknessCapacity"], int(thickness_cap))

        groups = max(1, (int(segment_count) + 63) // 64)
        glDispatchCompute(groups, 1, 1)
        glMemoryBarrier(GL_COMMAND_BARRIER_BIT | GL_SHADER_STORAGE_BARRIER_BIT)

        # 2) Render pass — bindings already in place, just swap program +
        # render-only uniforms.
        glUseProgram(program)
        glBindVertexArray(self._vao)

        if locs.get("u_mvp", -1) >= 0:
            glUniformMatrix4fv(locs["u_mvp"], 1, True, mvp)
        if locs.get("u_defaultColor", -1) >= 0:
            glUniform4f(locs["u_defaultColor"], *default_color)
        if locs.get("u_slotsPerParticle", -1) >= 0:
            glUniform1i(locs["u_slotsPerParticle"], slots)
        if locs.get("u_historyCapacity", -1) >= 0:
            glUniform1i(locs["u_historyCapacity"], int(history_cap))
        if locs.get("u_useColorBuffer", -1) >= 0:
            glUniform1i(locs["u_useColorBuffer"], int(use_color))
        if locs.get("u_paletteCount", -1) >= 0:
            glUniform1i(locs["u_paletteCount"], int(palette_count))
        if locs.get("u_topologyCapacity", -1) >= 0:
            glUniform1i(locs["u_topologyCapacity"], int(topology_cap))
        if locs.get("u_colorCapacity", -1) >= 0:
            glUniform1i(locs["u_colorCapacity"], int(color_cap))
        if is_tube:
            if locs.get("u_hasThicknessBuffer", -1) >= 0:
                glUniform1i(locs["u_hasThicknessBuffer"], int(has_thickness))
            if locs.get("u_hasRadiusBuffer", -1) >= 0:
                glUniform1i(locs["u_hasRadiusBuffer"], int(has_radius))
            if locs.get("u_radiusCount", -1) >= 0:
                glUniform1i(locs["u_radiusCount"], int(radius_count))
            if locs.get("u_thicknessCapacity", -1) >= 0:
                glUniform1i(locs["u_thicknessCapacity"], int(thickness_cap))

        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_ssbo)
        glDrawArraysIndirect(prim, None)
        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)
        glBindVertexArray(0)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def stage(self, context, pipeline: int, params) -> bool:
        if not _GL_OK or not self._bridge.load():
            return False
        if pipeline is None or int(params.source_count) <= 0:
            return False

        glMemoryBarrier(GL_ALL_BARRIER_BITS)

        bundle = _fetch_trail_bundle(pipeline)
        if bundle is None:
            self.reset(pipeline)
            return False
        if bundle.history_particle_capacity <= 0 or bundle.slots_per_particle <= 0:
            self.reset(pipeline)
            return False

        history = _to_buffer_export(bundle.history)
        topology = _to_buffer_export(bundle.topology)
        color = _to_buffer_export(bundle.color)
        thickness = _to_buffer_export(bundle.thickness)
        live_endpoint = _to_buffer_export(bundle.live_endpoint)
        if history is None or topology is None:
            self.reset(pipeline)
            return False

        radius_tup = _fetch_radius_export(pipeline, params)
        radius = _to_buffer_export(radius_tup) if radius_tup is not None else None

        if not self._ensure_programs():
            return False
        if not self._ensure_import(history, topology, color, thickness, radius, live_endpoint):
            return False

        segment_count = self._topology_segment_capacity(self._topology_size, params)
        if segment_count <= 0:
            return False
        if not self._ensure_scratch(segment_count):
            return False

        slots = int(bundle.slots_per_particle)
        max_pts = int(params.max_points_per_segment)
        if max_pts <= 0:
            max_pts = slots
        if max_pts <= 1:
            return False

        history_cap = self._payload_capacity(self._history_size, 16)
        topology_cap = self._payload_capacity(self._topology_size, 16)
        color_cap = self._payload_capacity(self._color_size, 16)
        thickness_cap = self._payload_capacity(self._thickness_size, 4)
        radius_count = (self._radius_size // 4) if self._radius_vbo is not None else 0
        has_thickness = 1 if (self._thickness_vbo is not None and thickness_cap > 0) else 0
        has_radius = 1 if (self._radius_vbo is not None and radius_count > 0) else 0
        use_color = 1 if (self._color_vbo is not None and color_cap > 0) else 0

        palette_count = self._upload_palette(params)

        mvp = self._resolve_mvp(context)
        if mvp is None:
            return False
        default_color = params.source_colors[0] if params.source_colors else (1.0, 1.0, 1.0, 1.0)

        saved = self._bridge.save_state_for_particle_draw()
        try:
            glEnable(GL_BLEND)
            glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ZERO)
            glBlendEquationSeparate(GL_FUNC_ADD, GL_FUNC_ADD)

            self._run_pass(
                draw_pass=_TRAIL_PASS_LINE,
                vertex_count=_line_vertex_count(max_pts),
                segment_count=segment_count,
                slots=slots,
                history_cap=history_cap,
                topology_cap=topology_cap,
                color_cap=color_cap,
                thickness_cap=thickness_cap,
                radius_count=radius_count,
                palette_count=palette_count,
                has_thickness=has_thickness,
                has_radius=has_radius,
                use_color=use_color,
                mvp=mvp,
                default_color=default_color,
                program=self._line_program,
                prim=GL_LINES,
                locs=self._line_locs,
                is_tube=False,
            )
            self._run_pass(
                draw_pass=_TRAIL_PASS_TUBE,
                vertex_count=_tube_vertex_count(max_pts),
                segment_count=segment_count,
                slots=slots,
                history_cap=history_cap,
                topology_cap=topology_cap,
                color_cap=color_cap,
                thickness_cap=thickness_cap,
                radius_count=radius_count,
                palette_count=palette_count,
                has_thickness=has_thickness,
                has_radius=has_radius,
                use_color=use_color,
                mvp=mvp,
                default_color=default_color,
                program=self._tube_program,
                prim=GL_TRIANGLES,
                locs=self._tube_locs,
                is_tube=True,
            )
        finally:
            self._bridge.restore_state(saved)
        return True


def make_opengl_stager(bridge) -> TrailsOpenGLRenderer:
    return TrailsOpenGLRenderer(bridge)
