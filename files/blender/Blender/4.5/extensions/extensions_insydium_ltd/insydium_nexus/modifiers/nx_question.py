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

from ..properties.nx_question import (
    QUESTION_CAMERA_SPEC,
    QUESTION_LINE_SPEC,
    QUESTION_POLY_SPEC,
    SPEC,
)
from .base import MenuCategory, NexusModifier, UIFlags


def _draw_question_nodetree(layout, data):
    from ..properties.nx_question import draw_question_item_settings
    from ..ui import draw_nodetree_hierarchy

    draw_nodetree_hierarchy(
        layout,
        data,
        "question_items",
        "question_items_index",
        label="Questions",
        draw_item_settings=draw_question_item_settings,
        menu_id="question_items",
    )


class NXQuestionModifier(NexusModifier):
    object_type = "NX_QUESTION"
    object_name = "nxQuestion"
    object_label = "Question"
    object_description = "Per-particle conditional logic"
    icon_name = "nx_question"
    category = "Logic"
    menu_category = MenuCategory.LOGIC
    cache_specs = (QUESTION_POLY_SPEC, QUESTION_LINE_SPEC, QUESTION_CAMERA_SPEC)

    ui_flags = UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls):
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True
        col.prop(data, "ID_NX_QUESTION_ITERATIONS")
        col.prop(data, "ID_NX_QUESTION_ITERATION_WEIGHT")

        layout.separator()

        _draw_question_nodetree(layout, data)
