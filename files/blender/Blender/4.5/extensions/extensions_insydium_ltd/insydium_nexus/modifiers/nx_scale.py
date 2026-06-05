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

from ..properties.nx_scale import SPEC
from .base import MenuCategory, NexusModifier, UIFlags


class NXScaleModifier(NexusModifier):
    object_type = "NX_SCALE"
    object_name = "nxScale"
    object_label = "Scale"
    object_description = "Scale particle geometry, radius, or mass with layered operations"
    icon_name = "nx_scale"
    category = "Particle"
    menu_category = MenuCategory.PARTICLE

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_scale import add_default_scale_layer

        add_default_scale_layer(obj)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        from ..properties.nx_scale import clear_scale_map_poly_cache

        clear_scale_map_poly_cache(modifier_name=mod_uid, free_resources=True)

    @classmethod
    def on_state_clear(cls, *, free_resources: bool = True) -> None:
        from ..properties.nx_scale import clear_scale_map_poly_cache

        clear_scale_map_poly_cache(free_resources=free_resources)

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_scale import draw_scale_layer_settings
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            data,
            "scale_layers",
            "scale_layers_index",
            label="Layers",
            draw_item_settings=draw_scale_layer_settings,
            menu_id="scale_layers",
        )

    @classmethod
    def draw_viewport(cls, obj, props, context):
        pass
