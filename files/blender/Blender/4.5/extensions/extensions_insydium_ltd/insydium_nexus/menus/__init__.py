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

from collections import defaultdict

import bpy

from ..icons import get_icon
from ..modifiers import MODIFIER_REGISTRY
from ..modifiers.base import MenuCategory

# Category rendering order for the modifier menu.
# Modifiers are auto-grouped by their menu_category attribute and
# alphabetised within each group
MENU_CATEGORY_ORDER = (
    MenuCategory.EMITTER,
    MenuCategory.OBJECTS,
    MenuCategory.SIMULATION,
    MenuCategory.GENERATORS,
    MenuCategory.LOGIC,
    MenuCategory.PARTICLE,
    MenuCategory.FORCE,
    MenuCategory.UTILITY,
)


def _build_menu_groups():
    """Group registered modifiers by menu_category, sorted alphabetically."""
    groups = defaultdict(list)
    for mod_type, mod_class in MODIFIER_REGISTRY.items():
        groups[mod_class.menu_category].append((mod_type, mod_class))

    for mod_list in groups.values():
        mod_list.sort(key=lambda pair: pair[1].object_name.lower())

    return [(cat, groups[cat]) for cat in MENU_CATEGORY_ORDER if cat in groups]


def draw_modifier_entries(layout):
    """Draw modifier add entries into *layout*. Shared by multiple menus."""
    for group_index, (category, entries) in enumerate(_build_menu_groups()):
        if group_index > 0:
            layout.separator()
        for mod_type, mod_class in entries:
            icon_id = mod_class.get_icon_id()
            op = layout.operator(
                "nexus.add_modifier",
                text=mod_class.object_name,
                icon_value=icon_id if icon_id else 0,
            )
            op.modifier_type = mod_type


class NEXUS_MT_nexus_modifiers(bpy.types.Menu):
    bl_idname = "NEXUS_MT_nexus_modifiers"
    bl_label = "NeXus"

    def draw(self, context):
        from ..libs import theron
        layout = self.layout
        initialized = theron.is_initialized()
        if not initialized:
            layout.operator("nexus.open_preferences", text="Enter License...", icon="PREFERENCES")
            layout.separator()
        col = layout.column()
        col.enabled = initialized
        draw_modifier_entries(col)


def menu_func_add(self, context):
    self.layout.separator()
    nexus_icon = get_icon("nexus")
    self.layout.menu(
        "NEXUS_MT_nexus_modifiers",
        text="INSYDIUM NeXus",
        icon_value=nexus_icon if nexus_icon else 0,
    )


classes = [
    NEXUS_MT_nexus_modifiers,
]


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass

    bpy.types.VIEW3D_MT_add.append(menu_func_add)


def unregister():
    bpy.types.VIEW3D_MT_add.remove(menu_func_add)

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
