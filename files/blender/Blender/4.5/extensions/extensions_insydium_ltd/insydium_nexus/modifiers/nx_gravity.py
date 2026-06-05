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

import bpy
import gpu
from mathutils import Vector

from ..properties.nx_gravity import SPEC, get_gravity_ui_config
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .base import MenuCategory, NexusModifier, UIFlags

TRACK_CONSTRAINT_NAME = "NX_GRAVITY_TRACK_TO"


class NXGravityModifier(NexusModifier):
    object_type = "NX_GRAVITY"
    object_name = "nxGravity"
    object_label = "Gravity Modifier"
    object_description = "Apply gravity force to particles"
    icon_name = "nx_gravity"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def _get_or_create_track_constraint(cls, obj: bpy.types.Object) -> bpy.types.TrackToConstraint:
        constraint = obj.constraints.get(TRACK_CONSTRAINT_NAME)
        if constraint is None:
            constraint = obj.constraints.new(type="TRACK_TO")
            constraint.name = TRACK_CONSTRAINT_NAME
            constraint.track_axis = "TRACK_NEGATIVE_Z"
            constraint.up_axis = "UP_Y"
            constraint.influence = 1.0
        return constraint

    @classmethod
    def _update_effect_towards(cls, obj: bpy.types.Object, target: bpy.types.Object) -> None:
        if target is None:
            constraint = obj.constraints.get(TRACK_CONSTRAINT_NAME)
            if constraint is not None:
                obj.constraints.remove(constraint)
        else:
            constraint = cls._get_or_create_track_constraint(obj)
            constraint.target = target

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_gravity_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_GRAVITY_STRENGTH", {}).get(
            "use_property_split", True
        )

        col.prop(data, "ID_NX_GRAVITY_STRENGTH")
        col.prop(data, "ID_NX_GRAVITY_STRENGTH_VAR")

        col.prop(data, "ID_NX_GRAVITY_VARIATION_MODE")
        col.prop(data, "ID_NX_GRAVITY_SEED")
        col.prop(data, "gravity_effect_towards")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        SIZE = 0.75
        LINESIZE = 0.75
        BARBSIZE = 0.1125

        mx = obj.matrix_world.copy()
        origin = mx.translation.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        draw_circle(shader, mx, SIZE, plane="XY")

        shader.uniform_float("color", XP_COLOR_MODS_RED)

        cross_lines = [
            (mx @ Vector((SIZE, 0.0, 0.0)), mx @ Vector((-SIZE, 0.0, 0.0))),
            (mx @ Vector((0.0, SIZE, 0.0)), mx @ Vector((0.0, -SIZE, 0.0))),
        ]
        draw_lines(shader, cross_lines)

        tip = mx @ Vector((0.0, 0.0, -LINESIZE))
        arrow_lines = [
            (origin, tip),
            (tip, mx @ Vector((-BARBSIZE, 0.0, -LINESIZE + BARBSIZE))),
            (tip, mx @ Vector((BARBSIZE, 0.0, -LINESIZE + BARBSIZE))),
            (tip, mx @ Vector((0.0, -BARBSIZE, -LINESIZE + BARBSIZE))),
            (tip, mx @ Vector((0.0, BARBSIZE, -LINESIZE + BARBSIZE))),
        ]
        draw_lines(shader, arrow_lines)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
