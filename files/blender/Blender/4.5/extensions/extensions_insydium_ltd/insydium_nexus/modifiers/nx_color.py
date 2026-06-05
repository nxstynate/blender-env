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

from ..properties.nx_color import SPEC
from .base import MenuCategory, NexusModifier, UIFlags


class NXColorModifier(NexusModifier):
    object_type = "NX_COLOR"
    object_name = "nxColor"
    object_label = "Color Modifier"
    object_description = "Control particle color with layered color operations"
    icon_name = "nx_color"
    category = "Particle"
    menu_category = MenuCategory.PARTICLE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_color import add_default_color_layer

        add_default_color_layer(obj)

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_color import draw_color_layer_settings
        from ..ui import draw_nodetree

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "ID_NX_COLOUR_CHANGE_BIRTH")

        layout.separator()

        draw_nodetree(
            layout,
            data,
            "color_layers",
            "color_layers_index",
            label="Layers",
            draw_item_settings=draw_color_layer_settings,
            menu_id="color_layers",
        )
