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

from .base import MenuCategory, NexusObject, UIFlags


class NexusGroup(NexusObject):
    object_type = "NX_GROUP"
    object_name = "nxGroup"
    object_label = "Group"
    object_description = "Assign particles to a group"
    icon_name = "nx_emitter_group"
    category = "Emitters"
    menu_category = MenuCategory.EMITTER

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        scene = bpy.context.scene
        if scene is None and obj.users_scene:
            scene = obj.users_scene[0]

        objects = scene.objects if scene is not None else bpy.data.objects

        max_group_id = 0
        for other in objects:
            if other == obj:
                continue
            if other.get("nexus_modifier_type") != cls.object_type:
                continue
            try:
                group_id = int(other.nexus_modifier.ID_NX_GROUP_ID)
            except (AttributeError, ReferenceError, TypeError, ValueError):
                continue
            if group_id > max_group_id:
                max_group_id = group_id

        obj.nexus_modifier.ID_NX_GROUP_ID = max_group_id + 1

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_GROUP_ID")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_GROUP_DISPLAY_MODE")
        col.prop(data, "ID_NX_GROUP_COLOR_MODE")
        col.prop(data, "ID_NX_GROUP_COLOR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_GROUP_SPEED")
        col.prop(data, "ID_NX_GROUP_SPEED_VAR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_GROUP_RADIUS")
        col.prop(data, "ID_NX_GROUP_RADIUS_VAR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_GROUP_MASS")
        col.prop(data, "ID_NX_GROUP_MASS_VAR")
