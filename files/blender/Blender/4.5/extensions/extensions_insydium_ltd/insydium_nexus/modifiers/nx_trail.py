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

import ctypes
import hashlib
import math
import zlib

import bpy
import numpy as np

from ..libs.cache_spec import (
    CacheKind,
    CacheSpec,
    evict_stale_entries_for,
)
from ..properties.nx_trail import SPEC, get_trail_ui_config
from .base import MenuCategory, NexusModifier, UIFlags

_TRAIL_CURVE_OBJECT_TYPE = "NX_TRAIL_SPLINE"
_TRAIL_PARENT_UID_PROP = "nexus_trail_parent_uid"
_TRAIL_SOURCE_UID_PROP = "nexus_trail_source_uid"
_TRAIL_TOPOLOGY_SIGNATURE_PROP = "nexus_trail_topology_signature"
_TRAIL_TYPE_SIGNATURE_PROP = "nexus_trail_type_signature"
_TRAIL_CYCLIC_SIGNATURE_PROP = "nexus_trail_cyclic_signature"
_TRAIL_RADIUS_SIGNATURE_PROP = "nexus_trail_radius_signature"
_TRAIL_COLOR_SIGNATURE_PROP = "nexus_trail_color_signature"
_TRAIL_APPLY_SIGNATURE_PROP = "nexus_trail_apply_signature"
_TRAIL_MATERIAL_PROP = "nexus_trail_generated_material"
_TRAIL_MATERIAL_SIGNATURE_PROP = "nexus_trail_material_signature"
_TRAIL_COLOR_ATTRIBUTE = "Color"
_TRAIL_CURVES_POINT_FALLBACK_RADIUS = 0.001

_LENGTH_MODE_MAP = {"TIME": 0, "DISTANCE": 1}
_ALGORITHM_MAP = {
    "NO_CONNECTIONS": 0,
    "STRAIGHT_SEQUENCE": 1,
    "SEGMENTED_SEQUENCE": 2,
    "MULTIPLE_SEQUENCE": 3,
    "ALL_POINTS": 4,
    "NEAREST_INDEX": 5,
    "NEAREST_DISTANCE": 6,
    "CLUSTER": 7,
}
_MULTIPLE_MODE_MAP = {"ALTERNATING": 0, "SEQUENTIAL": 1}
_DESTINATION_GROUPS_MAP = {
    "USE_ALL": 0,
    "ONLY_SAME_GROUP": 1,
    "ONLY_DIFFERENT_GROUPS": 2,
    "SPECIFIC_GROUP": 3,
    "ALL_EXCEPT_SPECIFIC_GROUP": 4,
}


def _object_group_id(obj) -> int:
    if obj is None:
        return 0
    try:
        nm = obj.nexus_modifier
    except (AttributeError, ReferenceError):
        return 0
    try:
        return int(getattr(nm, "ID_NX_GROUP_ID", 0) or 0)
    except (TypeError, ValueError):
        return 0


_COLOR_MODE_MAP = {"STANDARD": 0, "GRADIENT": 1}
_THICKNESS_MODE_MAP = {
    "NONE": 0,
    "VALUE": 1,
    "SPLINE": 2,
    "RADIUS_CURRENT": 3,
    "RADIUS_VARIABLE": 4,
}
_TRAIL_COLOR_MODE_MAP = {"PARTICLE": 0, "PER_VERTEX": 1}
_FREEZE_MODE_MAP = {"NONE": 0, "FREEZE_PARTICLE": 1, "FREEZE_TRAIL": 2}

_GRADIENT_SLOT_KIND = 0
_CURVE_SLOT_KIND = 1


_trail_source_cache: dict[tuple[str, str, int], tuple[int, int, str, str]] = {}

_TRAIL_SOURCE_SPEC = CacheSpec(
    kind=CacheKind.TRAIL_SOURCE,
    collection_attr="trail_emitters",
    cache_dict=_trail_source_cache,
)


class _PipelineAux:
    __slots__ = ("resource_container", "spline_cache")

    def __init__(self) -> None:
        self.resource_container: int | None = None
        self.spline_cache: tuple | None = None


_pipeline_aux: dict[int, _PipelineAux] = {}


def _aux_for(pipeline: int) -> _PipelineAux:
    aux = _pipeline_aux.get(pipeline)
    if aux is None:
        aux = _PipelineAux()
        _pipeline_aux[pipeline] = aux
    return aux


def _pipeline_for_scene(scene: bpy.types.Scene | None) -> int | None:
    if scene is None:
        return None
    from ..handlers.pipeline import get_pipeline

    return get_pipeline(scene)


def _safe_register_timer(callback) -> None:
    try:
        bpy.app.timers.register(callback, first_interval=0.0)
    except (AttributeError, RuntimeError):
        pass


def get_trail_source_key_by_id(scene: bpy.types.Scene | None = None) -> dict[int, tuple[str, str]]:
    pipeline = _pipeline_for_scene(scene) if scene is not None else None
    mapping: dict[int, tuple[str, str]] = {}
    for key, entry in _trail_source_cache.items():
        entry_pipeline, source_id = entry[0], entry[1]
        if scene is not None and entry_pipeline != pipeline:
            continue
        mapping[source_id] = (key[0], key[1])
    return mapping


def _drop_stale_entries_for_pipeline(pipeline: int) -> None:
    stale = [key for key, entry in _trail_source_cache.items() if entry[0] == pipeline]
    for key in stale:
        _trail_source_cache.pop(key, None)


def _clear_pipeline_trail_state(pipeline: int, *, free_resources: bool = True) -> None:
    aux = _pipeline_aux.pop(pipeline, None)
    if free_resources:
        from ..libs import theron

        theron.clear_trail_sources(pipeline)
        if aux is not None and aux.resource_container is not None:
            theron.free_container(aux.resource_container)

    stale = [
        key
        for key, entry in _trail_source_cache.items()
        if entry[0] == pipeline or key[2] == pipeline
    ]
    for key in stale:
        _trail_source_cache.pop(key, None)


def _remove_modifier_trail_sources(mod_uid: str) -> None:
    from ..libs import theron

    stale = [key for key in _trail_source_cache if key[0] == mod_uid]
    for key in stale:
        pipeline_handle, source_id = _trail_source_cache.pop(key)[:2]
        if pipeline_handle:
            theron.remove_trail_source(pipeline_handle, source_id)


def _resource_slot_id(source_id: int, kind: int) -> int:
    digest = hashlib.blake2b(f"{source_id}:{kind}".encode("utf-8"), digest_size=4).digest()
    value = int.from_bytes(digest, "little", signed=False) & 0x7FFFFFFF
    return value or 1


def _scene_fps(scene: bpy.types.Scene | None) -> float:
    if scene is None:
        return 24.0
    fps_base = scene.render.fps_base
    if fps_base > 0.0:
        return scene.render.fps / fps_base
    return float(scene.render.fps)


def _build_desc(
    item_eval,
    emitter_index: int,
    scene: bpy.types.Scene | None,
    *,
    emit_chains: bool = False,
):
    from ..libs.nexus_time import get_prop_time_mode, to_time_fraction
    from ..libs.theron_bindings import TrTime, TrTrailSourceDesc

    fps = _scene_fps(scene)

    desc = TrTrailSourceDesc()
    desc.structSize = ctypes.sizeof(TrTrailSourceDesc)
    desc.emitterIndex = int(emitter_index)
    desc.enabled = 1 if item_eval.enabled else 0
    desc.lengthMode = _LENGTH_MODE_MAP.get(item_eval.trail_length_mode, 0)

    if desc.lengthMode == 0:
        mode = get_prop_time_mode(item_eval, "trail_length")
        num, den = to_time_fraction(float(item_eval.trail_length), fps=fps, mode=mode)
        desc.trailTime = TrTime(num, den)
        desc.trailDistance = 0.0
    else:
        desc.trailTime = TrTime(0, 1)
        desc.trailDistance = float(item_eval.trail_length_distance)

    desc.frameSampling = int(item_eval.trail_frame_sampling)
    desc.fullSceneTrail = 1 if item_eval.trail_full_scene else 0
    desc.colorMode = _COLOR_MODE_MAP.get(item_eval.trail_color_mode, 0)
    for i in range(4):
        desc.color[i] = float(item_eval.trail_color[i])
    desc.thicknessMode = _THICKNESS_MODE_MAP.get(item_eval.trail_thickness_mode, 0)
    desc.thicknessValue = float(item_eval.trail_thickness_value)
    desc.thicknessVariation = float(item_eval.trail_thickness_variation)
    desc.thicknessSplineMax = float(item_eval.trail_thickness_spline_max)

    spline_mode = get_prop_time_mode(item_eval, "trail_thickness_spline_time")
    spline_num, spline_den = to_time_fraction(
        float(item_eval.trail_thickness_spline_time), fps=fps, mode=spline_mode
    )
    desc.thicknessSplineTime = TrTime(spline_num, spline_den)

    desc.noThicknessColorData = 1 if item_eval.trail_no_thickness_color_data else 0
    desc.trailColorMode = _TRAIL_COLOR_MODE_MAP.get(item_eval.trail_vertex_color_mode, 0)
    desc.freezeMode = _FREEZE_MODE_MAP.get(item_eval.trail_freeze_mode, 0)
    desc.freezeMovement = 1 if item_eval.trail_freeze_movement else 0
    desc.freezeScale = 1 if item_eval.trail_freeze_scale else 0
    desc.variation = float(item_eval.trail_variation)
    desc.algorithm = _ALGORITHM_MAP.get(getattr(item_eval, "trail_algorithm", "NO_CONNECTIONS"), 0)
    desc.segmentLength = max(1, int(getattr(item_eval, "trail_segment_length", 1)))
    desc.gapLength = max(1, int(getattr(item_eval, "trail_gap_length", 1)))
    desc.multipleMode = _MULTIPLE_MODE_MAP.get(
        getattr(item_eval, "trail_multiple_mode", "ALTERNATING"), 0
    )
    desc.sequenceCount = max(1, int(getattr(item_eval, "trail_sequences", 1)))
    desc.sequenceLength = max(1, int(getattr(item_eval, "trail_sequence_length", 1)))
    desc.emitChains = 1 if emit_chains else 0
    desc.maxConnections = max(1, int(getattr(item_eval, "trail_max_connections", 1)))
    desc.skipParticles = max(0, int(getattr(item_eval, "trail_skip_particles", 0)))
    desc.destinationGroups = _DESTINATION_GROUPS_MAP.get(
        getattr(item_eval, "trail_destination_groups", "USE_ALL"), 0
    )
    group_ref = getattr(item_eval, "trail_group_ref", None)
    desc.specificGroupId = _object_group_id(group_ref) if group_ref is not None else 0
    desc.minDistance = max(0.0, float(getattr(item_eval, "trail_min_distance", 0.0)))
    desc.maxDistance = max(desc.minDistance, float(getattr(item_eval, "trail_max_distance", 1.0)))
    desc.maxNumber = max(0, min(64, int(getattr(item_eval, "trail_max_number", 0))))
    desc.clusterDistance = max(0.0, float(getattr(item_eval, "trail_cluster_distance", 0.0)))
    desc.minParticlesInCluster = max(
        2, int(getattr(item_eval, "trail_min_particles_in_cluster", 2))
    )
    return desc


def _gradient_content_signature(stops) -> str:
    payload = []
    for stop in stops:
        payload.append(",".join(f"{float(v):.6f}" for v in stop))
    return zlib.crc32("|".join(payload).encode("utf-8")).to_bytes(4, "little").hex()


def _curve_content_signature(points) -> str:
    payload = ",".join(f"{float(px):.6f}:{float(py):.6f}" for px, py in points)
    return zlib.crc32(payload.encode("utf-8")).to_bytes(4, "little").hex()


def _ensure_resource_container(aux: _PipelineAux) -> int | None:
    from ..libs import theron

    if aux.resource_container is None:
        aux.resource_container = theron.create_container()
    return aux.resource_container


def _sync_trail_source_resources(
    aux: _PipelineAux,
    pipeline: int,
    source_id: int,
    obj,
    item_eval,
    item_orig,
    cached_gradient_sig: str,
    cached_curve_sig: str,
) -> tuple[str, str]:
    from ..libs import theron
    from ..properties.nx_trail import (
        TRAIL_COLOR_GRADIENT_SPEC,
        TRAIL_THICKNESS_SPLINE_SPEC,
    )
    from ..utils.curve import NexusCurve, resolve_curve_slot_name
    from ..utils.gradient import (
        NexusGradient,
        build_default_gradient_stops_data,
        resolve_gradient_slot_name,
        sync_gradient_to_theron,
    )

    gradient_sig = cached_gradient_sig
    curve_sig = cached_curve_sig

    container = _ensure_resource_container(aux)
    if container is None:
        return gradient_sig, curve_sig

    uid = item_orig.layer_uid
    if not uid:
        return gradient_sig, curve_sig

    if item_eval.trail_color_mode == "GRADIENT" and not item_eval.trail_no_thickness_color_data:
        slot = resolve_gradient_slot_name(TRAIL_COLOR_GRADIENT_SPEC, uid)
        if slot:
            gradient = NexusGradient(obj, slot)
            stops = gradient.extract_stops() or build_default_gradient_stops_data(
                TRAIL_COLOR_GRADIENT_SPEC
            )
            signature = _gradient_content_signature(stops.get("stops", ()))
            if signature != cached_gradient_sig:
                slot_id = _resource_slot_id(source_id, _GRADIENT_SLOT_KIND)
                grad_handle = theron.create_gradient(container, slot_id)
                if grad_handle is not None:
                    sync_gradient_to_theron(theron, grad_handle, stops)
                    if theron.set_trail_source_gradient(pipeline, source_id, grad_handle):
                        gradient_sig = signature
        elif cached_gradient_sig:
            theron.clear_trail_source_gradient(pipeline, source_id)
            gradient_sig = ""
    else:
        if cached_gradient_sig:
            theron.clear_trail_source_gradient(pipeline, source_id)
        gradient_sig = ""

    if item_eval.trail_thickness_mode == "SPLINE" and not item_eval.trail_no_thickness_color_data:
        slot = resolve_curve_slot_name(TRAIL_THICKNESS_SPLINE_SPEC, uid)
        if slot:
            curve = NexusCurve(obj, slot)
            points = curve.extract_points() or TRAIL_THICKNESS_SPLINE_SPEC.default_points
            if points:
                signature = _curve_content_signature(points)
                if signature != cached_curve_sig:
                    slot_id = _resource_slot_id(source_id, _CURVE_SLOT_KIND)
                    spline_handle = theron.create_spline(container, slot_id)
                    if spline_handle is not None:
                        theron.resize_spline(spline_handle, len(points))
                        for i, (px, py) in enumerate(points):
                            theron.set_spline_knot(spline_handle, i, px, py)
                        if theron.set_trail_source_curve(pipeline, source_id, spline_handle):
                            curve_sig = signature
        elif cached_curve_sig:
            theron.clear_trail_source_curve(pipeline, source_id)
            curve_sig = ""
    else:
        if cached_curve_sig:
            theron.clear_trail_source_curve(pipeline, source_id)
        curve_sig = ""

    return gradient_sig, curve_sig


class _SplineGenerationOptions:
    def __init__(self, props) -> None:
        self.spline_type = getattr(props, "trail_spline_type", "LINEAR")
        self.cyclic = bool(getattr(props, "trail_spline_close", False))
        self.intermediate = getattr(props, "trail_spline_intermediate", "NONE")
        if self.spline_type == "LINEAR" and self.intermediate == "ADAPTIVE":
            self.intermediate = "NONE"
        self.number = max(0, int(getattr(props, "trail_spline_number", 0)))
        self.angle = max(0.0, float(getattr(props, "trail_spline_angle", 0.0)))
        use_max_length = bool(getattr(props, "trail_spline_use_max_length", False))
        self.max_length = (
            max(0.0, float(getattr(props, "trail_spline_max_length", 0.0)))
            if use_max_length
            else 0.0
        )

    @property
    def curves_type(self) -> str:
        if self.spline_type == "BEZIER":
            return "BEZIER"
        if self.spline_type == "BSPLINE":
            return "NURBS"
        return "POLY"

    @property
    def signature_prefix(self) -> str:
        return (
            f"{self.curves_type}|{int(self.cyclic)}|{self.intermediate}|"
            f"{self.number}|{self.angle:.6f}|{self.max_length:.6f}"
        )

    @property
    def uses_raw_points(self) -> bool:
        return self.intermediate == "NONE" and self.max_length <= 0.0


def _trail_curve_children(obj: bpy.types.Object) -> list[bpy.types.Object]:
    return [
        child
        for child in obj.children
        if child.get("nexus_object_type") == _TRAIL_CURVE_OBJECT_TYPE
    ]


def _clear_curve_splines(curve: bpy.types.Curve) -> None:
    curve.splines.clear()


def _clear_curves_data(curves) -> bool:
    try:
        curve_count = len(curves.curves)
    except (AttributeError, RuntimeError, TypeError):
        return False

    try:
        if curve_count > 0:
            curves.remove_curves(indices=list(range(curve_count)))
    except (AttributeError, RuntimeError, TypeError):
        return False

    for name in (
        "radius",
        "cyclic",
        "handle_left",
        "handle_right",
        "handle_type_left",
        "handle_type_right",
    ):
        _remove_curves_attribute(curves, name)
    _remove_curves_color_attribute(curves, _TRAIL_COLOR_ATTRIBUTE)
    return True


def _remove_curve_object_now(curve_obj: bpy.types.Object) -> None:
    data = curve_obj.data
    try:
        bpy.data.objects.remove(curve_obj, do_unlink=True)
    except (ReferenceError, RuntimeError):
        return
    if data is None:
        return
    try:
        users = data.users
    except ReferenceError:
        return
    if users != 0:
        return
    if data.__class__.__name__ == "Curves" and hasattr(bpy.data, "hair_curves"):
        bpy.data.hair_curves.remove(data)
    elif data.__class__.__name__ == "Curve":
        bpy.data.curves.remove(data)


def _schedule_curve_object_removal(curve_obj: bpy.types.Object) -> None:
    try:
        target_name = curve_obj.name
    except (ReferenceError, AttributeError):
        return

    def _deferred():
        target = bpy.data.objects.get(target_name)
        if target is None:
            return None
        _remove_curve_object_now(target)
        return None

    _safe_register_timer(_deferred)


def _clear_trail_curve(curve_obj: bpy.types.Object) -> None:
    cleared = True
    if curve_obj.type == "CURVE" and curve_obj.data is not None:
        _clear_curve_splines(curve_obj.data)
    elif curve_obj.type == "CURVES" and curve_obj.data is not None:
        cleared = _clear_curves_data(curve_obj.data)
    if not cleared:
        return
    curve_obj[_TRAIL_TOPOLOGY_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_RADIUS_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = ""
    curve_obj.update_tag()


def _link_curve_to_scene(
    scene: bpy.types.Scene,
    trail_obj: bpy.types.Object,
    curve_obj: bpy.types.Object,
) -> None:
    for collection in trail_obj.users_collection:
        collection.objects.link(curve_obj)
        return
    scene.collection.objects.link(curve_obj)


def _pin_curve_child_transform(trail_obj: bpy.types.Object, curve_obj: bpy.types.Object) -> None:
    if curve_obj.parent is not trail_obj:
        curve_obj.parent = trail_obj
    target_inverse = trail_obj.matrix_world.inverted_safe()
    if curve_obj.matrix_parent_inverse != target_inverse:
        curve_obj.matrix_parent_inverse = target_inverse
    if not curve_obj.matrix_basis.is_identity:
        curve_obj.matrix_basis.identity()


def _ensure_trail_curve_child(
    scene: bpy.types.Scene,
    trail_obj: bpy.types.Object,
    trail_uid: str,
    source_obj: bpy.types.Object,
    source_uid: str,
) -> bpy.types.Object:
    for child in list(_trail_curve_children(trail_obj)):
        if child.get(_TRAIL_SOURCE_UID_PROP) == source_uid and child.type == "CURVE":
            _schedule_curve_object_removal(child)
            continue
        if child.get(_TRAIL_SOURCE_UID_PROP) == source_uid and child.type == "CURVES":
            _pin_curve_child_transform(trail_obj, child)
            return child

    curve = bpy.data.hair_curves.new(f"{trail_obj.name}_{source_obj.name}_trail")
    curve_obj = bpy.data.objects.new(curve.name, curve)
    curve_obj["nexus_object_type"] = _TRAIL_CURVE_OBJECT_TYPE
    curve_obj[_TRAIL_PARENT_UID_PROP] = trail_uid
    curve_obj[_TRAIL_SOURCE_UID_PROP] = source_uid
    _link_curve_to_scene(scene, trail_obj, curve_obj)
    _pin_curve_child_transform(trail_obj, curve_obj)
    return curve_obj


def _remove_stale_trail_curves(
    obj: bpy.types.Object,
    active_source_uids: set[str],
) -> None:
    for child in list(_trail_curve_children(obj)):
        if child.get(_TRAIL_SOURCE_UID_PROP) not in active_source_uids:
            _schedule_curve_object_removal(child)


def _point_distance(a: np.ndarray, b: np.ndarray) -> float:
    delta = b[:3] - a[:3]
    return float(np.sqrt(np.dot(delta, delta)))


def _edge_steps(length: float, uniform_points: int, max_length: float) -> int:
    steps = max(1, uniform_points + 1)
    if max_length > 0.0 and length > max_length:
        steps = max(steps, int(math.ceil(length / max_length)))
    return steps


def _corner_angle(prev_point: np.ndarray, point: np.ndarray, next_point: np.ndarray) -> float:
    incoming = point[:3] - prev_point[:3]
    outgoing = next_point[:3] - point[:3]
    incoming_len = float(np.sqrt(np.dot(incoming, incoming)))
    outgoing_len = float(np.sqrt(np.dot(outgoing, outgoing)))
    if incoming_len <= 1.0e-8 or outgoing_len <= 1.0e-8:
        return 0.0
    dot = float(np.dot(incoming, outgoing) / (incoming_len * outgoing_len))
    return math.acos(max(-1.0, min(1.0, dot)))


def _adaptive_split_edges(xyzw: np.ndarray, cyclic: bool, angle_threshold: float) -> set[int]:
    point_count = len(xyzw)
    if point_count < 3:
        return set()

    edge_count = point_count if cyclic else point_count - 1
    split_edges: set[int] = set()
    vertex_range = range(point_count) if cyclic else range(1, point_count - 1)
    for index in vertex_range:
        prev_index = (index - 1) % point_count
        next_index = (index + 1) % point_count
        angle = _corner_angle(xyzw[prev_index], xyzw[index], xyzw[next_index])
        if angle <= 1.0e-6 or angle + 1.0e-6 < angle_threshold:
            continue
        split_edges.add((index - 1) % edge_count)
        split_edges.add(index % edge_count)
    return split_edges


def _generate_spline_points(xyzw: np.ndarray, options: _SplineGenerationOptions) -> np.ndarray:
    coords = np.ascontiguousarray(xyzw, dtype=np.float32)
    point_count = len(coords)
    if point_count < 2:
        return coords

    uniform_points = options.number if options.intermediate == "UNIFORM" else 0
    adaptive_edges = (
        _adaptive_split_edges(coords, options.cyclic, options.angle)
        if options.intermediate == "ADAPTIVE"
        else set()
    )

    if uniform_points == 0 and options.max_length <= 0.0 and not adaptive_edges:
        return coords

    edge_count = point_count if options.cyclic else point_count - 1
    generated: list[np.ndarray] = [coords[0].copy()]
    for edge_index in range(edge_count):
        start = coords[edge_index]
        end = coords[(edge_index + 1) % point_count]
        edge_uniform_points = uniform_points
        if edge_index in adaptive_edges:
            edge_uniform_points = max(edge_uniform_points, 1)

        steps = _edge_steps(_point_distance(start, end), edge_uniform_points, options.max_length)
        last_step = steps - 1 if options.cyclic and edge_index == point_count - 1 else steps
        for step in range(1, last_step + 1):
            t = step / steps
            point = start * (1.0 - t) + end * t
            generated.append(point.astype(np.float32, copy=False))

    return np.ascontiguousarray(generated, dtype=np.float32)


def _ranges_array(ranges) -> np.ndarray:
    if isinstance(ranges, np.ndarray):
        if ranges.size == 0:
            return np.empty((0, 2), dtype=np.int32)
        return ranges.reshape((-1, 2))
    if not ranges:
        return np.empty((0, 2), dtype=np.int32)
    return np.asarray(ranges, dtype=np.int32).reshape((-1, 2))


def _interpolated_generated_ranges(
    ranges: np.ndarray,
    points: np.ndarray,
    colors: np.ndarray | None,
    gradient_lut: np.ndarray | None,
    options: _SplineGenerationOptions,
) -> list[np.ndarray]:
    generated: list[np.ndarray] = []
    for first, count in ranges:
        point_range = points[first : first + count]
        if gradient_lut is not None:
            source = np.empty((count, 8), dtype=np.float32)
            source[:, :4] = point_range
            source[:, 4:] = _gradient_colors_for_count(count, gradient_lut)
        elif colors is not None and len(colors) >= first + count:
            source = np.empty((count, 8), dtype=np.float32)
            source[:, :4] = point_range
            source[:, 4:] = colors[first : first + count]
        else:
            source = point_range
        coords = _generate_spline_points(source, options)
        if len(coords) >= 2:
            generated.append(coords)
    return generated


def _build_curves_payload(
    ranges: np.ndarray,
    points: np.ndarray,
    colors: np.ndarray | None,
    gradient_lut: np.ndarray | None,
    options: _SplineGenerationOptions,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    valid_ranges = ranges[ranges[:, 1] >= 2] if len(ranges) else ranges
    if len(valid_ranges) == 0:
        return (
            np.empty((0,), dtype=np.int32),
            np.empty((0, 3), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            np.empty((0, 4), dtype=np.float32),
        )

    has_colors = gradient_lut is not None or (colors is not None and len(colors) > 0)
    if options.uses_raw_points:
        sizes = np.ascontiguousarray(valid_ranges[:, 1], dtype=np.int32)
        total_points = int(np.sum(sizes, dtype=np.int64))
        positions = np.empty((total_points, 3), dtype=np.float32)
        radii = np.empty((total_points,), dtype=np.float32)
        color_values = np.empty((total_points, 4), dtype=np.float32)
        offset = 0
        expected_first = int(valid_ranges[0, 0])
        contiguous_first = expected_first
        contiguous = True
        for first, count in valid_ranges:
            if first != expected_first:
                contiguous = False
                break
            expected_first = first + count
        if contiguous and total_points > 0:
            positions[:] = points[contiguous_first : contiguous_first + total_points, :3]
            radii[:] = points[contiguous_first : contiguous_first + total_points, 3]
            if gradient_lut is not None:
                _fill_gradient_colors(color_values, sizes, gradient_lut)
            elif has_colors and len(colors) >= contiguous_first + total_points:
                color_values[:] = colors[contiguous_first : contiguous_first + total_points]
            else:
                color_values = np.empty((0, 4), dtype=np.float32)
            return sizes, positions, radii, color_values
        for first, count in valid_ranges:
            end = offset + count
            positions[offset:end] = points[first : first + count, :3]
            radii[offset:end] = points[first : first + count, 3]
            if gradient_lut is not None:
                color_values[offset:end] = _gradient_colors_for_count(count, gradient_lut)
            elif has_colors and len(colors) >= first + count:
                color_values[offset:end] = colors[first : first + count]
            else:
                color_values = np.empty((0, 4), dtype=np.float32)
                has_colors = False
            offset = end
        return sizes, positions, radii, color_values

    generated_ranges = _interpolated_generated_ranges(
        valid_ranges, points, colors, gradient_lut, options
    )
    if not generated_ranges:
        return (
            np.empty((0,), dtype=np.int32),
            np.empty((0, 3), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            np.empty((0, 4), dtype=np.float32),
        )

    sizes = np.fromiter((len(coords) for coords in generated_ranges), dtype=np.int32)
    positions = np.empty((int(np.sum(sizes, dtype=np.int64)), 3), dtype=np.float32)
    radii = np.empty((len(positions),), dtype=np.float32)
    color_values = np.empty((len(positions), 4), dtype=np.float32)
    has_generated_colors = generated_ranges[0].shape[1] >= 8
    offset = 0
    for coords in generated_ranges:
        count = len(coords)
        positions[offset : offset + count] = coords[:, :3]
        radii[offset : offset + count] = coords[:, 3]
        if has_generated_colors:
            color_values[offset : offset + count] = coords[:, 4:8]
        offset += count
    if not has_generated_colors:
        color_values = np.empty((0, 4), dtype=np.float32)
    return sizes, positions, radii, color_values


def _ensure_curves_attribute(curves, name: str, data_type: str, domain: str):
    attr = curves.attributes.get(name)
    if attr is not None and (
        getattr(attr, "data_type", data_type) != data_type
        or getattr(attr, "domain", domain) != domain
    ):
        curves.attributes.remove(attr)
        attr = None
    if attr is None:
        attr = curves.attributes.new(name, data_type, domain)
    return attr


def _remove_curves_attribute(curves, name: str) -> None:
    try:
        attr = curves.attributes.get(name)
        if attr is not None:
            curves.attributes.remove(attr)
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        pass


def _ensure_curves_color_attribute(curves, name: str):
    color_attributes = getattr(curves, "color_attributes", None)
    if color_attributes is None:
        return _ensure_curves_attribute(curves, name, "FLOAT_COLOR", "POINT")

    attr = color_attributes.get(name)
    if attr is not None and (
        getattr(attr, "data_type", "FLOAT_COLOR") != "FLOAT_COLOR"
        or getattr(attr, "domain", "POINT") != "POINT"
    ):
        color_attributes.remove(attr)
        attr = None
    if attr is None:
        attr = color_attributes.new(name=name, type="FLOAT_COLOR", domain="POINT")
    index = color_attributes.find(name)
    try:
        color_attributes.active_color_index = index
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    try:
        color_attributes.render_color_index = index
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return attr


def _remove_curves_color_attribute(curves, name: str) -> None:
    try:
        color_attributes = getattr(curves, "color_attributes", None)
        if color_attributes is not None:
            attr = color_attributes.get(name)
            if attr is not None:
                color_attributes.remove(attr)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    _remove_curves_attribute(curves, name)


def _write_curves_data_values(data, prop_name: str, values: np.ndarray) -> None:
    contiguous = np.ascontiguousarray(values)
    if contiguous.size == 0:
        return

    try:
        target_ptr = data[0].as_pointer() if len(data) > 0 else 0
    except (AttributeError, RuntimeError, TypeError, ValueError):
        target_ptr = 0

    if target_ptr:
        ctypes.memmove(target_ptr, contiguous.ctypes.data, contiguous.nbytes)
    else:
        data.foreach_set(prop_name, contiguous.ravel())


def _gradient_colors_for_count(count: int, gradient_lut: np.ndarray) -> np.ndarray:
    if count <= 0:
        return np.empty((0, 4), dtype=np.float32)
    if count == 1:
        return gradient_lut[0:1]
    ratios = np.linspace(1.0, 0.0, count, dtype=np.float32)
    indices = np.clip((ratios * 255.0).astype(np.int32), 0, 255)
    return gradient_lut[indices]


def _fill_gradient_colors(
    color_values: np.ndarray, sizes: np.ndarray, gradient_lut: np.ndarray
) -> None:
    offset = 0
    for size in sizes:
        count = int(size)
        end = offset + count
        color_values[offset:end] = _gradient_colors_for_count(count, gradient_lut)
        offset = end


def _trail_gradient_lut(trail_obj: bpy.types.Object, item_orig, item_eval) -> np.ndarray | None:
    if getattr(item_eval, "trail_color_mode", "STANDARD") != "GRADIENT":
        return None

    source_uid = getattr(item_orig, "layer_uid", "")
    if not source_uid:
        return None

    from ..properties.nx_trail import TRAIL_COLOR_GRADIENT_SPEC
    from ..utils.gradient import (
        NexusGradient,
        build_default_gradient_stops_data,
        resolve_gradient_slot_name,
    )

    slot = resolve_gradient_slot_name(TRAIL_COLOR_GRADIENT_SPEC, source_uid)
    if not slot:
        return None
    lut = NexusGradient(trail_obj, slot).lut
    if lut is None:
        default_stops = build_default_gradient_stops_data(TRAIL_COLOR_GRADIENT_SPEC)["stops"]
        start = np.asarray(default_stops[0][1:5], dtype=np.float32)
        end = np.asarray(default_stops[-1][1:5], dtype=np.float32)
        t = np.linspace(0.0, 1.0, 256, dtype=np.float32)[:, None]
        return np.ascontiguousarray(start * (1.0 - t) + end * t, dtype=np.float32)
    return np.ascontiguousarray(lut, dtype=np.float32)


def _set_curves_type(
    curve_obj: bpy.types.Object,
    curves,
    curve_type: str,
    curve_count: int,
    *,
    force: bool = False,
) -> None:
    if curve_count <= 0:
        return
    signature = f"{curve_type}:{curve_count}"
    if not force and curve_obj.get(_TRAIL_TYPE_SIGNATURE_PROP) == signature:
        return
    try:
        curves.set_types(type=curve_type, indices=list(range(curve_count)))
        curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = signature
    except (AttributeError, RuntimeError, TypeError, ValueError):
        if curve_type != "POLY":
            try:
                curves.set_types(type="POLY", indices=list(range(curve_count)))
                curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = f"POLY:{curve_count}"
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass


def _set_curves_cyclic(
    curve_obj: bpy.types.Object,
    curves,
    cyclic: bool,
    curve_count: int,
    *,
    force: bool = False,
) -> None:
    if curve_count <= 0:
        return
    signature = f"{int(cyclic)}:{curve_count}"
    if not force and curve_obj.get(_TRAIL_CYCLIC_SIGNATURE_PROP) == signature:
        return
    try:
        if not cyclic:
            _remove_curves_attribute(curves, "cyclic")
            curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = signature
            return
        attr = _ensure_curves_attribute(curves, "cyclic", "BOOLEAN", "CURVE")
        attr.data.foreach_set("value", np.ones(curve_count, dtype=bool))
        curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = signature
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        pass


def _trail_curves_radius(item_eval) -> float:
    if bool(getattr(item_eval, "trail_no_thickness_color_data", False)):
        return _TRAIL_CURVES_POINT_FALLBACK_RADIUS

    mode = getattr(item_eval, "trail_thickness_mode", "NONE")
    if mode == "NONE":
        return _TRAIL_CURVES_POINT_FALLBACK_RADIUS
    if mode == "SPLINE":
        value = float(getattr(item_eval, "trail_thickness_spline_max", 0.0))
    else:
        value = float(getattr(item_eval, "trail_thickness_value", 0.0))
    return max(_TRAIL_CURVES_POINT_FALLBACK_RADIUS, value)


def _bezier_handles_for_positions(
    sizes: np.ndarray, positions: np.ndarray, cyclic: bool
) -> tuple[np.ndarray, np.ndarray]:
    left = np.empty_like(positions)
    right = np.empty_like(positions)
    offset = 0
    for size in sizes:
        count = int(size)
        end = offset + count
        coords = positions[offset:end]
        if count < 2:
            left[offset:end] = coords
            right[offset:end] = coords
            offset = end
            continue

        if cyclic and count > 2:
            prev_points = np.roll(coords, 1, axis=0)
            next_points = np.roll(coords, -1, axis=0)
            tangent = (next_points - prev_points) / 6.0
            left[offset:end] = coords - tangent
            right[offset:end] = coords + tangent
            offset = end
            continue

        tangent = np.empty_like(coords)
        tangent[1:-1] = (coords[2:] - coords[:-2]) / 6.0
        tangent[0] = (coords[1] - coords[0]) / 3.0
        tangent[-1] = (coords[-1] - coords[-2]) / 3.0
        left[offset:end] = coords - tangent
        right[offset:end] = coords + tangent
        left[offset] = coords[0]
        right[end - 1] = coords[-1]
        offset = end
    return left, right


def _write_bezier_handles(
    curves,
    sizes: np.ndarray,
    positions: np.ndarray,
    cyclic: bool,
) -> None:
    if len(positions) == 0:
        return
    try:
        left, right = _bezier_handles_for_positions(sizes, positions, cyclic)
        left_attr = _ensure_curves_attribute(curves, "handle_left", "FLOAT_VECTOR", "POINT")
        right_attr = _ensure_curves_attribute(curves, "handle_right", "FLOAT_VECTOR", "POINT")
        _write_curves_data_values(left_attr.data, "vector", left)
        _write_curves_data_values(right_attr.data, "vector", right)

        # Blender applies explicit handle positions only to FREE handles.
        free_marker = np.full(len(positions), 0, dtype=np.int8)
        try:
            type_lookup = bpy.types.CurvesHandleType.FREE
            free_marker[:] = int(type_lookup)
        except (AttributeError, TypeError, ValueError):
            free_marker[:] = 0

        for attr_name in ("handle_type_left", "handle_type_right"):
            type_attr = _ensure_curves_attribute(curves, attr_name, "INT8", "POINT")
            _write_curves_data_values(type_attr.data, "value", free_marker)
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        pass


def _clear_bezier_handle_attributes(curves) -> None:
    _remove_curves_attribute(curves, "handle_left")
    _remove_curves_attribute(curves, "handle_right")
    _remove_curves_attribute(curves, "handle_type_left")
    _remove_curves_attribute(curves, "handle_type_right")


def _write_curves_points(
    curve_obj: bpy.types.Object,
    curves,
    positions: np.ndarray,
    radii: np.ndarray,
    item_eval,
) -> None:
    point_count = len(positions)
    if point_count == 0:
        return

    position_attr = curves.attributes.get("position")
    if position_attr is not None:
        _write_curves_data_values(position_attr.data, "vector", positions)
    else:
        _write_curves_data_values(curves.position_data, "vector", positions)

    try:
        fallback_radius = _trail_curves_radius(item_eval)
        if len(radii) == point_count:
            radius_values = np.ascontiguousarray(radii, dtype=np.float32)
            invalid = ~np.isfinite(radius_values) | (radius_values < 0.0)
            if np.all(invalid):
                radius_values = np.full(point_count, fallback_radius, dtype=np.float32)
            elif np.any(invalid):
                radius_values = radius_values.copy()
                radius_values[invalid] = fallback_radius
        else:
            radius_values = np.full(point_count, fallback_radius, dtype=np.float32)
        if len(radius_values) == point_count:
            invalid = ~np.isfinite(radius_values) | (radius_values < 0.0)
            if np.any(invalid):
                radius_values = radius_values.copy()
                radius_values[invalid] = fallback_radius
        radius_checksum = zlib.crc32(radius_values.view(np.uint8)) & 0xFFFFFFFF
        radius_signature = f"{point_count}:{radius_checksum:08x}"
        if (
            curve_obj.get(_TRAIL_RADIUS_SIGNATURE_PROP) == radius_signature
            and curves.attributes.get("radius") is not None
        ):
            return
        radius_attr = _ensure_curves_attribute(curves, "radius", "FLOAT", "POINT")
        _write_curves_data_values(radius_attr.data, "value", radius_values)
        curve_obj[_TRAIL_RADIUS_SIGNATURE_PROP] = radius_signature
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass


def _trail_color(item_eval) -> tuple[float, float, float, float]:
    color = tuple(float(v) for v in item_eval.trail_color)
    if len(color) == 4:
        return color
    return (1.0, 1.0, 1.0, 1.0)


def _trail_uses_point_color(item_eval) -> bool:
    if getattr(item_eval, "trail_color_mode", "STANDARD") == "GRADIENT":
        return True
    no_data = bool(getattr(item_eval, "trail_no_thickness_color_data", False))
    if no_data:
        return False
    return getattr(item_eval, "trail_vertex_color_mode", "PARTICLE") in {"PARTICLE", "PER_VERTEX"}


def _write_curves_color(
    curve_obj: bpy.types.Object,
    curves,
    color_values: np.ndarray,
    item_eval,
    point_count: int,
    *,
    force_attribute_color: bool = False,
) -> bool:
    if (
        point_count == 0
        or (not force_attribute_color and not _trail_uses_point_color(item_eval))
        or len(color_values) != point_count
    ):
        _remove_curves_color_attribute(curves, _TRAIL_COLOR_ATTRIBUTE)
        curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = ""
        return False

    try:
        colors = np.ascontiguousarray(color_values, dtype=np.float32)
        if not np.all(np.isfinite(colors)):
            colors = colors.copy()
            colors[~np.isfinite(colors)] = 1.0
        np.clip(colors, 0.0, 1.0, out=colors)
        checksum = zlib.crc32(colors.view(np.uint8)) & 0xFFFFFFFF
        signature = f"{_TRAIL_COLOR_ATTRIBUTE}:{point_count}:{checksum:08x}"
        if (
            curve_obj.get(_TRAIL_COLOR_SIGNATURE_PROP) == signature
            and curves.attributes.get(_TRAIL_COLOR_ATTRIBUTE) is not None
        ):
            return True
        color_attr = _ensure_curves_color_attribute(curves, _TRAIL_COLOR_ATTRIBUTE)
        _write_curves_data_values(color_attr.data, "color", colors)
        curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = signature
        return True
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _curves_topology_signature(sizes: np.ndarray) -> tuple[str, int]:
    if len(sizes) == 0:
        return "0:0:0", 0
    contiguous_sizes = np.ascontiguousarray(sizes, dtype=np.int32)
    total_points = int(np.sum(contiguous_sizes, dtype=np.int64))
    checksum = zlib.crc32(contiguous_sizes.view(np.uint8)) & 0xFFFFFFFF
    return f"{len(contiguous_sizes)}:{total_points}:{checksum:08x}", total_points


def _python_ints(values) -> list[int]:
    return [int(value) for value in values]


def _resize_curves(curve_obj: bpy.types.Object, curves, sizes: np.ndarray) -> bool:
    target_count = len(sizes)
    current_count = len(curves.curves)
    try:
        current_point_count = len(curves.points)
    except (AttributeError, RuntimeError, TypeError):
        current_point_count = -1
    signature, target_point_count = _curves_topology_signature(sizes)
    if (
        current_count == target_count
        and current_point_count == target_point_count
        and curve_obj.get(_TRAIL_TOPOLOGY_SIGNATURE_PROP) == signature
    ):
        return False

    if target_count == 0:
        if not _clear_curves_data(curves):
            return False
        curve_obj[_TRAIL_TOPOLOGY_SIGNATURE_PROP] = signature
        curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_RADIUS_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = ""
        return True

    if current_count == 0:
        curves.add_curves(_python_ints(sizes))
        curve_obj[_TRAIL_TOPOLOGY_SIGNATURE_PROP] = signature
        curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_RADIUS_SIGNATURE_PROP] = ""
        curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = ""
        return True

    resize_count = min(current_count, target_count)
    if resize_count:
        curves.resize_curves(
            _python_ints(sizes[:resize_count]),
            indices=list(range(resize_count)),
        )

    if target_count > current_count:
        curves.add_curves(_python_ints(sizes[current_count:]))
    elif target_count < current_count:
        curves.remove_curves(indices=list(range(target_count, current_count)))
    curve_obj[_TRAIL_TOPOLOGY_SIGNATURE_PROP] = signature
    curve_obj[_TRAIL_TYPE_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_CYCLIC_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_RADIUS_SIGNATURE_PROP] = ""
    curve_obj[_TRAIL_COLOR_SIGNATURE_PROP] = ""
    return True


def _configure_trail_curves_material(
    mat: bpy.types.Material,
    color: tuple[float, float, float, float],
    use_attribute_color: bool,
) -> None:
    signature = f"{int(use_attribute_color)}|" + ",".join(f"{channel:.6f}" for channel in color)
    if mat.get(_TRAIL_MATERIAL_SIGNATURE_PROP) == signature:
        return

    mat[_TRAIL_MATERIAL_PROP] = True
    mat.diffuse_color = color
    try:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")
        if bsdf is None:
            bsdf = next(
                (node for node in nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"),
                None,
            )
        if bsdf is None or "Base Color" not in bsdf.inputs:
            return

        base_input = bsdf.inputs["Base Color"]
        for link in list(base_input.links):
            links.remove(link)

        if use_attribute_color:
            attr = nodes.get("NX Trail Color")
            if attr is not None and attr.bl_idname != "ShaderNodeVertexColor":
                nodes.remove(attr)
                attr = None
            if attr is None:
                attr = nodes.new("ShaderNodeVertexColor")
                attr.name = "NX Trail Color"
                attr.label = "NX Trail Color"
            attr.layer_name = _TRAIL_COLOR_ATTRIBUTE
            links.new(attr.outputs["Color"], base_input)
        else:
            base_input.default_value = color

        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = color[3]
        mat[_TRAIL_MATERIAL_SIGNATURE_PROP] = signature
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        pass


def _trail_generated_material(curve_obj: bpy.types.Object, curves) -> bpy.types.Material | None:
    if curves.materials:
        mat = curves.materials[0]
        return mat if bool(mat.get(_TRAIL_MATERIAL_PROP, False)) else None

    mat = bpy.data.materials.new(f"{curve_obj.name}_material")
    mat[_TRAIL_MATERIAL_PROP] = True
    curves.materials.append(mat)
    return mat


def _set_object_color(curve_obj: bpy.types.Object, color: tuple[float, ...]) -> None:
    current = tuple(float(channel) for channel in curve_obj.color)
    if current != color:
        curve_obj.color = color


def _assign_trail_curves_material(
    curve_obj: bpy.types.Object, item_eval, use_attribute_color: bool
) -> None:
    color = _trail_color(item_eval)
    _set_object_color(curve_obj, color)
    data = curve_obj.data
    if data is None:
        return

    mat = _trail_generated_material(curve_obj, data)
    if mat is None:
        return
    _configure_trail_curves_material(mat, color, use_attribute_color)


def _float_array_crc32(values: np.ndarray) -> int:
    contiguous = np.ascontiguousarray(values, dtype=np.float32)
    return zlib.crc32(contiguous.view(np.uint8)) & 0xFFFFFFFF


def _trail_apply_signature(
    sizes: np.ndarray,
    positions: np.ndarray,
    radii: np.ndarray,
    color_values: np.ndarray,
    options: _SplineGenerationOptions,
    item_eval,
    gradient_lut: np.ndarray | None,
) -> str:
    topology, _ = _curves_topology_signature(sizes)
    pos_crc = _float_array_crc32(positions)
    radius_crc = _float_array_crc32(radii)
    color_crc = _float_array_crc32(color_values)
    color = ",".join(f"{channel:.6f}" for channel in _trail_color(item_eval))
    flags = f"{int(_trail_uses_point_color(item_eval))}{int(gradient_lut is not None)}"
    fallback_radius = _trail_curves_radius(item_eval)
    return (
        f"{topology}|{pos_crc:08x}|{radius_crc:08x}|{color_crc:08x}|"
        f"{options.signature_prefix}|{color}|{flags}|{fallback_radius:.6f}"
    )


def _update_trail_curves(
    curve_obj: bpy.types.Object,
    ranges,
    points: np.ndarray,
    colors: np.ndarray | None,
    gradient_lut: np.ndarray | None,
    item_eval,
) -> None:
    curves = curve_obj.data
    if curves is None or curve_obj.type != "CURVES":
        return

    options = _SplineGenerationOptions(item_eval)
    ranges_array = _ranges_array(ranges)
    sizes, positions, radii, color_values = _build_curves_payload(
        ranges_array, points, colors, gradient_lut, options
    )

    apply_signature = _trail_apply_signature(
        sizes, positions, radii, color_values, options, item_eval, gradient_lut
    )
    cached_signature = curve_obj.get(_TRAIL_APPLY_SIGNATURE_PROP)
    if cached_signature == apply_signature and len(curves.curves) == len(sizes):
        return

    topology_changed = _resize_curves(curve_obj, curves, sizes)
    curve_count = len(sizes)
    _set_curves_type(curve_obj, curves, options.curves_type, curve_count, force=topology_changed)
    _set_curves_cyclic(curve_obj, curves, options.cyclic, curve_count, force=topology_changed)
    _write_curves_points(curve_obj, curves, positions, radii, item_eval)
    use_attribute_color = _write_curves_color(
        curve_obj,
        curves,
        color_values,
        item_eval,
        len(positions),
        force_attribute_color=gradient_lut is not None,
    )
    _assign_trail_curves_material(curve_obj, item_eval, use_attribute_color)
    if options.curves_type == "BEZIER":
        _write_bezier_handles(curves, sizes, positions, options.cyclic)
    elif topology_changed or curves.attributes.get("handle_left") is not None:
        _clear_bezier_handle_attributes(curves)

    curves.update_tag()
    curve_obj.update_tag()
    curve_obj[_TRAIL_APPLY_SIGNATURE_PROP] = apply_signature


def _group_ranges_by_source_id(
    ranges_struct: np.ndarray,
) -> dict[int, np.ndarray]:
    if ranges_struct is None or len(ranges_struct) == 0:
        return {}
    valid = (ranges_struct["firstPoint"] >= 0) & (ranges_struct["pointCount"] >= 2)
    if not np.any(valid):
        return {}

    grouped: dict[int, np.ndarray] = {}
    valid_rows = ranges_struct[valid]
    unique_sources = np.unique(valid_rows["sourceId"])
    for source_id in unique_sources:
        subset = valid_rows[valid_rows["sourceId"] == source_id]
        pairs = np.stack(
            (subset["firstPoint"].astype(np.int32), subset["pointCount"].astype(np.int32)),
            axis=1,
        )
        grouped[int(source_id)] = np.ascontiguousarray(pairs, dtype=np.int32)
    return grouped


def _active_trail_emitters(
    props_orig, props_eval=None
) -> list[tuple[object, object, bpy.types.Object, str]]:
    from ..libs.nodetree_sync import resolve_evaluated_item

    items_orig = getattr(props_orig, "trail_emitters", ())
    items_eval = (
        getattr(props_eval, "trail_emitters", items_orig) if props_eval is not None else items_orig
    )
    emitters: list[tuple[object, object, bpy.types.Object, str]] = []
    for index, item_orig in enumerate(items_orig):
        item_eval = resolve_evaluated_item(items_eval, index, item_orig)
        if not getattr(item_eval, "enabled", False):
            continue
        emitter_obj = getattr(item_orig, "obj", None)
        if emitter_obj is None or emitter_obj.get("nexus_modifier_type") != "NX_EMITTER":
            continue
        source_uid = getattr(item_orig, "layer_uid", "")
        if not source_uid:
            continue
        emitters.append((item_orig, item_eval, emitter_obj, source_uid))
    return emitters


def _read_trail_spline_snapshot(
    scene: bpy.types.Scene,
    pipeline: int,
):
    from ..handlers import pipeline as pipeline_manager
    from ..libs import theron

    aux = _aux_for(pipeline)
    frame_subframe = int(round(float(getattr(scene, "frame_subframe", 0.0)) * 1_000_000))
    cache_key = (
        pipeline,
        pipeline_manager.get_execution_tick(),
        int(scene.frame_current),
        frame_subframe,
    )
    cached = aux.spline_cache
    if cached is not None and cached[0] == cache_key:
        return cached[1]

    readback = theron.read_trail_spline_data(pipeline)
    if readback is None:
        result = None
    else:
        grouped = _group_ranges_by_source_id(readback.ranges)
        points = np.asarray(readback.points, dtype=np.float32)
        colors = (
            np.asarray(readback.colors, dtype=np.float32)
            if readback.colors is not None and len(readback.colors) > 0
            else None
        )
        result = (grouped, points, colors)

    aux.spline_cache = (cache_key, result)
    return result


def _gather_post_execute_payload(
    scene: bpy.types.Scene,
    trail_obj: bpy.types.Object,
    pipeline: int,
    props,
    props_eval,
) -> dict | None:
    from ..pipeline_manager.identity import get_object_uid

    trail_uid = get_object_uid(trail_obj)
    if trail_uid is None:
        return None

    snapshot = _read_trail_spline_snapshot(scene, pipeline)
    if snapshot is None:
        return {"trail_uid": trail_uid, "rows": []}

    grouped, points, colors = snapshot

    rows: list[dict] = []
    for item_orig, item_eval, emitter_obj, source_uid in _active_trail_emitters(props, props_eval):
        entry = _trail_source_cache.get((trail_uid, source_uid, pipeline))
        if entry is None:
            continue
        source_id = entry[1]
        emitter_uid = get_object_uid(emitter_obj)
        if emitter_uid is None:
            continue
        gradient_lut = _trail_gradient_lut(trail_obj, item_orig, item_eval)
        ranges = grouped.get(source_id)
        if ranges is None:
            ranges = np.empty((0, 2), dtype=np.int32)
        rows.append(
            {
                "source_uid": source_uid,
                "source_obj_uid": emitter_uid,
                "ranges": ranges,
                "gradient_lut": gradient_lut,
                "item_eval_snapshot": _snapshot_item_for_curves(item_eval),
            }
        )

    return {
        "trail_uid": trail_uid,
        "rows": rows,
        "points": points,
        "colors": colors,
    }


def _snapshot_item_for_curves(item_eval) -> "_TrailItemSnapshot":
    return _TrailItemSnapshot(
        trail_spline_type=getattr(item_eval, "trail_spline_type", "LINEAR"),
        trail_spline_close=bool(getattr(item_eval, "trail_spline_close", False)),
        trail_spline_intermediate=getattr(item_eval, "trail_spline_intermediate", "NONE"),
        trail_spline_number=int(getattr(item_eval, "trail_spline_number", 0)),
        trail_spline_angle=float(getattr(item_eval, "trail_spline_angle", 0.0)),
        trail_spline_use_max_length=bool(getattr(item_eval, "trail_spline_use_max_length", False)),
        trail_spline_max_length=float(getattr(item_eval, "trail_spline_max_length", 0.0)),
        trail_color_mode=getattr(item_eval, "trail_color_mode", "STANDARD"),
        trail_color=tuple(float(c) for c in getattr(item_eval, "trail_color", (1.0,) * 4)),
        trail_thickness_mode=getattr(item_eval, "trail_thickness_mode", "NONE"),
        trail_thickness_value=float(getattr(item_eval, "trail_thickness_value", 0.01)),
        trail_thickness_spline_max=float(getattr(item_eval, "trail_thickness_spline_max", 0.01)),
        trail_no_thickness_color_data=bool(
            getattr(item_eval, "trail_no_thickness_color_data", False)
        ),
        trail_vertex_color_mode=getattr(item_eval, "trail_vertex_color_mode", "PARTICLE"),
    )


class _TrailItemSnapshot:
    __slots__ = (
        "trail_spline_type",
        "trail_spline_close",
        "trail_spline_intermediate",
        "trail_spline_number",
        "trail_spline_angle",
        "trail_spline_use_max_length",
        "trail_spline_max_length",
        "trail_color_mode",
        "trail_color",
        "trail_thickness_mode",
        "trail_thickness_value",
        "trail_thickness_spline_max",
        "trail_no_thickness_color_data",
        "trail_vertex_color_mode",
    )

    def __init__(self, **kwargs) -> None:
        for name in self.__slots__:
            setattr(self, name, kwargs[name])


def _apply_curves_payload_deferred(scene_session_uid: int, trail_uid: str, payload: dict) -> None:
    from ..pipeline_manager.identity import get_object_uid

    scene = next(
        (s for s in bpy.data.scenes if s.session_uid == scene_session_uid),
        None,
    )
    trail_obj = next(
        (o for o in bpy.data.objects if get_object_uid(o) == trail_uid),
        None,
    )
    if scene is None or trail_obj is None:
        return
    if trail_obj.get("nexus_modifier_type") != "NX_TRAIL":
        return

    rows = payload.get("rows", [])
    if not rows:
        _remove_stale_trail_curves(trail_obj, set())
        return

    trail_uid_payload = payload["trail_uid"]
    points = payload.get("points")
    colors = payload.get("colors")

    active_source_uids = {row["source_uid"] for row in rows}
    _remove_stale_trail_curves(trail_obj, active_source_uids)

    objects_by_uid = {get_object_uid(o): o for o in bpy.data.objects}
    for row in rows:
        source_obj = objects_by_uid.get(row["source_obj_uid"])
        if source_obj is None:
            continue
        curve_obj = _ensure_trail_curve_child(
            scene, trail_obj, trail_uid_payload, source_obj, row["source_uid"]
        )
        if curve_obj.hide_viewport:
            curve_obj.hide_viewport = False
        if curve_obj.hide_render:
            curve_obj.hide_render = False
        _update_trail_curves(
            curve_obj,
            row["ranges"],
            points if points is not None else np.empty((0, 4), dtype=np.float32),
            colors,
            row["gradient_lut"],
            row["item_eval_snapshot"],
        )


def _schedule_curves_apply(scene_session_uid: int, trail_uid: str, payload: dict) -> None:
    def _deferred():
        try:
            _apply_curves_payload_deferred(scene_session_uid, trail_uid, payload)
        except (ReferenceError, RuntimeError):
            return None
        return None

    _safe_register_timer(_deferred)


class NXTrailModifier(NexusModifier):
    object_type = "NX_TRAIL"
    object_name = "nxTrail"
    object_label = "Trail"
    object_description = "Render GPU-resident particle trails as a viewport overlay or curves"
    icon_name = "nx_trail"
    category = "Generators"
    menu_category = MenuCategory.GENERATORS
    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (_TRAIL_SOURCE_SPEC,)
    handles_own_sync = True

    @classmethod
    def get_theron_type(cls, _obj: bpy.types.Object) -> str | None:
        return None

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_tabs(cls, _props) -> list[tuple[str, str]]:
        return []

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_trail_ui_config()

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "trail_display")

        layout.separator()

        cls.draw_property(layout, data, "trail_emitters", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, _props, _context) -> None:
        pass

    @classmethod
    def sync_to_pipeline(
        cls,
        obj: bpy.types.Object,
        scene: bpy.types.Scene,
        *,
        pipeline_handle: int,
        disabled: bool,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        from ..handlers.pipeline import get_emitter_index
        from ..libs import theron
        from ..libs.nodetree_sync import resolve_evaluated_item
        from ..pipeline_manager.identity import ensure_object_uid

        mod_uid = ensure_object_uid(obj)

        if depsgraph is not None:
            try:
                eval_obj = obj.evaluated_get(depsgraph)
                props = eval_obj.nexus_modifier
            except (RuntimeError, AttributeError):
                props = obj.nexus_modifier
        else:
            props = obj.nexus_modifier
        original_props = obj.nexus_modifier
        collection_orig = original_props.trail_emitters
        collection_eval = props.trail_emitters

        if theron.get_trail_source_count(pipeline_handle) == 0:
            _drop_stale_entries_for_pipeline(pipeline_handle)

        aux = _aux_for(pipeline_handle)
        active_source_uids: set[str] = set()

        emit_chains = getattr(props, "trail_display", "LINES") == "SPLINES"

        for index, item_orig in enumerate(collection_orig):
            item_eval = resolve_evaluated_item(collection_eval, index, item_orig)

            if item_orig.obj is None:
                continue

            source_uid = getattr(item_orig, "layer_uid", "")
            if not source_uid:
                continue
            emitter_index = get_emitter_index(scene, item_orig.obj)
            if emitter_index is None:
                continue

            active_source_uids.add(source_uid)
            row_key = (mod_uid, source_uid, pipeline_handle)
            desc = _build_desc(item_eval, emitter_index, scene, emit_chains=emit_chains)
            if disabled:
                desc.enabled = 0
            entry = _trail_source_cache.get(row_key)

            if entry is not None:
                cached_pipeline, source_id, gradient_sig, curve_sig = entry
                if cached_pipeline == pipeline_handle and theron.update_trail_source(
                    pipeline_handle, source_id, desc
                ):
                    gradient_sig, curve_sig = _sync_trail_source_resources(
                        aux,
                        pipeline_handle,
                        source_id,
                        obj,
                        item_eval,
                        item_orig,
                        gradient_sig,
                        curve_sig,
                    )
                    _trail_source_cache[row_key] = (
                        pipeline_handle,
                        source_id,
                        gradient_sig,
                        curve_sig,
                    )
                    continue
                if cached_pipeline == pipeline_handle:
                    theron.remove_trail_source(pipeline_handle, source_id)
                _trail_source_cache.pop(row_key, None)

            new_id = theron.add_trail_source(pipeline_handle, desc)
            if new_id is not None:
                gradient_sig, curve_sig = _sync_trail_source_resources(
                    aux,
                    pipeline_handle,
                    new_id,
                    obj,
                    item_eval,
                    item_orig,
                    "",
                    "",
                )
                _trail_source_cache[row_key] = (
                    pipeline_handle,
                    new_id,
                    gradient_sig,
                    curve_sig,
                )

        evict_stale_entries_for(
            _TRAIL_SOURCE_SPEC,
            mod_uid,
            active_source_uids,
            entry_filter=lambda _key, entry: entry[0] == pipeline_handle,
        )
        if disabled:
            _schedule_modifier_curves_cleanup(mod_uid)

    @classmethod
    def post_execute_pipeline(
        cls,
        obj: bpy.types.Object,
        pipeline_handle: int,
        props,
        scene: bpy.types.Scene,
        *,
        depsgraph: bpy.types.Depsgraph | None = None,
    ) -> None:
        props_eval = None
        if depsgraph is not None:
            try:
                props_eval = obj.evaluated_get(depsgraph).nexus_modifier
            except (AttributeError, ReferenceError, RuntimeError):
                props_eval = None
        scalar_props = props_eval if props_eval is not None else props
        from ..pipeline_manager.identity import get_object_uid

        trail_uid = get_object_uid(obj)
        if trail_uid is None:
            return
        scene_session_uid = scene.session_uid

        if getattr(scalar_props, "trail_display", "LINES") != "SPLINES":
            _schedule_curves_apply(scene_session_uid, trail_uid, {"trail_uid": "", "rows": []})
            return

        payload = _gather_post_execute_payload(scene, obj, pipeline_handle, props, props_eval)
        if payload is None:
            return
        _schedule_curves_apply(scene_session_uid, trail_uid, payload)

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        _remove_modifier_trail_sources(mod_uid)
        _schedule_modifier_curves_cleanup(mod_uid)

    @classmethod
    def on_pipeline_destroy(cls, pipeline_handle: int, *, free_resources: bool = True) -> None:
        _clear_pipeline_trail_state(pipeline_handle, free_resources=free_resources)

    @classmethod
    def on_state_clear(cls, *, free_resources: bool = True) -> None:
        pipelines = {entry[0] for entry in _trail_source_cache.values()}
        pipelines.update(_pipeline_aux)
        if free_resources:
            for pipeline in list(pipelines):
                if pipeline:
                    _clear_pipeline_trail_state(pipeline, free_resources=True)
            _schedule_curves_global_cleanup()
        else:
            _trail_source_cache.clear()
            _pipeline_aux.clear()


def _schedule_modifier_curves_cleanup(mod_uid: str) -> None:
    def _deferred():
        for obj in list(bpy.data.objects):
            if obj.get("nexus_object_type") != _TRAIL_CURVE_OBJECT_TYPE:
                continue
            if obj.get(_TRAIL_PARENT_UID_PROP) == mod_uid:
                _remove_curve_object_now(obj)
        return None

    _safe_register_timer(_deferred)


def _schedule_curves_global_cleanup() -> None:
    def _deferred():
        for obj in list(bpy.data.objects):
            if obj.get("nexus_object_type") == _TRAIL_CURVE_OBJECT_TYPE:
                _clear_trail_curve(obj)
        return None

    _safe_register_timer(_deferred)
