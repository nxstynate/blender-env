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

import uuid

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty

from .folder_icons import remove_folder_icon
from .utils import (
    find_item_by_key,
    get_all_descendants,
    get_insertion_point,
    get_item_key,
    get_item_parent_key,
    is_item_valid,
    set_item_parent,
    would_create_cycle,
)


class NEXUS_OT_pipeline_move(bpy.types.Operator):
    bl_idname = "nexus.pipeline_move"
    bl_label = "Move Pipeline Item"
    bl_description = "Move the selected modifier up or down among its siblings"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        name="Direction",
        items=[
            ("UP", "Up", "Move item up"),
            ("DOWN", "Down", "Move item down"),
        ],
        default="UP",
    )

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return False
        pipeline = scene.nexus_pipeline
        return len(pipeline.modifier_order) > 1

    def _subtree_indices(self, pipeline, root_index):
        """Return sorted list of collection indices for an item and all its descendants."""
        item = pipeline.modifier_order[root_index]
        descendants = get_all_descendants(pipeline, item)
        desc_keys = {get_item_key(d) for d in descendants if get_item_key(d) is not None}
        indices = [root_index]
        for i, other in enumerate(pipeline.modifier_order):
            if i != root_index and get_item_key(other) in desc_keys:
                indices.append(i)
        indices.sort()
        return indices

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        index = pipeline.modifier_order_index
        count = len(pipeline.modifier_order)

        if not (0 <= index < count):
            return {"CANCELLED"}

        item = pipeline.modifier_order[index]
        parent_key = get_item_parent_key(item)

        siblings = []
        for i, other in enumerate(pipeline.modifier_order):
            if get_item_parent_key(other) == parent_key:
                siblings.append(i)

        sibling_pos = None
        for pos, sib_index in enumerate(siblings):
            if sib_index == index:
                sibling_pos = pos
                break

        if sibling_pos is None:
            return {"CANCELLED"}

        if self.direction == "UP":
            if sibling_pos <= 0:
                return {"CANCELLED"}
            other_root = siblings[sibling_pos - 1]
        else:
            if sibling_pos >= len(siblings) - 1:
                return {"CANCELLED"}
            other_root = siblings[sibling_pos + 1]

        my_indices = self._subtree_indices(pipeline, index)
        other_indices = self._subtree_indices(pipeline, other_root)

        if self.direction == "UP":
            dst = other_indices[0]
            for i, src in enumerate(my_indices):
                pipeline.modifier_order.move(src, dst + i)
            pipeline.modifier_order_index = dst
        else:
            dst = my_indices[0]
            for i, src in enumerate(other_indices):
                pipeline.modifier_order.move(src, dst + i)
            pipeline.modifier_order_index = dst + len(other_indices)

        return {"FINISHED"}


class NEXUS_OT_pipeline_refresh(bpy.types.Operator):
    """Force refresh of the pipeline list"""

    bl_idname = "nexus.pipeline_refresh"
    bl_label = "Refresh Pipeline"
    bl_description = "Force synchronization of the pipeline list with scene modifiers"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .sync import sync_modifier_list

        scene = context.scene
        sync_modifier_list(scene)

        self.report({"INFO"}, "Pipeline list refreshed")
        return {"FINISHED"}


class NEXUS_OT_pipeline_select(bpy.types.Operator):
    """Select modifier in viewport"""

    bl_idname = "nexus.pipeline_select"
    bl_label = "Select Modifier"
    bl_description = "Select this modifier in the viewport"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return False
        pipeline = scene.nexus_pipeline
        if not (0 <= pipeline.modifier_order_index < len(pipeline.modifier_order)):
            return False
        item = pipeline.modifier_order[pipeline.modifier_order_index]
        return not item.is_folder and item.modifier is not None

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        item = pipeline.modifier_order[pipeline.modifier_order_index]
        obj = item.modifier

        if obj is None:
            self.report({"WARNING"}, "Modifier object not found")
            return {"CANCELLED"}

        try:
            if obj.name not in bpy.data.objects:
                self.report({"WARNING"}, "Modifier object has been deleted")
                return {"CANCELLED"}
        except ReferenceError:
            self.report({"WARNING"}, "Modifier reference is invalid")
            return {"CANCELLED"}

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj

        return {"FINISHED"}


class NEXUS_OT_pipeline_indent(bpy.types.Operator):
    """Indent: parent the active item to the item above it"""

    bl_idname = "nexus.pipeline_indent"
    bl_label = "Indent"
    bl_description = "Parent this item to the item above it in the tree"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return False
        pipeline = scene.nexus_pipeline
        idx = pipeline.modifier_order_index
        if not (0 <= idx < len(pipeline.modifier_order)):
            return False
        return is_item_valid(pipeline.modifier_order[idx])

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        active_index = pipeline.modifier_order_index
        item = pipeline.modifier_order[active_index]
        parent_key = get_item_parent_key(item)

        prev_sibling = None
        for i, other in enumerate(pipeline.modifier_order):
            if i == active_index:
                break
            if get_item_parent_key(other) == parent_key:
                prev_sibling = other

        if prev_sibling is None or not is_item_valid(prev_sibling):
            self.report({"WARNING"}, "No sibling above to parent to")
            return {"CANCELLED"}

        prev_key = get_item_key(prev_sibling)
        if would_create_cycle(pipeline, item, prev_key):
            self.report({"WARNING"}, "Cannot indent: would create a cycle")
            return {"CANCELLED"}

        set_item_parent(item, prev_sibling)
        return {"FINISHED"}


class NEXUS_OT_pipeline_outdent(bpy.types.Operator):
    """Outdent: move the active item up one hierarchy level"""

    bl_idname = "nexus.pipeline_outdent"
    bl_label = "Outdent"
    bl_description = "Move this item up one hierarchy level"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return False
        pipeline = scene.nexus_pipeline
        idx = pipeline.modifier_order_index
        if not (0 <= idx < len(pipeline.modifier_order)):
            return False
        item = pipeline.modifier_order[idx]
        return get_item_parent_key(item) is not None

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        item = pipeline.modifier_order[pipeline.modifier_order_index]

        parent_key = get_item_parent_key(item)
        parent = find_item_by_key(pipeline, parent_key)

        grandparent = None
        if parent is not None:
            grandparent_key = get_item_parent_key(parent)
            if grandparent_key is not None:
                grandparent = find_item_by_key(pipeline, grandparent_key)

        set_item_parent(item, grandparent)
        return {"FINISHED"}


class NEXUS_OT_pipeline_remove(bpy.types.Operator):
    """Remove the active item from the pipeline"""

    bl_idname = "nexus.pipeline_remove"
    bl_label = "Remove Item"
    bl_description = "Delete the selected item from the pipeline"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return False
        pipeline = scene.nexus_pipeline
        idx = pipeline.modifier_order_index
        if not (0 <= idx < len(pipeline.modifier_order)):
            return False
        return is_item_valid(pipeline.modifier_order[idx])

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        index = pipeline.modifier_order_index
        item = pipeline.modifier_order[index]

        descendants = get_all_descendants(pipeline, item)

        objects_to_delete = []
        if not item.is_folder and item.modifier is not None:
            objects_to_delete.append(item.modifier)
        for desc in descendants:
            if not desc.is_folder and desc.modifier is not None:
                objects_to_delete.append(desc.modifier)

        all_keys_to_remove = {get_item_key(item)}
        for desc in descendants:
            key = get_item_key(desc)
            if key is not None:
                all_keys_to_remove.add(key)

        indices_to_remove = []
        for i, entry in enumerate(pipeline.modifier_order):
            if get_item_key(entry) in all_keys_to_remove:
                if entry.is_folder and entry.folder_id:
                    remove_folder_icon(entry.folder_id)
                indices_to_remove.append(i)

        for i in sorted(indices_to_remove, reverse=True):
            pipeline.modifier_order.remove(i)

        count = len(pipeline.modifier_order)
        if count > 0:
            pipeline.modifier_order_index = min(index, count - 1)
        else:
            pipeline.modifier_order_index = 0

        for o in objects_to_delete:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except ReferenceError:
                pass

        return {"FINISHED"}


class NEXUS_OT_pipeline_toggle_collapse(bpy.types.Operator):
    bl_idname = "nexus.pipeline_toggle_collapse"
    bl_label = "Toggle Collapse"
    bl_description = "Expand or collapse the item's children"
    bl_options = {"REGISTER"}

    index: IntProperty(name="Index", default=0)

    def execute(self, context):
        scene = context.scene
        pipeline = scene.nexus_pipeline
        if not (0 <= self.index < len(pipeline.modifier_order)):
            return {"CANCELLED"}
        item = pipeline.modifier_order[self.index]
        item.collapsed = not item.collapsed
        return {"FINISHED"}


class NEXUS_OT_pipeline_toggle_enable(bpy.types.Operator):
    bl_idname = "nexus.pipeline_toggle_enable"
    bl_label = "Toggle Enable"
    bl_description = "Toggle this item's enabled state"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(name="Index", default=0)
    is_folder: BoolProperty(name="Is Folder", default=False)

    def execute(self, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return {"CANCELLED"}
        pipeline = scene.nexus_pipeline
        if not (0 <= self.index < len(pipeline.modifier_order)):
            return {"CANCELLED"}
        item = pipeline.modifier_order[self.index]
        if self.is_folder:
            item.folder_enabled = not item.folder_enabled
        else:
            obj = item.modifier
            if obj is None:
                return {"CANCELLED"}
            obj.nexus_modifier.enabled = not obj.nexus_modifier.enabled
        return {"FINISHED"}


class NEXUS_OT_pipeline_add_folder(bpy.types.Operator):
    """Add an organizational folder to the pipeline"""

    bl_idname = "nexus.pipeline_add_folder"
    bl_label = "Add Folder"
    bl_description = "Add a folder to organize modifiers in the pipeline"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return {"CANCELLED"}

        pipeline = scene.nexus_pipeline
        insert_index, parent_item = get_insertion_point(pipeline)

        # Store key before .add() — otherwise invalidates existing bpy_struct wrappers.
        parent_key = get_item_key(parent_item) if parent_item is not None else None

        item = pipeline.modifier_order.add()
        item.is_folder = True
        item.folder_id = str(uuid.uuid4())
        item.folder_name = "Folder"

        if parent_key is not None:
            parent_ref = find_item_by_key(pipeline, parent_key)
            if parent_ref is not None:
                set_item_parent(item, parent_ref)

        if insert_index is not None:
            pipeline.modifier_order.move(len(pipeline.modifier_order) - 1, insert_index)
            pipeline.modifier_order_index = insert_index
        else:
            pipeline.modifier_order_index = len(pipeline.modifier_order) - 1

        return {"FINISHED"}


class NEXUS_OT_pipeline_folder_settings(bpy.types.Operator):
    """Edit folder settings"""

    bl_idname = "nexus.pipeline_folder_settings"
    bl_label = "Folder Settings"
    bl_description = "Edit folder name and color"
    bl_options = {"REGISTER"}

    index: IntProperty(name="Index", default=0)

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=200)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if not hasattr(scene, "nexus_pipeline"):
            return

        pipeline = scene.nexus_pipeline
        if not (0 <= self.index < len(pipeline.modifier_order)):
            return

        item = pipeline.modifier_order[self.index]
        if not item.is_folder:
            return

        layout.prop(item, "folder_name", text="Name")
        layout.template_color_picker(item, "folder_color", value_slider=True)

    def execute(self, context):
        return {"FINISHED"}


classes = [
    NEXUS_OT_pipeline_move,
    NEXUS_OT_pipeline_refresh,
    NEXUS_OT_pipeline_select,
    NEXUS_OT_pipeline_remove,
    NEXUS_OT_pipeline_indent,
    NEXUS_OT_pipeline_outdent,
    NEXUS_OT_pipeline_toggle_collapse,
    NEXUS_OT_pipeline_toggle_enable,
    NEXUS_OT_pipeline_add_folder,
    NEXUS_OT_pipeline_folder_settings,
]


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
