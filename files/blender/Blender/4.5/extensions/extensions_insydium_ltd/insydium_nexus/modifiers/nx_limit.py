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

from ..properties.nx_limit import SPEC
from .base import MenuCategory, NexusModifier, UIFlags


class NXLimitModifier(NexusModifier):
    object_type = "NX_LIMIT"
    object_name = "nxLimit"
    object_label = "Limit Modifier"
    object_description = "Limit particle properties with layered operations"
    icon_name = "nx_limit"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_limit import add_default_limit_layer

        add_default_limit_layer(obj)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_limit import draw_limit_layer_settings
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            data,
            "limit_layers",
            "limit_layers_index",
            label="Layers",
            draw_item_settings=draw_limit_layer_settings,
            menu_id="limit_layers",
        )

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
