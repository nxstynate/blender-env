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

from ..properties.nx_upres import SPEC, get_upres_ui_config
from .base import MenuCategory, NexusModifier, UIFlags


class NXUpresModifier(NexusModifier):
    object_type = "NX_UPRES"
    object_name = "nxUpres"
    object_label = "Upres Modifier"
    object_description = "Upres particles from source to destination emitters"
    icon_name = "nx_upres"
    category = "Utility"
    menu_category = MenuCategory.UTILITY

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_upres_ui_config()

        cls.draw_property(layout, data, "upres_source", ui_config)
        cls.draw_property(layout, data, "upres_dest", ui_config)

        col = layout.column()
        col.use_property_split = True

        col.separator(type="LINE")
        col.prop(data, "ID_NX_UPRES_STRENGTH")

        col.separator(type="LINE")
        col.prop(data, "ID_NX_UPRES_POSITION")
        col.prop(data, "ID_NX_UPRES_VELOCITY")
        col.prop(data, "ID_NX_UPRES_RADIUS")
        col.prop(data, "ID_NX_UPRES_MASS")
        col.prop(data, "ID_NX_UPRES_COLOR")

        col.separator(type="LINE")
        col.prop(data, "ID_NX_UPRES_GROUP")

        col.separator(type="LINE")
        col.prop(data, "ID_NX_UPRES_MAX_NB")
        col.prop(data, "ID_NX_UPRES_LIMIT_DIST")

        sub = col.column()
        sub.active = data.ID_NX_UPRES_LIMIT_DIST
        sub.prop(data, "ID_NX_UPRES_MAX_DIST")

        col.prop(data, "ID_NX_UPRES_PUSH")

        sub = col.column()
        sub.active = data.ID_NX_UPRES_PUSH
        sub.prop(data, "ID_NX_UPRES_PUSH_DISTANCE")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        pass
