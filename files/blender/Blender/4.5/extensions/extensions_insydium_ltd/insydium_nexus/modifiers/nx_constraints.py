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

from ..properties.nx_constraints import SPEC
from .base import MenuCategory, NexusModifier, UIFlags


class NXConstraintsModifier(NexusModifier):
    object_type = "NX_CONSTRAINTS"
    object_name = "nxConstraints"
    object_label = "Constraints Modifier"
    object_description = "Particle constraint solver with multiple constraint types"
    icon_name = "nx_constraints"
    category = "Dynamics"
    menu_category = MenuCategory.SIMULATION

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_constraints import draw_constraint_layer_settings
        from ..ui import draw_nodetree

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "ID_XPGPU_CONSTRAINTS_SUBSTEPS")
        col.prop(data, "ID_XPGPU_CONSTRAINTS_DAMP")

        col.separator(type="LINE")

        draw_nodetree(
            layout,
            data,
            "constraints_layers",
            "constraints_layers_index",
            label="Layers",
            draw_item_settings=draw_constraint_layer_settings,
            menu_id="constraints_layers",
        )

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        pass
