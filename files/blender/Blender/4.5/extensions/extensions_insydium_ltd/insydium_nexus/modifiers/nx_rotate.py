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

from ..properties.nx_rotate import SPEC
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_RED,
    draw_lines,
    draw_thick_circle,
    draw_thick_lines,
)
from .base import MenuCategory, NexusModifier, UIFlags


class NXRotateModifier(NexusModifier):
    object_type = "NX_ROTATE"
    object_name = "nxRotate"
    object_label = "Rotate Modifier"
    object_description = "Apply rotational force to particles"
    icon_name = "nx_rotate"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_ROTATE_TYPE")
        col.prop(data, "ID_NX_ROTATE_VALUE")
        col.prop(data, "ID_NX_ROTATE_SPEEDMULT")

        row = col.row()
        row.use_property_split = True
        row.enabled = data.ID_NX_ROTATE_TYPE == "ID_NX_ROTATE_TYPE_FORCE"
        row.prop(data, "ID_NX_ROTATE_ATTRACT")

        accel_row = col.row()
        split = accel_row.split(factor=0.385)

        label_row = split.row(align=True)
        label_row.alignment = "RIGHT"
        icon = "TRIA_DOWN" if data.rotate_accel_expanded else "TRIA_RIGHT"
        label_row.prop(
            data,
            "rotate_accel_expanded",
            icon=icon,
            icon_only=True,
            emboss=False,
        )
        label_row.label(text="Angular Accel")

        split.prop(data, "ID_NX_ROTATE_ACCEL", text="")

        if data.rotate_accel_expanded:
            col.prop(data, "ID_NX_ROTATE_SPEEDCLAMP")

            clamp_row = col.row()
            clamp_row.use_property_split = False
            split = clamp_row.split(factor=0.385)
            split.label(text="")

            right = split.row()
            pair = right.row(align=True)
            sub = pair.row(align=True)
            sub.enabled = data.ID_NX_ROTATE_SPEEDCLAMP in (
                "ROTATE_SPEEDCLAMP_BOTH",
                "ROTATE_SPEEDCLAMP_MIN",
            )
            sub.prop(data, "ID_NX_ROTATE_SPEEDCLAMP_MIN", text="Min Rot. Speed")
            sub = pair.row(align=True)
            sub.enabled = data.ID_NX_ROTATE_SPEEDCLAMP in (
                "ROTATE_SPEEDCLAMP_BOTH",
                "ROTATE_SPEEDCLAMP_MAX",
            )
            sub.prop(data, "ID_NX_ROTATE_SPEEDCLAMP_MAX", text="Max Rot. Speed")
            # Reserve decorator column space to align with property_split rows
            spacer = right.row()
            spacer.scale_x = 0.25
            spacer.label(text="")

        col.prop(data, "ID_NX_ROTATE_FORCELIMIT")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        mx = obj.matrix_world.copy()
        uniform_scale = mx.to_scale().length / math.sqrt(3)
        loc = mx.to_translation()
        rot = mx.to_3x3().normalized().to_4x4()
        rot = Matrix.Scale(uniform_scale, 4) @ rot
        rot.translation = loc
        mx = rot

        origin = mx.translation.copy()

        SIZE = 0.75
        LINESIZE = SIZE
        BARBSIZE = SIZE * 0.15

        # Thick blue circle in XZ plane
        draw_thick_circle(context, mx, SIZE, XP_COLOR_MODS_BLUE, line_width=3.0, plane="XZ")

        rotate_value = getattr(props, "ID_NX_ROTATE_VALUE", math.pi)
        speed_mult = getattr(props, "ID_NX_ROTATE_SPEEDMULT", 1.0)
        # Offset so rotation is zero-aligned at scene start frame
        frame = context.scene.frame_current - context.scene.frame_start
        fps = context.scene.render.fps

        rotation_angle = (rotate_value / fps) * speed_mult * frame

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        rot_local = Matrix.Rotation(rotation_angle, 4, "Y")
        rot_matrix = mx @ rot_local

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

        tip = mx @ Vector((0.0, LINESIZE, 0.0))

        # Thick arrow (shaft + barbs)
        arrow_lines = [
            (origin, tip),
            (tip, mx @ Vector((-BARBSIZE, LINESIZE - BARBSIZE, 0.0))),
            (tip, mx @ Vector((BARBSIZE, LINESIZE - BARBSIZE, 0.0))),
            (tip, mx @ Vector((0.0, LINESIZE - BARBSIZE, -BARBSIZE))),
            (tip, mx @ Vector((0.0, LINESIZE - BARBSIZE, BARBSIZE))),
        ]
        draw_thick_lines(context, arrow_lines, XP_COLOR_MODS_RED, line_width=3.0)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
