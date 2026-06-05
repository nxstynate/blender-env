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

"""Collect trail draw data driven by Theron's authoritative source list."""

from __future__ import annotations

from ..registry import TrailDrawParams
from . import reset_trail_caches_for_pipeline
from .constants import TRAIL_DEFAULT_COLOR


def collect_trail_draw_data(
    context,
    depsgraph=None,
) -> TrailDrawParams | None:
    """Collect trail drawing parameters from Theron-registered sources.

    Returns a TrailDrawParams if any registered source belongs to a trail
    modifier with line-overlay drawing enabled, or None if nothing to draw.
    """
    from ...handlers import pipeline as pipeline_manager
    from ...libs import theron
    from ...libs.nodetree_sync import resolve_evaluated_item
    from ...modifiers.nx_trail import get_trail_source_key_by_id
    from ...pipeline_manager.identity import get_object_uid
    from ...pipeline_manager.utils import is_modifier_effectively_disabled

    if not theron.is_initialized():
        return None

    scene = context.scene
    pipeline = pipeline_manager.get_pipeline(scene)
    if pipeline is None:
        return None

    bundle = theron.get_trail_buffer_exports(pipeline)
    if bundle is None or bundle.source_count <= 0:
        reset_trail_caches_for_pipeline(pipeline)
        return None
    if bundle.history is None or bundle.topology is None:
        reset_trail_caches_for_pipeline(pipeline)
        return None
    if bundle.history_particle_capacity <= 0 or bundle.slots_per_particle <= 0:
        reset_trail_caches_for_pipeline(pipeline)
        return None
    particle_count = theron.get_particle_count(pipeline)
    if particle_count <= 0:
        reset_trail_caches_for_pipeline(pipeline)
        return None

    source_infos = theron.get_trail_source_infos(pipeline)
    if not source_infos:
        reset_trail_caches_for_pipeline(pipeline)
        return None

    if depsgraph is None:
        depsgraph = context.evaluated_depsgraph_get()

    source_key_by_id = get_trail_source_key_by_id(scene)
    pipeline_data = scene.nexus_pipeline if hasattr(scene, "nexus_pipeline") else None

    trail_objs_by_uid: dict[str, object] = {}
    for obj in context.view_layer.objects:
        if obj.get("nexus_modifier_type") != "NX_TRAIL":
            continue
        uid = get_object_uid(obj)
        if uid is not None:
            trail_objs_by_uid[uid] = obj

    mod_eval_cache: dict[str, tuple[object, object, bool]] = {}

    def _resolve_modifier(mod_uid: str):
        cached = mod_eval_cache.get(mod_uid)
        if cached is not None:
            return cached
        obj = trail_objs_by_uid.get(mod_uid)
        if obj is None:
            entry = (None, None, False)
            mod_eval_cache[mod_uid] = entry
            return entry
        if obj.hide_viewport or obj.hide_get():
            entry = (obj, None, False)
            mod_eval_cache[mod_uid] = entry
            return entry
        if not obj.nexus_modifier.enabled:
            entry = (obj, None, False)
            mod_eval_cache[mod_uid] = entry
            return entry
        if pipeline_data is not None and is_modifier_effectively_disabled(pipeline_data, obj):
            entry = (obj, None, False)
            mod_eval_cache[mod_uid] = entry
            return entry
        eval_obj = obj.evaluated_get(depsgraph)
        eval_props = eval_obj.nexus_modifier
        if str(getattr(eval_props, "trail_display", "LINES")) != "LINES":
            entry = (obj, eval_props, False)
            mod_eval_cache[mod_uid] = entry
            return entry
        entry = (obj, eval_props, True)
        mod_eval_cache[mod_uid] = entry
        return entry

    def _find_source_item(obj, eval_props, source_uid: str):
        if obj is None:
            return None
        orig_props = obj.nexus_modifier
        sources_orig = getattr(orig_props, "trail_emitters", None)
        if sources_orig is None or len(sources_orig) == 0:
            return None
        sources_eval = (
            getattr(eval_props, "trail_emitters", sources_orig)
            if eval_props is not None
            else sources_orig
        )
        for index, item_orig in enumerate(sources_orig):
            if getattr(item_orig, "layer_uid", "") != source_uid:
                continue
            item_eval = resolve_evaluated_item(sources_eval, index, item_orig)
            if not getattr(item_eval, "enabled", False):
                return None
            if getattr(item_orig, "obj", None) is None:
                return None
            return item_eval
        return None

    source_count = int(bundle.source_count)
    source_colors: list[tuple[float, float, float, float]] = [
        TRAIL_DEFAULT_COLOR for _ in range(source_count)
    ]
    source_color_modes: list[str] = ["STANDARD" for _ in range(source_count)]
    source_thickness_modes: list[str] = ["NONE" for _ in range(source_count)]
    source_thickness_values: list[float] = [0.01 for _ in range(source_count)]
    source_no_data_flags: list[bool] = [False for _ in range(source_count)]
    source_trail_color_modes: list[str] = ["PARTICLE" for _ in range(source_count)]
    source_thickness_variations: list[float] = [0.0 for _ in range(source_count)]
    source_spline_max_values: list[float] = [0.01 for _ in range(source_count)]
    source_enabled_flags: list[bool] = [False for _ in range(source_count)]
    source_algorithms: list[str] = ["NO_CONNECTIONS" for _ in range(source_count)]
    source_segment_lengths: list[int] = [1 for _ in range(source_count)]
    source_gap_lengths: list[int] = [1 for _ in range(source_count)]
    source_multiple_modes: list[int] = [0 for _ in range(source_count)]
    source_sequences: list[int] = [1 for _ in range(source_count)]
    source_sequence_lengths: list[int] = [1 for _ in range(source_count)]
    source_min_distances: list[float] = [0.0 for _ in range(source_count)]
    source_max_distances: list[float] = [1.0 for _ in range(source_count)]
    source_max_numbers: list[int] = [0 for _ in range(source_count)]

    for info in source_infos:
        source_index = int(info.source_index)
        if source_index < 0 or source_index >= source_count:
            continue

        key = source_key_by_id.get(info.source_id)
        src = None
        lines_active = False
        if key is not None:
            mod_uid, source_uid = key
            obj, eval_props, lines_active = _resolve_modifier(mod_uid)
            if lines_active:
                src = _find_source_item(obj, eval_props, source_uid)

        if src is not None and lines_active:
            source_colors[source_index] = tuple(
                float(c) for c in getattr(src, "trail_color", TRAIL_DEFAULT_COLOR)
            )
            source_color_modes[source_index] = str(getattr(src, "trail_color_mode", "STANDARD"))
            source_thickness_modes[source_index] = str(
                getattr(src, "trail_thickness_mode", "NONE")
            )
            source_thickness_values[source_index] = float(
                getattr(src, "trail_thickness_value", 0.01)
            )
            source_no_data_flags[source_index] = bool(
                getattr(src, "trail_no_thickness_color_data", False)
            )
            source_trail_color_modes[source_index] = str(
                getattr(src, "trail_vertex_color_mode", "PARTICLE")
            )
            source_thickness_variations[source_index] = float(
                getattr(src, "trail_thickness_variation", 0.0)
            )
            source_spline_max_values[source_index] = float(
                getattr(src, "trail_thickness_spline_max", 0.01)
            )
            source_enabled_flags[source_index] = bool(info.enabled)
            source_algorithms[source_index] = str(
                getattr(src, "trail_algorithm", "NO_CONNECTIONS")
            )
            source_segment_lengths[source_index] = max(
                1, int(getattr(src, "trail_segment_length", 1))
            )
            source_gap_lengths[source_index] = max(1, int(getattr(src, "trail_gap_length", 1)))
            source_multiple_modes[source_index] = (
                1 if getattr(src, "trail_multiple_mode", "ALTERNATING") == "SEQUENTIAL" else 0
            )
            source_sequences[source_index] = max(1, int(getattr(src, "trail_sequences", 1)))
            source_sequence_lengths[source_index] = max(
                1, int(getattr(src, "trail_sequence_length", 1))
            )
            source_min_distances[source_index] = max(
                0.0, float(getattr(src, "trail_min_distance", 0.0))
            )
            source_max_distances[source_index] = max(
                source_min_distances[source_index],
                float(getattr(src, "trail_max_distance", 1.0)),
            )
            source_max_numbers[source_index] = max(
                0, min(64, int(getattr(src, "trail_max_number", 0)))
            )
        elif key is None:
            source_enabled_flags[source_index] = bool(info.enabled)

    if not any(source_enabled_flags):
        reset_trail_caches_for_pipeline(pipeline)
        return None

    return TrailDrawParams(
        pipeline=pipeline,
        source_count=source_count,
        slots_per_particle=bundle.slots_per_particle,
        history_capacity=bundle.history_particle_capacity,
        max_points_per_segment=max(1, bundle.slots_per_particle),
        source_colors=tuple(source_colors),
        source_color_modes=tuple(source_color_modes),
        source_thickness_modes=tuple(source_thickness_modes),
        source_thickness_values=tuple(source_thickness_values),
        source_no_data_flags=tuple(source_no_data_flags),
        source_trail_color_modes=tuple(source_trail_color_modes),
        source_thickness_variations=tuple(source_thickness_variations),
        source_spline_max_values=tuple(source_spline_max_values),
        source_enabled_flags=tuple(source_enabled_flags),
        source_algorithms=tuple(source_algorithms),
        source_segment_lengths=tuple(source_segment_lengths),
        source_gap_lengths=tuple(source_gap_lengths),
        source_multiple_modes=tuple(source_multiple_modes),
        source_sequences=tuple(source_sequences),
        source_sequence_lengths=tuple(source_sequence_lengths),
        source_min_distances=tuple(source_min_distances),
        source_max_distances=tuple(source_max_distances),
        source_max_numbers=tuple(source_max_numbers),
    )
