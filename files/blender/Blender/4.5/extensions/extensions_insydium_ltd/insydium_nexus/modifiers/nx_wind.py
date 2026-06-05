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

from ..properties.nx_wind import SPEC, get_wind_ui_config
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .base import MenuCategory, NexusModifier, UIFlags


class NXWindModifier(NexusModifier):
    object_type = "NX_WIND"
    object_name = "nxWind"
    object_label = "Wind Modifier"
    object_description = "Apply wind force to particles"
    icon_name = "nx_wind"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_wind_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_WIND_MODE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_WIND_MODE")

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_WIND_STR", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_WIND_STR")

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_WIND_STR_VAR", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_WIND_STR_VAR")

        box = layout.box()

        header = box.row()
        header.use_property_split = ui_config.get("wind_turb_expanded", {}).get(
            "use_property_split", True
        )
        header.prop(
            data,
            "wind_turb_expanded",
            icon="TRIA_DOWN" if data.wind_turb_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Turbulence")

        if data.wind_turb_expanded:
            col = box.column()
            col.use_property_split = ui_config.get("ID_NX_WIND_TURB_STR", {}).get(
                "use_property_split", True
            )

            col.prop(data, "ID_NX_WIND_TURB_STR")
            col.prop(data, "ID_NX_WIND_TURB_AXIS_STR")
            col.prop(data, "ID_NX_WIND_COORD_SPACE")

            col.separator()

            col.prop(data, "ID_NX_WIND_TURB_FREQ")
            col.prop(data, "ID_NX_WIND_TURB_SCALE")
            col.prop(data, "ID_NX_WIND_FRICTION_VELOCITY")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        strength = getattr(props, "ID_NX_WIND_STR", 1.5)

        SCALE = 0.01
        SIZE = 10.0 * SCALE
        LINE_LENGTH = 50.0 * SCALE
        BARB_SIZE = 10.0 * SCALE

        mx = obj.matrix_world.copy()
        origin = mx.translation.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)

        draw_circle(shader, mx, SIZE, plane="XZ")

        frame = context.scene.frame_current
        strength_cm = strength * 100
        rotation_angle = math.radians(strength_cm) * frame

        rot_local = Matrix.Rotation(rotation_angle, 4, "Y")
        rot_matrix = mx @ rot_local

        propeller_lines = [
            # 0
            (
                rot_matrix @ Vector((0.05, 0.0, 0.0866)),
                rot_matrix @ Vector((0.0, 0.0, 1.0)),
            ),
            (
                rot_matrix @ Vector((-0.05, 0.0, 0.0866)),
                rot_matrix @ Vector((0.0, 0.0, 1.0)),
            ),
            # 1
            (
                rot_matrix @ Vector((0.05, 0.0, -0.0866)),
                rot_matrix @ Vector((0.8666, 0.0, -0.5)),
            ),
            (
                rot_matrix @ Vector((0.10, 0.0, 0.0)),
                rot_matrix @ Vector((0.8666, 0.0, -0.5)),
            ),
            # 2
            (
                rot_matrix @ Vector((-0.05, 0.0, -0.0866)),
                rot_matrix @ Vector((-0.8666, 0.0, -0.5)),
            ),
            (
                rot_matrix @ Vector((-0.10, 0.0, 0.0)),
                rot_matrix @ Vector((-0.8666, 0.0, -0.5)),
            ),
        ]
        draw_lines(shader, propeller_lines)

        shader.uniform_float("color", XP_COLOR_MODS_RED)

        cross_lines = [
            (
                rot_matrix @ Vector((0.0, 0.0, SIZE)),
                rot_matrix @ Vector((0.0, 0.0, -SIZE)),
            ),
            (
                rot_matrix @ Vector((SIZE, 0.0, 0.0)),
                rot_matrix @ Vector((-SIZE, 0.0, 0.0)),
            ),
        ]
        draw_lines(shader, cross_lines)

        tip = mx @ Vector((0.0, LINE_LENGTH, 0.0))
        arrow_lines = [
            (origin, tip),
            (tip, mx @ Vector((-BARB_SIZE, LINE_LENGTH - BARB_SIZE, 0.0))),
            (tip, mx @ Vector((BARB_SIZE, LINE_LENGTH - BARB_SIZE, 0.0))),
            (tip, mx @ Vector((0.0, LINE_LENGTH - BARB_SIZE, BARB_SIZE))),
            (tip, mx @ Vector((0.0, LINE_LENGTH - BARB_SIZE, -BARB_SIZE))),
        ]
        draw_lines(shader, arrow_lines)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
