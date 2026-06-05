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

from typing import Dict, List, Set

import bpy

from .utils import (
    find_item_by_key,
    get_insertion_point,
    get_item_key,
    get_scene_nexus_modifiers,
    is_valid_modifier,
    set_item_parent,
)

_last_modifier_count: Dict[int, int] = {}
_tracked_modifiers: Dict[int, Set[str]] = {}


def sync_modifier_list(scene: bpy.types.Scene) -> None:
    """Full sync of pipeline list with scene state.
    Adds missing modifiers, removes deleted ones, preserves order for existing.

    Args:
        scene: The Blender scene to sync.
    """
    if not hasattr(scene, "nexus_pipeline"):
        return

    pipeline = scene.nexus_pipeline
    current_modifiers = get_scene_nexus_modifiers(scene)
    current_modifier_set = set(current_modifiers)

    existing_in_list: Dict[bpy.types.Object, int] = {}
    indices_to_remove: List[int] = []

    for i, item in enumerate(pipeline.modifier_order):
        if item.is_folder:
            continue
        if not is_valid_modifier(item.modifier):
            indices_to_remove.append(i)
        elif item.modifier not in current_modifier_set:
            indices_to_remove.append(i)
        else:
            existing_in_list[item.modifier] = i

    for i in reversed(indices_to_remove):
        pipeline.modifier_order.remove(i)

    modifiers_in_list = set(existing_in_list.keys())
    new_modifiers = [obj for obj in current_modifiers if obj not in modifiers_in_list]

    insert_index, parent_item = get_insertion_point(pipeline)
    parent_key = get_item_key(parent_item) if parent_item is not None else None

    for obj in new_modifiers:
        item = pipeline.modifier_order.add()
        item.modifier = obj

        if parent_key is not None:
            parent_ref = find_item_by_key(pipeline, parent_key)
            if parent_ref is not None:
                set_item_parent(item, parent_ref)

        if insert_index is not None:
            pipeline.modifier_order.move(len(pipeline.modifier_order) - 1, insert_index)
            insert_index += 1

    if new_modifiers:
        if insert_index is not None:
            pipeline.modifier_order_index = insert_index - 1
        else:
            pipeline.modifier_order_index = len(pipeline.modifier_order) - 1
    elif pipeline.modifier_order_index >= len(pipeline.modifier_order):
        pipeline.modifier_order_index = max(0, len(pipeline.modifier_order) - 1)


def get_ordered_modifiers(scene: bpy.types.Scene) -> List[bpy.types.Object]:
    """Get modifiers in pipeline order.

    Args:
        scene: The Blender scene.

    Returns:
        List of modifier objects in pipeline order.
    """
    if not hasattr(scene, "nexus_pipeline"):
        return get_scene_nexus_modifiers(scene)

    pipeline = scene.nexus_pipeline

    ordered = []
    for item in pipeline.modifier_order:
        if is_valid_modifier(item.modifier):
            ordered.append(item.modifier)

    return ordered


def _modifier_uids(objects) -> Set[str]:
    """Return the set of UIDs for ``objects``, lazily assigning one to any
    legacy modifier that doesn't have one yet.

    Called from depsgraph_update_post (write-safe), which is the first
    handler legacy objects pass through after a file load — so this is also
    the earliest legal site for the migration.
    """
    from .identity import ensure_object_uid

    return {ensure_object_uid(obj) for obj in objects}


@bpy.app.handlers.persistent
def _on_depsgraph_update(scene, depsgraph):
    """Handler to detect modifier changes and sync directly.

    Only performs sync when the modifier set changes (add/remove detected).
    Identity is tracked by UID so renames are not mistaken for add+remove.
    Follows the pattern from handlers/cleanup.py for safe ID data writes.
    """
    del depsgraph

    key = scene.session_uid
    current_modifiers = get_scene_nexus_modifiers(scene)
    current_count = len(current_modifiers)
    current_uids = _modifier_uids(current_modifiers)

    previous_count = _last_modifier_count.get(key, -1)
    previous_uids = _tracked_modifiers.get(key, set())

    added = current_uids - previous_uids
    removed = previous_uids - current_uids

    if added or removed or previous_count == -1 or previous_count != current_count:
        sync_modifier_list(scene)

    _last_modifier_count[key] = current_count
    _tracked_modifiers[key] = current_uids


@bpy.app.handlers.persistent
def _on_load_post(dummy):
    """Sync all scenes after file load."""
    del dummy

    _last_modifier_count.clear()
    _tracked_modifiers.clear()

    _ensure_gradient_nodes_for_loaded_objects()

    for scene in bpy.data.scenes:
        sync_modifier_list(scene)
        modifiers = get_scene_nexus_modifiers(scene)
        _last_modifier_count[scene.session_uid] = len(modifiers)
        _tracked_modifiers[scene.session_uid] = _modifier_uids(modifiers)


def _ensure_gradient_nodes_for_loaded_objects() -> None:
    """Create gradients for modifier classes have new gradients added since a .blend
    file was saved. Gradients that already exist are left untouched,
    so existing customisations are preserved.
    """
    from ..modifiers import MODIFIER_REGISTRY
    from ..utils.gradient import ensure_gradient_nodes

    for obj in bpy.data.objects:
        obj_type = obj.get("nexus_modifier_type")
        if not obj_type:
            continue
        cls = MODIFIER_REGISTRY.get(obj_type)
        if cls is None:
            continue
        specs = cls.get_gradient_specs()
        if specs:
            ensure_gradient_nodes(obj, specs)


def _clear_state() -> None:
    """Clear all module-level state."""
    _last_modifier_count.clear()
    _tracked_modifiers.clear()


# Mark handlers for identification during cleanup
_on_depsgraph_update._nexus_handler = True
_on_load_post._nexus_handler = True


def register():
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    _clear_state()
