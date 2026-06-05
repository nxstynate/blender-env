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

from ..utils.splash_data import (
    generate_default_handles,
    set_splash_handle_data,
    store_splash_prev_values,
)


class NEXUS_OT_splash_reset_handles(bpy.types.Operator):
    bl_idname = "nexus.splash_reset_handles"
    bl_label = "Reset Handles"
    bl_description = "Reset splash handles to their default positions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.get("nexus_modifier_type") == "NX_SPLASH"

    def execute(self, context):
        obj = context.object
        props = obj.nexus_modifier
        bhandles, strengths = generate_default_handles(
            props.ID_NX_SPLASH_HEIGHT,
            props.ID_NX_SPLASH_RADIUS_BOTTOM,
            props.ID_NX_SPLASH_RADIUS_TOP,
            props.ID_NX_SPLASH_HANDLE_COUNT,
        )
        set_splash_handle_data(obj, bhandles, strengths)
        store_splash_prev_values(obj, props)
        obj.update_tag()
        context.view_layer.depsgraph.update()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}
