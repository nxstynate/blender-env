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

"""CPU fallback solid UV-sphere particle mode."""

from __future__ import annotations

import math

import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

from ...core.particle_renderer import ParticleRenderer
from ..basic_utils import blinn_phong_batch, view_matrices

_shader = None

# UV sphere: 5 stacks, 8 slices.
# 64 triangles = 192 triangle vertices.
_N_SLICES = 8
_N_STACKS = 5
_PI = math.pi


def _sphere_pt(stack_idx: int, slice_idx: int) -> np.ndarray:
    """Unit-sphere point at given stack/slice index.

    stack_idx 0 = north pole (0,0,1), _N_STACKS = south pole (0,0,-1).
    """
    phi = stack_idx * _PI / _N_STACKS
    theta = slice_idx * 2.0 * _PI / _N_SLICES
    sp, cp = math.sin(phi), math.cos(phi)
    st, ct = math.sin(theta), math.cos(theta)
    return np.array([sp * ct, sp * st, cp], dtype=np.float32)


def _build_filled_verts() -> np.ndarray:
    """Return (192, 3) unit-sphere vertex positions (also normals).

    For a unit sphere the outward normal equals the vertex position.
    """
    verts: list[np.ndarray] = []

    # North cap
    for tri in range(_N_SLICES):
        verts.append(_sphere_pt(0, 0))
        verts.append(_sphere_pt(1, tri))
        verts.append(_sphere_pt(1, (tri + 1) % _N_SLICES))

    # Middle bands
    for band in range(_N_STACKS - 2):
        ring1 = band + 1
        ring2 = band + 2
        for sl in range(_N_SLICES):
            verts.append(_sphere_pt(ring1, sl))
            verts.append(_sphere_pt(ring2, sl))
            verts.append(_sphere_pt(ring2, (sl + 1) % _N_SLICES))
            verts.append(_sphere_pt(ring1, sl))
            verts.append(_sphere_pt(ring2, (sl + 1) % _N_SLICES))
            verts.append(_sphere_pt(ring1, (sl + 1) % _N_SLICES))

    # South cap (winding reversed so face points outward)
    for tri in range(_N_SLICES):
        verts.append(_sphere_pt(_N_STACKS, 0))
        verts.append(_sphere_pt(_N_STACKS - 1, (tri + 1) % _N_SLICES))
        verts.append(_sphere_pt(_N_STACKS - 1, tri))

    return np.stack(verts, axis=0).astype(np.float32)


# (V, 3) — for a unit sphere the normal at each vertex equals the vertex position.
_SPHERE_VERTS = _build_filled_verts()
_N_VERTS = _SPHERE_VERTS.shape[0]


def _get_shader():
    global _shader
    if _shader is not None:
        return _shader

    vert_out = gpu.types.GPUStageInterfaceInfo("sphere_if")
    vert_out.smooth("VEC3", "v_color")
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "vcol")
    info.vertex_out(vert_out)
    info.fragment_out(0, "VEC4", "FragColor")
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.vertex_source(
        "void main() {\n"
        "    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "    v_color = vcol;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n    FragColor = vec4(v_color, 1.0);\n}\n")
    _shader = gpu.shader.create_from_info(info)
    return _shader


class SphereBasicRenderer(ParticleRenderer):
    """Solid UV-sphere with Blinn-Phong shading (CPU path)."""

    def draw(self, context, pipeline, scene, params) -> bool:
        sk = scene.session_uid
        if not self.ensure_cpu_ready_for_params(scene, context, params):
            return True

        base = self.read_cpu_base_for_params(params, pipeline, sk)
        if base is None:
            return True
        positions, colors, count = base
        if count == 0:
            return True

        region_data = getattr(context, "region_data", None)
        if region_data is None:
            return True

        view_gl, r3, l_v = view_matrices(region_data.view_matrix)

        radii_result = self.read_cpu_radii_for_params(params, pipeline, sk)
        radii_array = radii_result[0] if radii_result is not None else None
        default_half = np.float32(params.size) * np.float32(0.01)

        indices = self.iter_particle_indices(params, len(positions))
        if indices.size == 0:
            return True
        K = indices.shape[0]

        pos_sub = positions[indices].astype(np.float32, copy=False)
        col_sub = colors[indices].astype(np.float32, copy=False)
        if radii_array is not None:
            h = radii_array[indices].astype(np.float32, copy=False)
            h = np.where(np.isfinite(h), h, default_half)
        else:
            h = np.full(K, default_half, dtype=np.float32)
        h = np.maximum(h, np.float32(1e-9))

        # (K, V, 3) world positions and normals.
        tri_pos = pos_sub[:, None, :] + _SPHERE_VERTS[None, :, :] * h[:, None, None]
        tri_normals = np.broadcast_to(_SPHERE_VERTS[None, :, :], (K, _N_VERTS, 3))
        base_rgb = col_sub[:, None, :]

        tri_cols = blinn_phong_batch(tri_pos, tri_normals, view_gl, r3, l_v, base_rgb)

        tri_pos = tri_pos.reshape(-1, 3)
        tri_cols = tri_cols.reshape(-1, 3)

        shader = _get_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", region_data.perspective_matrix)
        batch = batch_for_shader(shader, "TRIS", {"pos": tri_pos, "vcol": tri_cols})
        prev_depth_mask = gpu.state.depth_mask_get()
        prev_depth_test = gpu.state.depth_test_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(True)
            batch.draw(shader)
        finally:
            gpu.state.depth_mask_set(prev_depth_mask)
            gpu.state.depth_test_set(prev_depth_test)
        return True

    def shutdown(self) -> None:
        global _shader
        _shader = None
