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

from ..libs.nexus_time import draw_time_prop
from ..properties.nx_blend import SPEC
from .base import MenuCategory, NexusModifier, UIFlags


class NXBlendModifier(NexusModifier):
    object_type = "NX_BLEND"
    object_name = "nxBlend"
    object_label = "Blend Modifier"
    object_description = "Blend particle parameters between neighbouring particles"
    icon_name = "nx_blend"
    category = "Particle"
    menu_category = MenuCategory.PARTICLE

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True
        col.prop(data, "blend_type")
        col.prop(data, "ID_NX_BLEND_DISTANCE")
        col.prop(data, "blend_strength")
        draw_time_prop(col, data, "ID_NX_BLEND_MAXBLEND")

        col.separator()

        col.prop(data, "ID_NX_BLEND_PARAMS_RADIUS")
        col.prop(data, "ID_NX_BLEND_PARAMS_SCALE")
        col.prop(data, "ID_NX_BLEND_PARAMS_MASS")
        col.prop(data, "ID_NX_BLEND_PARAMS_ROTATION")
        col.prop(data, "ID_NX_BLEND_PARAMS_COLOR")
