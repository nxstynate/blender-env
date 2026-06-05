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

from dataclasses import dataclass
from typing import Any, Callable

import bpy

_nodetree_registry: dict[str, dict] = {}
_nodetree_data_paths: dict[str, str] = {}
_nodetree_tree_types: dict[str, str] = {}
_nodetree_per_item_toggles: dict[str, tuple] = {}


@dataclass(frozen=True)
class PerItemToggle:
    bit: int
    icons: tuple
    tooltip_a: str = ""
    tooltip_b: str = ""
    show_condition: Callable[[Any], bool] | None = None


_VALID_BLENDER_OBJECT_TYPES: frozenset[str] | None = None
_pending_nx_type_validation: set[str] = set()
_pending_ghost_slots: dict[str, Any] = {}
_pending_ghost_slots_locked: bool = False


def register_ghost_slot(name: str, prop: Any) -> None:
    """Queue a property for merge into NexusObjectProperties at registration."""
    if _pending_ghost_slots_locked:
        raise RuntimeError(
            f"register_ghost_slot({name!r}): queue already drained; "
            "import the owning modifier spec at module load."
        )
    _pending_ghost_slots[name] = prop


def get_pending_ghost_slots() -> dict[str, Any]:
    global _pending_ghost_slots_locked
    _pending_ghost_slots_locked = True
    return _pending_ghost_slots


def _get_valid_blender_object_types() -> frozenset[str]:
    global _VALID_BLENDER_OBJECT_TYPES
    if _VALID_BLENDER_OBJECT_TYPES is None:
        _VALID_BLENDER_OBJECT_TYPES = frozenset(
            item.identifier for item in bpy.types.Object.bl_rna.properties["type"].enum_items
        )
    return _VALID_BLENDER_OBJECT_TYPES


def _format_allowed_types_label(allowed_types: list[str]) -> str:
    parts = []
    for t in allowed_types:
        if t == "NX_*":
            parts.append("any NeXus modifier")
        elif t.startswith("NX_"):
            chunks = t[3:].split("_")
            parts.append("nx" + "".join(c.capitalize() for c in chunks))
        else:
            parts.append(t.replace("_", " ").title())
    return ", ".join(parts)


def _parse_allowed_types(allowed_types: list[str]) -> tuple[frozenset[str], frozenset[str], bool]:
    if not allowed_types:
        raise ValueError("allowed_types must not be empty")

    valid_blender_types = _get_valid_blender_object_types()

    blender_types = set()
    nx_types = set()
    any_nx = False

    for t in allowed_types:
        if not isinstance(t, str):
            raise ValueError(f"allowed_types entries must be strings, got {type(t).__name__}")
        normalized = t.upper()
        if normalized != t:
            raise ValueError(
                f"allowed_types entries must be UPPERCASE, got {t!r} (use {normalized!r} instead)"
            )
        if t == "NX_*":
            any_nx = True
        elif t.startswith("NX_"):
            nx_types.add(t)
        else:
            blender_types.add(t)

    invalid_blender = blender_types - valid_blender_types
    if invalid_blender:
        raise ValueError(
            f"Unknown Blender object type(s): {sorted(invalid_blender)}. "
            f"Valid types: {sorted(valid_blender_types)}"
        )

    if nx_types:
        _pending_nx_type_validation.update(nx_types)

    return frozenset(blender_types), frozenset(nx_types), any_nx


def _passes_type_filter(
    obj, frozen_blender: frozenset, frozen_nx: frozenset, any_nx: bool
) -> bool:
    if obj.type in frozen_blender:
        return True
    nx_type = obj.get("nexus_modifier_type")
    if any_nx and nx_type is not None:
        return True
    return bool(frozen_nx) and nx_type in frozen_nx


def make_allowed_types_poll(allowed_types: list[str]):
    frozen_blender, frozen_nx, any_nx = _parse_allowed_types(allowed_types)

    def _poll(self, obj):
        return _passes_type_filter(obj, frozen_blender, frozen_nx, any_nx)

    return _poll


def validate_pending_nx_types():
    if not _pending_nx_type_validation:
        return

    from ...modifiers import MODIFIER_REGISTRY

    valid = set(MODIFIER_REGISTRY.keys())
    unknown = sorted(t for t in _pending_nx_type_validation if t not in valid)
    if unknown:
        raise ValueError(
            f"Unknown NeXus modifier types in allowed_types: {unknown}. "
            f"Valid types: {sorted(valid)}"
        )
    _pending_nx_type_validation.clear()


def _resolve_data(obj, data_path: str):
    if not data_path:
        return obj.nexus_modifier
    try:
        return obj.path_resolve(data_path)
    except ValueError:
        return None


def _append_object_item(target_collection, obj):
    item = target_collection.add()
    item.obj = obj
    if hasattr(item, "enabled"):
        item.enabled = True
    return item


def make_drop_target_update(
    list_prop_name: str,
    index_prop_name: str,
    drop_prop_name: str,
    *,
    allow_duplicates: bool = False,
    allowed_types: list[str] | None = None,
):
    """Update callback for an Object- or Collection-typed drop slot.

    Object is appended directly. Collection is expanded via `all_objects`;
    each member is filtered through `allowed_types` before being added.
    """
    if allowed_types:
        frozen_blender, frozen_nx, any_nx = _parse_allowed_types(allowed_types)
        filter_active = True
    else:
        frozen_blender = frozenset()
        frozen_nx = frozenset()
        any_nx = False
        filter_active = False

    def _update(self, _context):
        picked = getattr(self, drop_prop_name, None)
        if picked is None:
            return

        target = getattr(self, list_prop_name, None)
        if target is None:
            self[drop_prop_name] = None
            return

        owner = self.id_data if hasattr(self, "id_data") else None

        if isinstance(picked, bpy.types.Collection):
            existing = {getattr(item, "obj", None) for item in target}
            added = 0
            for candidate in picked.all_objects:
                if candidate is None:
                    continue
                if owner is not None and candidate == owner:
                    continue
                if filter_active and not _passes_type_filter(
                    candidate, frozen_blender, frozen_nx, any_nx
                ):
                    continue
                if not allow_duplicates and candidate in existing:
                    continue
                _append_object_item(target, candidate)
                existing.add(candidate)
                added += 1
            if added > 0:
                try:
                    setattr(self, index_prop_name, len(target) - 1)
                except (TypeError, AttributeError):
                    pass
                if owner is not None:
                    owner.update_tag()
            self[drop_prop_name] = None
            return

        if not isinstance(picked, bpy.types.Object):
            self[drop_prop_name] = None
            return

        if owner is not None and picked == owner:
            self[drop_prop_name] = None
            return

        if filter_active and not _passes_type_filter(picked, frozen_blender, frozen_nx, any_nx):
            self[drop_prop_name] = None
            return

        if not allow_duplicates:
            for item in target:
                if getattr(item, "obj", None) == picked:
                    self[drop_prop_name] = None
                    return

        _append_object_item(target, picked)

        try:
            setattr(self, index_prop_name, len(target) - 1)
        except (TypeError, AttributeError):
            pass

        if owner is not None:
            owner.update_tag()

        self[drop_prop_name] = None

    return _update


def register_nodetree(
    menu_id: str,
    type_items: list,
    list_prop: str,
    index_prop: str,
    on_add=None,
    on_remove=None,
    child_pointer_prop: str = None,
    separator_after=None,
    hierarchy: bool = False,
    container_types=None,
    on_hierarchy_remove=None,
    on_hierarchy_move=None,
    folder_type: str = None,
    folder_color_prop: str = None,
    folder_icon_cache=None,
):
    _nodetree_registry[menu_id] = {
        "type_items": type_items,
        "list_prop": list_prop,
        "index_prop": index_prop,
        "on_add": on_add,
        "on_remove": on_remove,
        "child_pointer_prop": child_pointer_prop,
        "separator_after": separator_after or set(),
        "hierarchy": hierarchy,
        "container_types": container_types or set(),
        "on_hierarchy_remove": on_hierarchy_remove,
        "on_hierarchy_move": on_hierarchy_move,
        "folder_type": folder_type,
        "folder_color_prop": folder_color_prop,
        "folder_icon_cache": folder_icon_cache,
    }


def get_nodetree_config(menu_id: str):
    return _nodetree_registry.get(menu_id, {})


def get_child_cleanup_configs():
    configs = []
    for menu_data in _nodetree_registry.values():
        child_prop = menu_data.get("child_pointer_prop")
        if child_prop:
            configs.append(
                {
                    "list_prop": menu_data["list_prop"],
                    "index_prop": menu_data["index_prop"],
                    "child_pointer_prop": child_prop,
                }
            )
    return configs


def _lookup_type_info(type_identifier: str, menu_id: str = ""):
    if menu_id and menu_id in _nodetree_registry:
        for item in _nodetree_registry[menu_id].get("type_items", []):
            if len(item) >= 4 and item[0] == type_identifier:
                return (item[1], item[3])
        return None
    for menu_data in _nodetree_registry.values():
        for item in menu_data.get("type_items", []):
            if len(item) >= 4 and item[0] == type_identifier:
                return (item[1], item[3])
    return None


def _collection_has_prop(data, list_prop_name, prop_name):
    try:
        fixed_type = data.__class__.bl_rna.properties[list_prop_name].fixed_type
        return prop_name in fixed_type.properties
    except (KeyError, AttributeError):
        return False


def _get_enable_icons(tree_type: str) -> tuple[str, str]:
    if tree_type == "inexclude":
        return ("nx_include", "nx_disclude")
    return ("nx_enable", "nx_disable")
