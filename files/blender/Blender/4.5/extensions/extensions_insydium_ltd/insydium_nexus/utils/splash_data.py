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

import math

from mathutils import Vector

PART_TOP_ANCHOR = 0
PART_TOP_TANGENT_RIGHT = 1
PART_TOP_TANGENT_LEFT = 2
PART_BOTTOM_ANCHOR = 3
PART_BOTTOM_TANGENT_RIGHT = 4
PART_BOTTOM_TANGENT_LEFT = 5
PART_STRENGTH = 6

FLOATS_PER_HANDLE = 18
BEZIER_SUBDIVISIONS = 4

_RESAMPLE_SUBS = 128


def get_splash_handle_data(obj):
    bhandles = obj.get("_nx_splash_bhandles")
    strengths = obj.get("_nx_splash_strengths")
    if bhandles is None or strengths is None:
        return None, None
    return list(bhandles), list(strengths)


def set_splash_handle_data(obj, bhandles, strengths):
    obj["_nx_splash_bhandles"] = bhandles
    obj["_nx_splash_strengths"] = strengths


def get_handle_vec(bhandles, handle_index, part):
    base = handle_index * FLOATS_PER_HANDLE + part * 3
    return Vector((bhandles[base], bhandles[base + 1], bhandles[base + 2]))


def set_handle_vec(bhandles, handle_index, part, vec):
    base = handle_index * FLOATS_PER_HANDLE + part * 3
    bhandles[base] = vec.x
    bhandles[base + 1] = vec.y
    bhandles[base + 2] = vec.z


def get_bezier_points_for_span(bhandles, handle_count, i):
    j = (i + 1) % handle_count
    top_pts = [
        get_handle_vec(bhandles, i, PART_TOP_ANCHOR),
        get_handle_vec(bhandles, i, PART_TOP_TANGENT_RIGHT),
        get_handle_vec(bhandles, j, PART_TOP_TANGENT_LEFT),
        get_handle_vec(bhandles, j, PART_TOP_ANCHOR),
    ]
    bot_pts = [
        get_handle_vec(bhandles, i, PART_BOTTOM_ANCHOR),
        get_handle_vec(bhandles, i, PART_BOTTOM_TANGENT_RIGHT),
        get_handle_vec(bhandles, j, PART_BOTTOM_TANGENT_LEFT),
        get_handle_vec(bhandles, j, PART_BOTTOM_ANCHOR),
    ]
    return top_pts, bot_pts


def evaluate_bezier(p0, p1, p2, p3, t):
    """Evaluate cubic bezier at parameter t."""
    u = 1.0 - t
    uu = u * u
    uuu = uu * u
    tt = t * t
    ttt = tt * t
    return Vector(
        (
            uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0],
            uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1],
            uuu * p0[2] + 3 * uu * t * p1[2] + 3 * u * tt * p2[2] + ttt * p3[2],
        )
    )


def generate_default_handles(height, bottom_radius, top_radius, handle_count):
    """Generate default circular bezier handle positions for a splash shape."""
    bhandles = [0.0] * (FLOATS_PER_HANDLE * handle_count)
    strengths = [1.0] * handle_count

    interval = (2.0 * math.pi) / handle_count
    tangent_length_top = (2.0 * top_radius) / handle_count
    tangent_length_bot = (2.0 * bottom_radius) / handle_count

    for i in range(handle_count):
        angle = interval * (i + 2)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        cos_a2 = math.cos(angle + 0.0001)
        sin_a2 = math.sin(angle + 0.0001)

        tx = top_radius * cos_a
        ty = top_radius * sin_a
        bx = bottom_radius * cos_a
        by = bottom_radius * sin_a

        tx2 = top_radius * cos_a2
        ty2 = top_radius * sin_a2
        bx2 = bottom_radius * cos_a2
        by2 = bottom_radius * sin_a2

        t_dir_x = tx2 - tx
        t_dir_y = ty2 - ty
        t_len = math.sqrt(t_dir_x * t_dir_x + t_dir_y * t_dir_y)
        if t_len > 1e-8:
            t_dir_x /= t_len
            t_dir_y /= t_len

        b_dir_x = bx2 - bx
        b_dir_y = by2 - by
        b_len = math.sqrt(b_dir_x * b_dir_x + b_dir_y * b_dir_y)
        if b_len > 1e-8:
            b_dir_x /= b_len
            b_dir_y /= b_len

        base = i * FLOATS_PER_HANDLE

        bhandles[base + 0] = tx
        bhandles[base + 1] = ty
        bhandles[base + 2] = height

        bhandles[base + 3] = tx + tangent_length_top * t_dir_x
        bhandles[base + 4] = ty + tangent_length_top * t_dir_y
        bhandles[base + 5] = height

        bhandles[base + 6] = tx - tangent_length_top * t_dir_x
        bhandles[base + 7] = ty - tangent_length_top * t_dir_y
        bhandles[base + 8] = height

        bhandles[base + 9] = bx
        bhandles[base + 10] = by
        bhandles[base + 11] = 0.0

        bhandles[base + 12] = bx + tangent_length_bot * b_dir_x
        bhandles[base + 13] = by + tangent_length_bot * b_dir_y
        bhandles[base + 14] = 0.0

        bhandles[base + 15] = bx - tangent_length_bot * b_dir_x
        bhandles[base + 16] = by - tangent_length_bot * b_dir_y
        bhandles[base + 17] = 0.0

    return bhandles, strengths


def store_splash_prev_values(obj, props):
    obj["_nx_splash_prev_radius_top"] = props.ID_NX_SPLASH_RADIUS_TOP
    obj["_nx_splash_prev_radius_bottom"] = props.ID_NX_SPLASH_RADIUS_BOTTOM
    obj["_nx_splash_prev_height"] = props.ID_NX_SPLASH_HEIGHT
    obj["_nx_splash_prev_handle_count"] = props.ID_NX_SPLASH_HANDLE_COUNT


def scale_top_ring_handles(obj, scale_factor):
    bhandles, strengths = get_splash_handle_data(obj)
    if bhandles is None:
        return
    props = getattr(obj, "nexus_modifier", None)
    if props is None:
        return
    handle_count = props.ID_NX_SPLASH_HANDLE_COUNT
    if handle_count * FLOATS_PER_HANDLE > len(bhandles):
        return
    for i in range(handle_count):
        for part in (PART_TOP_ANCHOR, PART_TOP_TANGENT_RIGHT, PART_TOP_TANGENT_LEFT):
            vec = get_handle_vec(bhandles, i, part)
            vec.x *= scale_factor
            vec.y *= scale_factor
            set_handle_vec(bhandles, i, part, vec)
    set_splash_handle_data(obj, bhandles, strengths)


def scale_bottom_ring_handles(obj, scale_factor):
    bhandles, strengths = get_splash_handle_data(obj)
    if bhandles is None:
        return
    props = getattr(obj, "nexus_modifier", None)
    if props is None:
        return
    handle_count = props.ID_NX_SPLASH_HANDLE_COUNT
    if handle_count * FLOATS_PER_HANDLE > len(bhandles):
        return
    for i in range(handle_count):
        for part in (PART_BOTTOM_ANCHOR, PART_BOTTOM_TANGENT_RIGHT, PART_BOTTOM_TANGENT_LEFT):
            vec = get_handle_vec(bhandles, i, part)
            vec.x *= scale_factor
            vec.y *= scale_factor
            set_handle_vec(bhandles, i, part, vec)
    set_splash_handle_data(obj, bhandles, strengths)


def scale_height_handles(obj, scale_factor):
    bhandles, strengths = get_splash_handle_data(obj)
    if bhandles is None:
        return
    props = getattr(obj, "nexus_modifier", None)
    if props is None:
        return
    handle_count = props.ID_NX_SPLASH_HANDLE_COUNT
    if handle_count * FLOATS_PER_HANDLE > len(bhandles):
        return
    for i in range(handle_count):
        for part in range(6):
            vec = get_handle_vec(bhandles, i, part)
            vec.z *= scale_factor
            set_handle_vec(bhandles, i, part, vec)
    set_splash_handle_data(obj, bhandles, strengths)


def resample_handles(obj, old_count, new_count):
    bhandles, strengths = get_splash_handle_data(obj)
    if bhandles is None:
        return
    if old_count * FLOATS_PER_HANDLE > len(bhandles):
        return

    total_samples = old_count * _RESAMPLE_SUBS
    top_curve = []
    bot_curve = []
    for i in range(old_count):
        top_pts, bot_pts = get_bezier_points_for_span(bhandles, old_count, i)
        for sub in range(_RESAMPLE_SUBS):
            t = sub / _RESAMPLE_SUBS
            top_curve.append(evaluate_bezier(*top_pts, t))
            bot_curve.append(evaluate_bezier(*bot_pts, t))
    top_curve.append(top_curve[0])
    bot_curve.append(bot_curve[0])

    ext_strengths = strengths[:old_count] + [strengths[0]]
    new_strengths = []
    for i in range(new_count):
        pos = i / new_count * old_count
        src = min(int(pos), old_count - 1)
        frac = max(0.0, min(1.0, pos - src))
        s = ext_strengths[src] * (1.0 - frac) + ext_strengths[src + 1] * frac
        new_strengths.append(s)

    top_tang_lens = []
    bot_tang_lens = []
    for i in range(old_count):
        ta = get_handle_vec(bhandles, i, PART_TOP_ANCHOR)
        tr = get_handle_vec(bhandles, i, PART_TOP_TANGENT_RIGHT)
        top_tang_lens.append((tr - ta).length)
        ba = get_handle_vec(bhandles, i, PART_BOTTOM_ANCHOR)
        br = get_handle_vec(bhandles, i, PART_BOTTOM_TANGENT_RIGHT)
        bot_tang_lens.append((br - ba).length)
    top_tang_lens.append(top_tang_lens[0])
    bot_tang_lens.append(bot_tang_lens[0])

    tang_ratio = old_count / max(new_count, 1)

    new_bhandles = [0.0] * (FLOATS_PER_HANDLE * new_count)
    for i in range(new_count):
        pos = i / new_count
        curve_pos = pos * total_samples
        seg = min(int(curve_pos), total_samples - 1)
        frac = curve_pos - seg

        top_anchor = top_curve[seg] * (1.0 - frac) + top_curve[seg + 1] * frac
        bot_anchor = bot_curve[seg] * (1.0 - frac) + bot_curve[seg + 1] * frac

        eps = max(1, total_samples // 200)
        seg_fwd = min(seg + eps, total_samples)
        seg_bwd = max(seg - eps, 0)
        top_dir = (top_curve[seg_fwd] - top_curve[seg_bwd]).normalized()
        bot_dir = (bot_curve[seg_fwd] - bot_curve[seg_bwd]).normalized()

        src_handle = pos * old_count
        src_idx = min(int(src_handle), old_count - 1)
        src_frac = src_handle - src_idx
        top_tlen = (
            top_tang_lens[src_idx] * (1.0 - src_frac) + top_tang_lens[src_idx + 1] * src_frac
        ) * tang_ratio
        bot_tlen = (
            bot_tang_lens[src_idx] * (1.0 - src_frac) + bot_tang_lens[src_idx + 1] * src_frac
        ) * tang_ratio

        base = i * FLOATS_PER_HANDLE
        new_bhandles[base : base + 3] = [top_anchor.x, top_anchor.y, top_anchor.z]
        tr = top_anchor + top_dir * top_tlen
        new_bhandles[base + 3 : base + 6] = [tr.x, tr.y, tr.z]
        tl = top_anchor - top_dir * top_tlen
        new_bhandles[base + 6 : base + 9] = [tl.x, tl.y, tl.z]
        new_bhandles[base + 9 : base + 12] = [bot_anchor.x, bot_anchor.y, bot_anchor.z]
        br = bot_anchor + bot_dir * bot_tlen
        new_bhandles[base + 12 : base + 15] = [br.x, br.y, br.z]
        bl = bot_anchor - bot_dir * bot_tlen
        new_bhandles[base + 15 : base + 18] = [bl.x, bl.y, bl.z]

    set_splash_handle_data(obj, new_bhandles, new_strengths)
