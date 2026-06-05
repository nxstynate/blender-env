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

from ..properties.nx_avoid import (
    _AVOID_LINE_SPEC,
    _AVOID_POLY_SPEC,
    SPEC,
    get_avoid_ui_config,
)
from .base import MenuCategory, NexusModifier, UIFlags


class NXAvoidModifier(NexusModifier):
    object_type = "NX_AVOID"
    object_name = "nxAvoid"
    object_label = "Avoid Modifier"
    object_description = "Make particles avoid specified objects"
    icon_name = "nx_avoid"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (_AVOID_POLY_SPEC, _AVOID_LINE_SPEC)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_avoid_ui_config()
        col = layout.column()
        cls.draw_property(col, data, "avoid_objects", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
