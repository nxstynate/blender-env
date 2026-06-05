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

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import bpy


def get_scene_nexus_modifiers(scene: bpy.types.Scene) -> List[bpy.types.Object]:
    """Get all NeXus modifier objects in a scene.

    Args:
        scene: The Blender scene to search.

    Returns:
        List of objects that have nexus_modifier_type set.
    """
    return [obj for obj in scene.objects if obj.get("nexus_modifier_type") is not None]


def get_modifier_icon(mod_type: str, obj: Optional[bpy.types.Object] = None) -> int:
    """Get icon ID for a modifier type.

    Args:
        mod_type: The modifier type string (e.g., 'NX_GRAVITY').
        obj: Optional object for per-instance icon lookup.

    Returns:
        Icon ID for the modifier, or 0 if not found.
    """
    from ..modifiers import MODIFIER_REGISTRY

    if mod_type in MODIFIER_REGISTRY:
        if obj is not None:
            return MODIFIER_REGISTRY[mod_type].get_instance_icon_id(obj)
        return MODIFIER_REGISTRY[mod_type].get_icon_id()
    return 0


def is_valid_modifier(obj: Optional[bpy.types.Object]) -> bool:
    """Check if an object reference is a valid NeXus modifier.

    Handles None references and deleted objects gracefully.

    Args:
        obj: Object reference to check (may be None or invalid).

    Returns:
        True if the object exists and is a NeXus modifier.
    """
    if obj is None:
        return False
    try:
        return obj.name in bpy.data.objects and obj.get("nexus_modifier_type") is not None
    except ReferenceError:
        return False


def get_modifier_label(obj: bpy.types.Object) -> str:
    """Get the display label for a modifier object.

    Args:
        obj: The modifier object.

    Returns:
        Human-readable label (e.g., "Gravity Modifier").
    """
    from ..modifiers import MODIFIER_REGISTRY

    mod_type = obj.get("nexus_modifier_type")
    if mod_type and mod_type in MODIFIER_REGISTRY:
        return MODIFIER_REGISTRY[mod_type].object_label
    return "Unknown Modifier"


# ---------------------------------------------------------------------------
# Dual-mode identity helpers (folders + modifiers)
# ---------------------------------------------------------------------------


def _obj_key(obj) -> Optional[str]:
    """Return a stable identity key for a Blender object, or None.

    Prefers the persistent UID (rename-stable). Falls back to obj.name when
    the UID hasn't been assigned yet — this preserves identity for legacy
    saved files until the next write-safe sync assigns a UID.
    """
    if obj is None:
        return None
    try:
        from .identity import get_object_uid

        uid = get_object_uid(obj)
        if uid:
            return uid
        return obj.name
    except ReferenceError:
        return None


def get_item_key(item) -> Optional[str]:
    """Return a stable identity key for any pipeline item."""
    if item.is_folder:
        return f"__folder__{item.folder_id}" if item.folder_id else None
    return _obj_key(item.modifier)


def get_item_parent_key(item) -> Optional[str]:
    """Return the parent's identity key."""
    if item.parent_folder_id:
        return f"__folder__{item.parent_folder_id}"
    return _obj_key(item.parent_modifier)


def is_item_valid(item) -> bool:
    """Check whether a pipeline item is valid (folder or modifier)."""
    if item.is_folder:
        return bool(item.folder_id)
    return is_valid_modifier(item.modifier)


def is_item_enabled(item) -> bool:
    """Check whether a pipeline item is enabled."""
    if item.is_folder:
        return item.folder_enabled
    if item.modifier is not None:
        try:
            return item.modifier.nexus_modifier.enabled
        except (AttributeError, ReferenceError):
            return False
    return False


def find_item_by_key(pipeline, key) -> Optional[object]:
    """Find a pipeline item by its identity key.

    Tries the current key first (UID for objects, ``__folder__{id}`` for
    folders). Falls back to matching against ``obj.name`` so legacy stored
    keys (e.g. JSON-encoded names in ``cascade_disabled_keys``) still resolve
    until the next save replaces them.
    """
    if key is None:
        return None
    for item in pipeline.modifier_order:
        if get_item_key(item) == key:
            return item
    if key.startswith("__folder__"):
        return None
    for item in pipeline.modifier_order:
        if item.is_folder:
            continue
        obj = item.modifier
        if obj is None:
            continue
        try:
            if obj.name == key:
                return item
        except ReferenceError:
            continue
    return None


def find_item_for_folder(pipeline, folder_id: str) -> Optional[int]:
    """Return the collection index of the pipeline item matching a folder_id."""
    for i, item in enumerate(pipeline.modifier_order):
        if item.is_folder and item.folder_id == folder_id:
            return i
    return None


# ---------------------------------------------------------------------------
# Hierarchy utilities
# ---------------------------------------------------------------------------


def get_children(pipeline, item) -> list:
    key = get_item_key(item)
    if key is None:
        return []
    result = []
    for other in pipeline.modifier_order:
        if get_item_parent_key(other) == key:
            result.append(other)
    return result


def get_all_descendants(pipeline, item) -> list:
    descendants = []
    stack = get_children(pipeline, item)
    while stack:
        child = stack.pop(0)
        descendants.append(child)
        stack.extend(get_children(pipeline, child))
    return descendants


def get_depth(pipeline, item) -> int:
    depth = 0
    current = item
    visited = set()
    while True:
        parent_key = get_item_parent_key(current)
        if parent_key is None:
            break
        if parent_key in visited:
            break
        visited.add(parent_key)
        depth += 1
        parent = find_item_by_key(pipeline, parent_key)
        if parent is None:
            break
        current = parent
    return depth


def is_ancestor_disabled(pipeline, item) -> bool:
    current = item
    visited = set()
    while True:
        parent_key = get_item_parent_key(current)
        if parent_key is None:
            break
        if parent_key in visited:
            break
        visited.add(parent_key)
        parent = find_item_by_key(pipeline, parent_key)
        if parent is None:
            break
        if not is_item_enabled(parent):
            return True
        current = parent
    return False


def is_ancestor_collapsed(pipeline, item) -> bool:
    current = item
    visited = set()
    while True:
        parent_key = get_item_parent_key(current)
        if parent_key is None:
            break
        if parent_key in visited:
            break
        visited.add(parent_key)
        parent = find_item_by_key(pipeline, parent_key)
        if parent is None:
            break
        if parent.collapsed:
            return True
        current = parent
    return False


def has_children(pipeline, item) -> bool:
    key = get_item_key(item)
    if key is None:
        return False
    for other in pipeline.modifier_order:
        if get_item_parent_key(other) == key:
            return True
    return False


# ---------------------------------------------------------------------------
# Hierarchy cache (precomputed lookups for the sidebar hot path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HierarchyCache:
    """Per-row-index flags so duplicate UIDs (transient post-Shift+D) keep separate slots."""

    item_count: int
    depth: Tuple[int, ...] = ()
    has_children: Tuple[bool, ...] = ()
    ancestor_disabled: Tuple[bool, ...] = ()
    ancestor_collapsed: Tuple[bool, ...] = ()


_EMPTY_CACHE = HierarchyCache(item_count=0)


def build_hierarchy_cache(pipeline) -> HierarchyCache:
    """Build cache in one O(N) pass; duplicate keys anchor to first occurrence."""
    items = list(pipeline.modifier_order)
    count = len(items)
    if count == 0:
        return _EMPTY_CACHE

    raw_keys: List[Optional[str]] = [get_item_key(item) for item in items]
    parent_raw_keys: List[Optional[str]] = [get_item_parent_key(item) for item in items]

    raw_to_first_index: Dict[str, int] = {}
    for i, raw in enumerate(raw_keys):
        if raw is not None and raw not in raw_to_first_index:
            raw_to_first_index[raw] = i

    parent_index: List[int] = [-1] * count
    for i, parent_raw in enumerate(parent_raw_keys):
        if parent_raw is None:
            continue
        anchor = raw_to_first_index.get(parent_raw)
        if anchor is not None:
            parent_index[i] = anchor

    referenced_parent_keys = {p for p in parent_raw_keys if p is not None}
    has_children: List[bool] = [
        raw is not None and raw in referenced_parent_keys for raw in raw_keys
    ]

    depth: List[int] = [0] * count
    ancestor_disabled: List[bool] = [False] * count
    ancestor_collapsed: List[bool] = [False] * count
    resolved: List[bool] = [False] * count

    def resolve(start: int) -> None:
        if resolved[start]:
            return
        chain: List[int] = []
        seen: set = set()
        cur = start
        while 0 <= cur < count and not resolved[cur] and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            cur = parent_index[cur]

        # Walk outermost-first so parents resolve before children; cycle tops fall to defaults.
        for offset, ci in enumerate(reversed(chain)):
            pi = parent_index[ci]
            is_top = offset == 0
            if pi < 0 or (is_top and not resolved[pi]):
                depth[ci] = 0
                ancestor_disabled[ci] = False
                ancestor_collapsed[ci] = False
            else:
                parent_item = items[pi]
                parent_disabled = not is_item_enabled(parent_item)
                depth[ci] = depth[pi] + 1
                ancestor_disabled[ci] = ancestor_disabled[pi] or parent_disabled
                ancestor_collapsed[ci] = ancestor_collapsed[pi] or bool(parent_item.collapsed)
            resolved[ci] = True

    for i in range(count):
        resolve(i)

    return HierarchyCache(
        item_count=count,
        depth=tuple(depth),
        has_children=tuple(has_children),
        ancestor_disabled=tuple(ancestor_disabled),
        ancestor_collapsed=tuple(ancestor_collapsed),
    )


def build_visible_tree(pipeline) -> List[Tuple]:
    """Build ordered list of (item, flat_index, depth, has_children) for visible items.

    Preserves collection order among siblings. Skips descendants of collapsed items.
    flat_index is the item's index in the underlying CollectionProperty.
    """
    item_to_index = {}
    children_map: dict = {}
    for i, item in enumerate(pipeline.modifier_order):
        key = get_item_key(item)
        if key is None:
            key = f"__invalid_{i}"
        item_to_index[key] = i
        parent_key = get_item_parent_key(item)
        children_map.setdefault(parent_key, []).append((item, key))

    result = []

    def _walk(item, item_key, depth):
        idx = item_to_index[item_key]
        item_has_children = item_key in children_map
        result.append((item, idx, depth, item_has_children))
        if item.collapsed:
            return
        for child, child_key in children_map.get(item_key, []):
            _walk(child, child_key, depth + 1)

    for root, root_key in children_map.get(None, []):
        _walk(root, root_key, 0)

    return result


def find_item_for_object(pipeline, obj) -> Optional[int]:
    """Return the collection index of the pipeline item whose modifier matches obj."""
    for i, item in enumerate(pipeline.modifier_order):
        if item.modifier == obj:
            return i
    return None


def would_create_cycle(pipeline, item, proposed_parent_key: str) -> bool:
    """Return True if setting item's parent to proposed_parent_key would create a cycle."""
    item_key = get_item_key(item)
    if item_key is None or proposed_parent_key is None:
        return False
    if proposed_parent_key == item_key:
        return True
    current_key = proposed_parent_key
    visited = set()
    while current_key is not None:
        if current_key in visited:
            break
        visited.add(current_key)
        if current_key == item_key:
            return True
        parent = find_item_by_key(pipeline, current_key)
        if parent is None:
            break
        current_key = get_item_parent_key(parent)
    return False


def get_insertion_point(pipeline):
    """Return (insert_index, parent_item) for inserting after the selected item's subtree.

    The new item will be a sibling of the selected item (same parent).
    Returns (None, None) if the list is empty or index is out of range.
    """
    count = len(pipeline.modifier_order)
    idx = pipeline.modifier_order_index
    if count == 0 or not (0 <= idx < count):
        return (None, None)

    selected = pipeline.modifier_order[idx]
    selected_key = get_item_key(selected)

    descendants = get_all_descendants(pipeline, selected)
    subtree_keys = {selected_key}
    for desc in descendants:
        key = get_item_key(desc)
        if key is not None:
            subtree_keys.add(key)

    last_index = idx
    for i, item in enumerate(pipeline.modifier_order):
        if get_item_key(item) in subtree_keys:
            last_index = max(last_index, i)

    insert_index = last_index + 1

    parent_key = get_item_parent_key(selected)
    parent_item = find_item_by_key(pipeline, parent_key) if parent_key else None

    return (insert_index, parent_item)


def set_item_parent(item, parent_item):
    """Set the parent of item to parent_item, clearing the other reference.

    If parent_item is None, clears both parent references (makes item a root).
    """
    if parent_item is None:
        item.parent_modifier = None
        item.parent_folder_id = ""
    elif parent_item.is_folder:
        item.parent_folder_id = parent_item.folder_id
        item.parent_modifier = None
    else:
        item.parent_modifier = parent_item.modifier
        item.parent_folder_id = ""


# ---------------------------------------------------------------------------
# Hierarchy enable/disable memory
# ---------------------------------------------------------------------------


def store_enabled_children(pipeline, parent_item):
    """Record which direct children are currently enabled before a cascade disable."""
    if parent_item.cascade_disabled_keys:
        return
    enabled_keys = []
    for child in get_children(pipeline, parent_item):
        if is_item_enabled(child):
            key = get_item_key(child)
            if key is not None:
                enabled_keys.append(key)
    parent_item.cascade_disabled_keys = json.dumps(enabled_keys)


def restore_enabled_children(pipeline, parent_item):
    """Re-enable direct children that were force-disabled by this parent's cascade."""
    raw = parent_item.cascade_disabled_keys
    if not raw:
        return

    try:
        keys_to_restore = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parent_item.cascade_disabled_keys = ""
        return

    parent_key = get_item_key(parent_item)
    for key in keys_to_restore:
        item = find_item_by_key(pipeline, key)
        if item is None:
            continue
        # Skip items that were reparented (indent/outdent) while disabled.
        if get_item_parent_key(item) != parent_key:
            continue
        if item.is_folder:
            item.folder_enabled = True
        elif item.modifier is not None:
            try:
                item.modifier.nexus_modifier.enabled = True
            except (AttributeError, ReferenceError):
                pass

    parent_item.cascade_disabled_keys = ""


def is_modifier_effectively_disabled(pipeline_data, obj) -> bool:
    """Check if a mod is disabled either directly or by parent."""
    try:
        if not obj.nexus_modifier.enabled:
            return True
    except (AttributeError, ReferenceError):
        return False

    for item in pipeline_data.modifier_order:
        if item.is_folder:
            continue
        if item.modifier == obj:
            return is_ancestor_disabled(pipeline_data, item)

    return False


def cascade_disable_children(pipeline, parent_item):
    """Store enabled state then cascade-disable all direct children."""
    store_enabled_children(pipeline, parent_item)
    for child in get_children(pipeline, parent_item):
        if child.is_folder:
            child.folder_enabled = False
        elif child.modifier is not None:
            try:
                child.modifier.nexus_modifier.enabled = False
            except (AttributeError, ReferenceError):
                pass
