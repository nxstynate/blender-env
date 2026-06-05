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
from bpy.app.handlers import persistent

_tracked_nexus_modifiers: set[str] = set()
_tracked_all_objects: set[str] = set()
_tracked_object_count: int = 0
_ownership_audit_pending = True


def _tag_viewport_redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass


def _cleanup_orphaned_nexus_children():
    orphaned = []
    for obj in bpy.data.objects:
        if obj.get("nexus_object_type") is not None and obj.parent is None:
            orphaned.append(obj)

    for obj in orphaned:
        bpy.data.objects.remove(obj, do_unlink=True)


def _is_object_valid(obj):
    if obj is None:
        return False
    try:
        name = obj.name
        return bpy.data.objects.get(name) is not None
    except (ReferenceError, AttributeError):
        return False


def _cleanup_orphaned_nodetree_items():
    from ..ui.nodetree import get_child_cleanup_configs

    cleanup_configs = get_child_cleanup_configs()

    if not cleanup_configs:
        return

    for obj in bpy.data.objects:
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        props = obj.nexus_modifier

        for config in cleanup_configs:
            list_prop = config["list_prop"]
            index_prop = config["index_prop"]
            child_pointer_prop = config["child_pointer_prop"]

            if not hasattr(props, list_prop):
                continue

            collection = getattr(props, list_prop)

            if len(collection) == 0:
                continue

            indices_to_remove = []

            for idx, item in enumerate(collection):
                child_obj = getattr(item, child_pointer_prop, None)

                if not _is_object_valid(child_obj):
                    indices_to_remove.append(idx)

            for idx in reversed(indices_to_remove):
                collection.remove(idx)

            if indices_to_remove:
                current_index = getattr(props, index_prop, 0)
                if len(collection) > 0:
                    setattr(props, index_prop, min(current_index, len(collection) - 1))
                else:
                    setattr(props, index_prop, 0)


def _ensure_gradient_ownership_for_new_objects(new_modifier_names):
    from ..modifiers import get_modifier_class
    from ..utils.gradient import _get_gradient_id, ensure_gradient_ownership

    for name in new_modifier_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue

        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        gid = _get_gradient_id(obj)
        if gid is None:
            continue

        mod_cls = get_modifier_class(mod_type)
        if mod_cls is None:
            continue

        gradient_specs = mod_cls.get_gradient_specs()
        ensure_gradient_ownership(obj, gradient_specs or None)


def _ensure_curve_ownership_for_new_objects(new_modifier_names):
    from ..modifiers import get_modifier_class
    from ..utils.curve import _get_curve_id, ensure_curve_ownership

    for name in new_modifier_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue

        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        cid = _get_curve_id(obj)
        if cid is None:
            continue

        mod_cls = get_modifier_class(mod_type)
        if mod_cls is None:
            continue

        curve_specs = mod_cls.get_curve_specs()
        ensure_curve_ownership(obj, curve_specs or None)


def _run_ownership_audit_for_modifiers(modifier_names):
    from ..modifiers import get_modifier_class
    from ..utils.curve import ensure_curve_ownership
    from ..utils.gradient import ensure_gradient_ownership

    for name in modifier_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue

        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        mod_cls = get_modifier_class(mod_type)
        if mod_cls is None:
            continue

        ensure_gradient_ownership(obj, mod_cls.get_gradient_specs() or None)
        ensure_curve_ownership(obj, mod_cls.get_curve_specs() or None)


@persistent
def _on_depsgraph_update(_scene, _depsgraph):
    del _scene, _depsgraph

    from ..libs import theron

    if theron.is_shutting_down():
        return

    global \
        _ownership_audit_pending, \
        _tracked_nexus_modifiers, \
        _tracked_all_objects, \
        _tracked_object_count

    current_count = len(bpy.data.objects)

    # Most ticks don't add or remove objects — skip the O(N) scan.
    if current_count == _tracked_object_count and not _ownership_audit_pending:
        return

    current_all_objects = {obj.name for obj in bpy.data.objects}

    current_modifiers = {
        name
        for name in current_all_objects
        if bpy.data.objects[name].get("nexus_modifier_type") is not None
    }

    deleted_modifiers = _tracked_nexus_modifiers - current_modifiers

    if deleted_modifiers:
        _cleanup_orphaned_nexus_children()
        _tag_viewport_redraw()

        from ..utils.gradient import cleanup_orphaned_gradient_nodes

        cleanup_orphaned_gradient_nodes()

        from ..utils.curve import cleanup_orphaned_curve_nodes

        cleanup_orphaned_curve_nodes()

    if _ownership_audit_pending:
        if current_modifiers:
            _run_ownership_audit_for_modifiers(current_modifiers)
        _ownership_audit_pending = False
    else:
        new_modifiers = current_modifiers - _tracked_nexus_modifiers
        if new_modifiers:
            _ensure_gradient_ownership_for_new_objects(new_modifiers)
            _ensure_curve_ownership_for_new_objects(new_modifiers)

    deleted_objects = _tracked_all_objects - current_all_objects
    if deleted_objects:
        _cleanup_orphaned_nodetree_items()

    _tracked_nexus_modifiers = current_modifiers
    _tracked_all_objects = current_all_objects
    _tracked_object_count = current_count


@persistent
def _on_file_load(_dummy):
    del _dummy
    global \
        _ownership_audit_pending, \
        _tracked_nexus_modifiers, \
        _tracked_all_objects, \
        _tracked_object_count
    _tracked_nexus_modifiers = set()
    _tracked_all_objects = set()
    _tracked_object_count = 0
    _ownership_audit_pending = True

    from ..utils.gradient import clear_all_luts

    clear_all_luts()


# Mark handlers for identification during cleanup
_on_depsgraph_update._nexus_handler = True
_on_file_load._nexus_handler = True


def register():
    global _ownership_audit_pending
    _ownership_audit_pending = True
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    if _on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_file_load)


def unregister():
    global \
        _ownership_audit_pending, \
        _tracked_nexus_modifiers, \
        _tracked_all_objects, \
        _tracked_object_count
    _tracked_nexus_modifiers = set()
    _tracked_all_objects = set()
    _tracked_object_count = 0
    _ownership_audit_pending = True

    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    if _on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_file_load)
