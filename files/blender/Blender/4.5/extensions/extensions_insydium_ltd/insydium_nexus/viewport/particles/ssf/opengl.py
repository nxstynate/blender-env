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

"""OpenGL screen-space fluid renderer (proof of concept).

Pipeline (per frame):
    1. Depth pass:     render particles as sphere imposter point sprites,
                       output view-space Z to an R32F color attachment,
                       write gl_FragDepth for depth testing against itself.
    2. Thickness pass: same imposters, additive blend, accumulate sphere
                       thickness into an R32F color attachment (no depth test).
    3. Blur pass:      separable bilateral filter on the depth texture, N
                       iterations (ping-pong between two R32F FBOs). Preserves
                       silhouettes where neighbouring samples differ sharply.
    4. Composite:      full-screen triangle. Reconstruct view-space position
                       from smoothed depth, view-space normal from finite
                       differences, apply Fresnel + Beer-Lambert absorption,
                       write colour and gl_FragDepth so the fluid depth
                       integrates with Blender's scene depth buffer.

SSF particles have their own Theron prefix-sum bin (ID_NX_EMITTER_DISPLAY_MODE_SSF),
so this renderer iterates only over that bin via ``mode_bin_index("SSF")``.
The dispatch layer in particles/__init__.py registers this renderer alongside
SphereOpenGL — both run when their respective emitters are present, with no
bin sharing.
"""

from __future__ import annotations

import numpy as np

from ...core.buffer_state import BufferExport, buf_identity
from ..indirect_opengl_base import IndirectOpenGLBase

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_BLEND,
        GL_CLAMP_TO_EDGE,
        GL_COLOR_ATTACHMENT0,
        GL_COLOR_BUFFER_BIT,
        GL_CULL_FACE,
        GL_DEPTH_ATTACHMENT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_COMPONENT24,
        GL_DEPTH_TEST,
        GL_DRAW_FRAMEBUFFER_BINDING,
        GL_DRAW_INDIRECT_BUFFER,
        GL_FALSE,
        GL_FLOAT,
        GL_FRAMEBUFFER,
        GL_FRAMEBUFFER_COMPLETE,
        GL_LEQUAL,
        GL_NEAREST,
        GL_ONE,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_POINTS,
        GL_PROGRAM_POINT_SIZE,
        GL_R32F,
        GL_RED,
        GL_RENDERBUFFER,
        GL_RENDERBUFFER_BINDING,
        GL_SHADER_STORAGE_BUFFER,
        GL_SRC_ALPHA,
        GL_STATIC_DRAW,
        GL_TEXTURE0,
        GL_TEXTURE_2D,
        GL_TEXTURE_BINDING_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_TEXTURE_WRAP_S,
        GL_TEXTURE_WRAP_T,
        GL_TRIANGLES,
        GL_VIEWPORT,
        glActiveTexture,
        glBindBuffer,
        glBindBufferBase,
        glBindFramebuffer,
        glBindRenderbuffer,
        glBindTexture,
        glBindVertexArray,
        glBlendFunc,
        glBufferData,
        glCheckFramebufferStatus,
        glClear,
        glClearColor,
        glClearDepth,
        glDeleteBuffers,
        glDeleteFramebuffers,
        glDeleteProgram,
        glDeleteRenderbuffers,
        glDeleteTextures,
        glDeleteVertexArrays,
        glDepthFunc,
        glDepthMask,
        glDisable,
        glDrawArrays,
        glDrawArraysIndirect,
        glEnable,
        glEnableVertexAttribArray,
        glFramebufferRenderbuffer,
        glFramebufferTexture2D,
        glGenBuffers,
        glGenFramebuffers,
        glGenRenderbuffers,
        glGenTextures,
        glGenVertexArrays,
        glGetIntegerv,
        glGetUniformLocation,
        glRenderbufferStorage,
        glTexImage2D,
        glTexParameteri,
        glUniform1f,
        glUniform1fv,
        glUniform1i,
        glUniform2f,
        glUniform3f,
        glUniformMatrix4fv,
        glUseProgram,
        glVertexAttribPointer,
        glViewport,
    )

    _GL_OK = True
except ImportError:
    _GL_OK = False


_VERTS_PER_INSTANCE = 1  # one point per particle


def _gen_one(gen_fn, n=1):
    out = gen_fn(n)
    return out[0] if isinstance(out, (list, tuple, np.ndarray)) else out


# ---------------------------------------------------------------------------
# Shaders
# ---------------------------------------------------------------------------

# Common sphere-imposter vertex shader, used by both depth and thickness
# passes. One point per particle; gl_PointSize is the projected sphere
# diameter in pixels.
_IMPOSTER_VS = """
#version 430 core

layout(location = 0) in vec3 _dummy_v;

layout(std430, binding = 3) readonly buffer Positions { vec4 positions[]; };
layout(std430, binding = 4) readonly buffer BinnedIndices { uint binned[]; };
layout(std430, binding = 5) readonly buffer DrawState { uint start_index; };
layout(std430, binding = 6) readonly buffer Radii { float radii[]; };
layout(std430, binding = 7) readonly buffer Velocities { vec4 velocities[]; };
layout(std430, binding = 8) readonly buffer EmitterIndices { uint emitter_indices[]; };

uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec2 u_viewport;
uniform float u_fallback_radius;
uniform int u_use_radius;
uniform int u_emitter_sizes_count;
uniform float u_emitter_sizes[64];
uniform int u_use_anisotropy;
uniform float u_aniso_scale;
uniform float u_aniso_max_stretch;

out vec3 v_view_pos;
out float v_radius;
out vec2 v_axis;
out float v_stretch;

void main() {
    uint draw_idx = start_index + uint(gl_InstanceID);
    uint particle_idx = binned[draw_idx];
    uint emitter_idx = emitter_indices[particle_idx];

    float r = u_use_radius != 0 ? radii[particle_idx] : u_fallback_radius;
    if (u_use_radius == 0 && u_emitter_sizes_count > 0) {
        uint i = min(emitter_idx, uint(max(u_emitter_sizes_count - 1, 0)));
        r = u_emitter_sizes[i];
    }
    if (u_use_radius != 0 && (r != r || r < 0.0 || r > 1.0e6)) r = 1.0;

    vec3 world_pos = positions[particle_idx].xyz;
    vec4 view_pos = u_view * vec4(world_pos, 1.0);

    v_view_pos = view_pos.xyz;
    v_radius = r;
    v_axis = vec2(1.0, 0.0);
    v_stretch = 1.0;

    if (u_use_anisotropy != 0) {
        vec3 vel_view = (u_view * vec4(velocities[particle_idx].xyz, 0.0)).xyz;
        float speed = length(vel_view);
        v_stretch = clamp(1.0 + speed * u_aniso_scale, 1.0, u_aniso_max_stretch);
        vec2 axis = vel_view.xy;
        if (dot(axis, axis) > 1e-10) {
            v_axis = normalize(axis);
        }
    }

    vec4 clip = u_proj * view_pos;
    gl_Position = clip;

    // Project a point offset in the camera-right direction by r to measure
    // the sphere's screen-space radius in pixels.
    vec4 off_clip = u_proj * (view_pos + vec4(r, 0.0, 0.0, 0.0));
    vec2 s0 = clip.xy / max(clip.w, 1e-6);
    vec2 s1 = off_clip.xy / max(off_clip.w, 1e-6);
    float px_radius = length(s1 - s0) * 0.5 * u_viewport.x;
    gl_PointSize = clamp(px_radius * 2.0 * v_stretch, 2.0, 4096.0);
}
"""


_DEPTH_FS = """
#version 430 core

in vec3 v_view_pos;
in float v_radius;
in vec2 v_axis;
in float v_stretch;

uniform mat4 u_proj;

layout(location = 0) out float out_view_z;

void main() {
    vec2 n = gl_PointCoord * 2.0 - 1.0;
    n.y = -n.y;
    vec2 perp = vec2(-v_axis.y, v_axis.x);
    vec2 q = vec2(dot(n, v_axis), dot(n, perp));
    // gl_PointSize uses the stretched major axis as sprite diameter.
    // In this space, the minor axis shrinks by 1/stretch.
    vec2 e = vec2(q.x, q.y * max(v_stretch, 1e-5));
    float r2 = dot(e, e);
    if (r2 > 1.0) discard;
    float zoff = sqrt(1.0 - r2);
    vec2 view_xy = v_axis * (q.x * v_stretch) + perp * q.y;
    // View space surface point: sphere center + radius * local_normal. Here
    // local_normal's +z faces the camera (camera looks down -Z), so the
    // nearest surface point is center + radius * (n.xy, +zoff).
    vec3 surf = v_view_pos + vec3(view_xy, zoff) * v_radius;
    out_view_z = surf.z;  // negative where visible (in front of the camera)

    vec4 clip = u_proj * vec4(surf, 1.0);
    gl_FragDepth = (clip.z / clip.w) * 0.5 + 0.5;
}
"""


_THICKNESS_FS = """
#version 430 core

in float v_radius;
in vec2 v_axis;
in float v_stretch;

layout(location = 0) out float out_thickness;

void main() {
    vec2 n = gl_PointCoord * 2.0 - 1.0;
    n.y = -n.y;
    vec2 perp = vec2(-v_axis.y, v_axis.x);
    vec2 q = vec2(dot(n, v_axis), dot(n, perp));
    vec2 e = vec2(q.x, q.y * max(v_stretch, 1e-5));
    float r2 = dot(e, e);
    if (r2 > 1.0) discard;
    float t = sqrt(1.0 - r2);
    out_thickness = t * v_radius * 2.0;
}
"""


_FULLSCREEN_VS = """
#version 430 core

out vec2 v_uv;

void main() {
    vec2 p = vec2((gl_VertexID == 1) ? 3.0 : -1.0,
                  (gl_VertexID == 2) ? 3.0 : -1.0);
    v_uv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""


_BILATERAL_FS = """
#version 430 core

in vec2 v_uv;

uniform sampler2D u_depth;
uniform vec2 u_direction;
uniform int u_radius;
uniform float u_depth_falloff;
uniform float u_spatial_falloff;

layout(location = 0) out float out_depth;

void main() {
    float c = texture(u_depth, v_uv).r;
    if (c == 0.0) {
        out_depth = 0.0;
        return;
    }
    float sum = c;
    float w_sum = 1.0;
    for (int i = 1; i <= u_radius; ++i) {
        float fi = float(i);
        float w_s = exp(-fi * fi * u_spatial_falloff);
        float sp = texture(u_depth, v_uv + fi * u_direction).r;
        float sn = texture(u_depth, v_uv - fi * u_direction).r;
        if (sp != 0.0) {
            float dz = sp - c;
            float w = w_s * exp(-dz * dz * u_depth_falloff);
            sum += sp * w;
            w_sum += w;
        }
        if (sn != 0.0) {
            float dz = sn - c;
            float w = w_s * exp(-dz * dz * u_depth_falloff);
            sum += sn * w;
            w_sum += w;
        }
    }
    out_depth = sum / w_sum;
}
"""


_COMPOSITE_FS = """
#version 430 core

in vec2 v_uv;

uniform sampler2D u_depth;
uniform sampler2D u_thickness;

uniform mat4 u_inv_proj;
uniform mat4 u_proj;
uniform vec2 u_viewport;
uniform vec3 u_fluid_color;
uniform float u_absorption;
uniform vec3 u_background;
uniform vec3 u_light_view;
uniform float u_fresnel_power;
uniform float u_min_alpha;

layout(location = 0) out vec4 out_color;

vec3 reconstruct_view(vec2 uv, float view_z) {
    // Build a ray through (uv → NDC) on the near plane, then scale so its z
    // matches the sampled view-space depth.
    vec4 clip = vec4(uv * 2.0 - 1.0, 0.0, 1.0);
    vec4 v = u_inv_proj * clip;
    v /= v.w;
    return v.xyz * (view_z / v.z);
}

void main() {
    float vz = texture(u_depth, v_uv).r;
    if (vz == 0.0) discard;

    vec3 P = reconstruct_view(v_uv, vz);

    vec2 texel = 1.0 / u_viewport;
    float zpx = texture(u_depth, v_uv + vec2(texel.x, 0.0)).r;
    float zmx = texture(u_depth, v_uv - vec2(texel.x, 0.0)).r;
    float zpy = texture(u_depth, v_uv + vec2(0.0, texel.y)).r;
    float zmy = texture(u_depth, v_uv - vec2(0.0, texel.y)).r;

    vec3 Ppx = reconstruct_view(v_uv + vec2(texel.x, 0.0), zpx);
    vec3 Pmx = reconstruct_view(v_uv - vec2(texel.x, 0.0), zmx);
    vec3 Ppy = reconstruct_view(v_uv + vec2(0.0, texel.y), zpy);
    vec3 Pmy = reconstruct_view(v_uv - vec2(0.0, texel.y), zmy);

    // Prefer the smaller-magnitude difference in each direction to preserve
    // silhouettes at edges where neighbours are sky / empty.
    bool prefer_px = (zpx != 0.0
                      && (zmx == 0.0 || abs(Ppx.z - P.z) < abs(P.z - Pmx.z)));
    bool prefer_py = (zpy != 0.0
                      && (zmy == 0.0 || abs(Ppy.z - P.z) < abs(P.z - Pmy.z)));
    vec3 dx = prefer_px ? (Ppx - P) : (P - Pmx);
    vec3 dy = prefer_py ? (Ppy - P) : (P - Pmy);
    vec3 N = normalize(cross(dx, dy));

    float thickness = max(texture(u_thickness, v_uv).r, 0.0);

    vec3 V = normalize(-P);
    vec3 L = normalize(u_light_view);
    vec3 H = normalize(V + L);

    float NdotV = max(dot(N, V), 0.0);
    float NdotL = max(dot(N, L), 0.0);
    float NdotH = max(dot(N, H), 0.0);

    float F0 = 0.04;
    float F = F0 + (1.0 - F0) * pow(1.0 - NdotV, u_fresnel_power);

    vec3 absorbed = exp(-u_absorption * thickness * (vec3(1.0) - u_fluid_color));
    vec3 transmit = u_background * absorbed;

    float spec = pow(NdotH, 80.0);
    vec3 surface = mix(transmit, u_background, F) + vec3(1.0) * spec * 0.6;
    surface += u_fluid_color * NdotL * 0.15;

    vec4 clip = u_proj * vec4(P, 1.0);
    gl_FragDepth = (clip.z / clip.w) * 0.5 + 0.5;

    float alpha = clamp(thickness * 4.0, u_min_alpha, 1.0);
    out_color = vec4(surface, alpha);
}
"""


class SSFOpenGLRenderer(IndirectOpenGLBase):
    """Screen-space fluid renderer reading particles from the SPHERE bin."""

    _MAX_EMITTER_SIZES = 64

    def __init__(self, bridge):
        super().__init__(bridge)
        # Imported SSBOs (from Theron).
        self._pos_vbo: int | None = None
        self._rad_vbo: int | None = None
        self._radius_handle: object | None = None
        self._vel_vbo: int | None = None
        self._velocity_handle: object | None = None
        self._emit_idx_vbo: int | None = None
        self._prefix_vbo: int | None = None
        self._binned_vbo: int | None = None
        self._prefix_handle: int | None = None
        self._binned_handle: int | None = None
        self._has_radius = False
        self._has_velocity = False

        # Dummy VBO for the particle VAO's required attribute 0.
        self._mesh_vbo: int | None = None
        self._point_vao: int | None = None
        # Empty VAO for the full-screen triangle draws.
        self._fs_vao: int | None = None

        # Fallback radius VBO (unused for rendering; kept for API parity with
        # other imposter renderers — the radius comes from uniforms anyway).
        self._uniform_size_vbo: int | None = None

        # Programs for each pass.
        self._prog_depth: int | None = None
        self._prog_thickness: int | None = None
        self._prog_blur: int | None = None
        self._prog_composite: int | None = None

        # Uniform location caches.
        self._u_depth: dict[str, int] = {}
        self._u_thick: dict[str, int] = {}
        self._u_blur: dict[str, int] = {}
        self._u_comp: dict[str, int] = {}

        # FBOs + textures (lazy; resized on viewport change).
        self._fbo_depth: int | None = None
        self._fbo_thickness: int | None = None
        self._fbo_thickness_aux: int | None = None
        self._fbo_blur_a: int | None = None
        self._fbo_blur_b: int | None = None
        self._tex_depth: int | None = None
        self._tex_thickness: int | None = None
        self._tex_thickness_aux: int | None = None
        self._tex_blur_a: int | None = None
        self._tex_blur_b: int | None = None
        self._rb_depth: int | None = None
        self._fbo_size: tuple[int, int] = (0, 0)

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def _free_fbos(self) -> None:
        if not _GL_OK:
            self._fbo_depth = self._fbo_thickness = self._fbo_thickness_aux = None
            self._fbo_blur_a = self._fbo_blur_b = None
            self._tex_depth = self._tex_thickness = self._tex_thickness_aux = None
            self._tex_blur_a = self._tex_blur_b = None
            self._rb_depth = None
            self._fbo_size = (0, 0)
            return
        for fbo in (
            self._fbo_depth,
            self._fbo_thickness,
            self._fbo_thickness_aux,
            self._fbo_blur_a,
            self._fbo_blur_b,
        ):
            if fbo is not None:
                try:
                    glDeleteFramebuffers(1, [fbo])
                except Exception:
                    pass
        for tex in (
            self._tex_depth,
            self._tex_thickness,
            self._tex_thickness_aux,
            self._tex_blur_a,
            self._tex_blur_b,
        ):
            if tex is not None:
                try:
                    glDeleteTextures(1, [tex])
                except Exception:
                    pass
        if self._rb_depth is not None:
            try:
                glDeleteRenderbuffers(1, [self._rb_depth])
            except Exception:
                pass
        self._fbo_depth = self._fbo_thickness = self._fbo_thickness_aux = None
        self._fbo_blur_a = self._fbo_blur_b = None
        self._tex_depth = self._tex_thickness = self._tex_thickness_aux = None
        self._tex_blur_a = self._tex_blur_b = None
        self._rb_depth = None
        self._fbo_size = (0, 0)

    def _free_programs(self) -> None:
        if not _GL_OK:
            self._prog_depth = self._prog_thickness = None
            self._prog_blur = self._prog_composite = None
            return
        for prog in (
            self._prog_depth,
            self._prog_thickness,
            self._prog_blur,
            self._prog_composite,
        ):
            if prog is not None:
                try:
                    glDeleteProgram(prog)
                except Exception:
                    pass
        self._prog_depth = self._prog_thickness = None
        self._prog_blur = self._prog_composite = None
        self._u_depth = {}
        self._u_thick = {}
        self._u_blur = {}
        self._u_comp = {}

    def _free_resources(self) -> None:
        if _GL_OK:
            for buf in (self._mesh_vbo, self._uniform_size_vbo):
                if buf is not None:
                    try:
                        glDeleteBuffers(1, [buf])
                    except Exception:
                        pass
            if self._point_vao is not None:
                try:
                    glDeleteVertexArrays(1, [self._point_vao])
                except Exception:
                    pass
            if self._fs_vao is not None:
                try:
                    glDeleteVertexArrays(1, [self._fs_vao])
                except Exception:
                    pass
        self._mesh_vbo = None
        self._uniform_size_vbo = None
        self._point_vao = None
        self._fs_vao = None
        self._pos_vbo = None
        self._rad_vbo = None
        self._radius_handle = None
        self._vel_vbo = None
        self._velocity_handle = None
        self._emit_idx_vbo = None
        self._prefix_vbo = None
        self._binned_vbo = None
        self._prefix_handle = None
        self._binned_handle = None
        self._has_radius = False
        self._has_velocity = False
        self._free_indirect_resources()
        self._free_programs()
        self._free_fbos()
        # We own our VAOs/programs via _point_vao / _prog_* above, so null the
        # base-class references to avoid double-delete in super._free_resources.
        self._vao = None
        self._program = None
        super()._free_resources()

    # ------------------------------------------------------------------
    # FBO setup
    # ------------------------------------------------------------------

    def _ensure_fbos(self, width: int, height: int) -> bool:
        if width <= 0 or height <= 0:
            return False
        if self._fbo_size == (width, height) and self._fbo_depth is not None:
            return True
        prev_draw_fb = int(glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING))
        prev_tex_2d = int(glGetIntegerv(GL_TEXTURE_BINDING_2D))
        prev_rb = int(glGetIntegerv(GL_RENDERBUFFER_BINDING))
        self._free_fbos()
        try:
            # Color R32F textures — zero-initialised, nearest filter so we read
            # back exactly what the fragment wrote.
            def _mk_r32f_tex(w: int, h: int) -> int:
                tex = _gen_one(glGenTextures)
                glBindTexture(GL_TEXTURE_2D, tex)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, w, h, 0, GL_RED, GL_FLOAT, None)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                glBindTexture(GL_TEXTURE_2D, 0)
                return tex

            self._tex_depth = _mk_r32f_tex(width, height)
            self._tex_thickness = _mk_r32f_tex(width, height)
            self._tex_thickness_aux = _mk_r32f_tex(width, height)
            self._tex_blur_a = _mk_r32f_tex(width, height)
            self._tex_blur_b = _mk_r32f_tex(width, height)

            self._rb_depth = _gen_one(glGenRenderbuffers)
            glBindRenderbuffer(GL_RENDERBUFFER, self._rb_depth)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height)
            glBindRenderbuffer(GL_RENDERBUFFER, 0)

            def _mk_fbo(color_tex: int, depth_rb: int | None) -> int:
                fbo = _gen_one(glGenFramebuffers)
                glBindFramebuffer(GL_FRAMEBUFFER, fbo)
                glFramebufferTexture2D(
                    GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_tex, 0
                )
                if depth_rb is not None:
                    glFramebufferRenderbuffer(
                        GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_rb
                    )
                status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
                if status != GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"SSF FBO incomplete: 0x{int(status):x}")
                return fbo

            self._fbo_depth = _mk_fbo(self._tex_depth, self._rb_depth)
            self._fbo_thickness = _mk_fbo(self._tex_thickness, None)
            self._fbo_thickness_aux = _mk_fbo(self._tex_thickness_aux, None)
            self._fbo_blur_a = _mk_fbo(self._tex_blur_a, None)
            self._fbo_blur_b = _mk_fbo(self._tex_blur_b, None)

            self._fbo_size = (width, height)
            return True
        except Exception:
            self._free_fbos()
            return False
        finally:
            glBindFramebuffer(GL_FRAMEBUFFER, prev_draw_fb)
            glBindTexture(GL_TEXTURE_2D, prev_tex_2d)
            glBindRenderbuffer(GL_RENDERBUFFER, prev_rb)

    # ------------------------------------------------------------------
    # Import SSBOs + compile shaders
    # ------------------------------------------------------------------

    def _ensure_import(
        self,
        pos: BufferExport,
        prefix: BufferExport,
        binned: BufferExport,
        emit_idx: BufferExport,
        velocity: BufferExport | None = None,
        radius: BufferExport | None = None,
    ) -> bool:
        pos_id = buf_identity(pos)
        prefix_id = buf_identity(prefix)
        binned_id = buf_identity(binned)
        radius_id = buf_identity(radius)
        velocity_id = buf_identity(velocity)
        if (
            self._imported
            and self._handle == pos_id
            and self._prefix_handle == prefix_id
            and self._binned_handle == binned_id
            and self._radius_handle == radius_id
            and self._velocity_handle == velocity_id
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
        self._vel_vbo = self._import(velocity)
        if None in (self._pos_vbo, self._prefix_vbo, self._binned_vbo, self._emit_idx_vbo):
            self._free_resources()
            return False

        try:
            # Point VAO: just a dummy vertex attribute at location 0 so the
            # VAO is "valid". Our VS reads everything from SSBOs.
            mesh = _gen_one(glGenBuffers)
            dummy = np.zeros(3, dtype=np.float32)
            glBindBuffer(GL_ARRAY_BUFFER, mesh)
            glBufferData(GL_ARRAY_BUFFER, dummy.nbytes, dummy, GL_STATIC_DRAW)
            self._mesh_vbo = mesh

            point_vao = _gen_one(glGenVertexArrays)
            glBindVertexArray(point_vao)
            glBindBuffer(GL_ARRAY_BUFFER, mesh)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
            glEnableVertexAttribArray(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            self._point_vao = point_vao

            # Empty VAO for the full-screen triangle (vertex positions come
            # from gl_VertexID).
            fs_vao = _gen_one(glGenVertexArrays)
            self._fs_vao = fs_vao
        except Exception:
            self._free_resources()
            return False

        # Compile programs.
        prog_depth = self._bridge.compile_program(_IMPOSTER_VS, _DEPTH_FS)
        prog_thickness = self._bridge.compile_program(_IMPOSTER_VS, _THICKNESS_FS)
        prog_blur = self._bridge.compile_program(_FULLSCREEN_VS, _BILATERAL_FS)
        prog_composite = self._bridge.compile_program(_FULLSCREEN_VS, _COMPOSITE_FS)
        if None in (prog_depth, prog_thickness, prog_blur, prog_composite):
            self._free_resources()
            return False
        self._prog_depth = prog_depth
        self._prog_thickness = prog_thickness
        self._prog_blur = prog_blur
        self._prog_composite = prog_composite

        if not self._ensure_compute_program() or not self._ensure_indirect_buffers():
            self._free_resources()
            return False

        def _locs(program: int, names: tuple[str, ...]) -> dict[str, int]:
            return {name: glGetUniformLocation(program, name) for name in names}

        self._u_depth = _locs(
            prog_depth,
            (
                "u_view",
                "u_proj",
                "u_viewport",
                "u_fallback_radius",
                "u_use_radius",
                "u_emitter_sizes_count",
                "u_emitter_sizes",
                "u_use_anisotropy",
                "u_aniso_scale",
                "u_aniso_max_stretch",
            ),
        )
        self._u_thick = _locs(
            prog_thickness,
            (
                "u_view",
                "u_proj",
                "u_viewport",
                "u_fallback_radius",
                "u_use_radius",
                "u_emitter_sizes_count",
                "u_emitter_sizes",
                "u_use_anisotropy",
                "u_aniso_scale",
                "u_aniso_max_stretch",
            ),
        )
        self._u_blur = _locs(
            prog_blur,
            ("u_depth", "u_direction", "u_radius", "u_depth_falloff", "u_spatial_falloff"),
        )
        self._u_comp = _locs(
            prog_composite,
            (
                "u_depth",
                "u_thickness",
                "u_inv_proj",
                "u_proj",
                "u_viewport",
                "u_fluid_color",
                "u_absorption",
                "u_background",
                "u_light_view",
                "u_fresnel_power",
                "u_min_alpha",
            ),
        )

        # Leave self._vao / self._program as None — we manage our own VAOs and
        # programs explicitly, and the base-class _free_resources() checks for
        # None to skip deletion.
        self._handle = pos_id
        self._prefix_handle = prefix_id
        self._binned_handle = binned_id
        self._radius_handle = radius_id
        self._velocity_handle = velocity_id
        self._imported = True
        self._has_radius = self._rad_vbo is not None
        self._has_velocity = self._vel_vbo is not None
        return True

    # ------------------------------------------------------------------
    # Passes
    # ------------------------------------------------------------------

    def _apply_sphere_uniforms(
        self,
        u: dict[str, int],
        view,
        proj,
        viewport,
        fallback_r: float,
        emitter_sizes,
        use_anisotropy: bool,
        anisotropy_scale: float,
        anisotropy_max_stretch: float,
    ) -> None:
        glUniformMatrix4fv(u["u_view"], 1, True, view)
        glUniformMatrix4fv(u["u_proj"], 1, True, proj)
        glUniform2f(u["u_viewport"], float(viewport[0]), float(viewport[1]))
        glUniform1f(u["u_fallback_radius"], float(fallback_r))
        glUniform1i(u["u_use_radius"], 1 if self._has_radius else 0)
        glUniform1i(u["u_emitter_sizes_count"], len(emitter_sizes))
        if emitter_sizes and u["u_emitter_sizes"] is not None and u["u_emitter_sizes"] >= 0:
            glUniform1fv(u["u_emitter_sizes"], len(emitter_sizes), list(emitter_sizes))
        glUniform1i(u["u_use_anisotropy"], 1 if use_anisotropy else 0)
        glUniform1f(u["u_aniso_scale"], float(max(0.0, anisotropy_scale)))
        glUniform1f(u["u_aniso_max_stretch"], float(max(1.0, anisotropy_max_stretch)))

    def _draw_particles(self) -> None:
        glBindVertexArray(self._point_vao)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, self._pos_vbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, self._binned_vbo)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, self._draw_state_ssbo)
        if self._has_radius and self._rad_vbo is not None:
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 6, self._rad_vbo)
        else:
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 6, 0)
        if self._has_velocity and self._vel_vbo is not None:
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, self._vel_vbo)
        else:
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 7, 0)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 8, self._emit_idx_vbo)

        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, self._indirect_cmd)
        glDrawArraysIndirect(GL_POINTS, None)
        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, 0)

    def _pass_depth(
        self,
        view,
        proj,
        viewport,
        fallback_r: float,
        emitter_sizes,
        use_anisotropy: bool,
        anisotropy_scale: float,
        anisotropy_max_stretch: float,
    ) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_depth)
        glViewport(0, 0, int(viewport[0]), int(viewport[1]))
        glEnable(GL_DEPTH_TEST)
        glDepthMask(True)
        glDepthFunc(GL_LEQUAL)
        glClearDepth(1.0)
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glDisable(GL_BLEND)
        glEnable(GL_PROGRAM_POINT_SIZE)

        glUseProgram(self._prog_depth)
        self._apply_sphere_uniforms(
            self._u_depth,
            view,
            proj,
            viewport,
            fallback_r,
            emitter_sizes,
            use_anisotropy,
            anisotropy_scale,
            anisotropy_max_stretch,
        )
        self._draw_particles()

    def _pass_thickness(
        self,
        view,
        proj,
        viewport,
        fallback_r: float,
        emitter_sizes,
        use_anisotropy: bool,
        anisotropy_scale: float,
        anisotropy_max_stretch: float,
    ) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_thickness)
        glViewport(0, 0, int(viewport[0]), int(viewport[1]))
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glDisable(GL_DEPTH_TEST)
        glDepthMask(False)
        glEnable(GL_BLEND)
        glBlendFunc(GL_ONE, GL_ONE)
        glEnable(GL_PROGRAM_POINT_SIZE)

        glUseProgram(self._prog_thickness)
        self._apply_sphere_uniforms(
            self._u_thick,
            view,
            proj,
            viewport,
            fallback_r,
            emitter_sizes,
            use_anisotropy,
            anisotropy_scale,
            anisotropy_max_stretch,
        )
        self._draw_particles()

    def _pass_blur(
        self,
        viewport,
        iterations: int,
        radius: int,
        depth_falloff: float,
    ) -> int:
        """Run separable bilateral blur; returns the texture id with the final result.

        When ``iterations`` is 0 the input depth texture is returned unchanged.
        """
        if iterations <= 0:
            return self._tex_depth

        w, h = int(viewport[0]), int(viewport[1])
        glViewport(0, 0, w, h)
        glDisable(GL_DEPTH_TEST)
        glDepthMask(False)
        glDisable(GL_BLEND)

        glUseProgram(self._prog_blur)
        glUniform1i(self._u_blur["u_depth"], 0)
        glUniform1i(self._u_blur["u_radius"], int(radius))
        # Scale spatial falloff so a wider radius still reaches edge taps.
        spatial = 1.0 / max(float(radius) * float(radius) * 0.25, 1e-3)
        glUniform1f(self._u_blur["u_spatial_falloff"], spatial)
        glUniform1f(self._u_blur["u_depth_falloff"], float(depth_falloff))

        src_tex = self._tex_depth
        glBindVertexArray(self._fs_vao)
        for _ in range(int(iterations)):
            # Horizontal → fbo_a (tex_blur_a)
            glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_blur_a)
            glUniform2f(self._u_blur["u_direction"], 1.0 / max(w, 1), 0.0)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, src_tex)
            glDrawArrays(GL_TRIANGLES, 0, 3)

            # Vertical → fbo_b (tex_blur_b)
            glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_blur_b)
            glUniform2f(self._u_blur["u_direction"], 0.0, 1.0 / max(h, 1))
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._tex_blur_a)
            glDrawArrays(GL_TRIANGLES, 0, 3)

            src_tex = self._tex_blur_b
        return src_tex

    def _pass_blur_thickness(self, viewport, iterations: int, radius: int) -> None:
        """Gaussian blur the accumulated thickness (reuses the bilateral shader
        with ``u_depth_falloff = 0`` → spatial weights only).

        Ping-pongs between ``_tex_thickness`` and ``_tex_thickness_aux`` so the
        final result lives in ``_tex_thickness`` (what the composite samples).
        """
        if iterations <= 0:
            return

        w, h = int(viewport[0]), int(viewport[1])
        glViewport(0, 0, w, h)
        glDisable(GL_DEPTH_TEST)
        glDepthMask(False)
        glDisable(GL_BLEND)

        glUseProgram(self._prog_blur)
        glUniform1i(self._u_blur["u_depth"], 0)
        glUniform1i(self._u_blur["u_radius"], int(radius))
        spatial = 1.0 / max(float(radius) * float(radius) * 0.25, 1e-3)
        glUniform1f(self._u_blur["u_spatial_falloff"], spatial)
        # Zero depth falloff ⇒ the shader's range-weight term collapses to 1,
        # giving a plain separable gaussian — correct for thickness, which has
        # no meaningful "depth" and should blur uniformly.
        glUniform1f(self._u_blur["u_depth_falloff"], 0.0)

        glBindVertexArray(self._fs_vao)
        for _ in range(int(iterations)):
            # Horizontal: tex_thickness → tex_thickness_aux
            glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_thickness_aux)
            glUniform2f(self._u_blur["u_direction"], 1.0 / max(w, 1), 0.0)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._tex_thickness)
            glDrawArrays(GL_TRIANGLES, 0, 3)

            # Vertical: tex_thickness_aux → tex_thickness
            glBindFramebuffer(GL_FRAMEBUFFER, self._fbo_thickness)
            glUniform2f(self._u_blur["u_direction"], 0.0, 1.0 / max(h, 1))
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._tex_thickness_aux)
            glDrawArrays(GL_TRIANGLES, 0, 3)

    def _pass_composite(
        self,
        default_fbo: int,
        viewport,
        inv_proj,
        proj,
        smoothed_depth_tex: int,
        base_color,
        absorption: float,
        fresnel_power: float,
        min_alpha: float,
        background_color,
    ) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, default_fbo)
        glViewport(0, 0, int(viewport[0]), int(viewport[1]))
        glEnable(GL_DEPTH_TEST)
        glDepthMask(True)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glUseProgram(self._prog_composite)
        glUniformMatrix4fv(self._u_comp["u_inv_proj"], 1, True, inv_proj)
        glUniformMatrix4fv(self._u_comp["u_proj"], 1, True, proj)
        glUniform2f(self._u_comp["u_viewport"], float(viewport[0]), float(viewport[1]))
        r, g, b, _a = base_color
        glUniform3f(self._u_comp["u_fluid_color"], float(r), float(g), float(b))
        glUniform1f(self._u_comp["u_absorption"], float(absorption))
        br, bg, bb = background_color
        glUniform3f(self._u_comp["u_background"], float(br), float(bg), float(bb))
        # Light direction in view space (roughly over-the-shoulder).
        glUniform3f(self._u_comp["u_light_view"], 0.4, 0.5, 1.0)
        glUniform1f(self._u_comp["u_fresnel_power"], float(fresnel_power))
        glUniform1f(self._u_comp["u_min_alpha"], max(0.0, min(1.0, float(min_alpha))))

        glUniform1i(self._u_comp["u_depth"], 0)
        glUniform1i(self._u_comp["u_thickness"], 1)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, smoothed_depth_tex)
        glActiveTexture(GL_TEXTURE0 + 1)
        glBindTexture(GL_TEXTURE_2D, self._tex_thickness)
        glActiveTexture(GL_TEXTURE0)

        glBindVertexArray(self._fs_vao)
        glDrawArrays(GL_TRIANGLES, 0, 3)

    # ------------------------------------------------------------------
    # Matrix helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_proj_inv_proj(context):
        """Return (proj, inv_proj) as row-major 16-float flat lists."""
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return None
        try:
            proj_mat = region_data.window_matrix
            inv_proj_mat = proj_mat.inverted()
            proj = [proj_mat[i][j] for i in range(4) for j in range(4)]
            inv_proj = [inv_proj_mat[i][j] for i in range(4) for j in range(4)]
            return proj, inv_proj
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def draw(self, context, pipeline, scene, params) -> bool:
        if not _GL_OK:
            return False
        prep = self._prepare_draw(context, pipeline, params)
        if prep is None:
            return False
        mvp, view = prep
        proj_pair = self._get_proj_inv_proj(context)
        if proj_pair is None:
            return False
        proj, inv_proj = proj_pair

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
        vel = self.fetch_gpu_buffer(pipeline, "velocity")
        if not self._ensure_import(
            pos,
            prefix_buf,
            binned_buf,
            emit_idx,
            vel if vel and vel.valid else None,
            rad if rad and rad.valid else None,
        ):
            return False

        vp = glGetIntegerv(GL_VIEWPORT)
        vp_w, vp_h = int(vp[2]), int(vp[3])
        if vp_w <= 0 or vp_h <= 0:
            return False
        if not self._ensure_fbos(vp_w, vp_h):
            return False
        viewport = (vp_w, vp_h)

        # Bridge save/restore covers viewport, FBO, enables, blend/depth funcs,
        # clear values, point size, etc. We capture draw_fb separately because
        # the composite pass needs it as its render target.
        saved = self._bridge.save_state()
        prev_draw_fb = int(glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING))

        try:
            glDisable(GL_CULL_FACE)

            emitter_sizes = tuple(
                float(s) for s in params.emitter_point_sizes[: self._MAX_EMITTER_SIZES]
            )
            fallback_radius = float(params.size)
            use_anisotropy = bool(
                getattr(params, "ssf_use_anisotropy", False) and self._has_velocity
            )
            anisotropy_scale = float(getattr(params, "ssf_anisotropy_scale", 0.2))
            anisotropy_max_stretch = float(getattr(params, "ssf_anisotropy_max_stretch", 3.0))

            # Compute dispatch: writes cmd.instanceCount = particles in the
            # SSF bin (Theron's ID_NX_EMITTER_DISPLAY_MODE_SSF, index 14).
            self._dispatch_compute(
                self._prefix_vbo,
                self.mode_bin_index("SSF"),
                _VERTS_PER_INSTANCE,
                prefix_buf.size // 4,
            )

            self._pass_depth(
                view,
                proj,
                viewport,
                fallback_radius,
                emitter_sizes,
                use_anisotropy,
                anisotropy_scale,
                anisotropy_max_stretch,
            )
            self._pass_thickness(
                view,
                proj,
                viewport,
                fallback_radius,
                emitter_sizes,
                use_anisotropy,
                anisotropy_scale,
                anisotropy_max_stretch,
            )
            smoothed = self._pass_blur(
                viewport,
                int(getattr(params, "ssf_blur_iterations", 3)),
                int(getattr(params, "ssf_blur_radius", 8)),
                float(getattr(params, "ssf_blur_depth_falloff", 50.0)),
            )
            self._pass_blur_thickness(
                viewport,
                int(getattr(params, "ssf_thickness_blur_iterations", 2)),
                int(getattr(params, "ssf_blur_radius", 8)),
            )
            self._pass_composite(
                prev_draw_fb,
                viewport,
                inv_proj,
                proj,
                smoothed,
                params.color,
                float(getattr(params, "ssf_absorption", 2.0)),
                float(getattr(params, "ssf_fresnel_power", 5.0)),
                float(getattr(params, "ssf_min_alpha", 0.3)),
                tuple(getattr(params, "ssf_background_color", (0.55, 0.65, 0.78))),
            )
        except Exception:
            self._free_resources()
            return False
        finally:
            # save_state only tracks texture unit 0, so unbind our unit-1 slot
            # (used for the thickness sampler) before handing control back.
            glActiveTexture(GL_TEXTURE0 + 1)
            glBindTexture(GL_TEXTURE_2D, 0)
            self._bridge.restore_state(saved)
        return True
