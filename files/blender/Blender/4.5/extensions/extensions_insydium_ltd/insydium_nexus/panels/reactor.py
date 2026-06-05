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

"""Properties panel for an NX_FLOCK_REACTOR child of a NeXus Flock modifier."""

import bpy

from ..icons import get_icon
from ._helpers import get_reactor_parent_and_item, is_nexus_reactor


class NEXUS_PT_reactor_properties(bpy.types.Panel):
    bl_label = ""
    bl_idname = "NEXUS_PT_reactor_properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "physics"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            return False
        return is_nexus_reactor(obj)

    def draw_header(self, context):
        obj = context.object
        reactor_type = obj.get("nexus_reactor_type", "")
        type_label = reactor_type.title() if reactor_type else "Unknown"

        flock_obj, _ = get_reactor_parent_and_item(obj)
        flock_name = flock_obj.name if flock_obj else "Unknown"

        header_text = f"NeXus Flock Reactor - {type_label} [{flock_name}]"

        icon_name = f"nx_flock_reaction_{reactor_type.lower()}" if reactor_type else ""
        icon_id = get_icon(icon_name) if icon_name else 0
        if icon_id:
            self.layout.label(text=header_text, icon_value=icon_id)
        else:
            self.layout.label(text=header_text)

    def draw(self, context):
        from ..libs import theron
        layout = self.layout
        layout.enabled = theron.is_initialized()
        obj = context.object

        flock_obj, reaction_item = get_reactor_parent_and_item(obj)

        if flock_obj is None:
            layout.label(text="Parent flock modifier not found", icon="ERROR")
            return

        if reaction_item is None:
            layout.label(text="Reaction item not found", icon="ERROR")
            return

        from ..properties.nx_flock import draw_flock_reaction_settings

        draw_flock_reaction_settings(layout, reaction_item)


classes = [NEXUS_PT_reactor_properties]
