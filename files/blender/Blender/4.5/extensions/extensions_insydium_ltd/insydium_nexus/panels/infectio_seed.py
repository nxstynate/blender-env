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

"""Properties panel for an NX_INFECTIO_SEED child of a NeXus Infectio modifier."""

import bpy

from ..icons import get_icon
from ._helpers import get_infectio_seed_parent_and_item, is_nexus_infectio_seed


class NEXUS_PT_infectio_seed_properties(bpy.types.Panel):
    bl_label = ""
    bl_idname = "NEXUS_PT_infectio_seed_properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "physics"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            return False
        return is_nexus_infectio_seed(obj)

    def draw_header(self, context):
        obj = context.object
        infectio_obj, _ = get_infectio_seed_parent_and_item(obj)
        infectio_name = infectio_obj.name if infectio_obj else "Unknown"

        header_text = f"NeXus Infectio Seed [{infectio_name}]"

        icon_id = get_icon("nx_infectio")
        if icon_id:
            self.layout.label(text=header_text, icon_value=icon_id)
        else:
            self.layout.label(text=header_text)

    def draw(self, context):
        from ..libs import theron
        layout = self.layout
        layout.enabled = theron.is_initialized()
        obj = context.object

        infectio_obj, seed_item = get_infectio_seed_parent_and_item(obj)

        if infectio_obj is None:
            layout.label(text="Parent infectio modifier not found", icon="ERROR")
            return

        if seed_item is None:
            layout.label(text="Seed item not found", icon="ERROR")
            return

        from ..properties.nx_infectio import draw_seed_settings

        draw_seed_settings(layout, seed_item)


classes = [NEXUS_PT_infectio_seed_properties]
