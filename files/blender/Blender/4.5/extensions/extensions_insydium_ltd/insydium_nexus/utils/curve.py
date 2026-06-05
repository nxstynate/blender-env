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
import os

import bpy
import numpy as np
from bpy.types import CurveMapPoint

from ..libs.resource_spec import CurveSpec
from ._node_store import NodeStore, NodeStoreConfig

NEXUS_CURVE_MATERIAL_NAME = ".NexusCurves"
_CURVE_NODE_TYPE = "ShaderNodeRGBCurve"

_store = NodeStore(
    NodeStoreConfig(
        material_name=NEXUS_CURVE_MATERIAL_NAME,
        uid_prop="_nexus_curve_id",
        node_prefix=".nxc.",
    )
)


def resolve_curve_slot_name(curve_spec: CurveSpec, source=None) -> str | None:
    if isinstance(source, str):
        suffix = source
    elif source is None or curve_spec.slot_suffix_attr is None:
        suffix = None
    else:
        suffix = getattr(source, curve_spec.slot_suffix_attr, "")
        if not suffix:
            return None

    if suffix is None:
        return curve_spec.slot_name
    return f"{curve_spec.slot_name}_{suffix}"


def generate_curve_id() -> str:
    return os.urandom(4).hex()


def _node_name(curve_id: str, slot_name: str) -> str:
    return _store.node_name(curve_id, slot_name)


def _get_curve_material():
    return _store.ensure_material()


def _get_curve_id(obj) -> str | None:
    return _store.get_uid(obj)


def _set_curve_id(obj, cid: str):
    _store.set_uid(obj, cid)


def _apply_default_points(node, points: list[tuple[float, float]]):
    mapping = node.mapping
    mapping.use_clip = True
    mapping.clip_min_x = 0.0
    mapping.clip_max_x = 1.0
    mapping.clip_min_y = 0.0
    mapping.clip_max_y = 1.0

    curve = mapping.curves[3]
    if len(points) >= 2:
        curve.points[0].location = points[0]
        curve.points[1].location = points[-1]
        for px, py in points[1:-1]:
            curve.points.new(px, py)

    mapping.update()


def _create_curve_node(mat, node_name: str, points: list[tuple[float, float]]):
    node = mat.node_tree.nodes.new(_CURVE_NODE_TYPE)
    node.name = node_name
    _apply_default_points(node, points)
    return node


def create_curve_nodes(obj, curve_specs: list[CurveSpec]):
    cid = generate_curve_id()
    _store.set_uid(obj, cid)

    mat = _store.ensure_material()
    for curve_spec in curve_specs:
        name = _store.node_name(cid, curve_spec.slot_name)
        if mat.node_tree.nodes.get(name) is None:
            _create_curve_node(mat, name, curve_spec.default_points)


def get_curve_node_for_slot(obj, slot_name: str):
    return _store.get_node(obj, slot_name)


def get_curve_node_by_id(curve_id: str, slot_name: str):
    return _store.get_node_by_uid(curve_id, slot_name)


def _slot_from_node_name(uid: str, node_name: str) -> str | None:
    prefix = _store.node_name(uid, "")
    if not node_name.startswith(prefix):
        return None
    return node_name[len(prefix) :]


def _extract_curve_state(
    node,
) -> tuple[list[tuple[float, float]], list[str], tuple[float, float, float, float]]:
    curve = node.mapping.curves[3]
    points = [(point.location[0], point.location[1]) for point in curve.points]
    handles = [point.handle_type for point in curve.points]
    clip = (
        node.mapping.clip_min_x,
        node.mapping.clip_max_x,
        node.mapping.clip_min_y,
        node.mapping.clip_max_y,
    )
    return points, handles, clip


def ensure_curve_ownership(obj, curve_specs: list[CurveSpec] | None = None):
    cid = _store.get_uid(obj)
    if cid is None:
        if curve_specs:
            create_curve_nodes(obj, curve_specs)
        return

    if not _store.is_shared(obj):
        return

    mat = _store.get_material()
    if mat is None or mat.node_tree is None:
        if curve_specs:
            create_curve_nodes(obj, curve_specs)
        return

    old_nodes: dict[str, object] = {}
    for node in mat.node_tree.nodes:
        slot_name = _slot_from_node_name(cid, node.name)
        if slot_name is not None:
            old_nodes[slot_name] = node

    new_cid = _store.rotate_uid(obj)

    for slot_name, old_node in old_nodes.items():
        new_name = _store.node_name(new_cid, slot_name)
        points, handles, clip = _extract_curve_state(old_node)
        new_node = _create_curve_node(mat, new_name, points)
        new_curve = new_node.mapping.curves[3]
        for idx, point in enumerate(new_curve.points):
            if idx < len(handles):
                point.handle_type = handles[idx]
        new_node.mapping.clip_min_x = clip[0]
        new_node.mapping.clip_max_x = clip[1]
        new_node.mapping.clip_min_y = clip[2]
        new_node.mapping.clip_max_y = clip[3]
        new_node.mapping.update()

    if curve_specs:
        for curve_spec in curve_specs:
            if curve_spec.slot_name in old_nodes:
                continue
            new_name = _store.node_name(new_cid, curve_spec.slot_name)
            _create_curve_node(mat, new_name, curve_spec.default_points)


def remove_curve_nodes(obj):
    _store.remove_nodes_for(obj)


def create_item_curves(obj, source, curve_specs: list[CurveSpec]):
    """Create curve nodes for a collection item, under the object's curve namespace."""
    cid = _store.get_or_create_uid(obj)
    mat = _store.ensure_material()
    for curve_spec in curve_specs:
        slot = resolve_curve_slot_name(curve_spec, source)
        if slot is None:
            continue
        name = _store.node_name(cid, slot)
        if mat.node_tree.nodes.get(name) is None:
            _create_curve_node(mat, name, curve_spec.default_points)


def remove_item_curves(obj, source, curve_specs: list[CurveSpec]):
    """Remove curve nodes for a collection item."""
    cid = _store.get_uid(obj)
    if cid is None:
        return

    mat = _store.get_material()
    if mat is None or mat.node_tree is None:
        return

    for curve_spec in curve_specs:
        slot = resolve_curve_slot_name(curve_spec, source)
        if slot is None:
            continue
        node = mat.node_tree.nodes.get(_store.node_name(cid, slot))
        if node is not None:
            mat.node_tree.nodes.remove(node)


def cleanup_orphaned_curve_nodes():
    _store.cleanup_orphans()


class NexusCurve:
    __slots__ = ("_curve_id", "_object_name", "_slot_name")

    def __init__(self, obj_or_id, slot_name: str):
        if isinstance(obj_or_id, str):
            self._curve_id = obj_or_id
            self._object_name = ""
        else:
            self._curve_id = obj_or_id.get("_nexus_curve_id", "")
            self._object_name = obj_or_id.name
        self._slot_name = slot_name

    def __bool__(self):
        return self.node is not None

    @property
    def node(self):
        if not self._curve_id:
            return None
        return _store.get_node_by_uid(self._curve_id, self._slot_name)

    @property
    def mapping(self):
        node = self.node
        return node.mapping if node is not None else None

    @property
    def curve(self):
        mapping = self.mapping
        return mapping.curves[3] if mapping is not None else None

    def extract_points(self) -> list[tuple[float, float]] | None:
        curve = self.curve
        if curve is None:
            return None
        return [(point.location[0], point.location[1]) for point in curve.points]

    def get_curve_knots(self) -> list[CurveMapPoint] | None:
        curve = self.curve
        if curve is None:
            return None
        return curve.points

    def draw_ui(self, layout, label: str, enabled: bool = True):
        from ..icons import get_icon

        node = self.node
        if node is None:
            return
        row = layout.row()
        row.enabled = enabled
        split = row.split(factor=0.385)
        split.use_property_split = False
        label_row = split.row()
        label_row.alignment = "RIGHT"
        label_row.label(text=label)
        op = label_row.operator(
            "nexus.curve_preset_popup",
            text="",
            icon_value=get_icon("nx_curve_preset"),
        )
        op.curve_id = self._curve_id
        op.object_name = self._object_name
        op.slot_name = self._slot_name
        content_col = split.column()
        content_col.template_curve_mapping(node, "mapping", type="NONE", levels=False)


def make_obj_curve_callback(curve_specs: list[CurveSpec]):
    """PointerProperty update callback factory for per-item curve wire-up."""

    def on_obj_update(self, context):
        del context
        if self.obj is None:
            return
        if not self.curve_id:
            self.curve_id = generate_curve_id()
            create_item_curves(self.id_data, self.curve_id, curve_specs)

    return on_obj_update


def make_layer_curve_callbacks(type_curve_specs):
    """Create on_add/on_remove callbacks for typed nodetree layers with per-item curves.

    Args:
        type_curve_specs: dict mapping item_type string to a callable returning list[CurveSpec].
            Example: {"OFFSET": get_offset_defs, "TWIST": get_twist_defs}

    Returns:
        (on_add, on_remove) callback tuple for register_nodetree().
    """

    def on_add(context, obj, item):
        del context
        specs_fn = type_curve_specs.get(item.item_type)
        if specs_fn is None:
            return
        item.layer_uid = os.urandom(4).hex()
        create_item_curves(obj, item.layer_uid, specs_fn())

    def on_remove(context, obj, item):
        del context
        if not item.layer_uid:
            return
        specs_fn = type_curve_specs.get(item.item_type)
        if specs_fn is None:
            return
        remove_item_curves(obj, item.layer_uid, specs_fn())

    return on_add, on_remove


def sync_curve_to_theron(
    theron,
    container,
    obj,
    slot_name: str,
    param_id,
    *,
    default_ramp: list[tuple[float, float]],
):
    """Extract a Blender curve and push it to a Theron spline."""
    curve = NexusCurve(obj, slot_name)

    knots = curve.get_curve_knots()

    spline = theron.create_spline(container, param_id)
    if spline is None:
        return

    spline_len = len(knots) if knots is not None else len(default_ramp)
    theron.resize_spline(spline, spline_len)

    if knots is None:
        for idx, (x, y) in enumerate(default_ramp):
            theron.set_spline_knot(spline, idx, x, y, "VECTOR")
    else:
        for idx, knot in enumerate(knots):
            theron.set_spline_knot(spline, idx, knot.location.x, knot.location.y, knot.handle_type)


_curve_fast_write_available: bool | None = None


def _curve_point_base_and_stride(points) -> tuple[int, int] | None:
    point_count = len(points)
    if point_count == 0:
        return None

    base = points[0].as_pointer()
    if point_count == 1:
        return (base, 0)

    stride = points[1].as_pointer() - base
    if stride < 16:
        return None
    if point_count > 2 and points[2].as_pointer() - points[1].as_pointer() != stride:
        return None
    return (base, stride)


def fast_write_curve_points(points, xyzw: np.ndarray) -> bool:
    """Memmove float4 rows into a POLY/NURBS spline; False on layout/size mismatch."""
    point_count = len(points)
    if point_count != len(xyzw):
        return False
    if point_count == 0:
        return True
    if point_count == 1:
        points[0].co = tuple(float(v) for v in xyzw[0])
        return True

    ptr_stride = _curve_point_base_and_stride(points)
    if ptr_stride is None:
        return False

    base, stride = ptr_stride
    byte_count = stride * (point_count - 1) + 16
    raw = (ctypes.c_char * byte_count).from_address(base)
    dst = np.ndarray(
        shape=(point_count, 4),
        dtype=np.float32,
        buffer=raw,
        strides=(stride, 4),
    )
    dst[:] = xyzw
    return True


def _probe_curve_point_fast_write() -> bool:
    curve = bpy.data.curves.new("_nexus_curve_fast_write_probe", "CURVE")
    try:
        curve.dimensions = "3D"
        spline = curve.splines.new("POLY")
        spline.points.add(2)

        values = np.array(
            (
                (1.25, 2.5, 3.75, 1.0),
                (-4.0, 5.5, -6.25, 1.0),
                (7.0, -8.0, 9.0, 1.0),
            ),
            dtype=np.float32,
        )
        if not fast_write_curve_points(spline.points, values):
            return False

        for index, expected in enumerate(values):
            actual = spline.points[index].co
            if any(abs(float(actual[i]) - float(expected[i])) > 1.0e-6 for i in range(4)):
                return False
        return True
    except (AttributeError, RuntimeError, ValueError, TypeError):
        return False
    finally:
        bpy.data.curves.remove(curve)


def can_fast_write_curve_points() -> bool:
    global _curve_fast_write_available

    if _curve_fast_write_available is None:
        _curve_fast_write_available = _probe_curve_point_fast_write()
    return _curve_fast_write_available


def write_spline_points(spline: bpy.types.Spline, xyzw: np.ndarray) -> None:
    global _curve_fast_write_available

    coords = np.ascontiguousarray(xyzw, dtype=np.float32)
    if can_fast_write_curve_points():
        try:
            if fast_write_curve_points(spline.points, coords):
                return
        except (BufferError, RuntimeError, ValueError, TypeError):
            _curve_fast_write_available = False

    spline.points.foreach_set("co", coords.ravel())
