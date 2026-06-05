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

from ..properties.nx_sticky import (
    _STICKY_LINE_SPEC,
    _STICKY_POLY_SPEC,
    SPEC,
    get_sticky_ui_config,
)
from .base import MenuCategory, NexusModifier, UIFlags


class NXStickyModifier(NexusModifier):
    object_type = "NX_STICKY"
    object_name = "nxSticky"
    object_label = "Sticky Modifier"
    object_description = "Make particles stick to object surfaces"
    icon_name = "nx_sticky"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (_STICKY_POLY_SPEC, _STICKY_LINE_SPEC)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_sticky_ui_config()
        col = layout.column()
        cls.draw_property(col, data, "sticky_objects", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
