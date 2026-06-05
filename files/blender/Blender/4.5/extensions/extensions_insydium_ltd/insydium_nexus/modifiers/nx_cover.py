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

from ..properties.nx_cover import COVER_LINE_SPEC, COVER_POLY_SPEC, SPEC, get_cover_ui_config
from .base import MenuCategory, NexusModifier, UIFlags


class NXCoverModifier(NexusModifier):
    object_type = "NX_COVER"
    object_name = "nxCover"
    object_label = "Cover Modifier"
    object_description = "Make particles cover target object surfaces"
    icon_name = "nx_cover"
    category = "Motion"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (COVER_POLY_SPEC, COVER_LINE_SPEC)

    @classmethod
    def get_theron_type(cls, obj):
        return "TR_MODIFIER_TYPE_COVER"

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_cover_ui_config()

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_COVER_OBJECT_MODE")

        if data.ID_NX_COVER_OBJECT_MODE == "INDEX":
            col.prop(data, "ID_NX_COVER_INDEX")
        elif data.ID_NX_COVER_OBJECT_MODE == "RANDOM":
            col.prop(data, "ID_NX_COVER_RANDOM_SEED")

        if data.ID_NX_COVER_OBJECT_MODE in ("SEQUENCE", "RANDOM"):
            col.prop(data, "ID_NX_COVER_CYCLE")

        col.separator()

        cls.draw_property(col, data, "cover_objects", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
