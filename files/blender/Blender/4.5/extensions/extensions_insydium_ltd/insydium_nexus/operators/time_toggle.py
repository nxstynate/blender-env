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

"""Operator to toggle time property between Frames and Seconds display."""

import bpy
from bpy.props import StringProperty


class NEXUS_OT_toggle_time_mode(bpy.types.Operator):
    """Toggle this time property between Frames and Seconds"""

    bl_idname = "nexus.toggle_time_mode"
    bl_label = "Toggle Time Display"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    prop_name: StringProperty(
        name="Property Name",
        description="Name of the time property to toggle",
    )
    object_name: StringProperty(
        name="Object Name",
        description="Name of the Blender object owning the data",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path from the object to the property data block",
    )

    def execute(self, context):
        from ..libs.nexus_time import (
            get_prop_time_mode,
            set_prop_time_mode,
        )

        obj = bpy.data.objects.get(self.object_name)
        if obj is None:
            self.report({"WARNING"}, f"Object '{self.object_name}' not found")
            return {"CANCELLED"}

        try:
            if self.data_path:
                data = obj.path_resolve(self.data_path)
            else:
                data = obj
        except ValueError:
            self.report({"WARNING"}, f"Cannot resolve path: {self.data_path}")
            return {"CANCELLED"}

        if not hasattr(data, self.prop_name):
            self.report({"WARNING"}, f"Property '{self.prop_name}' not found")
            return {"CANCELLED"}

        fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-6)
        old_mode = get_prop_time_mode(data, self.prop_name)
        new_mode = "SECONDS" if old_mode == "FRAMES" else "FRAMES"
        old_value = getattr(data, self.prop_name)
        if old_mode == "FRAMES" and new_mode == "SECONDS":
            new_value = old_value / fps
        else:
            new_value = old_value * fps
        setattr(data, self.prop_name, new_value)

        set_prop_time_mode(data, self.prop_name, new_mode)

        obj.update_tag()

        for area in context.screen.areas:
            area.tag_redraw()

        return {"FINISHED"}
