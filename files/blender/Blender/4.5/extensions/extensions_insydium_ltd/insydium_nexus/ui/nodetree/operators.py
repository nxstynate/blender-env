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
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from .hierarchy import (
    hierarchy_fix_parent_indices_after_remove,
    hierarchy_get_descendants,
    hierarchy_recalculate_indent_levels,
    hierarchy_restore_item,
    hierarchy_snapshot_item,
)
from .registry import (
    _append_object_item,
    _lookup_type_info,
    _nodetree_registry,
    _resolve_data,
    get_nodetree_config,
)


def add_nodetree_item(
    context,
    obj,
    props,
    list_prop: str,
    index_prop: str,
    item_type: str = "",
    menu_id: str = "",
    *,
    pre_add_index: int | None = None,
):
    """Shared add path for `NEXUS_OT_nodetree_add` and non-operator callers."""
    if context is None:
        raise ValueError(
            "add_nodetree_item requires a real Blender context; on_add hooks may read it"
        )

    collection = getattr(props, list_prop)

    if pre_add_index is None:
        pre_add_index = getattr(props, index_prop, -1)
    context.window_manager.nexus_nodetree_pre_add_index = pre_add_index

    item = collection.add()

    if item_type and hasattr(item, "item_type"):
        item.item_type = item_type

    if item_type and hasattr(item, "name"):
        type_info = _lookup_type_info(item_type)
        base_name = type_info[0] if type_info else item_type

        existing_names = [i.name for i in collection if hasattr(i, "name") and i.name]

        from ...utils import generate_unique_name

        item.name = generate_unique_name(base_name, existing_names)

    desired_index = None
    if menu_id:
        menu_data = _nodetree_registry.get(menu_id, {})
        if menu_data.get("list_prop") == list_prop:
            on_add = menu_data.get("on_add")
            if on_add:
                desired_index = on_add(context, obj, item)

    if isinstance(desired_index, int):
        setattr(props, index_prop, desired_index)
    else:
        setattr(props, index_prop, len(collection) - 1)

    return item


class NEXUS_OT_nodetree_add(bpy.types.Operator):
    """Add a new item to the nodetree"""

    bl_idname = "nexus.nodetree_add"
    bl_label = "Add Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Property name for the collection",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Property name for the active index",
    )
    item_type: StringProperty(
        name="Item Type",
        description="Type identifier for the new item (optional)",
    )
    menu_id: StringProperty(
        name="Menu ID",
        description="Menu registry identifier for callback lookup (optional)",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection (optional)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        add_nodetree_item(
            context,
            obj,
            props,
            self.list_prop,
            self.index_prop,
            item_type=self.item_type,
            menu_id=self.menu_id,
        )

        obj.update_tag()

        for area in context.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_remove(bpy.types.Operator):
    """Remove the selected item from the nodetree"""

    bl_idname = "nexus.nodetree_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Property name for the collection",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Property name for the active index",
    )
    menu_id: StringProperty(
        name="Menu ID",
        description="Menu registry identifier for callback lookup",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection (optional)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        active_index = getattr(props, self.index_prop)

        if not collection or active_index < 0 or active_index >= len(collection):
            return {"CANCELLED"}

        menu_data = _nodetree_registry.get(self.menu_id or self.list_prop, {})
        if menu_data.get("list_prop") == self.list_prop:
            on_remove = menu_data.get("on_remove")
            if on_remove:
                item = collection[active_index]
                on_remove(context, obj, item)

        collection.remove(active_index)

        new_index = min(active_index, len(collection) - 1)
        setattr(props, self.index_prop, max(0, new_index))

        # Removing the last item can otherwise be a no-op for depsgraph updates.
        obj.update_tag()

        for area in context.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_move(bpy.types.Operator):
    """Move the selected item up or down in the nodetree"""

    bl_idname = "nexus.nodetree_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Property name for the collection",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Property name for the active index",
    )
    direction: EnumProperty(
        name="Direction",
        items=[
            ("UP", "Up", "Move item up"),
            ("DOWN", "Down", "Move item down"),
        ],
        default="UP",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection (optional)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        active_index = getattr(props, self.index_prop)

        if not collection or len(collection) < 2:
            return {"CANCELLED"}

        if self.direction == "UP":
            new_index = active_index - 1
            if new_index < 0:
                return {"CANCELLED"}
        else:
            new_index = active_index + 1
            if new_index >= len(collection):
                return {"CANCELLED"}

        collection.move(active_index, new_index)
        setattr(props, self.index_prop, new_index)

        # Reordering a nested CollectionProperty does not reliably propagate a
        # depsgraph update to the owning Object, so tag it explicitly.
        obj.update_tag()

        for area in context.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_clear(bpy.types.Operator):
    """Clear all items from the nodetree"""

    bl_idname = "nexus.nodetree_clear"
    bl_label = "Clear Items"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Property name for the collection",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Property name for the active index",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection (optional)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    def execute(self, context):
        from ...utils.modifier_presets import clear_collection_with_lifecycle

        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        clear_collection_with_lifecycle(obj, collection, self.list_prop, context=context)
        setattr(props, self.index_prop, 0)

        for area in context.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()

        obj.update_tag()
        return {"FINISHED"}


class NEXUS_OT_nodetree_continuous_pick(bpy.types.Operator):
    """Select objects in the viewport or outliner to add them. Press Escape to finish"""

    bl_idname = "nexus.nodetree_continuous_pick"
    bl_label = "Continuous Pick"
    bl_description = (
        "Select objects in the viewport or outliner to add them. Press Escape to finish"
    )
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Name of the CollectionProperty on the modifier data",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Name of the IntProperty tracking the active index",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection",
        default="",
    )
    allowed_types_csv: StringProperty(
        name="Allowed Types",
        description="Comma-separated list of allowed object/modifier types",
        default="",
    )
    allow_duplicates: BoolProperty(
        name="Allow Duplicates",
        description="Allow the same object to be added more than once",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def invoke(self, context, event):
        owner = context.object
        self._owner_name = owner.name

        data = _resolve_data(owner, self.data_path)
        if data is None:
            return {"CANCELLED"}
        if not hasattr(data, self.list_prop):
            return {"CANCELLED"}

        types_list = (
            [t for t in self.allowed_types_csv.split(",") if t] if self.allowed_types_csv else []
        )

        self._allowed_blender = frozenset(t for t in types_list if not t.startswith("NX_"))
        self._allowed_nx = frozenset(t for t in types_list if t.startswith("NX_"))
        self._filter_active = bool(types_list)

        self._prev_active_name = owner.name
        self._prev_selected_names = [obj.name for obj in context.selected_objects]

        self._added_count = 0
        self._last_active_name = owner.name
        self._list_prop = self.list_prop
        self._index_prop = self.index_prop
        self._data_path = self.data_path
        self._allow_duplicates = self.allow_duplicates

        self._timer = context.window_manager.event_timer_add(0.02, window=context.window)
        context.window.cursor_modal_set("EYEDROPPER")
        context.workspace.status_text_set("Select objects to add | Esc: Finish")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC" and event.value == "PRESS":
            self._finish(context)
            if self._added_count > 0:
                self.report({"INFO"}, f"Added {self._added_count} object(s)")
                return {"FINISHED"}
            return {"CANCELLED"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            area, region = self._find_view3d_under_mouse(context, event)
            if area and region:
                self._pick_from_viewport(context, area, region, event)
                return {"RUNNING_MODAL"}
            return {"PASS_THROUGH"}

        if event.type == "TIMER":
            active = context.view_layer.objects.active
            if not active or active.name == self._last_active_name:
                return {"PASS_THROUGH"}

            self._last_active_name = active.name

            if active.name == self._owner_name:
                return {"PASS_THROUGH"}

            owner = bpy.data.objects.get(self._owner_name)
            if owner is None:
                self._finish(context)
                return {"CANCELLED"}

            data = _resolve_data(owner, self._data_path)
            if data is None:
                self._finish(context)
                return {"CANCELLED"}

            self._try_add(data, active)
            self._restore_owner(context, owner)
            for area in context.screen.areas:
                area.tag_redraw()

            return {"PASS_THROUGH"}

        return {"PASS_THROUGH"}

    def _find_view3d_under_mouse(self, context, event):
        for area in context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            if not (
                area.x <= event.mouse_x < area.x + area.width
                and area.y <= event.mouse_y < area.y + area.height
            ):
                continue
            for region in area.regions:
                if region.type == "WINDOW":
                    return area, region
        return None, None

    def _pick_from_viewport(self, context, area, region, event):
        owner = bpy.data.objects.get(self._owner_name)
        if owner is None:
            self._finish(context)
            return

        data = _resolve_data(owner, self._data_path)
        if data is None:
            self._finish(context)
            return

        local_x = event.mouse_x - region.x
        local_y = event.mouse_y - region.y
        try:
            with context.temp_override(area=area, region=region):
                bpy.ops.view3d.select(location=(local_x, local_y))
        except Exception:
            self._restore_owner(context, owner)
            return

        picked = context.view_layer.objects.active
        if picked and picked.name != self._owner_name:
            self._try_add(data, picked)

        self._restore_owner(context, owner)
        for a in context.screen.areas:
            a.tag_redraw()

    def _try_add(self, data, obj):
        if not self._passes_filter(obj):
            return
        collection = getattr(data, self._list_prop)
        if not self._allow_duplicates:
            for item in collection:
                if getattr(item, "obj", None) == obj:
                    return
        _append_object_item(collection, obj)
        setattr(data, self._index_prop, len(collection) - 1)
        owner = getattr(data, "id_data", None)
        if owner is not None:
            owner.update_tag()
        self._added_count += 1

    def _passes_filter(self, obj):
        if not self._filter_active:
            return True
        if obj.type in self._allowed_blender:
            return True
        if self._allowed_nx and obj.get("nexus_modifier_type") in self._allowed_nx:
            return True
        return False

    def _restore_owner(self, context, owner):
        for obj in context.selected_objects:
            obj.select_set(False)
        owner.select_set(True)
        context.view_layer.objects.active = owner
        self._last_active_name = owner.name

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)
        for obj in context.selected_objects:
            obj.select_set(False)
        for name in self._prev_selected_names:
            obj = bpy.data.objects.get(name)
            if obj:
                obj.select_set(True)
        prev = bpy.data.objects.get(self._prev_active_name)
        if prev:
            context.view_layer.objects.active = prev

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)


class NEXUS_OT_nodetree_create_and_add(bpy.types.Operator):
    """Create a new NeXus modifier object and add it to this list"""

    bl_idname = "nexus.nodetree_create_and_add"
    bl_label = "Create and Add"
    bl_description = "Create a new NeXus modifier object and add it to this list"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(
        name="List Property",
        description="Name of the CollectionProperty on the modifier data",
    )
    index_prop: StringProperty(
        name="Index Property",
        description="Name of the IntProperty tracking the active index",
    )
    modifier_type: StringProperty(
        name="Modifier Type",
        description="NX_ type string for the modifier to create (e.g. NX_GROUP)",
    )
    data_path: StringProperty(
        name="Data Path",
        default="",
        description="RNA path to the data object owning the collection (optional)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    @classmethod
    def description(cls, context, properties):
        from ...modifiers import MODIFIER_REGISTRY

        mod_class = MODIFIER_REGISTRY.get(properties.modifier_type)
        if mod_class is not None:
            name = getattr(mod_class, "object_name", properties.modifier_type)
            return f"Create and add {name} object"
        return cls.bl_description

    def execute(self, context):
        emitter_obj = context.object

        from ...modifiers import MODIFIER_REGISTRY

        mod_class = MODIFIER_REGISTRY.get(self.modifier_type)
        if mod_class is None:
            self.report(
                {"ERROR"},
                f"Unknown modifier type: {self.modifier_type}",
            )
            return {"CANCELLED"}

        new_obj = mod_class.create_object(context)

        props = _resolve_data(emitter_obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        _append_object_item(collection, new_obj)
        setattr(props, self.index_prop, len(collection) - 1)

        emitter_obj.update_tag()

        bpy.ops.object.select_all(action="DESELECT")
        emitter_obj.select_set(True)
        context.view_layer.objects.active = emitter_obj

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_show_add_menu(bpy.types.Operator):
    """Show the add menu for nodetree items"""

    bl_idname = "nexus.nodetree_show_add_menu"
    bl_label = "Add"
    bl_options = {"REGISTER"}

    menu_id: StringProperty(
        name="Menu ID",
        description="Menu registry identifier",
    )
    data_path: StringProperty(
        name="Data Path",
        description="RNA path to the data object owning the collection (optional)",
    )

    def execute(self, context):
        context.window_manager.nexus_nodetree_menu_id = self.menu_id
        context.window_manager.nexus_nodetree_data_path = self.data_path
        bpy.ops.wm.call_menu(name="NEXUS_MT_nodetree_add")
        return {"FINISHED"}


class NEXUS_OT_nodetree_toggle_enable(bpy.types.Operator):
    """Toggle this item's enabled state"""

    bl_idname = "nexus.nodetree_toggle_enable"
    bl_label = "Toggle Enable"
    bl_description = "Toggle this item's enabled state"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    data_path: StringProperty(
        name="Data Path",
        description="RNA path from the active object to the data block holding the collection",
        default="",
    )
    list_prop: StringProperty(
        name="List Property",
        description="Name of the CollectionProperty on the resolved data block",
        default="",
    )
    index: IntProperty(
        name="Index",
        description="Index into the collection",
        default=-1,
    )
    prop_name: StringProperty(
        name="Property Name",
        description="Name of the BoolProperty to toggle",
        default="enabled",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop, None)
        if collection is None or self.index < 0 or self.index >= len(collection):
            return {"CANCELLED"}

        item = collection[self.index]
        if not hasattr(item, self.prop_name):
            return {"CANCELLED"}

        setattr(item, self.prop_name, not getattr(item, self.prop_name))
        # Toggling a enabled BoolProperty on a nested PropertyGroup item does not reliably
        # propagate a depsgraph update to the owning Object, so tag it explicitly.
        obj.update_tag()
        return {"FINISHED"}


class NEXUS_OT_nodetree_toggle_icon_flag(bpy.types.Operator):
    """Toggle a per-item icon flag bit"""

    bl_idname = "nexus.nodetree_toggle_icon_flag"
    bl_label = "Toggle Icon Flag"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    data_path: StringProperty(default="")
    list_prop: StringProperty(default="")
    index: IntProperty(default=-1)
    bit: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and "nexus_modifier_type" in obj

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop, None)
        if collection is None or self.index < 0 or self.index >= len(collection):
            return {"CANCELLED"}

        item = collection[self.index]
        if not hasattr(item, "icon_flags"):
            return {"CANCELLED"}

        item.icon_flags ^= 1 << self.bit
        obj.update_tag()
        return {"FINISHED"}


class NEXUS_MT_nodetree_add(bpy.types.Menu):
    bl_idname = "NEXUS_MT_nodetree_add"
    bl_label = "Add Item"

    def draw(self, context):
        layout = self.layout

        wm = context.window_manager
        menu_id = getattr(wm, "nexus_nodetree_menu_id", "")
        data_path = getattr(wm, "nexus_nodetree_data_path", "")

        menu_data = get_nodetree_config(menu_id)
        items = menu_data.get("type_items", [])
        list_prop = menu_data.get("list_prop", "")
        index_prop = menu_data.get("index_prop", "")
        separator_after = menu_data.get("separator_after", set())

        if not items:
            layout.label(text="No types available", icon="ERROR")
            return

        for item in items:
            if len(item) >= 5:
                identifier, name, description, icon, idx = item[:5]
            elif len(item) >= 4:
                identifier, name, description, icon = item[:4]
            else:
                continue

            if isinstance(icon, int) and icon > 0:
                op = layout.operator(
                    "nexus.nodetree_add",
                    text=name,
                    icon_value=icon,
                )
            elif isinstance(icon, str) and icon != "NONE":
                op = layout.operator(
                    "nexus.nodetree_add",
                    text=name,
                    icon=icon,
                )
            else:
                op = layout.operator(
                    "nexus.nodetree_add",
                    text=name,
                )

            op.list_prop = list_prop
            op.index_prop = index_prop
            op.item_type = identifier
            op.menu_id = menu_id
            op.data_path = data_path

            if identifier in separator_after:
                layout.separator()


class NEXUS_OT_nodetree_hierarchy_remove(bpy.types.Operator):
    """Remove the selected item and its descendants"""

    bl_idname = "nexus.nodetree_hierarchy_remove"
    bl_label = "Remove Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(name="List Property")
    index_prop: StringProperty(name="Index Property")
    menu_id: StringProperty(name="Menu ID")
    data_path: StringProperty(name="Data Path", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        idx = getattr(props, self.index_prop)

        if not collection or idx < 0 or idx >= len(collection):
            return {"CANCELLED"}

        registry_entry = _nodetree_registry.get(self.menu_id or self.list_prop, {})

        on_remove = registry_entry.get("on_remove")
        if on_remove:
            on_remove(context, obj, collection[idx])

        to_remove = [idx] + hierarchy_get_descendants(collection, idx)
        to_remove.sort(reverse=True)
        removed_original = sorted(to_remove)

        for ri in to_remove:
            collection.remove(ri)

        hierarchy_fix_parent_indices_after_remove(collection, removed_original)
        hierarchy_recalculate_indent_levels(collection)

        on_hierarchy_remove = registry_entry.get("on_hierarchy_remove")
        if on_hierarchy_remove:
            on_hierarchy_remove(context, obj)

        new_index = min(idx, len(collection) - 1)
        setattr(props, self.index_prop, max(0, new_index))

        obj.update_tag()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_hierarchy_move(bpy.types.Operator):
    """Move the selected item and its descendants up or down"""

    bl_idname = "nexus.nodetree_hierarchy_move"
    bl_label = "Move Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(name="List Property")
    index_prop: StringProperty(name="Index Property")
    menu_id: StringProperty(name="Menu ID")
    data_path: StringProperty(name="Data Path", default="")
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
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False
        return True

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        collection = getattr(props, self.list_prop)
        idx = getattr(props, self.index_prop)

        if not collection or len(collection) < 2:
            return {"CANCELLED"}
        if idx < 0 or idx >= len(collection):
            return {"CANCELLED"}

        current = collection[idx]
        parent_idx = current.parent_index

        siblings = [i for i in range(len(collection)) if collection[i].parent_index == parent_idx]

        sib_pos = None
        for si, sib_idx in enumerate(siblings):
            if sib_idx == idx:
                sib_pos = si
                break

        if sib_pos is None:
            return {"CANCELLED"}

        if self.direction == "UP":
            if sib_pos <= 0:
                return {"CANCELLED"}
            swap_idx = siblings[sib_pos - 1]
        else:
            if sib_pos >= len(siblings) - 1:
                return {"CANCELLED"}
            swap_idx = siblings[sib_pos + 1]

        block_a = sorted([idx] + hierarchy_get_descendants(collection, idx))
        block_b = sorted([swap_idx] + hierarchy_get_descendants(collection, swap_idx))

        count = len(collection)
        snapshots = [hierarchy_snapshot_item(collection[i]) for i in range(count)]

        old_order = list(range(count))
        block_a_set = set(block_a)
        block_b_set = set(block_b)

        combined_start = min(block_a[0], block_b[0])
        combined_end = max(block_a[-1], block_b[-1])

        middle = [
            i
            for i in range(combined_start, combined_end + 1)
            if i not in block_a_set and i not in block_b_set
        ]

        if self.direction == "UP":
            new_combined = block_a + middle + block_b
        else:
            new_combined = block_b + middle + block_a

        new_order = old_order[:combined_start] + new_combined + old_order[combined_end + 1 :]

        index_map = {}
        for new_pos, old_idx in enumerate(new_order):
            index_map[old_idx] = new_pos

        reordered = [snapshots[old_idx] for old_idx in new_order]

        for snap in reordered:
            pi = snap.get("parent_index", -1)
            if pi >= 0 and pi in index_map:
                snap["parent_index"] = index_map[pi]

        for i in range(count):
            hierarchy_restore_item(collection[i], reordered[i])

        hierarchy_recalculate_indent_levels(collection)
        setattr(props, self.index_prop, index_map[idx])

        registry_entry = _nodetree_registry.get(self.menu_id, {})
        on_hierarchy_move = registry_entry.get("on_hierarchy_move")
        if on_hierarchy_move:
            on_hierarchy_move(context, obj)

        obj.update_tag()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_hierarchy_indent(bpy.types.Operator):
    """Indent: parent item to previous sibling container"""

    bl_idname = "nexus.nodetree_hierarchy_indent"
    bl_label = "Indent Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(name="List Property")
    index_prop: StringProperty(name="Index Property")
    menu_id: StringProperty(name="Menu ID")
    data_path: StringProperty(name="Data Path", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False

        wm = context.window_manager
        menu_id = getattr(wm, "nexus_hierarchy_menu_id", "")
        if not menu_id:
            return False

        registry_entry = _nodetree_registry.get(menu_id, {})
        list_prop = registry_entry.get("list_prop", "")
        index_prop = registry_entry.get("index_prop", "")
        container_types = registry_entry.get("container_types", set())
        data_path = getattr(wm, "nexus_hierarchy_data_path", "")

        props = _resolve_data(obj, data_path)
        if props is None:
            return False

        items = getattr(props, list_prop, None)
        if items is None:
            return False
        idx = getattr(props, index_prop, -1)
        if not items or not (0 <= idx < len(items)):
            return False
        current_parent = items[idx].parent_index
        for i in range(idx - 1, -1, -1):
            if items[i].parent_index == current_parent and items[i].item_type in container_types:
                return True
        return False

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        registry_entry = _nodetree_registry.get(self.menu_id, {})
        container_types = registry_entry.get("container_types", set())

        items = getattr(props, self.list_prop)
        idx = getattr(props, self.index_prop)

        if not items or not (0 <= idx < len(items)):
            return {"CANCELLED"}

        current = items[idx]
        current_parent = current.parent_index

        prev_sibling_idx = None
        for i in range(idx - 1, -1, -1):
            if items[i].parent_index == current_parent and items[i].item_type in container_types:
                prev_sibling_idx = i
                break

        if prev_sibling_idx is None:
            return {"CANCELLED"}

        descendants = hierarchy_get_descendants(items, idx)
        if prev_sibling_idx in descendants:
            return {"CANCELLED"}

        current.parent_index = prev_sibling_idx
        hierarchy_recalculate_indent_levels(items)

        obj.update_tag()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_hierarchy_outdent(bpy.types.Operator):
    """Outdent: move item up one hierarchy level"""

    bl_idname = "nexus.nodetree_hierarchy_outdent"
    bl_label = "Outdent Item"
    bl_options = {"REGISTER", "UNDO"}

    list_prop: StringProperty(name="List Property")
    index_prop: StringProperty(name="Index Property")
    menu_id: StringProperty(name="Menu ID")
    data_path: StringProperty(name="Data Path", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return False

        wm = context.window_manager
        menu_id = getattr(wm, "nexus_hierarchy_menu_id", "")
        if not menu_id:
            return False

        registry_entry = _nodetree_registry.get(menu_id, {})
        list_prop = registry_entry.get("list_prop", "")
        index_prop = registry_entry.get("index_prop", "")
        data_path = getattr(wm, "nexus_hierarchy_data_path", "")

        props = _resolve_data(obj, data_path)
        if props is None:
            return False

        items = getattr(props, list_prop, None)
        if items is None:
            return False
        idx = getattr(props, index_prop, -1)
        if not items or not (0 <= idx < len(items)):
            return False
        return items[idx].parent_index >= 0

    def execute(self, context):
        obj = context.object
        props = _resolve_data(obj, self.data_path)
        if props is None:
            return {"CANCELLED"}

        items = getattr(props, self.list_prop)
        idx = getattr(props, self.index_prop)

        if not items or not (0 <= idx < len(items)):
            return {"CANCELLED"}

        current = items[idx]
        parent_idx = current.parent_index
        grandparent_idx = items[parent_idx].parent_index if 0 <= parent_idx < len(items) else -1
        current.parent_index = grandparent_idx
        hierarchy_recalculate_indent_levels(items)

        obj.update_tag()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        return {"FINISHED"}


class NEXUS_OT_nodetree_hierarchy_folder_settings(bpy.types.Operator):
    """Edit folder name and color"""

    bl_idname = "nexus.nodetree_hierarchy_folder_settings"
    bl_label = "Folder Settings"
    bl_description = "Edit folder name and color"
    bl_options = {"REGISTER"}

    index: IntProperty(name="Index", default=0)
    menu_id: StringProperty(name="Menu ID")
    data_path: StringProperty(name="Data Path", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and "nexus_modifier_type" in obj

    def invoke(self, context, _event):
        return context.window_manager.invoke_popup(self, width=200)

    def draw(self, context):
        obj = context.object
        if not obj or "nexus_modifier_type" not in obj:
            return

        registry_entry = _nodetree_registry.get(self.menu_id, {})
        folder_type = registry_entry.get("folder_type")
        folder_color_prop = registry_entry.get("folder_color_prop")
        list_prop_name = registry_entry.get("list_prop", "")

        props = _resolve_data(obj, self.data_path)
        if props is None:
            return

        items = getattr(props, list_prop_name, None)
        if items is None or not (0 <= self.index < len(items)):
            return

        item = items[self.index]
        if folder_type and item.item_type != folder_type:
            return

        layout = self.layout
        layout.prop(item, "name", text="Name")
        if folder_color_prop:
            layout.template_color_picker(item, folder_color_prop, value_slider=True)

    def execute(self, _context):
        return {"FINISHED"}
