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
from typing import List, Tuple

import bpy
import gpu
from mathutils import Matrix, Vector

from ..libs.nexus_time import draw_time_prop
from ..properties.nx_explode import SPEC, get_explode_ui_config
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .base import MenuCategory, NexusModifier, UIFlags


class NXExplodeModifier(NexusModifier):
    object_type = "NX_EXPLODE"
    object_name = "nxExplode"
    object_label = "Explode Modifier"
    object_description = "Explode particles outward from a point"
    icon_name = "nx_explode"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_tabs(cls, props):
        tabs = []
        tabs.append(("DISPLAY", "Display"))
        return tabs

    @classmethod
    def draw_tab(cls, section_id, layout, props):
        col = layout.column()
        col.use_property_split = True

        if section_id == "DISPLAY":
            cls.draw_display_section(layout, props)

    @classmethod
    def draw_display_section(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        vie_row = col.row()
        split = vie_row.split(factor=0.385)

        label_row = split.row(align=True)
        label_row.alignment = "RIGHT"
        icon = "TRIA_DOWN" if data.explode_display_expanded else "TRIA_RIGHT"
        label_row.prop(data, "explode_display_expanded", icon=icon, icon_only=True, emboss=False)
        label_row.label(text="Visible in Editor")

        split.prop(data, "visible_in_editor", text="")

        if data.explode_display_expanded:
            col.prop(data, "explode_icon_size")

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_explode_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_TIMING", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLODE_TIMING")

        timing_disabled = data.ID_NX_EXPLODE_TIMING == "EXPLODE_TIMING_NONE"

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_TIMING_MODE", {}).get(
            "use_property_split", True
        )
        col.enabled = not timing_disabled
        col.prop(data, "ID_NX_EXPLODE_TIMING_MODE")

        col = layout.column()
        col.use_property_split = ui_config.get(
            "ID_NX_EXPLODE_TIME",
            {},
        ).get("use_property_split", True)
        col.enabled = not timing_disabled
        draw_time_prop(col, data, "ID_NX_EXPLODE_TIME")

        layout.separator()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_SOURCE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLODE_SOURCE")

        col = layout.column()
        col.use_property_split = ui_config.get(
            "ID_NX_EXPLODE_SPEED",
            {},
        ).get("use_property_split", True)
        col.prop(data, "ID_NX_EXPLODE_SPEED")

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_SPEED_VAR", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLODE_SPEED_VAR")

        col = layout.column()
        col.use_property_split = ui_config.get(
            "ID_NX_EXPLODE_SEED",
            {},
        ).get("use_property_split", True)
        col.prop(data, "ID_NX_EXPLODE_SEED")

        layout.separator()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_UNSTICK", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLODE_UNSTICK")

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLODE_MAP_START", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLODE_MAP_START")

    @classmethod
    def _draw_arrow(
        cls, shader, matrix: Matrix, angle: float, length: float, barb_size: float
    ) -> List[Tuple[Vector, Vector]]:
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        start = matrix @ (direction * length)
        end = matrix @ (direction * length * 2)

        perp = Vector((-math.sin(angle), math.cos(angle), 0.0))
        barb1 = matrix @ (direction * (length * 2 - barb_size) + perp * barb_size * 0.5)
        barb2 = matrix @ (direction * (length * 2 - barb_size) - perp * barb_size * 0.5)

        return [
            (start, end),
            (end, barb1),
            (end, barb2),
        ]

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        icon_size = getattr(props, "explode_icon_size", 1.0)

        size = icon_size * 0.75
        barb_size = size * 0.15

        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        draw_circle(shader, mx, size, plane="XY")

        shader.uniform_float("color", XP_COLOR_MODS_RED)
        arrow_lines = []
        for i in range(8):
            angle = (i / 8) * math.tau
            arrow_lines.extend(cls._draw_arrow(shader, mx, angle, size, barb_size))
        draw_lines(shader, arrow_lines)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
