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

from ..libs.nexus_time import draw_time_prop
from ..properties.nx_push import SPEC, get_push_ui_config
from .base import MenuCategory, NexusModifier, UIFlags


class NXPushModifier(NexusModifier):
    object_type = "NX_PUSH"
    object_name = "nxPush"
    object_label = "Push Modifier"
    object_description = "Push particles apart to prevent overlapping"
    icon_name = "nx_push"
    category = "Collision"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_push_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_PUSH_DISTANCE_MODE", {}).get(
            "use_property_split", True
        )

        col.prop(data, "ID_NX_PUSH_DISTANCE_MODE")

        row = col.row()
        row.prop(data, "ID_NX_PUSH_DISTANCE")
        row.enabled = data.ID_NX_PUSH_DISTANCE_MODE == "ID_NX_PUSH_DISTANCE_MODE_ABSOLUTE"

        col.prop(data, "ID_NX_PUSH_STRENGTH")
        col.prop(data, "ID_NX_PUSH_ITERS")
        draw_time_prop(col, data, "ID_NX_PUSH_EASEIN")
        col.prop(data, "ID_NX_PUSH_SAMEGROUP")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        pass
