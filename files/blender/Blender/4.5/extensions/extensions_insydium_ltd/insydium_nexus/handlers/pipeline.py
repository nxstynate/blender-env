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

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from time import perf_counter

import bpy
from bpy.app.handlers import persistent

from ..libs import theron
from ..libs.theron_sync import sync_properties


@dataclass
class _SceneState:
    pipeline: int = 0

    # Maps a NeXus object UID to the Theron object handle that backs it.
    nexus_obj_handles: dict[str, int] = field(default_factory=dict)

    # Maps a NeXus object UID to its "nexus_modifier_type" value.
    nexus_obj_types: dict[str, str] = field(default_factory=dict)

    # Maps a NeXus object UID to its theron modifier type (or absent for non-modifiers).
    nexus_obj_handle_mod_types: dict[str, int] = field(default_factory=dict)

    # Set of UIDs observed in the scene last sync. Drives deletion detection.
    tracked_objects: set[str] = field(default_factory=set)

    # UID -> session_uid of the Blender ID we bound the handle to. Lets
    # duplicate-collision recovery distinguish the original from a Shift+D
    # copy that inherited the UID via custom-property duplication.
    nexus_obj_session_uids: dict[str, int] = field(default_factory=dict)

    last_frame: int | None = None
    executed_for_frame: int | None = None
    timing_signature: tuple[int, int, int, float, int] | None = None
    copy_mode: str = "GPU_ONLY"
    force_gpu_cpu_next: bool = False
    last_modifier_order: list[int] = field(default_factory=list)
    emitter_visibility: dict[str, bool] = field(default_factory=dict)

    # Emitter UID -> set of group UIDs the emitter is currently joined to.
    emitter_group_memberships: dict[str, set[str]] = field(default_factory=dict)


_scenes: dict[int, _SceneState] = {}
_dirty_objects: set[str] = set()
_last_frame_time_ms: float = 0.0
_playback_frame_start_perf: float | None = None
_prev_frame_change_perf: float | None = None
_last_wall_clock_ms: float = 0.0
_execution_tick: int = 0
_resync_in_progress: bool = False


def scene_key(scene: bpy.types.Scene) -> int:
    """Return a session-stable identity key for scene."""
    return scene.session_uid


def _blender_to_theron_frame(scene: bpy.types.Scene) -> int:
    """Convert Blender's current frame to a Theron simulation frame.
    Theron frame 0 is the reset frame (clears particles, no simulation).
    Theron frame 1 is the first simulation step.
    Blender's start frame maps to theron 0 so that the first
    frame_change_post (start + 1) naturally hits theron frame 1.
    """
    return max(0, scene.frame_current - scene.frame_start)


def _scene_timing_signature(scene: bpy.types.Scene) -> tuple[int, int, int, float, int]:
    render = scene.render
    fps_base = float(render.fps_base) if render.fps_base else 1.0
    substeps = 1
    if hasattr(scene, "nexus_pipeline"):
        substeps = int(scene.nexus_pipeline.global_opts.substeps)
    return (int(scene.frame_start), int(scene.frame_end), int(render.fps), fps_base, substeps)


def _configure_pipeline_timing(scene: bpy.types.Scene, state: _SceneState) -> bool:
    from ..libs.nexus_time import to_time_fraction, update_fps_cache

    signature = _scene_timing_signature(scene)
    fps = signature[2] / signature[3]
    theron.set_fps(state.pipeline, fps)
    theron.set_substeps(state.pipeline, signature[4])
    start_n, start_d = to_time_fraction(signature[0], fps=fps, mode="FRAMES")
    end_n, end_d = to_time_fraction(signature[1], fps=fps, mode="FRAMES")
    theron.set_min_max_time(state.pipeline, start_n, start_d, end_n, end_d)
    update_fps_cache(scene)

    changed = state.timing_signature != signature
    state.timing_signature = signature
    return changed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_theron_modifier_type(mod_type: str, obj: bpy.types.Object = None) -> int | None:
    """Derive theron modifier type from NX modifier type string.

    Delegates to the modifier class's ``get_theron_type()`` method, which
    allows each modifier to control its own C-side type mapping (e.g. fluids
    choosing between PBD and SPH based on the solver property).
    Returns None if no matching theron type exists (e.g. NX_EMITTER).
    """
    from ..modifiers import get_modifier_class

    mod_cls = get_modifier_class(mod_type)
    if mod_cls is None:
        return None

    type_name = mod_cls.get_theron_type(obj)
    if type_name is None:
        return None

    try:
        return theron.TrModifierType[type_name]
    except KeyError:
        return None


def _push_pipeline_settings(scene: bpy.types.Scene, state: _SceneState) -> None:
    from ..libs.nexus_time import to_time_fraction, update_fps_cache

    fps = scene.render.fps / scene.render.fps_base
    theron.set_fps(state.pipeline, fps)
    theron.set_substeps(state.pipeline, scene.nexus_pipeline.global_opts.substeps)
    start_n, start_d = to_time_fraction(scene.frame_start, fps=fps, mode="FRAMES")
    end_n, end_d = to_time_fraction(scene.frame_end, fps=fps, mode="FRAMES")
    theron.set_min_max_time(state.pipeline, start_n, start_d, end_n, end_d)
    update_fps_cache(scene)


def _get_or_create_state(scene: bpy.types.Scene) -> _SceneState | None:
    """Return the _SceneState for scene, creating a new C pipeline if needed."""
    key = scene_key(scene)
    state = _scenes.get(key)
    if state is not None:
        return state

    pipeline = theron.create_pipeline()
    if pipeline is None:
        return None

    state = _SceneState(pipeline=pipeline)
    _scenes[key] = state
    _push_pipeline_settings(scene, state)
    return state


def _resolve_copy_mode(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Set the pipeline copy mode based on the Accelerated Viewport pref + runtime lock."""
    from ..utils import use_accelerated_viewport
    from ..viewport.registry import is_locked_to_basic

    accelerated = use_accelerated_viewport() and not is_locked_to_basic()

    if state.force_gpu_cpu_next:
        state.force_gpu_cpu_next = False
        theron.set_particle_copy_mode(
            state.pipeline, theron.TrParticleCopyMode.TR_PARTICLE_COPY_MODE_GPU_CPU
        )
        state.copy_mode = "GPU_CPU"
    elif accelerated:
        theron.set_particle_copy_mode(
            state.pipeline, theron.TrParticleCopyMode.TR_PARTICLE_COPY_MODE_GPU_ONLY
        )
        state.copy_mode = "GPU_ONLY"
    else:
        theron.set_particle_copy_mode(
            state.pipeline, theron.TrParticleCopyMode.TR_PARTICLE_COPY_MODE_GPU_CPU
        )
        state.copy_mode = "GPU_CPU"


def _reorder_theron_modifiers(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Reorder Theron modifier execution order to match the pipeline sidebar."""
    if not hasattr(scene, "nexus_pipeline"):
        return

    pipeline_data = scene.nexus_pipeline
    if not pipeline_data.modifier_order:
        return

    from ..pipeline_manager.identity import get_object_uid

    ordered_handles: list[int] = []
    for item in pipeline_data.modifier_order:
        if item.is_folder:
            continue
        try:
            obj = item.modifier
            if obj is None:
                continue
        except ReferenceError:
            continue

        # Check this object is a modifier
        if _get_theron_modifier_type(obj.get("nexus_modifier_type"), obj) is None:
            continue

        uid = get_object_uid(obj)
        if uid is None:
            continue
        handle = state.nexus_obj_handles.get(uid)
        if handle is not None:
            ordered_handles.append(handle)

    if ordered_handles == state.last_modifier_order:
        return

    state.last_modifier_order = ordered_handles

    if len(ordered_handles) < 2:
        return

    theron.modifier_move(ordered_handles[0], None)
    for i in range(1, len(ordered_handles)):
        theron.modifier_move(ordered_handles[i], ordered_handles[i - 1])


def _execute_pipeline_frame(
    scene: bpy.types.Scene,
    state: _SceneState,
    theron_frame: int,
    depsgraph: bpy.types.Depsgraph | None = None,
    *,
    force_execute: bool = False,
) -> bool:
    """Sync, configure, and execute one frame. Returns True if execute_frame ran."""
    global _execution_tick

    sync_all_objects(scene, depsgraph)

    timing_changed = _configure_pipeline_timing(scene, state)

    _push_pipeline_settings(scene, state)
    _resolve_copy_mode(scene, state)

    if not force_execute and not timing_changed and state.executed_for_frame == theron_frame:
        _dirty_objects.clear()
        _tag_ui_redraw()
        return False

    # Ensure clean initial state for brand-new pipelines that have
    # never executed frame 0 (the reset/clear frame).
    if state.last_frame is None and theron_frame > 0:
        theron.execute_frame(state.pipeline, 0)

    theron.execute_frame(state.pipeline, theron_frame)
    state.executed_for_frame = theron_frame
    state.last_frame = theron_frame
    _execution_tick += 1

    _run_post_execute_hooks(scene, depsgraph)
    _dirty_objects.clear()
    return True


def get_or_create_pipeline(scene: bpy.types.Scene) -> int | None:
    state = _get_or_create_state(scene)
    if state is None:
        return None
    return state.pipeline


def ensure_pipeline_for_scene(scene: bpy.types.Scene) -> int | None:
    """Eagerly create the Theron pipeline + per-modifier handles for scene.
    Registers Theron handles only -- does NOT push properties/curves/gradients
    (full sync runs via the regular depsgraph/frame-change path). Does NOT
    execute any simulation frames. Idempotent."""
    if not theron.is_initialized():
        return None
    if theron.is_shutting_down():
        return None
    has_nx = any("nexus_modifier_type" in o for o in scene.objects)
    if not has_nx:
        return None
    state = _get_or_create_state(scene)
    if state is None:
        return None
    _register_handles_only(scene, state)
    return state.pipeline


def _register_handles_only(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Create a Theron handle for every NX object without syncing scalars/curves/gradients.
    Mirrors sync_object_to_theron's create-fn dispatch but stops after handle creation."""
    from ..modifiers import get_modifier_class
    from ..pipeline_manager.identity import resolve_uid_collisions

    objects = get_hierarchy_ordered_objects(scene)
    resolve_uid_collisions(objects, state.nexus_obj_session_uids)
    for obj in objects:
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        mod_cls = get_modifier_class(mod_type)
        if mod_cls is not None and mod_cls.handles_own_sync:
            continue

        if mod_type == "NX_EMITTER":
            create_fn = functools.partial(theron.create_emitter, state.pipeline)
            theron_type = None
        elif mod_type == "NX_CACHE":
            create_fn = functools.partial(theron.create_cache_instance, state.pipeline)
            theron_type = None
        elif mod_type == "NX_GROUP":
            create_fn = functools.partial(theron.create_particle_group, state.pipeline)
            theron_type = None
        elif mod_type == "NX_FALLOFF":
            create_fn = theron.create_falloff
            theron_type = None
        else:
            theron_type = _get_theron_modifier_type(mod_type, obj)
            if theron_type is None:
                continue
            create_fn = functools.partial(theron.add_modifier, state.pipeline, theron_type)

        _get_or_create_handle(state, obj, create_fn, theron_type, obj_type=mod_type)


def get_pipeline(scene: bpy.types.Scene) -> int | None:
    state = _scenes.get(scene_key(scene))
    return state.pipeline if state else None


def get_pipeline_for_scene_key(scene_key_value: int) -> int | None:
    state = _scenes.get(scene_key_value)
    return state.pipeline if state is not None else None


def get_modifier_handle(scene: bpy.types.Scene, obj: bpy.types.Object) -> int | None:
    """Return the Theron modifier handle for ``obj`` in this scene, or None."""
    state = _scenes.get(scene_key(scene))
    if state is None or obj is None:
        return None
    from ..pipeline_manager.identity import get_object_uid

    uid = get_object_uid(obj)
    if uid is None:
        return None
    return state.nexus_obj_handles.get(uid)


def find_object_for_handle(scene: bpy.types.Scene, handle: int) -> bpy.types.Object | None:
    """Return the Blender object whose Theron handle matches, or None."""
    state = _scenes.get(scene_key(scene))
    if state is None:
        return None

    from ..pipeline_manager.identity import get_object_uid

    uid = next((u for u, h in state.nexus_obj_handles.items() if h == handle), None)
    if uid is None:
        return None

    for obj in scene.objects:
        if get_object_uid(obj) == uid:
            return obj
    return None


def get_last_frame_time_ms() -> float:
    """Return the last measured per-frame time in milliseconds."""
    return _last_frame_time_ms


def set_last_frame_time_ms(ms: float) -> None:
    global _last_frame_time_ms
    _last_frame_time_ms = ms


def consume_playback_frame_start() -> float | None:
    """Pop the perf_counter timestamp set at the most recent _on_frame_change."""
    global _playback_frame_start_perf
    t = _playback_frame_start_perf
    _playback_frame_start_perf = None
    return t


def get_last_wall_clock_ms() -> float:
    """Wall-clock gap between the two most recent _on_frame_change events."""
    return _last_wall_clock_ms


def get_execution_tick() -> int:
    """Return a monotonic counter that increments on each execute_frame call."""
    return _execution_tick


def get_copy_mode(scene: bpy.types.Scene) -> str:
    """Return the last set copy mode: 'GPU_CPU' or 'GPU_ONLY'. Default 'GPU_ONLY' if unknown."""
    state = _scenes.get(scene_key(scene))
    return state.copy_mode if state else "GPU_ONLY"


def request_gpu_cpu_next_frame(scene: bpy.types.Scene) -> None:
    """Request that the pipeline use GPU_CPU on the next frame (for BASIC fallback)."""
    state = _scenes.get(scene_key(scene))
    if state is not None:
        state.force_gpu_cpu_next = True


def tag_ui_redraw() -> None:
    """Request a redraw of the 3D view and properties."""
    _tag_ui_redraw()


def get_nexus_obj_handle(scene: bpy.types.Scene, obj: bpy.types.Object) -> int | None:
    """Return the Theron object handle for ``obj`` in this scene, or None."""
    state = _scenes.get(scene_key(scene))
    if state is None or obj is None:
        return None
    from ..pipeline_manager.identity import get_object_uid

    uid = get_object_uid(obj)
    if uid is None:
        return None
    return state.nexus_obj_handles.get(uid)


def get_emitter_index(scene: bpy.types.Scene, emitter_obj: bpy.types.Object) -> int | None:
    """Return Theron's current emitter index for an NX_EMITTER, or None."""
    state = _scenes.get(scene_key(scene))
    if state is None or emitter_obj is None:
        return None
    from ..pipeline_manager.identity import get_object_uid

    target_uid = get_object_uid(emitter_obj)
    if target_uid is None:
        return None
    if state.nexus_obj_types.get(target_uid) != "NX_EMITTER":
        return None
    emitter_handle = state.nexus_obj_handles.get(target_uid)
    if emitter_handle is None:
        return None
    return theron.get_emitter_object_index(state.pipeline, emitter_handle)


def sync_emitter_group_memberships(
    scene: bpy.types.Scene,
    emitter_obj: bpy.types.Object,
    emitter_handle: int,
    desired: dict[str, int],
) -> None:
    """Reconcile group joins/leaves for ``emitter_obj``.

    ``desired`` maps target group UID → that group's Theron handle. Joins
    missing groups and leaves stale ones.
    """
    state = _scenes.get(scene_key(scene))
    if state is None or emitter_obj is None:
        return

    from ..pipeline_manager.identity import get_object_uid

    emitter_uid = get_object_uid(emitter_obj)
    if emitter_uid is None:
        return

    current_groups = state.emitter_group_memberships.setdefault(emitter_uid, set())

    # Add to groups not yet joined.
    for group_uid, group_handle in desired.items():
        if group_uid not in current_groups:
            theron.add_emitter_to_group(group_handle, emitter_handle)
            current_groups.add(group_uid)

    # Remove from groups that are tracked but no longer desired.
    stale = current_groups - set(desired.keys())
    for group_uid in stale:
        group_handle = state.nexus_obj_handles.get(group_uid)
        if group_handle is not None:
            theron.remove_emitter_from_group(group_handle, emitter_handle)
        current_groups.discard(group_uid)


def ensure_pipeline_ready_for_cpu_read(scene: bpy.types.Scene, context) -> bool:
    """Ensure the pipeline has executed with GPU_CPU so trGetParticlePosition works.

    Call from the draw handler when using the BASIC backend. If the draw runs before
    the pipeline handler (e.g. when switching from Vulkan to BASIC), this runs the
    pipeline update with GPU_CPU and sets executed_for_frame so the handler won't
    double-execute. Returns True if ready to read.
    """
    key = scene_key(scene)
    state = _scenes.get(key)
    if state is None or not theron.is_initialized():
        return False

    if context.scene.session_uid != scene.session_uid:
        return False

    depsgraph = context.evaluated_depsgraph_get()
    theron_frame = _blender_to_theron_frame(scene)
    timing_changed = _configure_pipeline_timing(scene, state)

    if not timing_changed and state.executed_for_frame == theron_frame:
        return state.copy_mode == "GPU_CPU"

    theron.set_particle_copy_mode(
        state.pipeline, theron.TrParticleCopyMode.TR_PARTICLE_COPY_MODE_GPU_CPU
    )
    state.copy_mode = "GPU_CPU"
    sync_all_objects(scene, depsgraph)
    _configure_pipeline_timing(scene, state)
    _push_pipeline_settings(scene, state)
    theron.execute_frame(state.pipeline, theron_frame)
    state.executed_for_frame = theron_frame
    _run_post_execute_hooks(scene, depsgraph)
    state.last_frame = theron_frame
    _dirty_objects.clear()
    return True


# ---------------------------------------------------------------------------
# Pipeline lifecycle
# ---------------------------------------------------------------------------


def reset_pipeline(scene: bpy.types.Scene) -> None:
    key = scene_key(scene)
    state = _scenes.get(key)
    if state is None:
        return

    state.last_frame = None
    state.executed_for_frame = None
    state.timing_signature = None
    state.copy_mode = "GPU_ONLY"
    state.force_gpu_cpu_next = False

    from ..viewport import clear_particle_cache
    from ..viewport.trails import reset_trail_caches_for_pipeline

    clear_particle_cache(key)
    reset_trail_caches_for_pipeline(state.pipeline)

    from ..modifiers import get_modifier_class
    from ..modifiers.base import NexusModifier

    for obj in scene.objects:
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue
        mod_cls = get_modifier_class(mod_type)
        if mod_cls is None:
            continue
        if mod_cls.on_reset is NexusModifier.on_reset:
            continue
        mod_cls.on_reset(obj, obj.nexus_modifier)


def destroy_pipeline(scene: bpy.types.Scene) -> None:
    key = scene_key(scene)
    state = _scenes.pop(key, None)
    if state is None:
        return

    from ..modifiers import MODIFIER_REGISTRY
    from ..modifiers.base import NexusModifier
    from ..viewport import clear_particle_cache
    from ..viewport.trails import reset_trail_caches_for_pipeline

    clear_particle_cache(key)
    for mod_cls in MODIFIER_REGISTRY.values():
        if mod_cls.on_pipeline_destroy is NexusModifier.on_pipeline_destroy:
            continue
        mod_cls.on_pipeline_destroy(state.pipeline, free_resources=True)
    reset_trail_caches_for_pipeline(state.pipeline)
    theron.destroy_pipeline(state.pipeline)


def destroy_all_pipelines() -> None:
    from ..modifiers import MODIFIER_REGISTRY
    from ..modifiers.base import NexusModifier
    from ..viewport import clear_particle_cache

    clear_particle_cache()

    for mod_cls in MODIFIER_REGISTRY.values():
        if mod_cls.on_state_clear is NexusModifier.on_state_clear:
            continue
        mod_cls.on_state_clear(free_resources=True)

    for state in _scenes.values():
        theron.destroy_pipeline(state.pipeline)

    _scenes.clear()
    _dirty_objects.clear()


def _clear_all_state() -> None:
    """Reset all module-level state without calling into the C library."""
    global _last_frame_time_ms, _playback_frame_start_perf, _execution_tick
    global _prev_frame_change_perf, _last_wall_clock_ms

    _scenes.clear()
    _dirty_objects.clear()
    _last_frame_time_ms = 0.0
    _playback_frame_start_perf = None
    _prev_frame_change_perf = None
    _last_wall_clock_ms = 0.0
    _execution_tick = 0

    from ..modifiers import MODIFIER_REGISTRY
    from ..modifiers.base import NexusModifier
    from ..viewport import clear_particle_cache

    clear_particle_cache()

    for mod_cls in MODIFIER_REGISTRY.values():
        if mod_cls.on_state_clear is NexusModifier.on_state_clear:
            continue
        mod_cls.on_state_clear(free_resources=False)


# ---------------------------------------------------------------------------
# Handle management
# ---------------------------------------------------------------------------


def _get_or_create_handle(
    state: _SceneState,
    obj: bpy.types.Object,
    create_fn,
    theron_type: int | None = None,
    obj_type: str = "",
) -> int | None:
    from ..pipeline_manager.identity import ensure_object_uid

    uid = ensure_object_uid(obj)

    if uid in state.nexus_obj_handles:
        if theron_type is not None:
            existing_type = state.nexus_obj_handle_mod_types.get(uid)
            if existing_type is not None and existing_type != theron_type:
                old_handle = state.nexus_obj_handles.pop(uid)
                state.nexus_obj_handle_mod_types.pop(uid, None)
                state.nexus_obj_types.pop(uid, None)
                state.nexus_obj_session_uids.pop(uid, None)
                theron.free_modifier(old_handle)
            else:
                return state.nexus_obj_handles[uid]
        else:
            return state.nexus_obj_handles[uid]

    handle = create_fn()
    if handle is None:
        return None

    state.nexus_obj_handles[uid] = handle
    state.nexus_obj_session_uids[uid] = obj.session_uid
    if obj_type:
        state.nexus_obj_types[uid] = obj_type
    if theron_type is not None:
        state.nexus_obj_handle_mod_types[uid] = theron_type
    return handle


# ---------------------------------------------------------------------------
# Effective-disable check
# ---------------------------------------------------------------------------


def _is_effectively_disabled(obj: bpy.types.Object, scene: bpy.types.Scene) -> bool:
    """Check if a modifier is disabled either directly or via ancestor cascade."""
    try:
        if not obj.nexus_modifier.enabled:
            return True
    except (AttributeError, ReferenceError):
        return False

    if not hasattr(scene, "nexus_pipeline"):
        return False

    pipeline_data = scene.nexus_pipeline

    from ..pipeline_manager.utils import is_ancestor_disabled

    target_item = None
    for item in pipeline_data.modifier_order:
        if item.modifier == obj:
            target_item = item
            break
    if target_item is None:
        return False

    return is_ancestor_disabled(pipeline_data, target_item)


def _sync_modifier_groups_tree(container, props, scene, *, collection_source=None):
    """Sync groups_affected items into the THERON_MODIFIER_GROUPS node tree."""
    from ..libs import theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item

    src = collection_source if collection_source is not None else props
    groups_orig = getattr(src, "groups_affected", None)
    if groups_orig is None:
        return
    groups_eval = (
        getattr(props, "groups_affected", None) if collection_source is not None else groups_orig
    )

    tree = theron.create_node_tree(container, theron_ids.get("THERON_MODIFIER_GROUPS"))
    if tree is None:
        return

    prev_node = None
    for index, item_orig in enumerate(groups_orig):
        group_obj = item_orig.obj
        if group_obj is None or group_obj.get("nexus_modifier_type") != "NX_GROUP":
            continue
        group_handle = get_nexus_obj_handle(scene, group_obj)
        if group_handle is None:
            continue

        item = resolve_evaluated_item(groups_eval, index, item_orig)

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_enabled(node, item.enabled)
        theron.set_node_link(node, group_handle)
        prev_node = node


FALLOFF_BLEND_MODE_IDS = {
    "NORMAL": "ID_NX_FALLOFF_BLEND_NORMAL",
    "ADD": "ID_NX_FALLOFF_BLEND_ADD",
    "SUB": "ID_NX_FALLOFF_BLEND_SUB",
    "MULT": "ID_NX_FALLOFF_BLEND_MULT",
    "DIFFERENCE": "ID_NX_FALLOFF_BLEND_DIFFERENCE",
    "SCREEN": "ID_NX_FALLOFF_BLEND_SCREEN",
    "OVERLAY": "ID_NX_FALLOFF_BLEND_OVERLAY",
    "MIN": "ID_NX_FALLOFF_BLEND_MIN",
    "MAX": "ID_NX_FALLOFF_BLEND_MAX",
}


def _sync_modifier_mapping_tree(
    container, props, scene, obj, depsgraph=None, *, collection_source=None
):
    """Sync generic mapping entries into the ID_XP_MOD_GROUP_DATAMAPPING_MAP node tree."""
    from ..libs import theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item
    from ..properties.mapping import CLAMP_VALUES, is_time_source

    src = collection_source if collection_source is not None else props
    mappings_orig = getattr(src, "mappings", None)
    if mappings_orig is None:
        return
    mappings_eval = (
        getattr(props, "mappings", None) if collection_source is not None else mappings_orig
    )

    tree = theron.create_node_tree(container, theron_ids.get("ID_XP_MOD_GROUP_DATAMAPPING_MAP"))
    if tree is None:
        return

    prev_node = None
    for index, item_orig in enumerate(mappings_orig):
        item = resolve_evaluated_item(mappings_eval, index, item_orig)
        if not item.enabled or item.dest_param == 0:
            continue

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_enabled(node, True)

        nc = theron.create_node_container(node)
        if nc is None:
            prev_node = node
            continue

        theron.set_int32(nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_PARAM"), int(item.dest_param))
        theron.set_int32(nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_MAPTO"), int(item.source_param))
        theron.set_int32(
            nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_MAPTO_LAYER"), int(item.layer_id)
        )

        if is_time_source(item.source_param):
            # stored values are in display-mode units; shader always reads seconds
            from ..libs.nexus_time import get_prop_time_mode, to_seconds

            fps_val = (
                scene.render.fps / scene.render.fps_base
                if scene is not None and scene.render.fps_base
                else None
            )
            min_mode = get_prop_time_mode(item, "range_min_time")
            max_mode = get_prop_time_mode(item, "range_max_time")
            min_val = to_seconds(float(item.range_min_time), fps=fps_val, mode=min_mode)
            max_val = to_seconds(float(item.range_max_time), fps=fps_val, mode=max_mode)
        else:
            min_val = float(item.range_min)
            max_val = float(item.range_max)
        theron.set_float(nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_RANGE_MIN"), min_val)
        theron.set_float(nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_RANGE_MAX"), max_val)

        theron.set_float(
            nc, theron_ids.get("ID_XP_MOD_DATAMAPPING_WEIGHT"), float(item.weight) * 0.01
        )
        theron.set_int32(
            nc,
            theron_ids.get("ID_XP_MOD_DATAMAPPING_CLAMP"),
            CLAMP_VALUES.get(item.clamp, CLAMP_VALUES["CLAMP"]),
        )

        if item_orig.curve_id:
            from ..properties.mapping import MAPPING_CURVE_SPEC
            from ..utils.curve import sync_curve_to_theron

            sync_curve_to_theron(
                theron,
                nc,
                obj,
                f"mapping_curve_{item_orig.curve_id}",
                theron_ids.get("ID_XP_MOD_DATAMAPPING_MAPPING"),
                default_ramp=MAPPING_CURVE_SPEC.default_points,
            )

        prev_node = node


def _sync_modifier_falloff_tree(container, props, scene, *, collection_source=None):
    """Sync falloff items into the THERON_MODIFIER_FALLOFFS node tree."""
    from ..libs import theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item

    src = collection_source if collection_source is not None else props
    falloff_orig = getattr(src, "falloffs", None)
    if falloff_orig is None:
        return
    falloff_eval = (
        getattr(props, "falloffs", None) if collection_source is not None else falloff_orig
    )

    tree = theron.create_node_tree(container, theron_ids.get("THERON_MODIFIER_FALLOFFS"))
    if tree is None:
        return

    prev_node = None
    for index, item_orig in enumerate(falloff_orig):
        falloff_obj = item_orig.obj
        if falloff_obj is None or falloff_obj.get("nexus_modifier_type") != "NX_FALLOFF":
            continue
        falloff_handle = get_nexus_obj_handle(scene, falloff_obj)
        if falloff_handle is None:
            continue

        item = resolve_evaluated_item(falloff_eval, index, item_orig)

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_enabled(node, item.enabled)
        theron.set_node_link(node, falloff_handle)

        bc = theron.create_node_container(node)
        if bc is not None:
            blend_mode_val = theron_ids.get(
                FALLOFF_BLEND_MODE_IDS.get(item.falloff_blend_mode, "ID_NX_FALLOFF_BLEND_NORMAL")
            )
            theron.set_int32(bc, theron_ids.get("ID_NX_FALLOFF_BLEND_MODE"), blend_mode_val)
            theron.set_float(
                bc,
                theron_ids.get("ID_NX_FALLOFF_BLEND_STRENGTH"),
                item.falloff_blend_strength * 0.01,
            )

        prev_node = node


# ---------------------------------------------------------------------------
# Per-object sync functions
# ---------------------------------------------------------------------------


def sync_object_to_theron(
    obj: bpy.types.Object,
    scene: bpy.types.Scene,
    depsgraph: bpy.types.Depsgraph | None = None,
) -> None:
    mod_type = obj.get("nexus_modifier_type")
    if mod_type is None:
        return

    state = _scenes.get(scene_key(scene))
    if state is None:
        return

    from ..modifiers import get_modifier_class

    mod_cls = get_modifier_class(mod_type)
    if mod_cls is not None and mod_cls.handles_own_sync:
        mod_cls.sync_to_pipeline(
            obj,
            scene,
            pipeline_handle=state.pipeline,
            disabled=_is_effectively_disabled(obj, scene),
            depsgraph=depsgraph,
        )
        return

    theron_type = None
    if mod_type == "NX_EMITTER":

        def create_fn():
            return theron.create_emitter(state.pipeline)

        get_container = theron.get_emitter_container
    elif mod_type == "NX_CACHE":

        def create_fn():
            return theron.create_cache_instance(state.pipeline)

        get_container = theron.get_object_container
    elif mod_type == "NX_GROUP":

        def create_fn():
            return theron.create_particle_group(state.pipeline)

        get_container = theron.get_object_container
    elif mod_type == "NX_FALLOFF":
        create_fn = theron.create_falloff
        get_container = theron.get_object_container
    else:
        theron_type = _get_theron_modifier_type(mod_type, obj)
        if theron_type is None:
            return

        def create_fn():
            return theron.add_modifier(state.pipeline, theron_type)

        get_container = theron.get_modifier_container

    disabled = _is_effectively_disabled(obj, scene)

    from ..pipeline_manager.identity import get_object_uid

    existing_uid = get_object_uid(obj)
    existing_handle = (
        state.nexus_obj_handles.get(existing_uid) if existing_uid is not None else None
    )
    if disabled and existing_handle is None:
        return

    handle = _get_or_create_handle(state, obj, create_fn, theron_type, obj_type=mod_type)
    if handle is None:
        return

    container = get_container(handle)
    if container is None:
        return

    if depsgraph is not None:
        try:
            eval_obj = obj.evaluated_get(depsgraph)
            props = eval_obj.nexus_modifier
        except (RuntimeError, AttributeError):
            props = obj.nexus_modifier
    else:
        props = obj.nexus_modifier
    original_props = obj.nexus_modifier

    from ..libs import theron_ids
    from ..libs.modifier_spec import get_modifier_spec
    from ..libs.nodetree_sync import sync_nodetrees
    from ..libs.resource_sync import sync_curve_specs, sync_gradient_specs
    from ..modifiers.base import NexusModifier

    if disabled:
        theron.set_bool(container, theron_ids.THERON_IS_ACTIVE, False)
        return

    theron.set_matrix(handle, obj.matrix_world)
    sync_properties(container, props, mod_type, scene)

    # NX_EMITTER visibility override: route hidden emitters' particles into the
    # NONE draw-mode bin. Must run AFTER sync_properties since that re-syncs
    # ID_NX_EMITTER_DISPLAY_MODE from the user's emitter_display_mode prop.
    if mod_type == "NX_EMITTER":
        show_particles = bool(getattr(props, "emitter_show_particles", True))
        hide_viewport = bool(getattr(obj, "hide_viewport", False))
        try:
            hide_get = bool(obj.hide_get())
        except (RuntimeError, AttributeError):
            hide_get = False
        if not show_particles or hide_viewport or hide_get:
            display_mode_id = theron_ids.get("ID_NX_EMITTER_DISPLAY_MODE")
            none_value = theron_ids.get("ID_NX_EMITTER_DISPLAY_MODE_NONE")
            theron.set_int32(container, display_mode_id, none_value)

    spec = get_modifier_spec(mod_type)
    if spec is not None and spec.nodetree_sync:
        sync_nodetrees(
            spec.nodetree_sync,
            container,
            props,
            obj=obj,
            scene=scene,
            depsgraph=depsgraph,
            collection_source=original_props,
        )

    if mod_cls is not None:
        curve_specs = mod_cls.get_curve_specs()
        if curve_specs:
            sync_curve_specs(theron, theron_ids.get, container, obj, curve_specs, source=props)

        gradient_specs = mod_cls.get_gradient_specs()
        if gradient_specs:
            sync_gradient_specs(
                theron,
                theron_ids.get,
                container,
                obj,
                gradient_specs,
                source=props,
            )

        if issubclass(mod_cls, NexusModifier):
            _sync_modifier_mapping_tree(
                container,
                props,
                scene,
                obj,
                depsgraph=depsgraph,
                collection_source=original_props,
            )

        mod_cls.post_sync(
            obj,
            container,
            handle,
            props,
            scene,
            depsgraph=depsgraph,
            original_props=original_props,
        )

    if mod_cls is not None and issubclass(mod_cls, NexusModifier):
        _sync_modifier_groups_tree(container, props, scene, collection_source=original_props)
        _sync_modifier_falloff_tree(container, props, scene, collection_source=original_props)


# ---------------------------------------------------------------------------
# Hierarchy ordering
# ---------------------------------------------------------------------------


def get_hierarchy_ordered_objects(scene: bpy.types.Scene) -> list[bpy.types.Object]:
    nexus_objects = [obj for obj in scene.objects if obj.get("nexus_modifier_type") is not None]

    def get_depth(obj: bpy.types.Object) -> int:
        depth = 0
        current = obj
        while current.parent is not None:
            depth += 1
            current = current.parent
        return depth

    nexus_objects.sort(key=get_depth)
    return nexus_objects


# ---------------------------------------------------------------------------
# Deletion detection and full-scene sync
# ---------------------------------------------------------------------------


def _detect_deleted_objects(
    state: _SceneState,
    current_uids: set[str],
) -> None:
    """Free Theron handles and per-modifier caches for UIDs no longer present.

    Any UID in ``state.tracked_objects`` that's not in ``current_uids`` is
    treated as deleted. ``on_destroy`` receives the deleted UID — caches are
    keyed by UID so the lookup stays correct across renames.
    """
    deleted_uids = state.tracked_objects - current_uids
    if not deleted_uids:
        return

    for uid in deleted_uids:
        state.tracked_objects.discard(uid)

        handle = state.nexus_obj_handles.pop(uid, None)
        if handle is not None:
            theron.free_object(handle)

        if state.nexus_obj_types.get(uid) == "NX_EMITTER":
            state.emitter_group_memberships.pop(uid, None)
        elif state.nexus_obj_types.get(uid) == "NX_GROUP":
            for memberships in state.emitter_group_memberships.values():
                memberships.discard(uid)

        state.nexus_obj_handle_mod_types.pop(uid, None)
        state.nexus_obj_types.pop(uid, None)
        state.nexus_obj_session_uids.pop(uid, None)

    from ..modifiers import MODIFIER_REGISTRY
    from ..modifiers.base import NexusModifier

    for mod_cls in MODIFIER_REGISTRY.values():
        if mod_cls.on_destroy is NexusModifier.on_destroy:
            continue
        for uid in deleted_uids:
            mod_cls.on_destroy(uid)


def _sync_theron_emitters_to_blender(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Create Blender NX_EMITTER objects for theron emitters with no Blender counterpart."""

    # Disabled for now until we do this properly for all objects, and have a flag to have a "dummy"
    # object not shown in Blender, e.g. for EFX
    return

    count = theron.get_emitter_count(state.pipeline)
    if count == 0:
        return

    tracked_handles = set(state.nexus_obj_handles.values())

    from ..pipeline_manager.identity import ensure_object_uid

    created_any = False
    for i in range(count):
        handle = theron.get_emitter(state.pipeline, i)
        if handle is None or handle in tracked_handles:
            continue

        obj = bpy.data.objects.new("nxEmitter", None)
        obj.empty_display_size = 0
        obj["nexus_modifier_type"] = "NX_EMITTER"
        scene.collection.objects.link(obj)

        uid = ensure_object_uid(obj)
        state.nexus_obj_handles[uid] = handle
        state.nexus_obj_session_uids[uid] = obj.session_uid
        state.nexus_obj_types[uid] = "NX_EMITTER"
        state.tracked_objects.add(uid)

        tracked_handles.add(handle)
        created_any = True

    if created_any:
        from ..pipeline_manager.sync import sync_modifier_list

        sync_modifier_list(scene)


def sync_all_objects(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph | None = None) -> None:
    state = _scenes.get(scene_key(scene))
    if state is None:
        return

    from ..pipeline_manager.identity import (
        ensure_object_uid,
        resolve_uid_collisions,
    )

    objects = get_hierarchy_ordered_objects(scene)

    # Catch Shift+D duplicates that copied a UID along with the rest of the
    # custom props before the duplicate gets its own handle.
    resolve_uid_collisions(objects, state.nexus_obj_session_uids)

    current_uids: set[str] = {ensure_object_uid(obj) for obj in objects}

    _detect_deleted_objects(state, current_uids)
    _sync_theron_emitters_to_blender(scene, state)

    for obj in objects:
        sync_object_to_theron(obj, scene, depsgraph)

    _reorder_theron_modifiers(scene, state)

    state.tracked_objects = current_uids


# ---------------------------------------------------------------------------
# Reset / redraw / post-execute
# ---------------------------------------------------------------------------


def _should_reset_pipeline(scene: bpy.types.Scene) -> bool:
    state = _scenes.get(scene_key(scene))
    if state is None or state.last_frame is None:
        return False

    current_theron_frame = _blender_to_theron_frame(scene)
    previous_theron_frame = state.last_frame

    if current_theron_frame - previous_theron_frame < -1:
        return True

    if current_theron_frame == 0 and previous_theron_frame > 0:
        return True

    return False


def _tag_ui_redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {"PROPERTIES", "VIEW_3D"}:
                    area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass


def _run_post_execute_hooks(
    scene: bpy.types.Scene,
    depsgraph: bpy.types.Depsgraph | None = None,
) -> None:
    from ..modifiers import get_modifier_class
    from ..modifiers.base import NexusModifier
    from ..operators import particle_console
    from ..pipeline_manager.identity import get_object_uid

    state = _scenes.get(scene_key(scene))
    if state is None:
        return

    for obj in scene.objects:
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is None:
            continue

        mod_cls = get_modifier_class(mod_type)
        if mod_cls is None:
            continue

        if mod_cls.handles_own_sync:
            if mod_cls.post_execute_pipeline is NexusModifier.post_execute_pipeline:
                continue
        else:
            if mod_cls.post_execute_object is NexusModifier.post_execute_object:
                continue

        uid = get_object_uid(obj)
        if uid is None:
            continue

        if _is_effectively_disabled(obj, scene):
            continue

        if mod_cls.handles_own_sync:
            mod_cls.post_execute_pipeline(
                obj, state.pipeline, obj.nexus_modifier, scene, depsgraph=depsgraph
            )
        else:
            handle = state.nexus_obj_handles.get(uid)
            if handle is None:
                continue
            mod_cls.post_execute_object(
                obj, handle, obj.nexus_modifier, scene, depsgraph=depsgraph
            )

    if particle_console.has_open_window():
        particle_console.update_particle_data(state.pipeline)


def _update_cache_state(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Sync object cache state to Blender property for displaying in the hierarchy UI."""

    from ..libs.theron_ids import get as get_theron_id
    from ..pipeline_manager.identity import get_object_uid

    for obj in scene.objects:
        if obj.get("nexus_modifier_type") is None:
            continue

        uid = get_object_uid(obj)
        if uid is None:
            continue

        handle = state.nexus_obj_handles.get(uid)
        if handle is None:
            continue

        props = obj.nexus_modifier
        container = theron.get_object_container(handle)
        if container is not None:
            props.is_cached = theron.get_bool(container, get_theron_id("THERON_IS_CACHED"))
            props.is_cached_full = theron.get_bool(
                container, get_theron_id("THERON_IS_CACHED_FULL")
            )
        else:
            props.is_cached = False
            props.is_cached_full = False


# ---------------------------------------------------------------------------
# Blender handlers
# ---------------------------------------------------------------------------


@persistent
def _on_frame_change(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    global _playback_frame_start_perf, _prev_frame_change_perf, _last_wall_clock_ms

    if not theron.is_initialized():
        return

    from ..viewport.generators.cache import load_capture_in_progress

    if load_capture_in_progress():
        return

    now = perf_counter()
    if _prev_frame_change_perf is not None:
        _last_wall_clock_ms = (now - _prev_frame_change_perf) * 1000.0
    _prev_frame_change_perf = now
    _playback_frame_start_perf = now

    did_reset = False
    if _should_reset_pipeline(scene):
        reset_pipeline(scene)
        did_reset = True

    state = _get_or_create_state(scene)
    if state is None:
        return

    theron_frame = _blender_to_theron_frame(scene)

    executed = _execute_pipeline_frame(scene, state, theron_frame, depsgraph)
    if executed:
        _update_cache_state(scene, state)
        _tag_ui_redraw()


def _resync_current_frame(
    scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph | None = None
) -> None:
    state = _scenes.get(scene_key(scene))
    if state is None:
        return

    theron_frame = _blender_to_theron_frame(scene)
    _execute_pipeline_frame(scene, state, theron_frame, depsgraph, force_execute=True)


def ensure_pipeline_timing_current(
    scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph | None = None
) -> bool:
    global _resync_in_progress

    if not theron.is_initialized():
        return False

    state = _scenes.get(scene_key(scene))
    if state is None or state.timing_signature == _scene_timing_signature(scene):
        return False

    if _resync_in_progress:
        return False

    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return False
    try:
        is_playing = screen.is_animation_playing
    except (AttributeError, RuntimeError):
        return False
    if is_playing:
        return False

    _resync_in_progress = True
    try:
        _resync_current_frame(scene, depsgraph)
    finally:
        _resync_in_progress = False
    return True


@persistent
def _on_depsgraph_update(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    from ..modifiers import MODIFIER_REGISTRY

    if not theron.is_initialized():
        return

    global _resync_in_progress

    state = _scenes.get(scene_key(scene))
    timing_changed = state is not None and state.timing_signature != _scene_timing_signature(scene)
    trigger_execute = timing_changed
    for update in depsgraph.updates:
        if not isinstance(update.id, bpy.types.Object):
            continue

        obj = update.id
        mod_type = obj.get("nexus_modifier_type")
        if mod_type is not None:
            _dirty_objects.add(obj.name)

            mod_class = MODIFIER_REGISTRY.get(mod_type)
            if mod_class is not None:
                if getattr(mod_class, "always_execute", False):
                    trigger_execute = True
                elif getattr(mod_class, "handles_own_sync", False):
                    trigger_execute = True

            # NX_EMITTER: detect hide_viewport / hide_get toggles.
            if mod_type == "NX_EMITTER" and state is not None:
                from ..pipeline_manager.identity import get_object_uid

                uid = get_object_uid(obj)
                if uid is not None:
                    props = obj.nexus_modifier
                    try:
                        hide_get = bool(obj.hide_get())
                    except (RuntimeError, AttributeError):
                        hide_get = False
                    current_visible = (
                        bool(getattr(props, "emitter_show_particles", True))
                        and not bool(getattr(obj, "hide_viewport", False))
                        and not hide_get
                    )
                    prev_visible = state.emitter_visibility.get(uid, True)
                    if current_visible != prev_visible:
                        state.emitter_visibility[uid] = current_visible
                        trigger_execute = True

    _deletion_detected = False
    if not _dirty_objects:
        if state is not None and state.tracked_objects:
            from ..pipeline_manager.identity import get_object_uid

            current_uids = {
                uid
                for uid in (
                    get_object_uid(obj)
                    for obj in scene.objects
                    if obj.get("nexus_modifier_type") is not None
                )
                if uid is not None
            }
            if state.tracked_objects - current_uids:
                _deletion_detected = True

    if not _dirty_objects and not _deletion_detected and not timing_changed:
        return

    if _resync_in_progress:
        return

    # Skip resync during playback -- the frame_change handler is authoritative there.
    # When no screen is available (e.g. background renders) we can't tell either way;
    # default to skipping rather than racing the frame handler.
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    try:
        is_playing = screen.is_animation_playing
    except (AttributeError, RuntimeError):
        return

    if is_playing:
        return

    if scene_key(scene) not in _scenes:
        if not _dirty_objects:
            return
        _resync_in_progress = True
        try:
            ensure_pipeline_for_scene(scene)
        finally:
            _resync_in_progress = False
        _dirty_objects.clear()
        return

    if not trigger_execute:
        return

    _resync_in_progress = True
    try:
        _resync_current_frame(scene, depsgraph)
    finally:
        _resync_in_progress = False


@persistent
def _on_load_post(dummy):
    del dummy
    _clear_all_state()
    bpy.app.timers.register(_rebuild_pipelines_after_load, first_interval=0.0)


def _restore_cache_sources(scene: bpy.types.Scene, state: _SceneState) -> None:
    """Push saved cache_sources collection into the ID_NX_CACHE_SOURCES node tree.

    Called on file load after all handles exist but before the first frame
    executes, so _sync_sources sees a populated tree instead of clearing the
    collection.
    """
    from ..libs import theron_ids
    from ..pipeline_manager.identity import get_object_uid

    for obj in scene.objects:
        if obj.get("nexus_modifier_type") != "NX_CACHE":
            continue

        props = obj.nexus_modifier
        if not props.cache_sources:
            continue

        uid = get_object_uid(obj)
        if uid is None:
            continue
        handle = state.nexus_obj_handles.get(uid)
        if handle is None:
            continue

        container = theron.get_object_container(handle)
        if container is None:
            continue

        tree = theron.create_node_tree(container, theron_ids.get("ID_NX_CACHE_SOURCES"))
        if tree is None:
            continue

        prev_node = None
        for item in props.cache_sources:
            if item.obj is None:
                continue
            source_handle = get_nexus_obj_handle(scene, item.obj)
            if source_handle is None:
                continue
            node = theron.node_tree_insert(tree, None, prev_node)
            if node is None:
                continue
            theron.set_node_link(node, source_handle)
            prev_node = node


def _rebuild_pipelines_after_load() -> None:
    if not theron.is_initialized():
        return None

    from ..viewport.generators.cache import restore_frozen_meshes_for_scene

    for scene in bpy.data.scenes:
        if ensure_pipeline_for_scene(scene) is None:
            continue

        has_nexus_modifier = any(o.get("nexus_modifier_type") is not None for o in scene.objects)
        if not has_nexus_modifier:
            continue

        state = _scenes.get(scene_key(scene))
        if state is None:
            continue

        _restore_cache_sources(scene, state)
        restore_frozen_meshes_for_scene(scene)

        theron_frame = _blender_to_theron_frame(scene)
        _execute_pipeline_frame(scene, state, theron_frame, force_execute=True)

    _tag_ui_redraw()
    return None


# Mark handlers for identification during cleanup
_on_frame_change._nexus_handler = True
_on_depsgraph_update._nexus_handler = True
_on_load_post._nexus_handler = True


def register():
    if _on_frame_change not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_on_frame_change)
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_frame_change in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_on_frame_change)
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
