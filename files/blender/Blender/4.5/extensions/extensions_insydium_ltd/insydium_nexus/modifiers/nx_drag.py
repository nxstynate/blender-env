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

from ..properties.nx_drag import SPEC, get_drag_ui_config
from .base import MenuCategory, NexusModifier, UIFlags


class NXDragModifier(NexusModifier):
    object_type = "NX_DRAG"
    object_name = "nxDrag"
    object_label = "Drag Modifier"
    object_description = "Apply aerodynamic drag to particles"
    icon_name = "nx_drag"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_drag_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_DRAG_DENSITY", {}).get(
            "use_property_split", True
        )

        col.prop(data, "ID_NX_DRAG_DENSITY")

        row = col.row()
        row.prop(data, "ID_NX_DRAG_DENSITY_VALUE")
        row.enabled = data.ID_NX_DRAG_DENSITY == "ID_NX_DRAG_DENSITY_CUSTOM"

        col.prop(data, "ID_NX_DRAG_COEFF")

        row = col.row()
        row.prop(data, "ID_NX_DRAG_COEFF_VALUE")
        row.enabled = data.ID_NX_DRAG_COEFF == "ID_NX_DRAG_COEFF_CUSTOM"

        col.prop(data, "ID_NX_DRAG_MULTI")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        pass
