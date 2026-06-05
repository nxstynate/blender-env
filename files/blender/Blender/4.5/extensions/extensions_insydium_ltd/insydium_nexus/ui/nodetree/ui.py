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
from bpy.props import BoolProperty, IntProperty, PointerProperty

from .hierarchy import hierarchy_is_ancestor_collapsed
from .registry import (
    _collection_has_prop,
    _format_allowed_types_label,
    _get_enable_icons,
    _lookup_type_info,
    _nodetree_data_paths,
    _nodetree_per_item_toggles,
    _nodetree_registry,
    _nodetree_tree_types,
    make_allowed_types_poll,
    make_drop_target_update,
    register_ghost_slot,
)


class NexusNodeTreeItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)
    icon_flags: IntProperty(name="Icon Flags", default=0)


class NEXUS_UL_nodetree(bpy.types.UIList):
    bl_idname = "NEXUS_UL_nodetree"

    def draw_item(
        self,
        _context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_propname,
        index,
    ):
        from ...icons import get_icon

        is_typed = hasattr(item, "item_type")

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            if is_typed:
                self._draw_typed_item(row, item)
            else:
                self._draw_object_item(row, layout, item)

            data_path = _nodetree_data_paths.get(self.list_id, "")
            registry_entry = _nodetree_registry.get(self.list_id)
            list_prop = registry_entry["list_prop"] if registry_entry else self.list_id

            toggles = _nodetree_per_item_toggles.get(self.list_id, ())
            for toggle in toggles:
                if not hasattr(item, "icon_flags"):
                    continue
                if toggle.show_condition and not toggle.show_condition(item):
                    continue

                sub = row.row(align=True)
                sub.ui_units_x = 1.0
                is_set = bool(item.icon_flags & (1 << toggle.bit))
                icon_name = toggle.icons[0] if is_set else toggle.icons[1]
                icon_value = get_icon(icon_name)
                op = sub.operator(
                    "nexus.nodetree_toggle_icon_flag",
                    text="",
                    icon_value=icon_value,
                    emboss=False,
                )
                op.data_path = data_path
                op.list_prop = list_prop
                op.index = index
                op.bit = toggle.bit

            enable_sub = row.row(align=True)
            enable_sub.ui_units_x = 1.0
            _enabled_icon, _disabled_icon = _get_enable_icons(
                _nodetree_tree_types.get(self.list_id, "regular")
            )

            op = enable_sub.operator(
                "nexus.nodetree_toggle_enable",
                text="",
                icon_value=get_icon(_enabled_icon) if item.enabled else get_icon(_disabled_icon),
                emboss=False,
            )
            op.data_path = data_path
            op.list_prop = list_prop
            op.index = index
            op.prop_name = "enabled"

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            if is_typed:
                self._draw_typed_grid(layout, item)
            else:
                if item.obj:
                    icon_value = layout.icon(item.obj)
                    nx_icon = self._resolve_nexus_object_icon(item.obj)
                    if nx_icon > 0:
                        icon_value = nx_icon
                    layout.label(text="", icon_value=icon_value)
                else:
                    layout.label(text="", icon="ERROR")

    @staticmethod
    def _resolve_nexus_object_icon(obj) -> int:
        from ...icons import get_icon
        from ...modifiers import MODIFIER_REGISTRY

        mod_type = obj.get("nexus_modifier_type")
        if not mod_type:
            return 0
        mod_class = MODIFIER_REGISTRY.get(mod_type)
        if mod_class is None:
            return 0
        icon_name = getattr(mod_class, "icon_name", None)
        if not icon_name:
            return 0
        return get_icon(icon_name)

    def _draw_object_item(self, row, layout, item):
        if item.obj:
            icon_value = layout.icon(item.obj)
            nx_icon = self._resolve_nexus_object_icon(item.obj)
            if nx_icon > 0:
                icon_value = nx_icon
            if hasattr(item, "get_list_icon") and callable(item.get_list_icon):
                override = item.get_list_icon()
                if isinstance(override, int) and override > 0:
                    icon_value = override
            row.prop(
                item.obj,
                "name",
                text="",
                emboss=False,
                icon_value=icon_value,
            )
        else:
            row.label(text="<Empty>", icon="ERROR")

    def _draw_typed_item(self, row, item):
        item_type = getattr(item, "item_type", None)
        icon_value = 0
        icon_str = "BLANK1"

        if item_type:
            type_info = _lookup_type_info(item_type, self.list_id)
            if type_info:
                _, icon = type_info
                if isinstance(icon, int) and icon > 0:
                    icon_value = icon
                elif isinstance(icon, str) and icon != "NONE":
                    icon_str = icon

        if hasattr(item, "get_list_icon") and callable(item.get_list_icon):
            _override = item.get_list_icon()
            if isinstance(_override, int) and _override > 0:
                icon_value = _override
                icon_str = "BLANK1"

        if hasattr(item, "name") and item.name:
            if icon_value > 0:
                row.prop(item, "name", text="", emboss=False, icon_value=icon_value)
            else:
                row.prop(item, "name", text="", emboss=False, icon=icon_str)
        elif item_type:
            type_info = _lookup_type_info(item_type, self.list_id)
            if type_info:
                label = type_info[0]
                if icon_value > 0:
                    row.label(text=label, icon_value=icon_value)
                else:
                    row.label(text=label, icon=icon_str)
            else:
                row.label(text="<Unknown Type>", icon="ERROR")
        else:
            row.label(text="<Unknown Type>", icon="ERROR")

    def _draw_typed_grid(self, layout, item):
        item_type = getattr(item, "item_type", None)
        if item_type:
            type_info = _lookup_type_info(item_type, self.list_id)
            if type_info:
                _, icon = type_info
                icon_value = 0
                icon_str = "BLANK1"
                if isinstance(icon, int) and icon > 0:
                    icon_value = icon
                elif isinstance(icon, str) and icon != "NONE":
                    icon_str = icon

                if hasattr(item, "get_list_icon") and callable(item.get_list_icon):
                    _override = item.get_list_icon()
                    if isinstance(_override, int) and _override > 0:
                        icon_value = _override
                        icon_str = "BLANK1"

                if icon_value > 0:
                    layout.label(text="", icon_value=icon_value)
                else:
                    layout.label(text="", icon=icon_str)
                return
        layout.label(text="", icon="ERROR")


class NEXUS_UL_nodetree_hierarchy(bpy.types.UIList):
    bl_idname = "NEXUS_UL_nodetree_hierarchy"

    def draw_item(
        self, _context, layout, _data, item, _icon, _active_data, _active_propname, index
    ):
        from ...icons import get_icon

        registry_entry = _nodetree_registry.get(self.list_id, {})
        container_types = registry_entry.get("container_types", set())
        folder_type = registry_entry.get("folder_type")
        folder_color_prop = registry_entry.get("folder_color_prop")
        folder_icon_cache = registry_entry.get("folder_icon_cache")

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            if item.indent_level > 0:
                indent = row.row()
                indent.ui_units_x = item.indent_level * 0.7
                indent.label(text="")

            arrow_col = row.row(align=True)
            arrow_col.ui_units_x = 1.0
            if item.item_type in container_types:
                arrow_col.prop(
                    item,
                    "expanded",
                    text="",
                    icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT",
                    emboss=False,
                )
            else:
                arrow_col.label(text="")

            type_info = _lookup_type_info(item.item_type, self.list_id)
            icon_value = 0
            icon_str = "BLANK1"

            is_folder_item = (
                folder_type
                and item.item_type == folder_type
                and folder_icon_cache
                and folder_color_prop
            )
            if is_folder_item:
                cache_key = f"hf_{index}"
                color = getattr(item, folder_color_prop, (0.5, 0.5, 0.5))
                icon_value = folder_icon_cache.get_icon_id(cache_key, tuple(color))
                icon_sub = row.row(align=True)
                icon_sub.ui_units_x = 1.2

                data_path = _nodetree_data_paths.get(self.list_id, "")

                op = icon_sub.operator(
                    "nexus.nodetree_hierarchy_folder_settings",
                    text="",
                    icon_value=icon_value,
                    emboss=False,
                )
                op.index = index
                op.menu_id = self.list_id
                op.data_path = data_path
                row.prop(item, "name", text="", emboss=False)
            else:
                if type_info:
                    _, icon = type_info
                    if isinstance(icon, int) and icon > 0:
                        icon_value = icon
                    elif isinstance(icon, str) and icon != "NONE":
                        icon_str = icon

                if hasattr(item, "get_list_icon") and callable(item.get_list_icon):
                    _override = item.get_list_icon()
                    if isinstance(_override, int) and _override > 0:
                        icon_value = _override
                        icon_str = "BLANK1"

                if item.name:
                    if icon_value > 0:
                        row.prop(item, "name", text="", emboss=False, icon_value=icon_value)
                    else:
                        row.prop(item, "name", text="", emboss=False, icon=icon_str)
                else:
                    label = type_info[0] if type_info else item.item_type
                    if icon_value > 0:
                        row.label(text=label, icon_value=icon_value)
                    else:
                        row.label(text=label, icon=icon_str)

            data_path = _nodetree_data_paths.get(self.list_id, "")
            list_prop = registry_entry.get("list_prop", self.list_id)

            enable_sub = row.row(align=True)
            enable_sub.ui_units_x = 1.0
            _enabled_icon, _disabled_icon = _get_enable_icons(
                _nodetree_tree_types.get(self.list_id, "regular")
            )
            op = enable_sub.operator(
                "nexus.nodetree_toggle_enable",
                text="",
                icon_value=get_icon(_enabled_icon) if item.enabled else get_icon(_disabled_icon),
                emboss=False,
            )
            op.data_path = data_path
            op.list_prop = list_prop
            op.index = index
            op.prop_name = "enabled"

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="QUESTION")

    def filter_items(self, _context, data, propname):
        items = getattr(data, propname)
        count = len(items)
        flt_flags = [self.bitflag_filter_item] * count
        flt_neworder = list(range(count))
        for i, item in enumerate(items):
            if hierarchy_is_ancestor_collapsed(items, item):
                flt_flags[i] = 0
        return flt_flags, flt_neworder


def draw_nodetree(
    layout,
    data,
    list_prop_name: str,
    index_prop_name: str,
    label: str = "Objects",
    draw_item_settings=None,
    menu_id: str = None,
    data_path: str = "",
    show_quick_add: bool | None = None,
    allowed_types: list[str] | None = None,
    allow_duplicates: bool = False,
    extra_operators: list[dict] | None = None,
    tree_type: str = "regular",
    per_item_toggles: tuple | None = None,
):
    has_obj = _collection_has_prop(data, list_prop_name, "obj")
    has_menu = bool(menu_id)

    if show_quick_add is None:
        effective_show_quick_add = has_obj and not has_menu
    else:
        effective_show_quick_add = bool(show_quick_add) and has_obj and not has_menu

    drop_prop_name = f"{list_prop_name}_drop_target"
    drop_collection_prop_name = f"{list_prop_name}_drop_collection"
    has_rna = hasattr(data.__class__, "bl_rna")
    has_drop_target = drop_prop_name in data.__class__.bl_rna.properties if has_rna else False
    has_collection_drop_target = (
        drop_collection_prop_name in data.__class__.bl_rna.properties if has_rna else False
    )

    split = layout.split(factor=0.385)
    split.use_property_split = False

    label_col = split.column()
    label_col.alignment = "RIGHT"
    label_col.label(text=label)

    content_col = split.column()

    if effective_show_quick_add and has_drop_target:
        from ...icons import get_icon

        pick_row = content_col.row(align=True)
        drop_col = pick_row.column(align=True)
        drop_col.prop(data, drop_prop_name, text="")
        if has_collection_drop_target:
            drop_col.prop(data, drop_collection_prop_name, text="")
        side = pick_row.column(align=True)
        op = side.operator(
            "nexus.nodetree_continuous_pick",
            text="",
            icon_value=get_icon("nx_multi_picker"),
        )
        op.list_prop = list_prop_name
        op.index_prop = index_prop_name
        op.data_path = data_path
        op.allowed_types_csv = ",".join(allowed_types) if allowed_types else ""
        op.allow_duplicates = allow_duplicates

        content_col.separator(factor=0.5)

    list_row = content_col.row()

    list_id = menu_id or list_prop_name
    _nodetree_data_paths[list_id] = data_path
    _nodetree_tree_types[list_id] = tree_type
    _nodetree_per_item_toggles[list_id] = tuple(per_item_toggles) if per_item_toggles else ()

    list_row.template_list(
        "NEXUS_UL_nodetree",
        list_id,
        data,
        list_prop_name,
        data,
        index_prop_name,
        rows=3,
    )

    col = list_row.column(align=True)

    if has_menu:
        op = col.operator("nexus.nodetree_show_add_menu", icon="ADD", text="")
        op.menu_id = menu_id
        op.data_path = data_path
    else:
        if not has_obj:
            op = col.operator("nexus.nodetree_add", icon="ADD", text="")
            op.list_prop = list_prop_name
            op.index_prop = index_prop_name
            op.item_type = ""
            op.menu_id = ""
            op.data_path = data_path

    if extra_operators:
        for extra in extra_operators:
            icon_arg = extra.get("icon", "NONE")
            if isinstance(icon_arg, int):
                op = col.operator(
                    extra["operator"], text=extra.get("text", ""), icon_value=icon_arg
                )
            else:
                op = col.operator(extra["operator"], text=extra.get("text", ""), icon=icon_arg)
            op.data_path = data_path
            for k, v in extra.get("properties", {}).items():
                setattr(op, k, v)

    op = col.operator("nexus.nodetree_remove", icon="REMOVE", text="")
    op.list_prop = list_prop_name
    op.index_prop = index_prop_name
    op.menu_id = menu_id if has_menu else ""
    op.data_path = data_path

    col.separator()

    op = col.operator("nexus.nodetree_move", icon="TRIA_UP", text="")
    op.list_prop = list_prop_name
    op.index_prop = index_prop_name
    op.direction = "UP"
    op.data_path = data_path

    op = col.operator("nexus.nodetree_move", icon="TRIA_DOWN", text="")
    op.list_prop = list_prop_name
    op.index_prop = index_prop_name
    op.direction = "DOWN"
    op.data_path = data_path

    collection = getattr(data, list_prop_name)
    active_index = getattr(data, index_prop_name)
    if collection and 0 <= active_index < len(collection):
        item = collection[active_index]

        if draw_item_settings is not None:
            layout.separator(factor=0.5)
            settings_col = layout.column()
            settings_col.use_property_split = True
            draw_item_settings(settings_col, item)


class NodeTreeDef:
    def __init__(
        self,
        label: str = "Objects",
        item_type=None,
        menu_id=None,
        allowed_types: list[str] | None = None,
        show_quick_add: bool | None = None,
        allow_duplicates: bool = False,
        per_item_toggles=None,
        nodetree_sync=None,
    ):
        self.label = label
        self.item_type = item_type if item_type is not None else NexusNodeTreeItem
        self.menu_id = menu_id
        self.allowed_types = list(allowed_types) if allowed_types else None
        self._poll = make_allowed_types_poll(allowed_types) if allowed_types else None
        self.show_quick_add = show_quick_add
        self.allow_duplicates = allow_duplicates
        self.per_item_toggles = tuple(per_item_toggles) if per_item_toggles else None
        if nodetree_sync is None:
            self.sync_specs = ()
        elif isinstance(nodetree_sync, (list, tuple)):
            self.sync_specs = tuple(nodetree_sync)
        else:
            self.sync_specs = (nodetree_sync,)

    def properties(self, name: str) -> dict:
        from bpy.props import CollectionProperty, IntProperty

        props = {
            name: CollectionProperty(
                name=self.label,
                type=self.item_type,
            ),
            f"{name}_index": IntProperty(
                name="Active Index",
                default=0,
                min=0,
            ),
        }

        has_obj = "obj" in getattr(self.item_type, "__annotations__", {})
        emit_ghost = has_obj and self.show_quick_add is not False

        if emit_ghost:
            drop_prop_name = f"{name}_drop_target"
            description = "Pick or drop an object to add it to the list"
            if self.allowed_types:
                description += f".\nAccepts: {_format_allowed_types_label(self.allowed_types)}"
            ghost_kwargs = {
                "name": "Add Object",
                "description": description,
                "type": bpy.types.Object,
                "update": make_drop_target_update(
                    name,
                    f"{name}_index",
                    drop_prop_name,
                    allow_duplicates=self.allow_duplicates,
                    allowed_types=self.allowed_types,
                ),
            }
            if self._poll is not None:
                ghost_kwargs["poll"] = self._poll
            props[drop_prop_name] = PointerProperty(**ghost_kwargs)

            drop_collection_prop_name = f"{name}_drop_collection"
            collection_description = "Drop a collection to add its objects to the list"
            if self.allowed_types:
                collection_description += (
                    f".\nAccepts: {_format_allowed_types_label(self.allowed_types)}"
                )
            collection_drop_prop = PointerProperty(
                name="Add Collection",
                description=collection_description,
                type=bpy.types.Collection,
                update=make_drop_target_update(
                    name,
                    f"{name}_index",
                    drop_collection_prop_name,
                    allow_duplicates=self.allow_duplicates,
                    allowed_types=self.allowed_types,
                ),
            )
            props[drop_collection_prop_name] = collection_drop_prop
            register_ghost_slot(drop_collection_prop_name, collection_drop_prop)

        return props

    def ui_config(self, name: str) -> dict:
        config = {
            "type": "nodetree",
            "index_prop": f"{name}_index",
            "label": self.label,
        }
        if self.menu_id:
            config["menu_id"] = self.menu_id
        if self.show_quick_add is not None:
            config["show_quick_add"] = self.show_quick_add
        if self.allow_duplicates:
            config["allow_duplicates"] = self.allow_duplicates
        if self.allowed_types is not None:
            config["allowed_types"] = self.allowed_types
        if self.per_item_toggles:
            config["per_item_toggles"] = self.per_item_toggles
        return {name: config}

    def draw(
        self,
        layout,
        data,
        list_prop_name,
        index_prop_name=None,
        draw_item_settings=None,
        extra_operators=None,
    ):
        if index_prop_name is None:
            index_prop_name = f"{list_prop_name}_index"

        draw_nodetree(
            layout,
            data,
            list_prop_name,
            index_prop_name,
            label=self.label,
            draw_item_settings=draw_item_settings,
            menu_id=self.menu_id,
            show_quick_add=self.show_quick_add,
            allowed_types=self.allowed_types,
            allow_duplicates=self.allow_duplicates,
            extra_operators=extra_operators,
            per_item_toggles=self.per_item_toggles,
        )


def combine_nodetree_sync(*entries) -> tuple:
    specs = []
    for entry in entries:
        if entry is None:
            continue
        if isinstance(entry, NodeTreeDef):
            specs.extend(entry.sync_specs)
        elif isinstance(entry, (list, tuple)):
            specs.extend(entry)
        else:
            specs.append(entry)
    return tuple(specs)


def draw_nodetree_hierarchy(
    layout,
    data,
    list_prop_name: str,
    index_prop_name: str,
    label: str = "Items",
    draw_item_settings=None,
    menu_id: str = None,
    data_path: str = "",
):
    split = layout.split(factor=0.385)
    split.use_property_split = False

    label_col = split.column()
    label_col.alignment = "RIGHT"
    label_col.label(text=label)

    content_col = split.column()
    list_row = content_col.row()

    list_id = menu_id or list_prop_name
    _nodetree_data_paths[list_id] = data_path

    wm = bpy.context.window_manager
    wm.nexus_hierarchy_menu_id = list_id
    wm.nexus_hierarchy_data_path = data_path

    list_row.template_list(
        "NEXUS_UL_nodetree_hierarchy",
        list_id,
        data,
        list_prop_name,
        data,
        index_prop_name,
        rows=5,
    )

    col = list_row.column(align=True)

    op = col.operator("nexus.nodetree_show_add_menu", icon="ADD", text="")
    op.menu_id = list_id
    op.data_path = data_path

    registry_entry = _nodetree_registry.get(list_id, {})
    list_prop = registry_entry.get("list_prop", list_prop_name)
    index_prop = registry_entry.get("index_prop", index_prop_name)

    op = col.operator("nexus.nodetree_hierarchy_remove", icon="REMOVE", text="")
    op.list_prop = list_prop
    op.index_prop = index_prop
    op.menu_id = list_id
    op.data_path = data_path

    col.separator()

    op = col.operator("nexus.nodetree_hierarchy_move", icon="TRIA_UP", text="")
    op.list_prop = list_prop
    op.index_prop = index_prop
    op.menu_id = list_id
    op.data_path = data_path
    op.direction = "UP"

    op = col.operator("nexus.nodetree_hierarchy_move", icon="TRIA_DOWN", text="")
    op.list_prop = list_prop
    op.index_prop = index_prop
    op.menu_id = list_id
    op.data_path = data_path
    op.direction = "DOWN"

    col.separator()

    op = col.operator("nexus.nodetree_hierarchy_indent", icon="TRIA_RIGHT", text="")
    op.list_prop = list_prop
    op.index_prop = index_prop
    op.menu_id = list_id
    op.data_path = data_path

    op = col.operator("nexus.nodetree_hierarchy_outdent", icon="TRIA_LEFT", text="")
    op.list_prop = list_prop
    op.index_prop = index_prop
    op.menu_id = list_id
    op.data_path = data_path

    collection = getattr(data, list_prop_name)
    active_index = getattr(data, index_prop_name)
    if collection and 0 <= active_index < len(collection):
        item = collection[active_index]

        if draw_item_settings is not None:
            layout.separator(factor=0.5)
            settings_col = layout.column()
            settings_col.use_property_split = True
            draw_item_settings(settings_col, item)
