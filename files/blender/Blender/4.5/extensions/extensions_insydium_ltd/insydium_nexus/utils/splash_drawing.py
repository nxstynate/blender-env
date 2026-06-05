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

import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from . import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .splash_data import (
    BEZIER_SUBDIVISIONS,
    PART_BOTTOM_ANCHOR,
    PART_TOP_ANCHOR,
    evaluate_bezier,
    get_bezier_points_for_span,
    get_handle_vec,
)
from .viewport import draw_thick_lines

COLOR_BEZIER = XP_COLOR_MODS_BLUE
COLOR_POLE_ROOT = XP_COLOR_MODS_BLUE
COLOR_POLE_SECONDARY = XP_COLOR_MODS_RED
COLOR_STRENGTH_LINE = (*XP_COLOR_MODS_BLUE[:3], 0.7)


def draw_splash_cone(context, mx, bhandles, strengths, handle_count):
    """Draw the complete splash cone wireframe: bezier rings, poles, strength lines."""
    top_ring_lines = []
    bot_ring_lines = []
    anchor_poles = []
    sub_poles = []

    for i in range(handle_count):
        top_pts, bot_pts = get_bezier_points_for_span(bhandles, handle_count, i)
        for sub in range(BEZIER_SUBDIVISIONS):
            t0 = sub / BEZIER_SUBDIVISIONS
            t1 = (sub + 1) / BEZIER_SUBDIVISIONS
            tp0 = mx @ evaluate_bezier(*top_pts, t0)
            bp0 = mx @ evaluate_bezier(*bot_pts, t0)
            top_ring_lines.append((tp0, mx @ evaluate_bezier(*top_pts, t1)))
            bot_ring_lines.append((bp0, mx @ evaluate_bezier(*bot_pts, t1)))

            if sub == 0:
                anchor_poles.extend([bp0, tp0])
            else:
                sub_poles.extend([bp0, tp0])

    draw_thick_lines(context, bot_ring_lines, COLOR_BEZIER, 1.5)
    draw_thick_lines(context, top_ring_lines, COLOR_BEZIER, 3.0)

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    shader.bind()
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")

    if sub_poles:
        shader.uniform_float("color", COLOR_POLE_SECONDARY)
        batch = batch_for_shader(shader, "LINES", {"pos": sub_poles})
        batch.draw(shader)
    if anchor_poles:
        shader.uniform_float("color", COLOR_POLE_ROOT)
        batch = batch_for_shader(shader, "LINES", {"pos": anchor_poles})
        batch.draw(shader)

    strength_coords = []
    for i in range(handle_count):
        top_anchor = mx @ get_handle_vec(bhandles, i, PART_TOP_ANCHOR)
        bot_anchor = mx @ get_handle_vec(bhandles, i, PART_BOTTOM_ANCHOR)
        direction = top_anchor - bot_anchor
        d_len = direction.length
        if d_len > 1e-8:
            direction /= d_len
        strength_point = top_anchor + direction * strengths[i]
        strength_coords.extend([top_anchor, strength_point])

    if strength_coords:
        shader.uniform_float("color", COLOR_STRENGTH_LINE)
        batch = batch_for_shader(shader, "LINES", {"pos": strength_coords})
        batch.draw(shader)

    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("NONE")


def draw_splash_fallback(context, mx, props, handle_count):
    """Draw simple circle-based fallback when handle data is unavailable."""
    radius_bottom = getattr(props, "ID_NX_SPLASH_RADIUS_BOTTOM", 0.25)
    radius_top = getattr(props, "ID_NX_SPLASH_RADIUS_TOP", 1.0)
    height = getattr(props, "ID_NX_SPLASH_HEIGHT", 0.75)

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.line_width_set(1.5)

    shader.uniform_float("color", COLOR_BEZIER)
    draw_circle(shader, mx, radius_bottom, plane="XY")
    top_matrix = mx @ Matrix.Translation(Vector((0.0, 0.0, height)))
    draw_circle(shader, top_matrix, radius_top, plane="XY")

    shader.uniform_float("color", COLOR_POLE_SECONDARY)
    connecting_lines = []
    for i in range(handle_count):
        angle = (i / handle_count) * math.pi * 2
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        bottom_point = mx @ Vector((cos_a * radius_bottom, sin_a * radius_bottom, 0.0))
        top_point = mx @ Vector((cos_a * radius_top, sin_a * radius_top, height))
        connecting_lines.append((bottom_point, top_point))
    draw_lines(shader, connecting_lines)

    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("NONE")
    gpu.state.line_width_set(1.0)
