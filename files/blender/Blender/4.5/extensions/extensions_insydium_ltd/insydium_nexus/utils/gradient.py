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

import os

from ..libs.resource_spec import GradientSpec
from ..libs.theron_bindings import (
    TrGradientColorMode,
    TrGradientHueInterpolation,
    TrGradientKnotInterpolation,
)
from ._node_store import NodeStore, NodeStoreConfig

NEXUS_GRADIENT_MATERIAL_NAME = ".NexusGradients"
_GRADIENT_NODE_TYPE = "ShaderNodeValToRGB"
LUT_SIZE = 256

_store = NodeStore(
    NodeStoreConfig(
        material_name=NEXUS_GRADIENT_MATERIAL_NAME,
        uid_prop="_nexus_gradient_id",
        node_prefix=".nxg.",
    )
)

_lut_cache: dict[str, tuple[list, int]] = {}


def resolve_gradient_slot_name(gradient_spec: GradientSpec, source=None) -> str | None:
    if isinstance(source, str):
        suffix = source
    elif source is None or gradient_spec.slot_suffix_attr is None:
        suffix = None
    else:
        suffix = getattr(source, gradient_spec.slot_suffix_attr, "")
        if not suffix:
            return None

    if suffix is None:
        return gradient_spec.slot_name
    return f"{gradient_spec.slot_name}_{suffix}"


def build_default_gradient_stops_data(gradient_spec: GradientSpec) -> dict:
    stops = [
        (position, color[0], color[1], color[2], color[3])
        for position, color in gradient_spec.default_stops
    ]
    return {
        "stops": stops,
        "interpolation": gradient_spec.default_interpolation,
        "color_mode": gradient_spec.default_color_mode,
        "hue_interpolation": gradient_spec.default_hue_interpolation,
        "num_stops": len(stops),
    }


def _generate_gradient_id() -> str:
    return os.urandom(4).hex()


def _node_name(gradient_id: str, slot_name: str) -> str:
    return _store.node_name(gradient_id, slot_name)


def _get_gradient_material():
    return _store.ensure_material()


def _get_gradient_id(obj) -> str | None:
    return _store.get_uid(obj)


def _set_gradient_id(obj, gid: str):
    _store.set_uid(obj, gid)


def _apply_default_stops(node, stops: list[tuple[float, tuple[float, float, float, float]]]):
    sorted_stops = sorted(stops, key=lambda stop: stop[0])
    ramp = node.color_ramp

    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[1])

    ramp.elements[0].position = sorted_stops[0][0]
    ramp.elements[0].color = sorted_stops[0][1]
    ramp.elements[1].position = sorted_stops[-1][0]
    ramp.elements[1].color = sorted_stops[-1][1]

    for position, color in sorted_stops[1:-1]:
        elem = ramp.elements.new(position)
        elem.color = color


def _apply_gradient_defaults(
    node,
    *,
    interpolation: str = "LINEAR",
    color_mode: str = "RGB",
    hue_interpolation: str = "NEAR",
):
    ramp = node.color_ramp
    ramp.interpolation = interpolation
    ramp.color_mode = color_mode
    ramp.hue_interpolation = hue_interpolation


def _create_gradient_node(
    mat,
    node_name: str,
    stops: list[tuple[float, tuple[float, float, float, float]]],
    *,
    interpolation: str = "LINEAR",
    color_mode: str = "RGB",
    hue_interpolation: str = "NEAR",
):
    node = mat.node_tree.nodes.new(_GRADIENT_NODE_TYPE)
    node.name = node_name
    _apply_default_stops(node, stops)
    _apply_gradient_defaults(
        node,
        interpolation=interpolation,
        color_mode=color_mode,
        hue_interpolation=hue_interpolation,
    )
    return node


def create_gradient_nodes(obj, gradient_specs: list[GradientSpec]):
    gid = _generate_gradient_id()
    _store.set_uid(obj, gid)

    mat = _store.ensure_material()
    for gradient_spec in gradient_specs:
        name = _store.node_name(gid, gradient_spec.slot_name)
        if mat.node_tree.nodes.get(name) is None:
            _create_gradient_node(
                mat,
                name,
                gradient_spec.default_stops,
                interpolation=gradient_spec.default_interpolation,
                color_mode=gradient_spec.default_color_mode,
                hue_interpolation=gradient_spec.default_hue_interpolation,
            )


def ensure_gradient_nodes(obj, gradient_specs: list[GradientSpec]):
    """Create any missing gradient nodes for `obj` without altering existing ones.

    Unlike ``create_gradient_nodes``, this preserves any of the object's existing
    gradient UID and only creates fresh ones for  slots that don't already have a node.
    This is useful for migrating .blend files saved before a modifier class gained a
    new gradient.
    """
    gid = _store.get_or_create_uid(obj)
    mat = _store.ensure_material()
    for gradient_spec in gradient_specs:
        name = _store.node_name(gid, gradient_spec.slot_name)
        if mat.node_tree.nodes.get(name) is None:
            _create_gradient_node(
                mat,
                name,
                gradient_spec.default_stops,
                interpolation=gradient_spec.default_interpolation,
                color_mode=gradient_spec.default_color_mode,
                hue_interpolation=gradient_spec.default_hue_interpolation,
            )


def get_gradient_node_for_slot(obj, slot_name: str):
    return _store.get_node(obj, slot_name)


def get_gradient_node_by_id(gradient_id: str, slot_name: str):
    return _store.get_node_by_uid(gradient_id, slot_name)


def _slot_from_node_name(uid: str, node_name: str) -> str | None:
    prefix = _store.node_name(uid, "")
    if not node_name.startswith(prefix):
        return None
    return node_name[len(prefix) :]


def ensure_gradient_ownership(obj, gradient_specs: list[GradientSpec] | None = None):
    gid = _store.get_uid(obj)
    if gid is None:
        if gradient_specs:
            create_gradient_nodes(obj, gradient_specs)
        return

    if not _store.is_shared(obj):
        return

    mat = _store.get_material()
    if mat is None or mat.node_tree is None:
        if gradient_specs:
            create_gradient_nodes(obj, gradient_specs)
        return

    old_nodes: dict[str, object] = {}
    for node in mat.node_tree.nodes:
        slot_name = _slot_from_node_name(gid, node.name)
        if slot_name is not None:
            old_nodes[slot_name] = node

    new_gid = _store.rotate_uid(obj)

    for slot_name, old_node in old_nodes.items():
        new_name = _store.node_name(new_gid, slot_name)
        old_ramp = old_node.color_ramp
        stops = [(elem.position, tuple(elem.color)) for elem in old_ramp.elements]
        new_node = _create_gradient_node(mat, new_name, stops)
        new_node.color_ramp.interpolation = old_ramp.interpolation
        new_node.color_ramp.color_mode = old_ramp.color_mode
        new_node.color_ramp.hue_interpolation = old_ramp.hue_interpolation

    if gradient_specs:
        for gradient_spec in gradient_specs:
            if gradient_spec.slot_name in old_nodes:
                continue
            new_name = _store.node_name(new_gid, gradient_spec.slot_name)
            _create_gradient_node(
                mat,
                new_name,
                gradient_spec.default_stops,
                interpolation=gradient_spec.default_interpolation,
                color_mode=gradient_spec.default_color_mode,
                hue_interpolation=gradient_spec.default_hue_interpolation,
            )


def remove_gradient_nodes(obj):
    _store.remove_nodes_for(obj)


def create_item_gradients(obj, source, gradient_specs: list[GradientSpec]):
    gid = _store.get_or_create_uid(obj)
    mat = _store.ensure_material()
    for gradient_spec in gradient_specs:
        slot = resolve_gradient_slot_name(gradient_spec, source)
        if slot is None:
            continue
        name = _store.node_name(gid, slot)
        if mat.node_tree.nodes.get(name) is None:
            _create_gradient_node(
                mat,
                name,
                gradient_spec.default_stops,
                interpolation=gradient_spec.default_interpolation,
                color_mode=gradient_spec.default_color_mode,
                hue_interpolation=gradient_spec.default_hue_interpolation,
            )


def remove_item_gradients(obj, source, gradient_specs: list[GradientSpec]):
    gid = _store.get_uid(obj)
    if gid is None:
        return

    mat = _store.get_material()
    if mat is None or mat.node_tree is None:
        return

    for gradient_spec in gradient_specs:
        slot = resolve_gradient_slot_name(gradient_spec, source)
        if slot is None:
            continue
        node = mat.node_tree.nodes.get(_store.node_name(gid, slot))
        if node is not None:
            mat.node_tree.nodes.remove(node)


# ---------------------------------------------------------------------------
# LUT system
# ---------------------------------------------------------------------------


def _compute_gradient_hash(color_ramp) -> int:
    parts = [
        len(color_ramp.elements),
        color_ramp.interpolation,
        color_ramp.color_mode,
    ]
    for elem in color_ramp.elements:
        parts.append(round(elem.position, 6))
        parts.append(round(elem.color[0], 6))
        parts.append(round(elem.color[1], 6))
        parts.append(round(elem.color[2], 6))
        parts.append(round(elem.color[3], 6))
    return hash(tuple(parts))


def _bake_lut(color_ramp) -> list[tuple[float, float, float, float]]:
    lut = []
    for i in range(LUT_SIZE):
        pos = i / (LUT_SIZE - 1)
        color = color_ramp.evaluate(pos)
        lut.append((color[0], color[1], color[2], color[3]))
    return lut


def get_lut(obj, slot_name: str) -> list[tuple[float, float, float, float]] | None:
    node = get_gradient_node_for_slot(obj, slot_name)
    if node is None:
        return None

    ramp = node.color_ramp
    current_hash = _compute_gradient_hash(ramp)

    cache_key = node.name
    cached = _lut_cache.get(cache_key)
    if cached is not None and cached[1] == current_hash:
        return cached[0]

    lut = _bake_lut(ramp)
    _lut_cache[cache_key] = (lut, current_hash)
    return lut


def lut_lookup(lut, value: float) -> tuple[float, float, float, float]:
    return lut[max(0, min(255, int(value * 255.0)))]


def get_gradient_hash(obj, slot_name: str) -> int | None:
    node = get_gradient_node_for_slot(obj, slot_name)
    if node is None:
        return None
    return _compute_gradient_hash(node.color_ramp)


def clear_all_luts():
    _lut_cache.clear()


class NexusGradient:
    __slots__ = ("_obj", "_slot_name")

    def __init__(self, obj, slot_name: str):
        self._obj = obj
        self._slot_name = slot_name

    def __bool__(self):
        return self.node is not None

    @property
    def node(self):
        return get_gradient_node_for_slot(self._obj, self._slot_name)

    @property
    def color_ramp(self):
        node = self.node
        return node.color_ramp if node is not None else None

    @property
    def lut(self):
        return get_lut(self._obj, self._slot_name)

    @property
    def hash(self):
        return get_gradient_hash(self._obj, self._slot_name)

    def lookup(self, value: float) -> tuple[float, float, float, float]:
        lut = self.lut
        if lut is None:
            return (1.0, 1.0, 1.0, 1.0)
        return lut[max(0, min(255, int(value * 255.0)))]

    def extract_stops(self) -> dict | None:
        return extract_gradient_stops(self._obj, self._slot_name)

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
            "nexus.gradient_preset_popup",
            text="",
            icon_value=get_icon("nx_gradient_preset"),
        )
        op.gradient_id = _get_gradient_id(self._obj) or ""
        op.object_name = self._obj.name
        op.slot_name = self._slot_name
        content_col = split.column()
        content_col.template_color_ramp(node, "color_ramp")


# ---------------------------------------------------------------------------
# Theron sync
# ---------------------------------------------------------------------------


BLENDER_INTERPOLATION_MAP = {
    "CONSTANT": TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_CONSTANT,
    "LINEAR": TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_LINEAR,
    "EASE": TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_EASE,
    "CARDINAL": TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_CARDINAL,
    "B_SPLINE": TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_B_SPLINE,
}

BLENDER_COLOR_MODE_MAP = {
    "RGB": TrGradientColorMode.TR_GRADIENT_COLOR_MODE_RGB,
    "HSV": TrGradientColorMode.TR_GRADIENT_COLOR_MODE_HSV,
    "HSL": TrGradientColorMode.TR_GRADIENT_COLOR_MODE_HSL,
}

BLENDER_HUE_INTERPOLATION_MAP = {
    "NEAR": TrGradientHueInterpolation.TR_GRADIENT_HUE_INTERPOLATION_NEAR,
    "FAR": TrGradientHueInterpolation.TR_GRADIENT_HUE_INTERPOLATION_FAR,
    "CW": TrGradientHueInterpolation.TR_GRADIENT_HUE_INTERPOLATION_CW,
    "CCW": TrGradientHueInterpolation.TR_GRADIENT_HUE_INTERPOLATION_CCW,
}


def sync_gradient_to_theron(theron_module, grad_handle, stops_data: dict) -> None:
    """Sync full gradient state (knots, interpolation, color mode) to Theron.

    Args:
        theron_module: The theron wrapper module (libs.theron).
        grad_handle: The Theron gradient handle from create_gradient().
        stops_data: Dict from extract_gradient_stops() containing stops,
                    interpolation, color_mode, and hue_interpolation.
    """
    stops = stops_data["stops"]
    color_mode_str = stops_data.get("color_mode", "RGB")

    # Lock to LINEAR for HSV/HSL
    if color_mode_str in ("HSV", "HSL"):
        knot_interpolation = TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_LINEAR
    else:
        knot_interpolation = BLENDER_INTERPOLATION_MAP.get(
            stops_data.get("interpolation", "LINEAR"),
            TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_LINEAR,
        )

    theron_module.resize_gradient(grad_handle, len(stops))
    for i, stop in enumerate(stops):
        pos, r, g, b, _a = stop
        theron_module.set_gradient_knot(
            grad_handle, i, r, g, b, pos, interpolation=knot_interpolation
        )

    color_mode = BLENDER_COLOR_MODE_MAP.get(
        color_mode_str,
        TrGradientColorMode.TR_GRADIENT_COLOR_MODE_RGB,
    )
    hue_interpolation = BLENDER_HUE_INTERPOLATION_MAP.get(
        stops_data.get("hue_interpolation", "NEAR"),
        TrGradientHueInterpolation.TR_GRADIENT_HUE_INTERPOLATION_NEAR,
    )
    theron_module.set_gradient_color_mode(grad_handle, color_mode, hue_interpolation)


def extract_gradient_stops(obj, slot_name: str) -> dict | None:
    node = get_gradient_node_for_slot(obj, slot_name)
    if node is None:
        return None

    ramp = node.color_ramp
    stops = []
    for elem in ramp.elements:
        stops.append(
            (
                elem.position,
                elem.color[0],
                elem.color[1],
                elem.color[2],
                elem.color[3],
            )
        )

    return {
        "stops": stops,
        "interpolation": ramp.interpolation,
        "color_mode": ramp.color_mode,
        "hue_interpolation": ramp.hue_interpolation,
        "num_stops": len(stops),
    }


def cleanup_orphaned_gradient_nodes():
    _store.cleanup_orphans()
