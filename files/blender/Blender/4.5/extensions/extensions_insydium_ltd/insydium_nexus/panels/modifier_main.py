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

"""Main NeXus modifier properties panel — header + tabbed body (Object / Groups
Affected / Mapping / Falloff / per-modifier custom tabs) + footer buttons.

Per-section drawing (mapping, falloff, groups) is delegated to its own module.
"""

import bpy

from ..icons import get_icon
from ..modifiers.base import UIFlags
from ._helpers import get_available_sections, get_modifier_class, is_nexus_modifier
from .mapping import draw_mapping_section


class NEXUS_PT_modifier_main(bpy.types.Panel):
    bl_label = ""
    bl_idname = "NEXUS_PT_modifier_main"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "physics"
    bl_options = set()  # Expanded by default for Pipeline Manager workflow

    @classmethod
    def poll(cls, context):
        return context.object and is_nexus_modifier(context.object)

    def draw_header(self, context):
        obj = context.object
        mod_class = get_modifier_class(obj)
        if mod_class:
            header_text = f"NeXus {mod_class.object_label} [{obj.name}]"
            icon_id = mod_class.get_instance_icon_id(obj)
            if icon_id:
                self.layout.label(text=header_text, icon_value=icon_id)
            else:
                self.layout.label(text=header_text)

    def draw(self, context):
        from ..libs import theron

        layout = self.layout

        if not theron.is_initialized():
            layout.label(
                text="No valid license",
                icon="ERROR",
            )

        layout.enabled = theron.is_initialized()
        obj = context.object
        mod_class = get_modifier_class(obj)

        if not mod_class:
            layout.label(text="Unknown modifier type", icon="ERROR")
            return

        props = obj.nexus_modifier

        sections = get_available_sections(mod_class, props)

        if len(sections) > 1:
            row = layout.row(align=True)
            for section_id, section_label in sections:
                row.prop_enum(props, "ui_section", section_id)
            layout.separator()

        current_section = props.ui_section
        available_ids = [s[0] for s in sections]
        if current_section not in available_ids:
            current_section = "OBJECT_PROPERTIES"

        if current_section == "OBJECT_PROPERTIES":
            mod_class.draw_ui(layout, props)

        elif current_section == "FALLOFF":
            self.draw_falloff_section(layout, props)

        elif current_section == "GROUPS_AFFECTED":
            self.draw_groups_affected_section(layout, props)

        elif current_section == "MAPPING":
            draw_mapping_section(layout, props)

        else:
            mod_class.draw_tab(current_section, layout, props)

        if UIFlags.RESET_BUTTON in mod_class.ui_flags or UIFlags.HELP_BUTTON in mod_class.ui_flags:
            layout.separator()
            row = layout.row(align=True)
            row.alignment = "RIGHT"
            sub = row.row(align=True)
            sub.emboss = "NONE"
            if UIFlags.RESET_BUTTON in mod_class.ui_flags:
                preset_button = sub.row(align=True)
                preset_button.operator(
                    "nexus.modifier_preset_popup",
                    text="",
                    icon_value=get_icon("nx_modifier_preset"),
                )
                sub.operator(
                    "nexus.reset_modifier",
                    text="",
                    icon_value=get_icon("nx_reset"),
                )
            if UIFlags.HELP_BUTTON in mod_class.ui_flags:
                sub.operator(
                    "nexus.open_help",
                    text="",
                    icon_value=get_icon("nx_help"),
                )

    def draw_falloff_section(self, layout, props):
        from ..ui import draw_nodetree

        def _draw_falloff_item_settings(col, item):
            col.prop(item, "falloff_blend_mode")
            col.prop(item, "falloff_blend_strength")

            falloff_obj = item.obj
            if falloff_obj is None:
                return

            mod_class = get_modifier_class(falloff_obj)
            if mod_class is None:
                return

            col.separator(type="LINE")
            mod_class.draw_ui(col, falloff_obj.nexus_modifier)

        draw_nodetree(
            layout,
            props,
            "falloffs",
            "falloffs_index",
            label="Falloffs",
            allowed_types=["NX_FALLOFF"],
            draw_item_settings=_draw_falloff_item_settings,
            extra_operators=[
                {
                    "operator": "nexus.nodetree_create_and_add",
                    "icon": get_icon("nx_falloff_box"),
                    "text": "",
                    "properties": {
                        "list_prop": "falloffs",
                        "index_prop": "falloffs_index",
                        "modifier_type": "NX_FALLOFF",
                    },
                },
            ],
        )

    def draw_groups_affected_section(self, layout, props):
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            props,
            "groups_affected",
            "groups_affected_index",
            label="Groups",
            allowed_types=["NX_GROUP"],
            tree_type="inexclude",
            extra_operators=[
                {
                    "operator": "nexus.nodetree_create_and_add",
                    "icon": get_icon("nx_emitter_group"),
                    "text": "",
                    "properties": {
                        "list_prop": "groups_affected",
                        "index_prop": "groups_affected_index",
                        "modifier_type": "NX_GROUP",
                    },
                },
            ],
        )


classes = [NEXUS_PT_modifier_main]
