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

import bpy
import gpu
from mathutils import Matrix, Vector

from ..properties.nx_direction import SPEC
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .base import MenuCategory, NexusModifier, UIFlags


class NXDirectionModifier(NexusModifier):
    object_type = "NX_DIRECTION"
    object_name = "nxDirection"
    object_label = "Direction"
    object_description = "Control particle direction with layered operations"
    icon_name = "nx_direction"
    category = "Motion"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_direction import add_default_direction_layer

        add_default_direction_layer(obj)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_direction import (
            draw_direction_layer_settings,
        )
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            data,
            "direction_layers",
            "direction_layers_index",
            label="Layers",
            draw_item_settings=draw_direction_layer_settings,
            menu_id="direction_layers",
        )

    @classmethod
    def _draw_barbs(cls, shader, tip_matrix: Matrix, barb_size: float) -> None:
        tip = tip_matrix.translation.copy()
        lines = [
            (tip, tip_matrix @ Vector((-barb_size, -barb_size, 0.0))),
            (tip, tip_matrix @ Vector((barb_size, -barb_size, 0.0))),
            (tip, tip_matrix @ Vector((0.0, -barb_size, -barb_size))),
            (tip, tip_matrix @ Vector((0.0, -barb_size, barb_size))),
        ]
        draw_lines(shader, lines)

    @classmethod
    def _draw_arrow(
        cls,
        shader,
        matrix: Matrix,
        length: float,
        barb_size: float = 0.1,
        start_offset: float = 0.0,
    ) -> None:
        """Draw a straight arrow along the matrix's local +Y axis."""
        start = matrix @ Vector((0.0, start_offset, 0.0))
        tip = matrix @ Vector((0.0, length, 0.0))

        draw_lines(shader, [(start, tip)])

        tip_mx = matrix.copy()
        tip_mx.translation = tip
        cls._draw_barbs(shader, tip_mx, barb_size)

    @classmethod
    def _draw_crosshair(cls, shader, matrix: Matrix, size: float) -> None:
        """Draw crosshair in XZ plane (C4D XY plane → Blender XZ plane)."""
        cross_lines = [
            (matrix @ Vector((size, 0.0, 0.0)), matrix @ Vector((-size, 0.0, 0.0))),
            (matrix @ Vector((0.0, 0.0, size)), matrix @ Vector((0.0, 0.0, -size))),
        ]
        draw_lines(shader, cross_lines)

    @classmethod
    def _draw_direction_arrow(
        cls, shader, matrix: Matrix, heading: float, pitch: float, length: float
    ) -> None:
        """Draw a direction arrow based on heading/pitch angles."""
        origin = matrix.translation.copy()
        barb_size = length * 0.15

        pitch_cos = math.cos(pitch)
        pitch_sin = math.sin(pitch)
        yaw_cos = math.cos(heading)
        yaw_sin = math.sin(heading)
        direction = Vector(
            (
                -yaw_sin * pitch_cos,
                pitch_cos * yaw_cos,
                pitch_sin,
            )
        )

        tip = origin + direction * length

        draw_lines(shader, [(origin, tip)])

        # Build arrowhead matrix at tip, oriented along the direction
        fwd = direction.normalized()
        up = Vector((0.0, 0.0, 1.0))
        right = fwd.cross(up).normalized()
        if right.length < 0.001:
            right = Vector((1.0, 0.0, 0.0))
            up = right.cross(fwd).normalized()
        else:
            up = right.cross(fwd).normalized()

        tip_mx = Matrix(
            (
                right.to_4d(),
                fwd.to_4d(),
                up.to_4d(),
                tip.to_4d(),
            )
        ).transposed()
        cls._draw_barbs(shader, tip_mx, barb_size)

    @classmethod
    def _draw_layer_viewport(cls, shader, obj, item) -> None:
        mx = obj.matrix_world.copy()

        uniform_scale = mx.to_scale().length / math.sqrt(3)
        loc = mx.to_translation()
        rot = mx.to_3x3().normalized().to_4x4()
        rot = Matrix.Scale(uniform_scale, 4) @ rot
        rot.translation = loc
        mx = rot

        origin = mx.translation.copy()
        linesize = 0.75
        radius = linesize * 0.25
        barbsize = linesize * 0.1

        layer_type = item.item_type

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        draw_circle(shader, mx, radius, plane="XZ")

        shader.uniform_float("color", XP_COLOR_MODS_RED)

        if layer_type == "DIRECTION_FORCE":
            cls._draw_arrow(shader, mx, linesize, barbsize, start_offset=-radius)

        elif layer_type in ("RELATIVE", "ABSOLUTE"):
            cls._draw_crosshair(shader, mx, radius)
            cls._draw_direction_arrow(shader, mx, item.heading, item.pitch, linesize)

        elif layer_type == "USE_MODIFIER_ROTATION":
            tip = mx @ Vector((0.0, linesize, 0.0))
            draw_lines(shader, [(origin, tip)])

            tip_mx = mx.copy()
            tip_mx.translation = tip
            cls._draw_barbs(shader, tip_mx, barbsize)

        elif layer_type == "CIRCULAR":
            heading = item.heading
            y_kick = item.y_kick

            rot3 = mx.to_3x3()
            right = (rot3 @ Vector((1.0, 0.0, 0.0))).normalized()
            fwd = (rot3 @ Vector((0.0, 1.0, 0.0))).normalized()
            up = (rot3 @ Vector((0.0, 0.0, 1.0))).normalized()

            bend = abs(heading)
            sgn = -1.0 if heading >= 0.0 else 1.0
            segs = 32

            if bend <= 1e-6:
                p1 = origin + fwd * linesize + up * y_kick
                draw_lines(shader, [(origin, p1)])

                tan = (fwd * linesize + up * y_kick).normalized()
                t_right = tan.cross(up).normalized()
                if t_right.length < 0.001:
                    t_right = right
                t_up = t_right.cross(tan).normalized()

                tip_mx = Matrix(
                    (
                        t_right.to_4d(),
                        tan.to_4d(),
                        t_up.to_4d(),
                        p1.to_4d(),
                    )
                ).transposed()
                cls._draw_barbs(shader, tip_mx, barbsize)
            else:
                # Curved arc
                r = linesize / bend
                prev = origin
                for i in range(1, segs + 1):
                    t = i / segs
                    th = bend * t
                    x = sgn * r * (1.0 - math.cos(th))
                    y = r * math.sin(th)
                    p = origin + right * x + fwd * y + up * (y_kick * t)
                    draw_lines(shader, [(prev, p)])
                    prev = p

                # Arrowhead at end of arc
                th = bend
                tan = (
                    right * (sgn * linesize * math.sin(th))
                    + fwd * (linesize * math.cos(th))
                    + up * y_kick
                ).normalized()
                t_right = tan.cross(up).normalized()
                if t_right.length < 0.001:
                    t_right = right
                t_up = t_right.cross(tan).normalized()

                tip_mx = Matrix(
                    (
                        t_right.to_4d(),
                        tan.to_4d(),
                        t_up.to_4d(),
                        prev.to_4d(),
                    )
                ).transposed()
                cls._draw_barbs(shader, tip_mx, barbsize)

        elif layer_type == "RING":
            inner_radius = radius * 0.3
            outer_radius = radius

            draw_circle(shader, mx, inner_radius, plane="XZ")
            draw_circle(shader, mx, outer_radius, plane="XZ")

            num_spokes = 8
            for i in range(num_spokes):
                angle = (i / num_spokes) * math.tau
                inner_pt = mx @ Vector(
                    (
                        math.cos(angle) * inner_radius,
                        0.0,
                        math.sin(angle) * inner_radius,
                    )
                )
                outer_pt = mx @ Vector(
                    (
                        math.cos(angle) * outer_radius,
                        0.0,
                        math.sin(angle) * outer_radius,
                    )
                )
                draw_lines(shader, [(inner_pt, outer_pt)])

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        if not hasattr(props, "direction_layers") or len(props.direction_layers) == 0:
            return

        active_index = props.direction_layers_index
        if active_index < 0 or active_index >= len(props.direction_layers):
            return

        item = props.direction_layers[active_index]

        if not item.enabled or not item.layer_visible_in_editor:
            return

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        cls._draw_layer_viewport(shader, obj, item)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
