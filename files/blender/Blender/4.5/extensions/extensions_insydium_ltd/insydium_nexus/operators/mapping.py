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

"""Operators for the Mapping tab (generic modifier parameter mapping).

Entry layer semantics:
- Each entry is a "layer" keyed by its SOURCE (particle data feed, e.g. Speed / Age / a
  modifier-specific _mapTo entry).
- The destination (which modifier param is being modulated) is configured inside the entry
  via NEXUS_OT_mapping_set_dest.
"""

import uuid

import bpy
from bpy.props import EnumProperty, IntProperty


def _active_nexus_props(context):
    obj = context.object
    if obj is None or "nexus_modifier_type" not in obj:
        return None
    return obj.nexus_modifier


class NEXUS_OT_mapping_add_entry(bpy.types.Operator):
    """Add a new mapping layer for the given particle-data source"""

    bl_idname = "nexus.mapping_add_entry"
    bl_label = "Add Mapping Layer"
    bl_options = {"REGISTER", "UNDO"}

    source_param: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return _active_nexus_props(context) is not None

    def execute(self, context):
        from ..properties.mapping import MAPPING_CURVE_SPEC
        from ..utils.curve import create_item_curves

        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}

        obj = context.object
        entry = props.mappings.add()
        entry.source_param = int(self.source_param)
        entry.curve_id = uuid.uuid4().hex

        create_item_curves(obj, entry.curve_id, [MAPPING_CURVE_SPEC])

        props.mappings_index = len(props.mappings) - 1
        obj.update_tag()
        return {"FINISHED"}


class NEXUS_OT_mapping_remove_entry(bpy.types.Operator):
    """Remove the selected mapping layer"""

    bl_idname = "nexus.mapping_remove_entry"
    bl_label = "Remove Mapping Layer"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = _active_nexus_props(context)
        return props is not None and len(props.mappings) > 0

    def execute(self, context):
        from ..properties.mapping import MAPPING_CURVE_SPEC
        from ..utils.curve import remove_item_curves

        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}
        idx = props.mappings_index
        if 0 <= idx < len(props.mappings):
            entry = props.mappings[idx]
            if entry.curve_id:
                remove_item_curves(context.object, entry.curve_id, [MAPPING_CURVE_SPEC])
            props.mappings.remove(idx)
            if props.mappings_index >= len(props.mappings):
                props.mappings_index = max(0, len(props.mappings) - 1)
            context.object.update_tag()
        return {"FINISHED"}


class NEXUS_OT_mapping_move_entry(bpy.types.Operator):
    """Move the selected mapping layer up or down"""

    bl_idname = "nexus.mapping_move_entry"
    bl_label = "Move Mapping Layer"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
        default="UP",
    )

    @classmethod
    def poll(cls, context):
        props = _active_nexus_props(context)
        return props is not None and len(props.mappings) > 1

    def execute(self, context):
        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}
        idx = props.mappings_index
        moved = False
        if self.direction == "UP" and idx > 0:
            props.mappings.move(idx, idx - 1)
            props.mappings_index = idx - 1
            moved = True
        elif self.direction == "DOWN" and idx < len(props.mappings) - 1:
            props.mappings.move(idx, idx + 1)
            props.mappings_index = idx + 1
            moved = True
        if moved:
            context.object.update_tag()
        return {"FINISHED"}


class NEXUS_OT_mapping_set_source(bpy.types.Operator):
    """Change the particle-data source feeding this mapping layer"""

    bl_idname = "nexus.mapping_set_source"
    bl_label = "Set Mapping Source"
    bl_options = {"REGISTER", "UNDO"}

    source_param: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        props = _active_nexus_props(context)
        return props is not None and 0 <= props.mappings_index < len(props.mappings)

    def execute(self, context):
        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}
        entry = props.mappings[props.mappings_index]
        entry.source_param = int(self.source_param)
        context.object.update_tag()
        return {"FINISHED"}


class NEXUS_OT_mapping_set_dest(bpy.types.Operator):
    """Set the destination parameter this mapping layer modulates"""

    bl_idname = "nexus.mapping_set_dest"
    bl_label = "Set Mapping Destination"
    bl_options = {"REGISTER", "UNDO"}

    dest_param: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        props = _active_nexus_props(context)
        return props is not None and 0 <= props.mappings_index < len(props.mappings)

    def execute(self, context):
        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}
        entry = props.mappings[props.mappings_index]
        entry.dest_param = int(self.dest_param)
        context.object.update_tag()
        return {"FINISHED"}


class NEXUS_OT_mapping_set_layer(bpy.types.Operator):
    """Set which runtime layer of a layered modifier (e.g. Turbulence noise layer) this mapping
    applies to. Tree index 0 = first layer; layered modifiers always require a specific layer.
    """

    bl_idname = "nexus.mapping_set_layer"
    bl_label = "Set Mapping Layer"
    bl_options = {"REGISTER", "UNDO"}

    layer_id: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        props = _active_nexus_props(context)
        return props is not None and 0 <= props.mappings_index < len(props.mappings)

    def execute(self, context):
        props = _active_nexus_props(context)
        if props is None:
            return {"CANCELLED"}
        entry = props.mappings[props.mappings_index]
        entry.layer_id = int(self.layer_id)
        context.object.update_tag()
        return {"FINISHED"}


mapping_classes = [
    NEXUS_OT_mapping_add_entry,
    NEXUS_OT_mapping_remove_entry,
    NEXUS_OT_mapping_move_entry,
    NEXUS_OT_mapping_set_source,
    NEXUS_OT_mapping_set_dest,
    NEXUS_OT_mapping_set_layer,
]
