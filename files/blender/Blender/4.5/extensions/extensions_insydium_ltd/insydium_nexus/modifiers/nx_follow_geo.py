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

from ..properties.nx_follow_geo import (
    FOLLOW_GEO_LINE_SPEC,
    FOLLOW_GEO_POLY_SPEC,
    SPEC,
    get_follow_geo_ui_config,
)
from .base import MenuCategory, NexusModifier, UIFlags


class NXFollowGeoModifier(NexusModifier):
    object_type = "NX_FOLLOW_GEO"
    object_name = "nxFollowGeo"
    object_label = "Follow Geo Modifier"
    object_description = "Make particles follow geometry surfaces or edges"
    icon_name = "nx_follow_geo"
    category = "Motion"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (FOLLOW_GEO_POLY_SPEC, FOLLOW_GEO_LINE_SPEC)

    @classmethod
    def get_theron_type(cls, obj):
        return "TR_MODIFIER_TYPE_FOLLOW_SURFACE"

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_follow_geo_ui_config()
        col = layout.column()
        cls.draw_property(col, data, "follow_geo_objects", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
