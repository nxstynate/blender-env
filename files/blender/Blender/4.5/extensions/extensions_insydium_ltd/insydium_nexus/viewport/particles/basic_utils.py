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

"""Vectorized helpers shared by the basic (CPU-upload) particle renderers.

Every function in this module is allocation-light and avoids per-particle
Python loops.  Renderers build their vertex buffers by broadcasting over
(K,) particle batches, then hand numpy arrays straight to ``batch_for_shader``.
"""

from __future__ import annotations

import numpy as np

# World-space light direction used by every filled renderer (matches native shaders).
LWORLD = np.array([0.45, 0.75, 0.4], dtype=np.float32)
LWORLD /= np.linalg.norm(LWORLD)

UP_MAP = {
    "X_POS": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    "X_NEG": np.array([-1.0, 0.0, 0.0], dtype=np.float32),
    "Y_POS": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    "Y_NEG": np.array([0.0, -1.0, 0.0], dtype=np.float32),
    "Z_POS": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    "Z_NEG": np.array([0.0, 0.0, -1.0], dtype=np.float32),
}


def resolve_forced_up(up_value) -> np.ndarray:
    """Convert a Params.rotation_up_vector value to a (3,) float32 vector."""
    if isinstance(up_value, (tuple, list, np.ndarray)) and len(up_value) == 3:
        return np.asarray(up_value, dtype=np.float32)
    return UP_MAP.get(str(up_value), UP_MAP["Y_POS"])


def view_basis(view_matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return camera (right, up, forward) axes from ``region_data.view_matrix``."""
    view_inv = view_matrix.inverted()
    right = np.array([view_inv[0][0], view_inv[1][0], view_inv[2][0]], dtype=np.float32)
    up = np.array([view_inv[0][1], view_inv[1][1], view_inv[2][1]], dtype=np.float32)
    forward = -np.array([view_inv[0][2], view_inv[1][2], view_inv[2][2]], dtype=np.float32)
    right /= max(1e-12, float(np.linalg.norm(right)))
    up /= max(1e-12, float(np.linalg.norm(up)))
    forward /= max(1e-12, float(np.linalg.norm(forward)))
    return right, up, forward


def view_matrices(view_matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(view_gl, r3, l_v)`` used by Blinn-Phong filled renderers.

    * ``view_gl`` is the column-major 4x4 view matrix.
    * ``r3`` is the upper-left 3x3 rotation part.
    * ``l_v`` is the world light direction transformed into view space.
    """
    view_row = np.asarray(view_matrix, dtype=np.float32).reshape(4, 4)
    view_gl = view_row.T
    r3 = view_gl[:3, :3]
    l_v = r3 @ LWORLD
    ln = float(np.linalg.norm(l_v))
    if ln > 1e-20:
        l_v = l_v / ln
    return view_gl, r3, l_v


def gather_sub(arr: np.ndarray | None, indices: np.ndarray) -> np.ndarray | None:
    """Advanced-index ``arr`` if provided, else return None."""
    return arr[indices] if arr is not None else None


# ---------------------------------------------------------------------------
# Rotation matrices
# ---------------------------------------------------------------------------


def _rot_mats_velocity(vel_sub: np.ndarray) -> np.ndarray:
    """Per-particle (right, forward, up) orientation from velocity.

    Returns ``(K, 3, 3)`` with columns ``[right, forward, up]`` (column-stack).
    Matches ``_orient_from_velocity`` in the old per-particle code.
    """
    v = vel_sub.astype(np.float32, copy=False) * np.float32(0.01)
    len_sq = np.einsum("ki,ki->k", v, v)
    safe = len_sq > 1e-18
    inv_len = np.zeros_like(len_sq)
    np.reciprocal(np.sqrt(np.maximum(len_sq, 1e-18)), out=inv_len)
    forward = v * inv_len[:, None]
    fallback = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    forward = np.where(safe[:, None], forward, fallback[None, :])

    z_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    y_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    ref = np.where(np.abs(forward[:, 2:3]) < 0.999, z_up, y_up)

    right = np.cross(forward, ref)
    r_len = np.linalg.norm(right, axis=1, keepdims=True)
    right = right / np.maximum(r_len, 1e-12)
    up = np.cross(right, forward)
    return np.stack([right, forward, up], axis=2)


def _orient_from_up(up_ref: np.ndarray) -> np.ndarray:
    """Constant (3, 3) orient-from-up basis used by UP_VECTOR mode."""
    up_len_sq = float(np.dot(up_ref, up_ref))
    if up_len_sq > 1e-12:
        up = up_ref / np.sqrt(up_len_sq)
    else:
        up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    ref = (
        np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if abs(up[2]) < 0.999
        else np.array([0.0, 1.0, 0.0], dtype=np.float32)
    )
    right = np.cross(up, ref)
    right /= max(1e-12, float(np.linalg.norm(right)))
    forward = np.cross(right, up)
    forward /= max(1e-12, float(np.linalg.norm(forward)))
    return np.column_stack((right, forward, up)).astype(np.float32)


def _rot_mats_hpb(rot_sub: np.ndarray, forced_up: np.ndarray) -> np.ndarray:
    """Per-particle HPB rotation matrix with axis remap + orient-from-up.

    Mirrors: ``_orient_from_up(forced_up) @ rot_z(hpb[2]) @ rot_x(hpb[0]) @ rot_y(hpb[1])``.
    Returns ``(K, 3, 3)``.
    """
    orient = _orient_from_up(forced_up)

    hpb = rot_sub[:, [1, 2, 0]].astype(np.float32, copy=False)
    ax, ay, az = hpb[:, 0], hpb[:, 1], hpb[:, 2]
    cx, sx = np.cos(ax), np.sin(ax)
    cy, sy = np.cos(ay), np.sin(ay)
    cz, sz = np.cos(az), np.sin(az)

    K = rot_sub.shape[0]
    zeros = np.zeros(K, dtype=np.float32)
    ones = np.ones(K, dtype=np.float32)
    # Build Rx (K, 3, 3)
    rx = np.stack(
        [
            np.stack([ones, zeros, zeros], axis=1),
            np.stack([zeros, cx, sx], axis=1),
            np.stack([zeros, -sx, cx], axis=1),
        ],
        axis=1,
    )
    # Ry
    ry = np.stack(
        [
            np.stack([cy, zeros, -sy], axis=1),
            np.stack([zeros, ones, zeros], axis=1),
            np.stack([sy, zeros, cy], axis=1),
        ],
        axis=1,
    )
    # Rz
    rz = np.stack(
        [
            np.stack([cz, sz, zeros], axis=1),
            np.stack([-sz, cz, zeros], axis=1),
            np.stack([zeros, zeros, ones], axis=1),
        ],
        axis=1,
    )
    # orient @ Rz @ Rx @ Ry
    rxy = np.einsum("kij,kjl->kil", rx, ry)
    rzxy = np.einsum("kij,kjl->kil", rz, rxy)
    return np.einsum("ij,kjl->kil", orient, rzxy)


def rot_mats_for_shape(
    use_hpb: bool,
    use_tangential: bool,
    rotations_sub: np.ndarray | None,
    velocities_sub: np.ndarray | None,
    forced_up: np.ndarray,
    count: int,
) -> np.ndarray:
    """Return (K, 3, 3) rotation matrices for the active mode.

    Falls back to identity when no data is available. ``rotations_sub`` and
    ``velocities_sub`` must already be gathered for the active sub-range.
    """
    if use_hpb and rotations_sub is not None:
        return _rot_mats_hpb(rotations_sub, forced_up)
    if use_tangential and velocities_sub is not None:
        return _rot_mats_velocity(velocities_sub)
    identity = np.eye(3, dtype=np.float32)
    return np.broadcast_to(identity, (count, 3, 3)).copy()


# ---------------------------------------------------------------------------
# Rotation-mode resolution (matches box/pyramid branching)
# ---------------------------------------------------------------------------


def resolve_rotation_mode(
    params,
    rotations_result,
    velocities_result,
) -> tuple[bool, bool, np.ndarray | None, np.ndarray | None]:
    """Replicate the ``use_hpb/use_tangential`` branching used by box/pyramid.

    Returns ``(use_hpb, use_tangential, rotations_arr, velocities_arr)``.
    """
    rotation_mode = str(getattr(params, "rotation_mode", "NONE"))
    use_hpb = rotation_mode == "UP_VECTOR"
    use_tangential = rotation_mode in ("NONE", "TANGENTIAL")
    if use_hpb and rotations_result is None:
        use_hpb = False
    if use_tangential and velocities_result is None:
        use_tangential = False
    if not use_hpb and not use_tangential and velocities_result is not None:
        use_tangential = True
    rotations_arr = rotations_result[0] if (use_hpb and rotations_result is not None) else None
    velocities_arr = (
        velocities_result[0] if (use_tangential and velocities_result is not None) else None
    )
    return use_hpb, use_tangential, rotations_arr, velocities_arr


# ---------------------------------------------------------------------------
# Blinn-Phong shading (batched)
# ---------------------------------------------------------------------------


def blinn_phong_batch(
    positions_world: np.ndarray,
    normals_world: np.ndarray,
    view_gl: np.ndarray,
    r3: np.ndarray,
    l_v: np.ndarray,
    base_rgb: np.ndarray,
) -> np.ndarray:
    """Shade a batch of vertices with the same ambient/diffuse/specular model.

    * ``positions_world`` and ``normals_world`` must share shape ``(..., 3)``.
    * ``base_rgb`` is broadcast-compatible with ``positions_world[..., 0]``.

    Returns an RGB array of the same leading shape (always ``float32``).
    """
    p_view_xyz = positions_world @ r3.T + view_gl[:3, 3]
    v_dir = -p_view_xyz
    v_len = np.linalg.norm(v_dir, axis=-1, keepdims=True)
    v_dir = v_dir / np.maximum(v_len, 1e-20)

    n_v = normals_world @ r3.T
    n_len = np.linalg.norm(n_v, axis=-1, keepdims=True)
    n_v = n_v / np.maximum(n_len, 1e-20)

    hvec = l_v + v_dir
    h_len = np.linalg.norm(hvec, axis=-1, keepdims=True)
    hvec = hvec / np.maximum(h_len, 1e-20)

    diff = np.maximum(np.einsum("...i,i->...", n_v, l_v), 0.0)
    spec = np.maximum(np.einsum("...i,...i->...", n_v, hvec), 0.0) ** 48
    rgb = base_rgb * (0.12 + 0.58 * diff[..., None]) + np.float32(0.25) * spec[..., None]
    return np.clip(rgb, 0.0, 1.0).astype(np.float32, copy=False)
