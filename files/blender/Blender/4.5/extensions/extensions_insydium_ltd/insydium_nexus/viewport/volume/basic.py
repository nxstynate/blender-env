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

"""Pure-Python volume renderers for nxExplosiaFX.

Provides the "BASIC" volume backend with two render styles:

  RAYMARCHER: full-viewport-quad approach

  SLICES:     view-aligned clipped-volume-slice stack composited
              front-to-back with a per-channel transfer-function shader

VolumeBasicRenderer is a thin dispatcher registered with the backend
registry. This routes draws to one of the two style classes, which each
own all GPU resources for their path.

This BASIC method has limitations:
- CPU->GPU data copies required to populate textures.
"""

from __future__ import annotations

import numpy as np

from ..core.renderer import NexusRenderer

# ---------------------------------------------------------------------------
# Gaussian volume texture
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shader sources
# ---------------------------------------------------------------------------

_RAYMARCHER_VERT_SRC = """\
void main() {
    gl_Position = vec4(pos.xy, -1.0, 1.0);
    ndcpos = pos.xy;
}
"""

_RAYMARCHER_FRAG_SRC = """\

// Domain bounds in model space (unit cube centred at origin)
const float boxMin = -0.5f;
const float boxMax =  0.5f;

// --- Black body -> RGB (Stefan-Boltzmann T^4 intensity scaling)
vec3 BlackBodyRGB(float T)
{
  // Padé approximants fitted to the coordinates on a u, v chromaticity diagram
  // of the blackbody emission locus
  float u = (0.860117757f + 1.54118254e-4f * T + 1.28641212e-7f * T * T) /
            (1.f + 8.42420235e-4f * T + 7.08145163e-7f * T * T);
  float v = (0.317398726f + 4.22806245e-5f * T + 4.20481691e-8f * T * T) /
            (1.f - 2.89741816e-5f * T + 1.61456053e-7f * T * T);

  // Convert u,v to chromaticity coordinates in the CIE 1931 color space
  float x = 3.f * u / (2.f * u - 8.f * v + 4.f);
  float y = 2.f * v / (2.f * u - 8.f * v + 4.f);
  float z = 1.f - x - y;

  // Tristimulus values XYZ from approximate integrals of color matching functions
  //  Assume Y (lumunance) = 1.
  vec3 XYZ = vec3( x/y, 1.f, z/y );

  // The following is the transformation matrix from tristimulus values XYZ
  // to RGB using sRGB D65 mapping
  mat3 XYZtoRGB = mat3(
      3.2404542f, -0.9692660f, 0.0556434f,
     -1.5371385f, 1.8760108f, -0.2040259f,
     -0.4985314f, 0.0415560f, 1.0572252f
  );

  vec3 RGB = XYZtoRGB * XYZ;

  // Normalized Tn = T/2500K; Stefan-Boltzmann-type intensity will be scaled to 1 @ 2500K
  float Tn = 0.0004f * T;

  return RGB * Tn * Tn * Tn * Tn;
}


// Secondary ray: light transmittance calculation
// Calculates how much ambient light arrives at position "startPos".
// Uses total extinction (we dont care about decay channels - absorption or
// scattering in any direction,
// just how much of the ray survives the journey to startPos).
vec3 TraceUniformLightTransmittance(vec3 startPos, vec3 lightDir,
                                    vec3 sigmaExt, int maxSteps, float stepSize)
{
  vec3 pos = startPos;
  float densityPrev = max(0.0, texture(densityTex, pos).r);
  vec3 opticalDepth = vec3(0.f, 0.f, 0.f);

  for (int j = 0; j < maxSteps; ++j)
  {
      vec3 nextPos = pos - lightDir * stepSize;
      // Clamp the position to the domain for partial-step absorption when ray exits
      vec3 clampedNextPos = clamp(nextPos, 0.f, 1.f);
      // What fraction of the step size survived clamping?
      // Assumes lightDir normalized
      float stepFrac = clamp(dot(pos - clampedNextPos, lightDir) / stepSize, 0.f, 1.f);

      float densityCurr = max(0.0, texture(densityTex, clampedNextPos).r);
      float densityAvg = 0.5f * (densityPrev + densityCurr);

      // Accumulate optical depth
      opticalDepth += sigmaExt * densityAvg * (stepSize * stepFrac);

      // Early exit possibilities:
      // 1. Stepped over boundary
      if (stepFrac < 0.9999f)
        break;
      // 2. Ambient light already fully absorbed / scattered (<1% remaining)
      if (all(greaterThan(opticalDepth, vec3(4.61f))))
        break;

      densityPrev = densityCurr;
      pos = nextPos;
  }

  vec3 lightTrans = vec3(1.f, 1.f, 1.f);
  // Taylor expand for small exponents
  if (all(lessThan(opticalDepth, vec3(0.01f))))
  {
    lightTrans *= (1.0f - opticalDepth + 0.5f * opticalDepth * opticalDepth -
                   opticalDepth * opticalDepth * opticalDepth / 6.0f);
  }
  else
  {
    lightTrans *= exp(-opticalDepth);
  }

  return lightTrans;
}

void main()
{
    // Unpack all tunable parameters from UBO into local variables.
    // Smoke scattering
    vec3  smokeAbsorbColor       = rcBuf.smokeAbsorbColorExtinction.xyz;
    float smokeExtinctionCoef    = rcBuf.smokeAbsorbColorExtinction.w;
    float smokeAlbedo            = rcBuf.smokeAlbedoAnisotropy.x;
    float smokeScatterAnisotropy = rcBuf.smokeAlbedoAnisotropy.y;
    // Flame emission
    float flameEmitMinT          = rcBuf.flame.x;
    float flameIntensity         = rcBuf.flame.y;
    // Ambient lighting
    vec3  lightDirn              = rcBuf.lightDirnIntensity.xyz;
    float lightIntensity         = rcBuf.lightDirnIntensity.w;
    vec3  lightColor             = rcBuf.lightColor.xyz;
    // Hot gas emission
    vec3  hotGasEmitColor        = rcBuf.hotGasEmitColorStrength.xyz;
    float hotGasEmitStrength     = rcBuf.hotGasEmitColorStrength.w;
    int   hotGasEmitType         = int(round(rcBuf.hotGasEmitTypeVec.x));
    // Ray marching
    float rayStepSize            = rcBuf.rayMarch.x;
    int   rayMaxSteps            = int(round(rcBuf.rayMarch.y));
    float globalOpacity          = rcBuf.rayMarch.z;

    // ========================================
    // RAY SETUP
    // ========================================
    // Reconstruct rays from near/far clip-plane points through the inverse P and V matrices.
    vec4 nearclippos = vec4(ndcpos, -1.f, 1.f);
    vec4 farclippos  = vec4(ndcpos,  1.f, 1.f);

    // Clip -> view space
    vec4 nearViewPos = rcBuf.invProjMatrix * nearclippos;
    vec4 farViewPos  = rcBuf.invProjMatrix * farclippos;

    // Perspective divide
    nearViewPos /= max(nearViewPos.w, 1e-8);
    farViewPos  /= max(farViewPos.w,  1e-8);

    // View -> world space
    vec3 rayDirn   = normalize((rcBuf.invViewMatrix * (farViewPos - nearViewPos)).xyz);
    vec3 rayOrigin = (rcBuf.invViewMatrix * nearViewPos).xyz;

    // World -> model space (domain_size already included in invModelMatrix)
    vec3 rayDirn_model   = normalize((rcBuf.invModelMatrix * vec4(rayDirn, 0.f)).xyz);
    vec3 rayOrigin_model = (rcBuf.invModelMatrix * vec4(rayOrigin, 1.f)).xyz;

    // ========================================
    // RAY-BOX INTERSECTION (slab method)
    // ========================================
    float tMin = 0.f;
    float tMax = 1e6f;
    for (int idir = 0; idir < 3; ++idir)
    {
        if (abs(rayDirn_model[idir]) < 1e-6f)
        {
            // Ray parallel to slab — miss if origin is outside
            if (rayOrigin_model[idir] < boxMin || rayOrigin_model[idir] > boxMax)
            {
                tMin = 1e6f;
                tMax = -1e6f;
                break;
            }
            continue;
        }
        float invD = 1.f / rayDirn_model[idir];
        float t0   = (boxMin - rayOrigin_model[idir]) * invD;
        float t1   = (boxMax - rayOrigin_model[idir]) * invD;
        if (invD < 0.f)
        {
            float tmp = t0;
            t0 = t1;
            t1 = tmp;
        }
        tMin = max(tMin, t0);
        tMax = min(tMax, t1);
    }

    // Check intersection is valid. If ray is missing the domain, discard this pixel / fragment.
    if (tMax <= tMin)
        discard;  // Ray misses the domain

    // Secondary ray for light trace -- optionally modify the step size vs. primary ray.
    int secondaryMaxSteps = rayMaxSteps; // / 2;
    float secondaryStepSize = rayStepSize; // * 2.f;

    // ========================================
    // SCATTERING PHASE FUNCTION (using HENYEY-GREENSTEIN function)
    // ========================================
    // Scattering phase factor can be pre-computed outside of ray marching loop
    // for uniform directional lights, since the ray-camera angle doesn't change along the path.
    // NOTE: this is missing the 1/4pi normalization, which is basically folded
    // into the scaling of lightIntensity input parameter.
    vec3 L = normalize(lightDirn.xyz);
    float cosTheta = dot(L, -rayDirn_model);
    float g = clamp(smokeScatterAnisotropy, -0.999f, 0.999f);
    float denom = max(1.f + g*g - 2.f * g * cosTheta, 1.e-6f);
    float scatteringPhase = (1.f - g*g) / (denom * sqrt(denom));

    // ========================================
    // SMOKE-LIGHT INTERACTION: EXTINCTION COEFFICIENTS
    // ========================================
    // These are MOLAR extinction coefficients. Multiply by medium density
    // (i.e., smoke) to get p.u.v.
    // - Total molar extinction coef = scattering + absorbtion.
    //   i.e., sigmaExtinction = sigmaScattering + sigmaAbsorption.
    // - Albedo := sigmaScattering / sigmaExtinction (total). Albedo is in range [0, 1].
    // - The total (sigmaExtinction) is used to determine the radiance lost during each step.
    // Note that we allow the overall absorption to have a color dependence
    // (smoke absorbs different colors with different weights)
    //   but scattering is independent of wavelength.
    // Note on absorption: decouple the tint / absorb color from the overall
    // strength by normalizing the color to a channel-summed absorption of 1.
    vec3 sigmaAbsorption = vec3(smokeExtinctionCoef * (1.f - smokeAlbedo));
    float avgAbsorptionColor = dot(smokeAbsorbColor.xyz, vec3(0.333f));
    if (avgAbsorptionColor > 1.e-4f)
      sigmaAbsorption *= smokeAbsorbColor.xyz / avgAbsorptionColor;
    float sigmaScattering = smokeExtinctionCoef * smokeAlbedo;
    vec3 sigmaExtinction = sigmaAbsorption + sigmaScattering;

    // ========================================
    // DEPTH BUFFER TERMINATION DISTANCE
    // ========================================
    // Reconstruct the world-space ray parameter for the nearest opaque scene object so
    // the marching loop can terminate before marching through solid geometry.
    // depthBuffer is [0, 1]; 1.0 means far plane — no ray termination at all should occur.
    float tScene = 1e6f;
    {
      // Sample the depth texture
      float sceneDepth = texture(depthBuffer, ndcpos * 0.5f + 0.5f).r;
      // Depth is set closer than far plane?
      if (sceneDepth < 0.9999f)
      {
        // Depth is in [0,1]
        // (NOTE: OpenGL convention NDC z in [-1, 1]; Blender GPU layer normalises this; revert)
        float z_ndc = sceneDepth * 2.0f - 1.0f;
        // Transform into model space
        vec4 sceneDepth_view = rcBuf.invProjMatrix * vec4(ndcpos, z_ndc, 1.0f);
        sceneDepth_view /= max(sceneDepth_view.w, 1e-8f);
        vec3 sceneDepth_world = (rcBuf.invViewMatrix * vec4(sceneDepth_view.xyz, 1.0f)).xyz;
        vec3 sceneDepth_model = (rcBuf.invModelMatrix * vec4(sceneDepth_world, 1.0f)).xyz;
        // Project onto the ray direction to get parametric distance
        // (works for perspective and ortho)
        tScene = dot(sceneDepth_model - rayOrigin_model, rayDirn_model);
      }
    }

    // ========================================
    // RAY MARCHING INITIALIZATION
    // ========================================
    // +0.5 to shift to [0,1] tx coords
    vec3 pos = rayOrigin_model + rayDirn_model * tMin + vec3(0.5f);
    float t = tMin;

    float densityPrev = max(0.0, texture(densityTex, pos).r);
    float TPrev = max(0.0, texture(temperatureTex, pos).r);

    vec3 accumColor = vec3(0.f);
    vec3 transmittance = vec3(1.f);
    float glowAlpha = 0.f;
    float tHit = 1e6; // Distance along ray of first hit with non-zero volume data


    // ========================================
    // PRIMARY RAY MARCHING LOOP
    // ========================================
    for (int i = 0; i < rayMaxSteps; ++i)
    {
      pos += rayDirn_model * rayStepSize;
      t += rayStepSize;
      if (t >= tMax)
        break; // Exit ray stepping if exited domain

      // Domain bounds check.
      // Why do this if the ray is constrained to stepping between tMin & tMax?
      // Because discrete steps can step over tMax, resulting in
      // visual artifacts when the smoke touches the edge of the domain.
      if (any(lessThan(pos, vec3(-0.0001f))) || any(greaterThan(pos, vec3(1.0001f))))
        break;

      // Sample current density and temperature
      float densityCurr = max(0.0, texture(densityTex, pos).r);
      float TCurr = max(0.0, texture(temperatureTex, pos).r);

      // Average values over segment (trapezoidal rule)
      float densityAvg = 0.5f * (densityPrev + densityCurr);
      float TAvg = 0.5f * (TPrev + TCurr);

      // Skip the work if segment is empty
      if (densityAvg < 0.001f && TAvg < flameEmitMinT)
      {
        densityPrev = densityCurr;
        TPrev = TCurr;
        continue;
      }

      // ========================================
      // OPTICAL DEPTH AND ATTENUATION
      // ========================================
      // Optical depth over this segment: τ = ∫ σ_t ρ(s) ds ≈ σ_t ρ_avg Δs
      vec3 opticalDepth = sigmaExtinction * densityAvg * rayStepSize;
      // Exponential attenuation: exp(-τ)
      vec3 stepAttenuation = exp(-opticalDepth);
      // Step opacity: 1 - exp(-τ)
      vec3 stepOpacity = 1.f - stepAttenuation;

      // ========================================
      // ANALYTICAL INTEGRATION WEIGHT
      // ========================================
      // For sources in absorbing medium: Weight = Δs * [1 - exp(-τ)]/τ
      vec3 analyticalWeight;
      if (all(lessThan(opticalDepth, vec3(0.01f))))
      {
        // Taylor series for numerical stability
        // [1 - exp(-τ)]/τ ≈ 1 - τ/2 + τ²/6 - τ³/24
        analyticalWeight = rayStepSize * (1.0f - 0.5f * opticalDepth +
                                opticalDepth * opticalDepth / 6.0f -
                                opticalDepth * opticalDepth * opticalDepth / 24.0f);
      }
      else
      {
        // Standard formula: Δs * [1 - exp(-τ)]/τ
        analyticalWeight = rayStepSize * stepOpacity / max(opticalDepth, 1e-6f);
      }

      // ========================================
      // SOURCE TERMS
      // ========================================
      vec3 totalSource = vec3(0.f);

      // === DIRECT EMISSION TERMS ===
      if (TAvg > flameEmitMinT)
      {
        // T -> RGB
        vec3 BBRGB = BlackBodyRGB(TAvg);
        float smoothing = smoothstep(flameEmitMinT, flameEmitMinT + 200.f, TAvg);

        // Glowing soot
        if (densityAvg > 0.001f)
        {
          // Note: sigma_a factor as required by Kircchoff's law of local thermal equilibrium.
          vec3 sootEmission = sigmaAbsorption * BBRGB * flameIntensity * smoothing * densityAvg;
          totalSource += sootEmission;
        }

        // Glowing background gas (density independent)
        vec3 gasEmission;
        if (hotGasEmitType == 0)
          gasEmission = hotGasEmitColor.xyz * hotGasEmitStrength * smoothing;
        else if (hotGasEmitType == 1)
          gasEmission = BBRGB * hotGasEmitStrength * smoothing;
        totalSource += gasEmission;

        // Ensure the pixel doesn't get assigned transparent if there's no smoke.
        glowAlpha += dot(gasEmission, vec3(0.2126, 0.7152, 0.0722));
      }

      // === IN-SCATTERING AMBIENT LIGHT SOURCE ===
      if (densityAvg > 0.001f)
      {
        vec3 lightTrans = TraceUniformLightTransmittance(
            pos, L, sigmaExtinction, secondaryMaxSteps, secondaryStepSize);
        // Above we calculated how much ambient light arrived at the primary ray.
        // This used total extinction.
        // Now, of the ambient light that has reached this point, how much is
        // directed towards the camera?
        // *That* depends on the integrated scattering anisotropy factor,
        // as well as just the scattering part of sigma.
        vec3 scatteredLight = (sigmaScattering * densityAvg) * scatteringPhase
            * lightIntensity * lightColor.xyz * lightTrans;
        totalSource += scatteredLight;
      }

      // ========================================
      // RADIANCE ACCUMULATION
      // ========================================
      // Add source contributions with analytical integration weight.
      accumColor += transmittance * analyticalWeight * totalSource;

      // Update transmittance for next step
      transmittance *= stepAttenuation;

      // Record hit distance (for depth buffer)
      if (densityAvg > 0.01f || TAvg > flameEmitMinT)
        tHit = min(t, tHit);

      // ========================================
      // EARLY EXITS
      // ========================================
      // Exit if fully opaque
      if (all(lessThan(transmittance, vec3(0.01f))))
        break;

      // Update previous values for next iteration
      densityPrev = densityCurr;
      TPrev = TCurr;
    }

    // ========================================
    // FINAL FRAGMENT OUTPUT
    // ========================================
    // Set final fragment transparency based on perceptual brightness for the transmitted light
    // (a convention for converting three-component transmittance value to a pixel alpha)
    // Regions with no smoke become transparent
    float smokeAlpha = 1.f - dot(transmittance, vec3(0.2126, 0.7152, 0.0722));
    glowAlpha = clamp(glowAlpha, 0.f, 1.f);
    // Final fragment alpha value
    float alpha = max(smokeAlpha, glowAlpha);

    // Apply the global opacity factor
    alpha *= globalOpacity;

    FragColor = vec4( accumColor.r, accumColor.g, accumColor.b, alpha );

    // Write depth at the first significant volume intersection so that opaque objects
    // drawn behind the volume (and after in the pipeline) are correctly occluded by it.
    // gl_FragDepth must be written in ALL code paths once any path writes it, so write even
    // if no hit on this ray
    if (tHit < 1e5f)
    {
      vec3 hitPos_model = rayOrigin_model + rayDirn_model * tHit;
      vec4 hitPos_clip  = rcBuf.MVP * vec4(hitPos_model, 1.f);
      float z_ndc = hitPos_clip.z / max(hitPos_clip.w, 1e-8f);
      gl_FragDepth = z_ndc * 0.5f + 0.5f;
    }
    else
    {
      // No volume hit (transparent fragment) — write far plane so nothing is occluded.
      gl_FragDepth = 1.0f;
    }

//    // Debug: shade surviving fragments by NDC position
//    FragColor = vec4(ndcpos.x, ndcpos.y, 0.10, 0.50);
}
"""

# ---------------------------------------------------------------------------
# Style renderers
# ---------------------------------------------------------------------------


class VolumeRaymarchBasicRenderer(NexusRenderer):
    """RAYMARCHER style

    Uses 3D textures for smoke (densityTex) and temperature (temperatureTex)
    to render a smoke and fire scene using a ray marching algorithm.

    Field data is fetched from Theron each frame via:
      theron.get_efx_smoke_field(handle)       -> (flat_ctypes_array, (nx, ny, nz), dx) | None
      theron.get_efx_temperature_field(handle) -> (flat_ctypes_array, (nx, ny, nz), dx) | None

    When one of the two channels is disabled in the backend (so that its fetch returns
    None), a 1×1×1 zero-valued placeholder is bound for the missing sampler so
    the shader falls back to single-channel rendering. The draw is only skipped
    when BOTH channels are unavailable.
    """

    def __init__(self):
        self._shader = None
        self._ubo = None
        # Cached Theron field textures and the frame they were fetched for.
        self._cached_density_tex = None
        self._cached_temperature_tex = None
        self._cached_frame = None
        # Effective upres decision (display_upres AND upres_factor > 1) that the
        # cached textures were fetched under. A change forces a re-fetch.
        self._cached_use_upres = False
        # 1x1 R32F texture (value = 1.0) used as depthBuffer fallback for if the
        # viewport depth texture is not accessible via the Blender GPU API.
        self._fallback_depth_tex = None
        # 1x1x1 R32F=0.0 placeholder bound in place of a missing density or temperature texture.
        self._fallback_zero_field_tex = None

    def _get_fallback_zero_field_tex(self):
        """1×1×1 R32F texture (value = 0.0) used to stand in for a missing channel.

        If Theron is configured with a disabled smoke or temperature channel,
        the fetch returns None for that channel. In that case, do not refuse to draw.
        Instead, bind this zero-valued placeholder tx to the missing sampler so
        the fragment shader naturally falls back to a single-channel render:

        - Missing density -> smoke absorption / scattering / soot emission all
          multiply by densityAvg ≈ 0 and disappear. Only the density-independent
          hot-gas-emission term remains, driven by temperature.
        - Missing temperature -> "TAvg < flameEmitMinT" is true everywhere,
          so the entire emission branch is skipped. Smoke absorbs and
          scatters ambient light as usual.
        """
        if self._fallback_zero_field_tex is None:
            import gpu

            buf = gpu.types.Buffer("FLOAT", 1, [0.0])
            self._fallback_zero_field_tex = gpu.types.GPUTexture(
                (1, 1, 1), is_cubemap=False, format="R32F", data=buf
            )
        return self._fallback_zero_field_tex

    # ------------------------------------------------------------------
    # GPU resource helpers
    # ------------------------------------------------------------------

    def _get_shader(self):
        if self._shader is not None:
            return self._shader
        import gpu

        # Pass ndc coordinate from vs to fs
        iface = gpu.types.GPUStageInterfaceInfo("volume_raymarcher_iface")
        iface.smooth("VEC2", "ndcpos")

        info = gpu.types.GPUShaderCreateInfo()
        # VS interface: VBO containing vec2 positions; output is iface defined above.
        info.vertex_in(0, "VEC2", "pos")
        info.vertex_out(iface)
        # FS: output is vec4 frag color + explicit depth write (enables gl_FragDepth in the shader)
        info.fragment_out(0, "VEC4", "FragColor")
        info.depth_write("ANY")
        # All push consts
        # UBO — mirrors the three inverse matrices above (future replacement for push constants)
        info.typedef_source("""\
struct RaymarcherUBO
{
    mat4 MVP;
    mat4 invModelMatrix;
    mat4 invViewMatrix;
    mat4 invProjMatrix;
    // Smoke scattering
    vec4 smokeAbsorbColorExtinction;  // xyz=absorbColor, w=extinctionCoef
    vec4 smokeAlbedoAnisotropy;       // x=albedo, y=scatterAnisotropy, zw=unused
    // Flame emission
    vec4 flame;                       // x=emitMinT, y=intensity, zw=unused
    // Ambient lighting
    vec4 lightDirnIntensity;          // xyz=lightDirn, w=lightIntensity
    vec4 lightColor;                  // xyz=lightColor, w=unused
    // Hot gas emission
    vec4 hotGasEmitColorStrength;     // xyz=emitColor, w=emitStrength
    vec4 hotGasEmitTypeVec;           // x=float(emitType), yzw=unused
    // Ray marching
    vec4 rayMarch;                    // x=stepSize, y=float(maxSteps), z=globalOpacity, w=unused
};""")
        info.uniform_buf(0, "RaymarcherUBO", "rcBuf")
        # Textures / samplers
        info.sampler(0, "FLOAT_3D", "densityTex")
        info.sampler(1, "FLOAT_3D", "temperatureTex")
        info.sampler(2, "FLOAT_2D", "depthBuffer")

        info.vertex_source(_RAYMARCHER_VERT_SRC)
        info.fragment_source(_RAYMARCHER_FRAG_SRC)
        self._shader = gpu.shader.create_from_info(info)
        return self._shader

    def _update_ubo(self, mvp, inv_model, inv_view, inv_proj, params):
        """Pack RaymarcherUBO into the GPU uniform buffer.

        Layout: 4 × mat4 (64 floats) + 8 × vec4 (32 floats) = 96 floats = 384 bytes.
        All fields are vec4 — no vec3 padding ambiguity across GPU backends.
        """
        import gpu

        floats = []
        # Matrices — 4 × 16 = 64 floats
        for m in (mvp, inv_model, inv_view, inv_proj):
            for col in m.col:
                floats.extend(col)
        # Smoke scattering — 2 × vec4
        r, g, b = params.smoke_tint_color
        floats += [1.0 - r, 1.0 - g, 1.0 - b, params.smoke_extinction_coef]
        floats += [params.smoke_albedo, params.smoke_scatter_anisotropy, 0.0, 0.0]
        # Flame emission — 1 × vec4
        floats += [params.flame_emit_min_t, params.flame_intensity, 0.0, 0.0]
        # Ambient lighting — 2 × vec4
        lx, ly, lz = params.light_dirn
        floats += [-lz, -lx, -ly, params.light_intensity]  # Alter dirn.
        lr, lg, lb = params.light_color
        floats += [lr, lg, lb, 0.0]
        # Hot gas emission — 2 × vec4
        hx, hy, hz = params.hot_gas_emit_color
        floats += [hx, hy, hz, params.hot_gas_emit_strength]
        floats += [float(params.hot_gas_emit_type), 0.0, 0.0, 0.0]
        # Ray marching — 1 × vec4
        rt_three = 1.73205080757
        floats += [
            rt_three / float(params.ray_max_steps),
            float(params.ray_max_steps),
            1.0 - params.global_transparency,
            0.0,
        ]
        # Total: 64 + 32 = 96 floats = 384 bytes
        buf = gpu.types.Buffer("FLOAT", len(floats), floats)
        if self._ubo is None:
            self._ubo = gpu.types.GPUUniformBuf(buf)
        else:
            self._ubo.update(buf)

    @staticmethod
    def _make_field_texture(flat_data, resolution):
        """Upload a flat float array to a R32F 3D GPUTexture.

        flat_data  — Python list or buffer of floats; length must equal nx*ny*nz.
        resolution — (nx, ny, nz) voxel dimensions.
        """
        import gpu

        nx, ny, nz = resolution
        buf = gpu.types.Buffer("FLOAT", len(flat_data), flat_data)
        tex = gpu.types.GPUTexture((nx, ny, nz), is_cubemap=False, format="R32F", data=buf)
        # Blender 5.1 has the filter_mode API function to enable trilinear filtering on sampling,
        # but this is apparently not present on earlier versions. Enable if possible.
        if hasattr(tex, "filter_mode"):
            tex.filter_mode(True)
        return tex

    def _fetch_field_textures(self, params, current_frame):
        """Try to fetch live density and temperature textures from Theron.

        Returns (density_tex, temperature_tex) where either may be None when the
        corresponding field data is not yet available.

        When params.display_upres is True and params.upres_factor > 1 the upscaled
        channel (get_efx_field_upres) is queried instead of the base channel.

        Results are cached per (frame, use_upres): the cached textures are returned
        immediately when both match the last fetch.
        """

        modifier_handle = params.modifier_handle
        if modifier_handle is None:
            return None, None

        use_upres = bool(params.display_upres) and int(params.upres_factor) > 1

        if current_frame == self._cached_frame and use_upres == self._cached_use_upres:
            return self._cached_density_tex, self._cached_temperature_tex

        try:
            from ...libs import theron
            from ...libs.theron import TrEFXChannel
        except ImportError:
            return None, None

        if not theron.is_initialized():
            return None, None

        fetch_fn = theron.get_efx_field_upres if use_upres else theron.get_efx_field

        density_tex = None
        temperature_tex = None

        try:
            result = fetch_fn(modifier_handle, TrEFXChannel.TR_EFX_CHANNEL_SMOKE)
            if result is not None:
                # dx is Theron's actual voxel size. Unused — the raymarcher samples
                # the texture in the unit cube and scales by params.domain_size.
                flat_data, resolution, _dx = result
                density_tex = self._make_field_texture(flat_data, resolution)
        except Exception as exc:
            print(f"[VolumeRaymarchBasicRenderer] density field fetch failed: {exc}")

        try:
            result = fetch_fn(modifier_handle, TrEFXChannel.TR_EFX_CHANNEL_TEMPERATURE)
            if result is not None:
                flat_data, resolution, _dx = result
                temperature_tex = self._make_field_texture(flat_data, resolution)
        except Exception as exc:
            print(f"[VolumeRaymarchBasicRenderer] temperature field fetch failed: {exc}")

        self._cached_density_tex = density_tex
        self._cached_temperature_tex = temperature_tex
        self._cached_frame = current_frame
        self._cached_use_upres = use_upres
        return density_tex, temperature_tex

    # ------------------------------------------------------------------

    def draw(self, context, pipeline, scene, params) -> bool:
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return False

        # No texture data is available at frame 1 (simulation start); skip draw.
        # Also invalidate the field-texture cache: the pipeline handler resets Theron
        # when the timeline jumps back to start, so any cached textures keyed on a
        # Blender frame number now refer to data from the previous run.
        if scene.frame_current <= scene.frame_start:
            self._cached_frame = None
            self._cached_density_tex = None
            self._cached_temperature_tex = None
            self._cached_use_upres = False
            return False

        import gpu
        from gpu_extras.batch import batch_for_shader

        try:
            shader = self._get_shader()
        except Exception as exc:
            print(f"[VolumeRaymarchBasicRenderer] GPU resource init failed: {exc}")
            return False

        smoketexture, temperaturetexture = self._fetch_field_textures(params, scene.frame_current)
        # Allow single-channel fallback visualization: if one of the two channels is disabled
        # in the Theron backend (and therefore returned None), substitute a 1x1x1 zero-valued
        # placeholder for the missing sampler.
        # Only disable draw when BOTH channels are unavailable.
        if smoketexture is None and temperaturetexture is None:
            return False
        if smoketexture is None:
            smoketexture = self._get_fallback_zero_field_tex()
        if temperaturetexture is None:
            temperaturetexture = self._get_fallback_zero_field_tex()

        corners = []
        corners.append((-1.0, -1.0))
        corners.append((1.0, -1.0))
        corners.append((1.0, 1.0))
        corners.append((-1.0, 1.0))

        tris_quad = []
        tris_quad.append((0, 1, 2))
        tris_quad.append((0, 2, 3))

        tri_pos = [corners[idx] for tri in tris_quad for idx in tri]

        batch = batch_for_shader(shader, "TRIS", {"pos": tri_pos})

        import mathutils

        # Inverse view matrix (V^{-1}): region_data.view_matrix is world->view.
        inv_view = region_data.view_matrix.inverted()

        # Inverse projection matrix (P^{-1}): region_data.window_matrix is view->clip.
        inv_proj = region_data.window_matrix.inverted()

        # Model matrix: reconstruct from flat row-major world_matrix, then bake in domain_size
        # so that model space == the unit cube [-0.5, 0.5]^3 (matching boxMin/boxMax constants).
        wm = params.world_matrix
        model_mat = mathutils.Matrix((wm[0:4], wm[4:8], wm[8:12], wm[12:16]))
        sx, sy, sz = params.domain_size
        scale_mat = mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
        model_mat_scaled = model_mat @ scale_mat
        inv_model = model_mat_scaled.inverted()

        # Composite MVP with the same domain-size scale baked in.
        mvp = region_data.perspective_matrix @ model_mat_scaled

        # ------------------------------------------------------------------
        # Depth buffer — bind the viewport depth texture so the shader can
        # terminate rays at opaque geometry and write its own depth value.
        # Requires API gpu.state.active_framebuffer_get() / fb.texture_depth are available
        # If these are not available, the try/except block triggers use of the 1x1 fallback tex.
        # ------------------------------------------------------------------
        depth_tex = None
        try:
            fb = gpu.state.active_framebuffer_get()
            depth_tex = fb.texture_depth
        except (AttributeError, Exception):
            pass

        if depth_tex is None:
            # Fallback: 1x1 R32F texture with value 1.0 (= far plane / background).
            # The shader reads 1.0, skips depth termination, and writes its own depth
            # from tHit — depth writes still work correctly without a real input texture.
            if self._fallback_depth_tex is None:
                buf = gpu.types.Buffer("FLOAT", 1, [1.0])
                self._fallback_depth_tex = gpu.types.GPUTexture((1, 1), format="R32F", data=buf)
            depth_tex = self._fallback_depth_tex

        shader.bind()
        # UBO constants
        self._update_ubo(mvp, inv_model, inv_view, inv_proj, params)
        shader.uniform_block("rcBuf", self._ubo)
        shader.uniform_sampler("densityTex", smoketexture)
        shader.uniform_sampler("temperatureTex", temperaturetexture)
        shader.uniform_sampler("depthBuffer", depth_tex)

        prev_depth_test = gpu.state.depth_test_get()
        prev_depth_mask = gpu.state.depth_mask_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(True)  # Allow gl_FragDepth writes from the shader
            gpu.state.blend_set("ALPHA")
            batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")
            gpu.state.depth_test_set(prev_depth_test)
            gpu.state.depth_mask_set(prev_depth_mask)

        return True

    def shutdown(self) -> None:
        self._shader = None
        self._ubo = None
        self._cached_density_tex = None
        self._cached_temperature_tex = None
        self._cached_frame = None
        self._cached_use_upres = False
        self._fallback_depth_tex = None
        self._fallback_zero_field_tex = None


class VolumeSlicesBasicRenderer(NexusRenderer):
    """SLICES style: view-aligned clipped-volume-slice stack composited
    front-to-back, with a per-channel transfer function driving fragment
    colour. Geometry is regenerated on transform/slice-count changes; field
    textures are fetched per frame from Theron and looked up against
    gradient-generated 1D LUTs.
    """

    def __init__(self):
        self._shader = None
        # Saved slice vertex coordinates and MVP transform, plus the
        # settings that gave rise to them (slice count + four transforms).
        # Saved slice coordinates are used in the vertex buffer unless invalidated
        # by any of the settings used to generate.
        self._slice_batch = None
        self._slice_mvp = None
        self._cache_slice_num = None
        self._cache_world_matrix = None
        self._cache_domain_size = None
        self._cache_view_matrix = None
        self._cache_persp_matrix = None
        # Fallback textures: these get bound to any sampler slot the current display mode
        # isn't actively using. This avoids draw call fails from unbound textures.
        self._fallback_fieldtex = None
        self._fallback_xfertex = None
        # SPEED display mode: per-frame cache of the Theron speed field texture.
        self._speed_field_tex = None
        self._cached_speed_frame = None
        # SMOKE / TEMPERATURE / FUEL display modes: cache of 3D field
        # textures fetched via theron.get_efx_field / get_efx_field_upres,
        # keyed by channel enum and invalidated when the frame number or the
        # use_upres display mode changes.
        self._efx_field_cache: dict = {}
        # Transfer-function (1D RGBA) texture cache. Cache is keyed by the color
        # gradient slot name; value is a (texture, hash_key) tuple where
        # hash_key = (color_hash, alpha_hash, min_clip, max_clip). Any of
        # those four changing forces a re-generation.
        self._xfer_tex_cache: dict = {}

    def _get_shader(self):
        if self._shader is not None:
            return self._shader
        import gpu

        iface = gpu.types.GPUStageInterfaceInfo("volume_slices_iface")
        iface.smooth("VEC3", "localpos")

        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_out(iface)
        info.fragment_out(0, "VEC4", "FragColor")
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        # Channel-selection + blackbody parameters.
        info.push_constant("INT", "usebb")
        info.push_constant("FLOAT", "bbPower")
        info.push_constant("FLOAT", "bbMin")
        info.push_constant("FLOAT", "bbMax")
        info.push_constant("INT", "mode")
        info.push_constant("FLOAT", "ch0trans")
        info.push_constant("FLOAT", "ch1trans")
        info.push_constant("FLOAT", "glblopacity")
        info.push_constant("FLOAT", "field0MinRange")
        info.push_constant("FLOAT", "field0InvRange")
        info.push_constant("FLOAT", "field1MinRange")
        info.push_constant("FLOAT", "field1InvRange")
        # Up to three 3D field textures (smoke, temperature, fuel, color, etc.,
        # depending on "mode") plus up to two 1D transfer-function lookups.
        info.sampler(0, "FLOAT_3D", "fieldtex0")
        info.sampler(1, "FLOAT_3D", "fieldtex1")
        info.sampler(2, "FLOAT_3D", "fieldtex2")
        info.sampler(3, "FLOAT_1D", "xfertex0")
        info.sampler(4, "FLOAT_1D", "xfertex1")
        info.vertex_source("""\
void main() {
    localpos = pos + vec3(0.5);
    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
}
""")
        info.fragment_source("""\
vec3 BlackBodyRGB(float T, float power)
{
  float u = (0.860117757f + 1.54118254e-4f * T + 1.28641212e-7f * T * T) /
            (1.f + 8.42420235e-4f * T + 7.08145163e-7f * T * T);

  float v = (0.317398726f + 4.22806245e-5f * T + 4.20481691e-8f * T * T) /
            (1.f - 2.89741816e-5f * T + 1.61456053e-7f * T * T);

  float x = 3.f * u / (2.f * u - 8.f * v + 4.f);
  float y = 2.f * v / (2.f * u - 8.f * v + 4.f);
  float z = 1.f - x - y;

  vec3 XYZ = vec3( x/y, 1.f, z/y ); // = (x, y, z)/y

  mat3 XYZtoRGB = mat3(
      3.2404542f, -0.9692660f, 0.0556434f,
     -1.5371385f, 1.8760108f, -0.2040259f,
     -0.4985314f, 0.0415560f, 1.0572252f
  );

  vec3 RGB = XYZtoRGB * XYZ;

  return RGB * pow(0.0004f * T, power);
}

void main()
{
  if (mode == 0)
  {
    float val0 = texture(fieldtex0, localpos).r;
    val0 = clamp((val0 - field0MinRange) * field0InvRange, 0.f, 1.f);
    if (usebb == 1)
    {
      float T = bbMin + (val0 * (bbMax-bbMin));
      vec3 bbcol = BlackBodyRGB(T, bbPower);
      FragColor = vec4(bbcol, texture(xfertex0, val0).a);
    }
    else
    {
        FragColor = texture(xfertex0, val0);
    }
    FragColor.a *= (1.f - ch0trans);
  }
  else if (mode == 1)
  {
    float val0 = texture(fieldtex0, localpos).r;
    val0 = clamp((val0 - field0MinRange) * field0InvRange, 0.f, 1.f);
    vec4 col0;
    if (usebb == 1)
    {
      float T = bbMin + (val0 * (bbMax-bbMin));
      vec3 bbcol = BlackBodyRGB(T, bbPower);
      col0 = vec4(bbcol, texture(xfertex0, val0).a);
    }
    else
    {
      col0 = texture(xfertex0, val0);
    }
    col0.a *= (1.f - ch0trans);

    float val1 = texture(fieldtex1, localpos).r;
    val1 = clamp((val1 - field1MinRange) * field1InvRange, 0.f, 1.f);
    vec4 col1  = texture(xfertex1, val1);
    col1.a *= (1.f - ch1trans);

    // Blend "over"
    FragColor.a = col1.a + col0.a * (1.f - col1.a);
    FragColor.rgb = col1.rgb * col1.a + col0.rgb * col0.a * (1.f - col1.a);
    if (FragColor.a != 0.f)
      FragColor.rgb /= FragColor.a;
  }
  else if (mode == 2)
  {
    FragColor.r = texture(fieldtex0, localpos).r;
    FragColor.g = texture(fieldtex1, localpos).r;
    FragColor.b = texture(fieldtex2, localpos).r;
    FragColor.a = (FragColor.r + FragColor.g + FragColor.b) / 3.f;
  }

  if (glblopacity != 1.f)
    FragColor.a *= glblopacity;

  if (FragColor.a < 0.001f)
    discard;
}
""")
        self._shader = gpu.shader.create_from_info(info)
        return self._shader

    # ---------------------------------------------------------------------------
    # View-aligned slice generation
    # ---------------------------------------------------------------------------

    # Unit-cube domain corners in model space. Numbering matches the
    # _SLICER_EDGE_LIST below (face-loop winding around -Z, then +Z).
    _SLICER_VERTICES = np.array(
        [
            [-0.5, -0.5, -0.5],  # v0
            [0.5, -0.5, -0.5],  # v1
            [0.5, 0.5, -0.5],  # v2
            [-0.5, 0.5, -0.5],  # v3
            [-0.5, -0.5, 0.5],  # v4
            [0.5, -0.5, 0.5],  # v5
            [0.5, 0.5, 0.5],  # v6
            [-0.5, 0.5, 0.5],  # v7
        ],
        dtype=np.float64,
    )

    # 12 edges as (start, end) vertex-index pairs.
    _SLICER_EDGES = np.array(
        [
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0],  # -Z face loop
            [0, 4],
            [1, 5],
            [2, 6],
            [3, 7],  # verticals
            [4, 5],
            [5, 6],
            [6, 7],
            [7, 4],  # +Z face loop
        ],
        dtype=np.int32,
    )

    # For each leading (front-most) corner index, the 12 edges reordered into the three
    # 4-edge "rings" expected by the intersection lookup (slots 0-1, 2-3, 4-5).
    _SLICER_EDGE_LIST = np.array(
        [
            [0, 1, 5, 6, 4, 8, 11, 9, 3, 7, 2, 10],  # v0 leading
            [0, 4, 3, 11, 1, 2, 6, 7, 5, 9, 8, 10],  # v1
            [1, 5, 0, 8, 2, 3, 7, 4, 6, 10, 9, 11],  # v2
            [7, 11, 10, 8, 2, 6, 1, 9, 3, 0, 4, 5],  # v3
            [8, 5, 9, 1, 11, 10, 7, 6, 4, 3, 0, 2],  # v4
            [9, 6, 10, 2, 8, 11, 4, 7, 5, 0, 1, 3],  # v5
            [9, 8, 5, 4, 6, 1, 2, 0, 10, 7, 11, 3],  # v6
            [10, 9, 6, 5, 7, 2, 3, 1, 11, 4, 8, 0],  # v7
        ],
        dtype=np.int32,
    )

    # Triangle-fan indices into the 6-vertex polygon: 4 triangles -> 12 indices per slice.
    _SLICER_FAN = np.array([0, 2, 1, 0, 3, 2, 0, 4, 3, 0, 5, 4], dtype=np.int32)

    # Per-slot intersection candidate lists. Last entry in each tuple is the
    # unconditional fallback used when none of the preceding candidates have a
    # parametric value in [0, 1) — matches the C++ if/else-if chain.
    _SLICER_CANDIDATES = (
        ((0, 1), 3),
        ((2, 0, 1), 3),
        ((4, 5), 7),
        ((6, 4, 5), 7),
        ((8, 9), 11),
        ((10, 8, 9), 11),
    )

    _SLICER_MAX_SLICES = 1024

    # Display mode -> shader "mode" integer. Modes that index a single
    # field land on 0; modes that combine a smoke field with a second field
    # land on 1; pre-shaded colour-field rendering lands on 2.
    _SLICER_CHANNEL_TO_MODE = {
        "SPEED": 0,
        "TEMP": 0,
        "FUEL": 0,
        "SMOKE": 0,
        "SMOKE_TEMP": 1,
        "SMOKE_FUEL": 1,
        "COLOR": 2,
    }

    def _generate_slice_coordinates(self, num_slices, view_dir_model):
        """Build view-aligned slice geometry through the unit-cube domain.

        num_slices       — number of slicing planes (clamped to _SLICER_MAX_SLICES).
        view_dir_model   — (3,) camera direction expressed in model space.

        Returns a contiguous float32 array with (num_slices * 12, 3) coordinates:
        the model-space vertex positions, ordered far-to-near. This format is ready
        to upload as the vertex buffer. Each slice writes 12 vertices:
        a 4-triangle fan over the 3-6 corner polygon formed by the slicing
        plane / cube intersection.
        """
        num_slices = max(1, min(int(num_slices), self._SLICER_MAX_SLICES))
        view_dir = np.asarray(view_dir_model, dtype=np.float64).reshape(3)

        # Distance of every corner along the view direction; the corner with the
        # largest distance is the front-most (leading) vertex.
        corner_dists = self._SLICER_VERTICES @ view_dir  # (8,)
        max_index = int(np.argmax(corner_dists))
        max_dist = float(corner_dists[max_index]) + 1.0e-6
        min_dist = float(corner_dists.min()) - 1.0e-6

        # Reorder the 12 edges for this leading vertex, then look up each edge's
        # start vertex and the direction vector (end - start).
        edge_seq = self._SLICER_EDGE_LIST[max_index]  # (12,)
        edge_pairs = self._SLICER_EDGES[edge_seq]  # (12, 2)
        vec_start = self._SLICER_VERTICES[edge_pairs[:, 0]]  # (12, 3)
        vec_dir = self._SLICER_VERTICES[edge_pairs[:, 1]] - vec_start

        denom = vec_dir @ view_dir  # (12,)
        plane_dist_inc = (max_dist - min_dist) / float(num_slices)
        plane_dist_start = min_dist + 0.5 * plane_dist_inc

        # Per-edge plane-intersection parameter at slice 0 and its per-slice increment.
        # Edges parallel to the view (denom == 0) get lambda = -1 so the validity
        # test below always rejects them.
        nonzero = denom != 0.0
        safe_denom = np.where(nonzero, denom, 1.0)
        lambda_inc = np.where(nonzero, plane_dist_inc / safe_denom, 0.0)
        lambda0 = np.where(
            nonzero,
            (plane_dist_start - (vec_start @ view_dir)) / safe_denom,
            -1.0,
        )

        # Walk slices far -> near.
        i_range = np.arange(num_slices - 1, -1, -1, dtype=np.float64)  # (N,)
        dL = lambda0[None, :] + i_range[:, None] * lambda_inc[None, :]  # (N, 12)
        valid = (dL >= 0.0) & (dL < 1.0)

        # Evaluate every (slice, edge) intersection point in one shot, then per-slot
        # gather the one we actually want using the candidate priority lists.
        all_inter = vec_start[None, :, :] + dL[:, :, None] * vec_dir[None, :, :]  # (N, 12, 3)

        polygon = np.empty((num_slices, 6, 3), dtype=np.float64)
        slice_idx = np.arange(num_slices)
        for slot, (checks, fallback) in enumerate(self._SLICER_CANDIDATES):
            # Start with the unconditional fallback, then overwrite (in reverse
            # priority order) with each higher-priority candidate that has a valid dL.
            # Reverse iteration means the highest-priority valid edge wins.
            chosen = np.full(num_slices, fallback, dtype=np.int32)
            for e in reversed(checks):
                chosen = np.where(valid[:, e], np.int32(e), chosen)
            polygon[:, slot, :] = all_inter[slice_idx, chosen, :]

        # Triangle-fan expansion: (N, 6, 3) -> (N, 12, 3) -> (N*12, 3).
        fan = polygon[:, self._SLICER_FAN, :]
        return np.ascontiguousarray(fan.reshape(num_slices * 12, 3), dtype=np.float32)

    @staticmethod
    def _make_r32f_field_texture(flat_data, resolution):
        """Upload a flat float array to an R32F 3D GPUTexture with trilinear
        filtering enabled where available. Mirrors the raymarcher helper."""
        import gpu

        nx, ny, nz = resolution
        buf = gpu.types.Buffer("FLOAT", len(flat_data), flat_data)
        tex = gpu.types.GPUTexture((nx, ny, nz), is_cubemap=False, format="R32F", data=buf)
        if hasattr(tex, "filter_mode"):
            tex.filter_mode(True)
        return tex

    def _fetch_speed_texture(self, params, current_frame):
        """Return the SPEED-channel 3D texture, fetched fresh on a frame
        change and cached otherwise. None when Theron has no data yet."""
        modifier_handle = params.modifier_handle
        if modifier_handle is None:
            return None

        if current_frame == self._cached_speed_frame and self._speed_field_tex is not None:
            return self._speed_field_tex

        try:
            from ...libs import theron
        except ImportError:
            return None

        if not theron.is_initialized():
            return None

        try:
            result = theron.get_efx_speed(modifier_handle)
        except Exception as exc:
            print(f"[VolumeSlicesBasicRenderer] speed field fetch failed: {exc}")
            return None

        if result is None:
            return None

        # dx is Theron's actual voxel size. Unused here — the slices renderer samples
        # the texture in the unit cube and positions geometry from props.
        flat_data, resolution, _dx = result
        try:
            tex = self._make_r32f_field_texture(flat_data, resolution)
        except Exception as exc:
            print(f"[VolumeSlicesBasicRenderer] speed texture upload failed: {exc}")
            return None

        self._speed_field_tex = tex
        self._cached_speed_frame = current_frame
        return tex

    def _fetch_efx_field_texture(self, params, current_frame, channel):
        """Return a 3D R32F texture of the named EFX field (SMOKE / TEMPERATURE /
        FUEL / COLOR_*). Mirrors the raymarcher's fetch: uses the upres channel
        when the simulation has upres enabled (upres_factor > 1) AND if the display preferences
        has the display-upres toggled on. Otherwise falls back to the base resolution."""
        modifier_handle = params.modifier_handle
        if modifier_handle is None:
            return None

        use_upres = bool(params.display_upres) and int(params.upres_factor) > 1

        cached = self._efx_field_cache.get(channel)
        if cached is not None:
            cached_tex, cached_frame, cached_upres = cached
            if cached_frame == current_frame and cached_upres == use_upres:
                return cached_tex

        try:
            from ...libs import theron
        except ImportError:
            return None

        if not theron.is_initialized():
            return None

        fetch_fn = theron.get_efx_field_upres if use_upres else theron.get_efx_field

        try:
            result = fetch_fn(modifier_handle, channel)
        except Exception as exc:
            print(f"[VolumeSlicesBasicRenderer] EFX field fetch failed (channel={channel}): {exc}")
            return None

        if result is None:
            return None

        flat_data, resolution, _dx = result
        try:
            tex = self._make_r32f_field_texture(flat_data, resolution)
        except Exception as exc:
            print(f"[VolumeSlicesBasicRenderer] EFX field texture upload failed: {exc}")
            return None

        self._efx_field_cache[channel] = (tex, current_frame, use_upres)
        return tex

    def _ensure_xfer_texture(
        self,
        obj,
        color_slot: str,
        alpha_slot: str,
        min_clip: float = 0.0,
        max_clip: float = 1.0,
    ):
        """Generate a 256-element 1D RGBA32F LUT from a colour/alpha gradient pair.

        - color_slot: string for the NexusGradient object for the RGB part.
        - alpha_slot: string for the NexusGradient object for the A part (in R channel).
        - min_clip / max_clip: (in [0, 1]) zero out LUT entries whose
          alpha falls outside the band. Defaults pass everything through, so
          channels without a clip control (e.g. SPEED) can call this with
          just the slot names.

        Cached one LUT per "color_slot".
        The hash key for stale LUT detection includes both gradient hashes and both clip bounds,
        so any edit of these controls triggers a re-generation.
        """
        if obj is None:
            return None

        from ...utils.gradient import NexusGradient

        color_grad = NexusGradient(obj, color_slot)
        alpha_grad = NexusGradient(obj, alpha_slot)
        color_lut = color_grad.lut
        alpha_lut = alpha_grad.lut
        if color_lut is None or alpha_lut is None:
            return None

        new_hash = (color_grad.hash, alpha_grad.hash, min_clip, max_clip)
        cached = self._xfer_tex_cache.get(color_slot)
        if cached is not None and cached[1] == new_hash:
            return cached[0]

        import gpu

        data = []
        for i in range(256):
            r, g, b, _ = color_lut[i]
            a = alpha_lut[i][0]
            if a < min_clip or a > max_clip:
                data.extend((0.0, 0.0, 0.0, 0.0))
            else:
                data.extend((r, g, b, a))
        buf = gpu.types.Buffer("FLOAT", len(data), data)
        tex = gpu.types.GPUTexture((256,), is_cubemap=False, format="RGBA32F", data=buf)
        if hasattr(tex, "filter_mode"):
            tex.filter_mode(True)

        self._xfer_tex_cache[color_slot] = (tex, new_hash)
        return tex

    def draw(self, context, pipeline, scene, params) -> bool:
        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return False

        # No texture data is available at frame 1 (simulation start), so skip draw.
        # Also invalidate the field-texture caches: the pipeline handler resets
        # Theron when the timeline jumps back to start, so anything cached with a
        # frame number now refers to data from the previous run.
        if scene.frame_current <= scene.frame_start:
            self._cached_speed_frame = None
            self._speed_field_tex = None
            self._efx_field_cache.clear()
            return False

        import gpu
        import mathutils
        from gpu_extras.batch import batch_for_shader

        try:
            shader = self._get_shader()
        except Exception as exc:
            print(f"[VolumeSlicesBasicRenderer] GPU resource init failed: {exc}")
            return False

        slice_num = int(params.slicer_count)

        # Store the four transforms that slice geometry and MVP depend on, plus
        # the slice count itself.
        world_matrix = tuple(params.world_matrix)
        domain_size = tuple(params.domain_size)
        view_matrix_flat = tuple(c for row in region_data.view_matrix for c in row)
        persp_matrix_flat = tuple(c for row in region_data.perspective_matrix for c in row)

        cache_valid = (
            self._slice_batch is not None
            and self._cache_slice_num == slice_num
            and self._cache_world_matrix == world_matrix
            and self._cache_domain_size == domain_size
            and self._cache_view_matrix == view_matrix_flat
            and self._cache_persp_matrix == persp_matrix_flat
        )

        if not cache_valid:
            # Scaled model matrix: maps the unit cube [-0.5, 0.5]^3 (where the
            # slicer's _SLICER_VERTICES live) to the domain box in world space.
            wm = params.world_matrix
            model_mat = mathutils.Matrix((wm[0:4], wm[4:8], wm[8:12], wm[12:16]))
            sx, sy, sz = params.domain_size
            scale_mat = mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
            model_mat_scaled = model_mat @ scale_mat

            # Camera forward direction in world space. view_matrix.inverted().col[2]
            # is view-space +Z transformed back to world space, which is the axis
            # pointing out of the screen toward the viewer, so negate to get the
            # direction the camera is pointing *into*.
            # The slicer's far-to-near sweep then produces back-to-front output for
            # proper alpha blending.
            inv_view = region_data.view_matrix.inverted()
            view_dir_world = -inv_view.col[2].to_3d()

            # Inverse of (rotation @ scale) applied to a direction vector takes
            # the world-space camera ray into the unit-cube frame.
            # Since this transform can contain scale, not simply pure rotation, it
            # is not necessarily orthogonal and we have to use inverse rather than transpose.
            view_dir_model = model_mat_scaled.to_3x3().inverted() @ view_dir_world

            verts = self._generate_slice_coordinates(
                slice_num,
                (view_dir_model.x, view_dir_model.y, view_dir_model.z),
            )

            # Rebuild via batch_for_shader on every update.
            self._slice_batch = batch_for_shader(shader, "TRIS", {"pos": verts})

            self._slice_mvp = region_data.perspective_matrix @ model_mat_scaled
            self._cache_slice_num = slice_num
            self._cache_world_matrix = world_matrix
            self._cache_domain_size = domain_size
            self._cache_view_matrix = view_matrix_flat
            self._cache_persp_matrix = persp_matrix_flat

        if self._fallback_fieldtex is None:
            buf3d = gpu.types.Buffer("FLOAT", 1, [0.0])
            self._fallback_fieldtex = gpu.types.GPUTexture(
                (1, 1, 1), is_cubemap=False, format="R32F", data=buf3d
            )
        if self._fallback_xfertex is None:
            # Fallback matches the real LUT format (RGBA32F). Using alpha=0 makes the missing
            # channel disappear in the over compositing.
            buf1d = gpu.types.Buffer("FLOAT", 4, [0.0, 0.0, 0.0, 0.0])
            self._fallback_xfertex = gpu.types.GPUTexture(
                (1,), is_cubemap=False, format="RGBA32F", data=buf1d
            )

        mode_val = self._SLICER_CHANNEL_TO_MODE.get(params.slicer_channel, 0)

        # Default per-channel bindings.
        fieldtex0 = self._fallback_fieldtex
        fieldtex1 = self._fallback_fieldtex
        fieldtex2 = self._fallback_fieldtex
        xfertex0 = self._fallback_xfertex
        xfertex1 = self._fallback_xfertex
        glblopacity_val = 1.0 - (params.slicer_transparency / 100.0)
        field0_min = 0.0
        field0_inv = 1.0
        ch0trans_val = 0.0
        field1_min = 0.0
        field1_inv = 1.0
        ch1trans_val = 0.0
        useBB = 0
        bbPower = params.slicer_temp_bb_power
        bbMin = params.slicer_temp_bb_min
        bbMax = params.slicer_temp_bb_max

        if params.slicer_channel == "SPEED":
            speed_tex = self._fetch_speed_texture(params, scene.frame_current)
            if speed_tex is None:
                # Theron has no speed data for this frame yet — skip the draw
                # entirely rather than rendering against an empty fallback.
                return False
            fieldtex0 = speed_tex

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            speed_xfer = self._ensure_xfer_texture(
                obj,
                "explosiafx_display_slicer_speed_color",
                "explosiafx_display_slicer_speed_alpha",
            )
            if speed_xfer is not None:
                xfertex0 = speed_xfer

            field0_min = float(params.slicer_speed_min)
            # InvRange = 1 / (max - min). The shader normalises speed via
            # `(value - MinRange) * InvRange`; guard against zero-width range.
            field0_inv = 1.0 / max(params.slicer_speed_max - params.slicer_speed_min, 1e-6)
            ch0trans_val = 0.0

        elif params.slicer_channel == "SMOKE":
            from ...libs.theron import TrEFXChannel

            smoke_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_SMOKE
            )
            if smoke_tex is None:
                return False
            fieldtex0 = smoke_tex

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            # Clip bounds are stored as percentages 0..100; convert to the
            # [0, 1] range that the baked LUT's alpha lives in.
            smoke_min_clip = float(params.slicer_smoke_min_opacity_clip) / 100.0
            smoke_max_clip = float(params.slicer_smoke_max_opacity_clip) / 100.0
            smoke_xfer = self._ensure_xfer_texture(
                obj,
                "explosiafx_display_slicer_smoke_color",
                "explosiafx_display_slicer_smoke_alpha",
                smoke_min_clip,
                smoke_max_clip,
            )
            if smoke_xfer is not None:
                xfertex0 = smoke_xfer

            field0_min = 0.0
            field0_inv = 1.0
            # Smoke-channel transparency is per-channel; in [0, 1] for the shader.
            ch0trans_val = float(params.slicer_smoke_transparency) / 100.0

        elif params.slicer_channel == "TEMP":
            from ...libs.theron import TrEFXChannel

            temp_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_TEMPERATURE
            )
            if temp_tex is None:
                return False
            fieldtex0 = temp_tex

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            # Clip bounds are stored as percentages 0..100; convert to the
            # [0, 1] range that the baked LUT's alpha lives in.
            temp_min_clip = float(params.slicer_temp_min_opacity_clip) / 100.0
            temp_max_clip = float(params.slicer_temp_max_opacity_clip) / 100.0
            temp_xfer = self._ensure_xfer_texture(
                obj,
                "explosiafx_display_slicer_temp_color",
                "explosiafx_display_slicer_temp_alpha",
                temp_min_clip,
                temp_max_clip,
            )
            if temp_xfer is not None:
                xfertex0 = temp_xfer

            glblopacity_val = 1.0 - (params.slicer_transparency / 100.0)
            field0_min = float(params.slicer_temp_min)
            # InvRange = 1 / (max - min). The shader normalises via
            # `(value - MinRange) * InvRange`; guard against zero-width range.
            field0_inv = 1.0 / max(params.slicer_temp_max - params.slicer_temp_min, 1e-6)
            # Temperature-channel transparency is per-channel; in [0, 1] for the shader.
            ch0trans_val = float(params.slicer_temp_transparency) / 100.0

            # Color mode
            useBB = 1 if params.slicer_temp_color_mode == "BLACKBODY" else 0

        elif params.slicer_channel == "FUEL":
            from ...libs.theron import TrEFXChannel

            fuel_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_FUEL
            )
            if fuel_tex is None:
                return False
            fieldtex0 = fuel_tex

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            # Clip bounds are stored as percentages 0..100; convert to the
            # [0, 1] range that the baked LUT's alpha lives in.
            fuel_min_clip = float(params.slicer_fuel_min_opacity_clip) / 100.0
            fuel_max_clip = float(params.slicer_fuel_max_opacity_clip) / 100.0
            fuel_xfer = self._ensure_xfer_texture(
                obj,
                "explosiafx_display_slicer_fuel_color",
                "explosiafx_display_slicer_fuel_alpha",
                fuel_min_clip,
                fuel_max_clip,
            )
            if fuel_xfer is not None:
                xfertex0 = fuel_xfer

            glblopacity_val = 1.0 - (params.slicer_transparency / 100.0)
            field0_min = float(params.slicer_fuel_min)
            # InvRange = 1 / (max - min). The shader normalises via
            # `(value - MinRange) * InvRange`; guard against zero-width range.
            field0_inv = 1.0 / max(params.slicer_fuel_max - params.slicer_fuel_min, 1e-6)
            # Fuel-channel transparency is per-channel; in [0, 1] for the shader.
            ch0trans_val = float(params.slicer_fuel_transparency) / 100.0

        elif params.slicer_channel == "SMOKE_TEMP":
            from ...libs.theron import TrEFXChannel

            # Channel 0 - temperature
            temp_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_TEMPERATURE
            )

            # Channel 1 - smoke
            smoke_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_SMOKE
            )

            # Fall back to single-channel rendering when one of the two channels
            # is disabled in the backend: leave the missing channel bound to the
            # 1×1×1 zero-fallback texture with the identity range and zero
            # transparency that the defaults block above already set. The shader's
            # "over" composite then collapses to just the surviving layer
            #
            # If both channels are unavailable, disable draw.
            if temp_tex is None and smoke_tex is None:
                return False

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            glblopacity_val = 1.0 - (params.slicer_transparency / 100.0)

            if temp_tex is not None:
                fieldtex0 = temp_tex
                #
                # TEMPERATURE
                #
                # Clip bounds are stored as percentages 0..100; convert to the
                # [0, 1] range that the baked LUT's alpha lives in.
                temp_min_clip = float(params.slicer_temp_min_opacity_clip) / 100.0
                temp_max_clip = float(params.slicer_temp_max_opacity_clip) / 100.0
                temp_xfer = self._ensure_xfer_texture(
                    obj,
                    "explosiafx_display_slicer_temp_color",
                    "explosiafx_display_slicer_temp_alpha",
                    temp_min_clip,
                    temp_max_clip,
                )
                if temp_xfer is not None:
                    xfertex0 = temp_xfer

                field0_min = float(params.slicer_temp_min)
                # InvRange = 1 / (max - min). The shader normalises via
                # `(value - MinRange) * InvRange`; guard against zero-width range.
                field0_inv = 1.0 / max(params.slicer_temp_max - params.slicer_temp_min, 1e-6)
                # Temperature-channel transparency is per-channel; in [0, 1] for the shader.
                ch0trans_val = float(params.slicer_temp_transparency) / 100.0

                # Color mode
                useBB = 1 if params.slicer_temp_color_mode == "BLACKBODY" else 0

            if smoke_tex is not None:
                fieldtex1 = smoke_tex
                #
                # SMOKE
                #
                # Clip bounds are stored as percentages 0..100; convert to the
                # [0, 1] range that the baked LUT's alpha lives in.
                smoke_min_clip = float(params.slicer_smoke_min_opacity_clip) / 100.0
                smoke_max_clip = float(params.slicer_smoke_max_opacity_clip) / 100.0
                smoke_xfer = self._ensure_xfer_texture(
                    obj,
                    "explosiafx_display_slicer_smoke_color",
                    "explosiafx_display_slicer_smoke_alpha",
                    smoke_min_clip,
                    smoke_max_clip,
                )
                if smoke_xfer is not None:
                    xfertex1 = smoke_xfer

                field1_min = 0.0
                field1_inv = 1.0
                # Smoke-channel transparency is per-channel; in [0, 1] for the shader.
                ch1trans_val = float(params.slicer_smoke_transparency) / 100.0

        elif params.slicer_channel == "SMOKE_FUEL":
            from ...libs.theron import TrEFXChannel

            # Channel 0 - fuel
            fuel_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_FUEL
            )

            # Channel 1 - smoke
            smoke_tex = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_SMOKE
            )

            # See SMOKE_TEMP comment — same single-channel fallback strategy.
            if fuel_tex is None and smoke_tex is None:
                return False

            import bpy

            obj = bpy.data.objects.get(params.obj_name) if params.obj_name else None
            glblopacity_val = 1.0 - (params.slicer_transparency / 100.0)

            if fuel_tex is not None:
                fieldtex0 = fuel_tex
                #
                # FUEL
                #
                # Clip bounds are stored as percentages 0..100; convert to the
                # [0, 1] range that the baked LUT's alpha lives in.
                fuel_min_clip = float(params.slicer_fuel_min_opacity_clip) / 100.0
                fuel_max_clip = float(params.slicer_fuel_max_opacity_clip) / 100.0
                fuel_xfer = self._ensure_xfer_texture(
                    obj,
                    "explosiafx_display_slicer_fuel_color",
                    "explosiafx_display_slicer_fuel_alpha",
                    fuel_min_clip,
                    fuel_max_clip,
                )
                if fuel_xfer is not None:
                    xfertex0 = fuel_xfer

                field0_min = float(params.slicer_fuel_min)
                # InvRange = 1 / (max - min). The shader normalises via
                # `(value - MinRange) * InvRange`; guard against zero-width range.
                field0_inv = 1.0 / max(params.slicer_fuel_max - params.slicer_fuel_min, 1e-6)
                # Fuel-channel transparency is per-channel; in [0, 1] for the shader.
                ch0trans_val = float(params.slicer_fuel_transparency) / 100.0

            if smoke_tex is not None:
                fieldtex1 = smoke_tex
                #
                # SMOKE
                #
                # Clip bounds are stored as percentages 0..100; convert to the
                # [0, 1] range that the baked LUT's alpha lives in.
                smoke_min_clip = float(params.slicer_smoke_min_opacity_clip) / 100.0
                smoke_max_clip = float(params.slicer_smoke_max_opacity_clip) / 100.0
                smoke_xfer = self._ensure_xfer_texture(
                    obj,
                    "explosiafx_display_slicer_smoke_color",
                    "explosiafx_display_slicer_smoke_alpha",
                    smoke_min_clip,
                    smoke_max_clip,
                )
                if smoke_xfer is not None:
                    xfertex1 = smoke_xfer

                field1_min = 0.0
                field1_inv = 1.0
                # Smoke-channel transparency is per-channel; in [0, 1] for the shader.
                ch1trans_val = float(params.slicer_smoke_transparency) / 100.0

        elif params.slicer_channel == "COLOR":
            from ...libs.theron import TrEFXChannel

            color_r = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_COLOR_R
            )
            color_g = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_COLOR_G
            )
            color_b = self._fetch_efx_field_texture(
                params, scene.frame_current, TrEFXChannel.TR_EFX_CHANNEL_COLOR_B
            )
            if color_r is None or color_g is None or color_b is None:
                return False
            fieldtex0 = color_r
            fieldtex1 = color_g
            fieldtex2 = color_b

        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", self._slice_mvp)
        shader.uniform_int("mode", mode_val)
        shader.uniform_int("usebb", useBB)
        shader.uniform_float("bbPower", float(bbPower))
        shader.uniform_float("bbMin", bbMin)
        shader.uniform_float("bbMax", bbMax)
        shader.uniform_float("ch0trans", ch0trans_val)
        shader.uniform_float("ch1trans", ch1trans_val)
        shader.uniform_float("glblopacity", glblopacity_val)
        shader.uniform_float("field0MinRange", field0_min)
        shader.uniform_float("field0InvRange", field0_inv)
        shader.uniform_float("field1MinRange", field1_min)
        shader.uniform_float("field1InvRange", field1_inv)
        shader.uniform_sampler("fieldtex0", fieldtex0)
        shader.uniform_sampler("fieldtex1", fieldtex1)
        shader.uniform_sampler("fieldtex2", fieldtex2)
        shader.uniform_sampler("xfertex0", xfertex0)
        shader.uniform_sampler("xfertex1", xfertex1)

        prev_depth_test = gpu.state.depth_test_get()
        prev_depth_mask = gpu.state.depth_mask_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(False)
            gpu.state.blend_set("ALPHA")
            self._slice_batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")
            gpu.state.depth_test_set(prev_depth_test)
            gpu.state.depth_mask_set(prev_depth_mask)
        return True

    def shutdown(self) -> None:
        self._shader = None
        self._slice_batch = None
        self._slice_mvp = None
        self._cache_slice_num = None
        self._cache_world_matrix = None
        self._cache_domain_size = None
        self._cache_view_matrix = None
        self._cache_persp_matrix = None
        self._fallback_fieldtex = None
        self._fallback_xfertex = None
        self._speed_field_tex = None
        self._cached_speed_frame = None
        self._efx_field_cache.clear()
        self._xfer_tex_cache.clear()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_raymarcher: VolumeRaymarchBasicRenderer | None = None
_slices: VolumeSlicesBasicRenderer | None = None


class VolumeBasicRenderer(NexusRenderer):
    """Dispatcher: routes to the correct style renderer for this object."""

    def draw(self, context, pipeline, scene, params) -> bool:
        global _raymarcher, _slices

        # Turn off the VRM preview when the viewport is in a shading mode that
        # already renders the Volume object, otherwise the raymarcher preview
        # draws on top of the Cycles/Eevee render.
        # ``params.show_in_rendered`` allows override to keep our GPU volume preview.
        if not params.show_in_rendered:
            space = getattr(context, "space_data", None)
            shading = getattr(space, "shading", None)
            if getattr(shading, "type", None) in {"MATERIAL", "RENDERED"}:
                return False

        if params.render_style == "SLICES":
            if _slices is None:
                _slices = VolumeSlicesBasicRenderer()
            return _slices.draw(context, pipeline, scene, params)

        # Default == ray marcher
        if _raymarcher is None:
            _raymarcher = VolumeRaymarchBasicRenderer()
        return _raymarcher.draw(context, pipeline, scene, params)

    def shutdown(self) -> None:
        global _shader, _raymarcher, _slices
        _shader = None
        if _raymarcher is not None:
            _raymarcher.shutdown()
            _raymarcher = None
        if _slices is not None:
            _slices.shutdown()
            _slices = None
