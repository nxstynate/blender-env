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
from mathutils import Matrix, Vector

from ..properties.nx_falloff import SPEC, get_falloff_curve_specs, get_falloff_gradient_specs
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_ORANGE,
    XP_COLOR_MODS_RED,
    draw_circle,
    draw_lines,
)
from .base import NexusObject, UIFlags


class NexusFalloff(NexusObject):
    object_type = "NX_FALLOFF"
    object_name = "nxFalloff"
    object_label = "Falloff Object"
    object_description = "Spatial falloff object for controlling modifier influence"
    icon_name = "nx_falloff_box"
    category = "Objects"
    menu_category = None
    gizmo_max_handles = 7

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def on_create(cls, obj) -> None:
        from ..properties.nx_falloff import FALLOFF_MODE_DISPLAY_NAMES

        obj.name = FALLOFF_MODE_DISPLAY_NAMES.get("ID_NX_FALLOFF_MODE_BOX", cls.object_name)

    @classmethod
    def get_instance_icon_id(cls, obj) -> int:
        from ..icons import get_icon
        from ..properties.nx_falloff import FALLOFF_MODE_ICONS

        mode = obj.nexus_modifier.ID_NX_FALLOFF_MODE
        icon_name = FALLOFF_MODE_ICONS.get(mode, cls.icon_name)
        return get_icon(icon_name)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_curve_specs(cls):
        return get_falloff_curve_specs()

    @classmethod
    def get_gradient_specs(cls):
        return get_falloff_gradient_specs()

    @classmethod
    def draw_ui(cls, layout, data):
        from ..utils.curve import NexusCurve
        from ..utils.gradient import NexusGradient

        obj = data.id_data

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_FALLOFF_MODE")
        col.prop(data, "ID_NX_FALLOFF_INVERT")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_FALLOFF_WEIGHT")
        col.prop(data, "ID_NX_FALLOFF_SCALE")

        mode = data.ID_NX_FALLOFF_MODE

        if mode == "ID_NX_FALLOFF_MODE_LINEAR":
            col.prop(data, "ID_NX_FALLOFF_LINEAR_DIR")

        col.separator(type="LINE")

        if mode == "ID_NX_FALLOFF_MODE_SPHERE":
            col.prop(data, "ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET")
            col.prop(data, "ID_NX_FALLOFF_SPHERE_RADIUS_OUTER")
        elif mode == "ID_NX_FALLOFF_MODE_BOX":
            col.prop(data, "ID_NX_FALLOFF_BOX_SIZE_OFFSET")
            col.prop(data, "ID_NX_FALLOFF_BOX_SIZE_OUTER")
        elif mode == "ID_NX_FALLOFF_MODE_LINEAR":
            col.prop(data, "ID_NX_FALLOFF_LINEAR_SIZE_OFFSET")

        if mode != "ID_NX_FALLOFF_MODE_NOISE":
            col.separator(type="LINE")
            NexusCurve(obj, "falloff_spline").draw_ui(layout, "Falloff Spline")

        if mode == "ID_NX_FALLOFF_MODE_NOISE":
            col = layout.column()
            col.use_property_split = True

            col.prop(data, "ID_NX_FALLOFF_NOISE_TYPE")
            col.separator(type="LINE")

            col.prop(data, "ID_NX_FALLOFF_NOISE_SEED")
            col.separator(type="LINE")

            if obj:
                NexusGradient(obj, "falloff_noise_contrast").draw_ui(col, "Contrast")
            col.separator(type="LINE")

            col.prop(data, "ID_NX_FALLOFF_NOISE_SCALE")
            col.prop(data, "ID_NX_FALLOFF_NOISE_PERSISTENCE")
            col.prop(data, "ID_NX_FALLOFF_NOISE_LACUNARITY")
            col.prop(data, "ID_NX_FALLOFF_NOISE_FREQUENCY")
            col.prop(data, "ID_NX_FALLOFF_NOISE_OCTAVES")

    @classmethod
    def draw_viewport(cls, obj, props, context) -> None:
        mode = getattr(props, "ID_NX_FALLOFF_MODE", "ID_NX_FALLOFF_MODE_BOX")
        scale = getattr(props, "ID_NX_FALLOFF_SCALE", 100.0) / 100.0

        mx = obj.matrix_world.copy()
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(1.5)

        if mode == "ID_NX_FALLOFF_MODE_BOX":
            cls._draw_box_mode(shader, mx, props, scale)
        elif mode == "ID_NX_FALLOFF_MODE_SPHERE":
            cls._draw_sphere_mode(shader, mx, props, scale)
        elif mode == "ID_NX_FALLOFF_MODE_LINEAR":
            cls._draw_linear_mode(shader, mx, props, scale)
        elif mode == "ID_NX_FALLOFF_MODE_NOISE":
            cls._draw_noise_mode(shader, mx, props, scale)

        gpu.state.blend_set("NONE")
        gpu.state.line_width_set(1.0)

    @classmethod
    def _draw_box_mode(cls, shader, mx, props, scale):
        outer = Vector(getattr(props, "ID_NX_FALLOFF_BOX_SIZE_OUTER", (1.0, 1.0, 1.0)))
        offset = getattr(props, "ID_NX_FALLOFF_BOX_SIZE_OFFSET", -0.25)

        half_size = outer * 0.5 * scale

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        cls._draw_bounding_box(shader, mx, half_size)

        inner_half = Vector(
            (
                max(half_size.x + offset, 0),
                max(half_size.y + offset, 0),
                max(half_size.z + offset, 0),
            )
        )
        if inner_half.x > 0 and inner_half.y > 0 and inner_half.z > 0:
            shader.uniform_float("color", XP_COLOR_MODS_ORANGE)
            cls._draw_bounding_box(shader, mx, inner_half)

    @classmethod
    def _draw_sphere_mode(cls, shader, mx, props, scale):
        outer_radius = getattr(props, "ID_NX_FALLOFF_SPHERE_RADIUS_OUTER", 0.5) * scale
        offset = getattr(props, "ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET", -0.25)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        draw_circle(shader, mx, outer_radius, plane="XY")
        draw_circle(shader, mx, outer_radius, plane="XZ")
        draw_circle(shader, mx, outer_radius, plane="YZ")

        inner_radius = max(outer_radius + offset, 0)
        if inner_radius > 0:
            shader.uniform_float("color", XP_COLOR_MODS_ORANGE)
            draw_circle(shader, mx, inner_radius, plane="XY")
            draw_circle(shader, mx, inner_radius, plane="XZ")
            draw_circle(shader, mx, inner_radius, plane="YZ")

    @classmethod
    def _draw_linear_mode(cls, shader, mx, props, scale):
        offset = getattr(props, "ID_NX_FALLOFF_LINEAR_SIZE_OFFSET", 1.0) * scale
        direction = getattr(props, "ID_NX_FALLOFF_LINEAR_DIR", "ID_NX_FALLOFF_LINEAR_DIR_Y_P")
        kxy = 0.5

        axis_map = {
            "ID_NX_FALLOFF_LINEAR_DIR_X_P": (
                Vector((1, 0, 0)),
                Vector((0, 1, 0)),
                Vector((0, 0, 1)),
            ),
            "ID_NX_FALLOFF_LINEAR_DIR_X_N": (
                Vector((-1, 0, 0)),
                Vector((0, 1, 0)),
                Vector((0, 0, 1)),
            ),
            "ID_NX_FALLOFF_LINEAR_DIR_Y_P": (
                Vector((0, 1, 0)),
                Vector((1, 0, 0)),
                Vector((0, 0, 1)),
            ),
            "ID_NX_FALLOFF_LINEAR_DIR_Y_N": (
                Vector((0, -1, 0)),
                Vector((1, 0, 0)),
                Vector((0, 0, 1)),
            ),
            "ID_NX_FALLOFF_LINEAR_DIR_Z_P": (
                Vector((0, 0, 1)),
                Vector((1, 0, 0)),
                Vector((0, 1, 0)),
            ),
            "ID_NX_FALLOFF_LINEAR_DIR_Z_N": (
                Vector((0, 0, -1)),
                Vector((1, 0, 0)),
                Vector((0, 1, 0)),
            ),
        }

        default_dir = "ID_NX_FALLOFF_LINEAR_DIR_Y_P"
        primary, perp_a, perp_b = axis_map.get(
            direction,
            axis_map[default_dir],
        )

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        cls._draw_rectangle(shader, mx, primary * offset, perp_a, perp_b, kxy)
        cls._draw_rectangle(shader, mx, primary * -offset, perp_a, perp_b, kxy)

        shader.uniform_float("color", XP_COLOR_MODS_ORANGE)
        cls._draw_rectangle(shader, mx, Vector((0, 0, 0)), perp_a, perp_b, kxy)

        shader.uniform_float("color", XP_COLOR_MODS_RED)
        start = mx @ (primary * -offset)
        end = mx @ (primary * offset)
        tip = primary * offset
        barb_size = 0.1

        arrow_lines = [
            (start, end),
            (end, mx @ (tip - primary * barb_size + perp_a * barb_size * 0.5)),
            (end, mx @ (tip - primary * barb_size - perp_a * barb_size * 0.5)),
            (end, mx @ (tip - primary * barb_size + perp_b * barb_size * 0.5)),
            (end, mx @ (tip - primary * barb_size - perp_b * barb_size * 0.5)),
        ]
        draw_lines(shader, arrow_lines)

    @classmethod
    def _draw_noise_mode(cls, shader, mx, props, scale):
        outer_half = max(scale * 0.5, 0)
        inner_half = outer_half * 0.5

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        cls._draw_rounded_square_xy(shader, mx, outer_half, corner_radius=0.08, segments=8)

        shader.uniform_float("color", XP_COLOR_MODS_ORANGE)
        cls._draw_rounded_square_xy(shader, mx, inner_half, corner_radius=0.08, segments=8)

        noise_scale = getattr(props, "ID_NX_FALLOFF_NOISE_SCALE", 100.0) / 100.0
        diag_dir = Vector((1, 1, 0)).normalized()
        diag_end = diag_dir * outer_half * noise_scale

        shader.uniform_float("color", XP_COLOR_MODS_RED)
        origin = mx @ Vector((0, 0, 0))
        end = mx @ diag_end
        draw_lines(shader, [(origin, end)])

    @staticmethod
    def _draw_bounding_box(shader, mx: Matrix, half_size: Vector) -> None:
        hx, hy, hz = half_size.x, half_size.y, half_size.z

        corners = [
            Vector((-hx, -hy, -hz)),
            Vector((hx, -hy, -hz)),
            Vector((hx, -hy, hz)),
            Vector((-hx, -hy, hz)),
            Vector((-hx, hy, -hz)),
            Vector((hx, hy, -hz)),
            Vector((hx, hy, hz)),
            Vector((-hx, hy, hz)),
        ]
        corners = [mx @ c for c in corners]

        edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]

        lines = [(corners[e[0]], corners[e[1]]) for e in edges]
        draw_lines(shader, lines)

    @staticmethod
    def _draw_rectangle(
        shader, mx: Matrix, center: Vector, perp_a: Vector, perp_b: Vector, half_extent: float
    ) -> None:
        c0 = mx @ (center + perp_a * half_extent + perp_b * half_extent)
        c1 = mx @ (center + perp_a * half_extent - perp_b * half_extent)
        c2 = mx @ (center - perp_a * half_extent - perp_b * half_extent)
        c3 = mx @ (center - perp_a * half_extent + perp_b * half_extent)

        draw_lines(shader, [(c0, c1), (c1, c2), (c2, c3), (c3, c0)])

    @staticmethod
    def _draw_rounded_square_xy(
        shader, mx: Matrix, half_extent: float, corner_radius: float, segments: int = 8
    ) -> None:
        if half_extent <= 0:
            return

        r = min(corner_radius, half_extent)
        h = half_extent - r

        corner_centers = [
            Vector((h, h, 0)),
            Vector((-h, h, 0)),
            Vector((-h, -h, 0)),
            Vector((h, -h, 0)),
        ]
        start_angles = [0.0, math.pi * 0.5, math.pi, math.pi * 1.5]

        lines = []
        prev_point = None
        first_point = None

        for ci in range(4):
            center = corner_centers[ci]
            start_angle = start_angles[ci]

            for si in range(segments + 1):
                angle = start_angle + (si / segments) * (math.pi * 0.5)
                point = mx @ Vector(
                    (
                        center.x + math.cos(angle) * r,
                        center.y + math.sin(angle) * r,
                        0.0,
                    )
                )

                if first_point is None:
                    first_point = point

                if prev_point is not None:
                    lines.append((prev_point, point))

                prev_point = point

        if prev_point is not None and first_point is not None:
            lines.append((prev_point, first_point))

        draw_lines(shader, lines)

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        mode = getattr(props, "ID_NX_FALLOFF_MODE", "ID_NX_FALLOFF_MODE_BOX")

        if mode == "ID_NX_FALLOFF_MODE_BOX":
            return [
                HandleConfig(
                    Vector((1, 0, 0)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=0,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 1, 0)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=1,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 0, 1)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=2,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((-1, 0, 0)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=0,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, -1, 0)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=1,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 0, -1)),
                    "ID_NX_FALLOFF_BOX_SIZE_OUTER",
                    prop_component=2,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((1, 0, 0)),
                    "ID_NX_FALLOFF_BOX_SIZE_OFFSET",
                    position_base_fn=lambda p: p.ID_NX_FALLOFF_BOX_SIZE_OUTER[0] * 0.5,
                    min_value_fn=lambda p: (
                        -min(
                            p.ID_NX_FALLOFF_BOX_SIZE_OUTER[0],
                            p.ID_NX_FALLOFF_BOX_SIZE_OUTER[1],
                            p.ID_NX_FALLOFF_BOX_SIZE_OUTER[2],
                        )
                        * 0.5
                    ),
                    max_value=0.0,
                ),
            ]

        elif mode == "ID_NX_FALLOFF_MODE_SPHERE":
            return [
                HandleConfig(
                    Vector((1, 0, 0)),
                    "ID_NX_FALLOFF_SPHERE_RADIUS_OUTER",
                    position_factor=1.0,
                    min_value=0.0,
                ),
                HandleConfig(
                    Vector((1, 0, 0)),
                    "ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET",
                    position_base_fn=lambda p: p.ID_NX_FALLOFF_SPHERE_RADIUS_OUTER,
                    min_value_fn=lambda p: -p.ID_NX_FALLOFF_SPHERE_RADIUS_OUTER,
                    max_value=0.0,
                ),
            ]

        elif mode == "ID_NX_FALLOFF_MODE_LINEAR":
            dir_axis = {
                "ID_NX_FALLOFF_LINEAR_DIR_X_P": Vector((1, 0, 0)),
                "ID_NX_FALLOFF_LINEAR_DIR_X_N": Vector((-1, 0, 0)),
                "ID_NX_FALLOFF_LINEAR_DIR_Y_P": Vector((0, 1, 0)),
                "ID_NX_FALLOFF_LINEAR_DIR_Y_N": Vector((0, -1, 0)),
                "ID_NX_FALLOFF_LINEAR_DIR_Z_P": Vector((0, 0, 1)),
                "ID_NX_FALLOFF_LINEAR_DIR_Z_N": Vector((0, 0, -1)),
            }
            direction = getattr(
                props,
                "ID_NX_FALLOFF_LINEAR_DIR",
                "ID_NX_FALLOFF_LINEAR_DIR_Y_P",
            )
            axis = dir_axis.get(direction, Vector((0, 1, 0)))
            return [
                HandleConfig(
                    axis,
                    "ID_NX_FALLOFF_LINEAR_SIZE_OFFSET",
                    position_factor=1.0,
                    min_value=0.0,
                ),
                HandleConfig(
                    -axis,
                    "ID_NX_FALLOFF_LINEAR_SIZE_OFFSET",
                    position_factor=1.0,
                    min_value=0.0,
                ),
            ]

        elif mode == "ID_NX_FALLOFF_MODE_NOISE":
            diag = Vector((1, 1, 0)).normalized()
            return [
                HandleConfig(
                    diag,
                    "ID_NX_FALLOFF_NOISE_SCALE",
                    position_factor=0.005,
                    min_value=0.0,
                ),
            ]

        return []
