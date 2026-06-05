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
import re

import bpy
import numpy as np
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import (
    draw_time_prop,
    get_prop_time_mode,
    nexus_time_property,
    to_time_fraction,
)
from ..libs.nodetree_sync import BlendSpec, NodeTreeSyncSpec
from ..libs.theron_sync import TRANSFORM_FACTORS, Transform
from ..ui import make_allowed_types_poll
from ..ui.nodetree import auto_rename

SCALE_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_SCALE_BLEND_MODE",
    strength_id_name="ID_NX_SCALE_BLEND_STRENGTH",
    id_map={
        "NORMAL": "ID_NX_SCALE_BLEND_NORMAL",
        "MIN": "ID_NX_SCALE_BLEND_MIN",
        "SUBTRACT": "ID_NX_SCALE_BLEND_SUB",
        "MULTIPLY": "ID_NX_SCALE_BLEND_MULT",
        "OVERLAY": "ID_NX_SCALE_BLEND_OVERLAY",
        "MAX": "ID_NX_SCALE_BLEND_MAX",
        "ADD": "ID_NX_SCALE_BLEND_ADD",
        "SCREEN": "ID_NX_SCALE_BLEND_SCREEN",
        "DIFFERENCE": "ID_NX_SCALE_BLEND_DIFFERENCE",
    },
    labels={
        "NORMAL": ("Normal", "Standard blend"),
        "MIN": ("Min", "Minimum of values"),
        "SUBTRACT": ("Subtract", "Subtract from previous"),
        "MULTIPLY": ("Multiply", "Multiply with previous"),
        "OVERLAY": ("Overlay", "Overlay blend"),
        "MAX": ("Max", "Maximum of values"),
        "ADD": ("Add", "Add to previous"),
        "SCREEN": ("Screen", "Screen blend"),
        "DIFFERENCE": ("Difference", "Difference blend"),
    },
)

SCALE_LAYER_DEFS = {
    "RANGE": {
        "name": "Range",
        "description": "Scale within min/max range",
        "icon_name": "nx_scale_layer_range",
        "blender_icon": "SEQ_HISTOGRAM",
    },
    "NOISE": {
        "name": "Noise",
        "description": "Scale using noise function",
        "icon_name": "nx_noise_simplex",
        "blender_icon": "MOD_NOISE",
    },
    "SET": {
        "name": "Change Value Over Time (Absolute)",
        "description": "Change value over time (absolute)",
        "icon_name": "nx_scale_layer_set",
        "blender_icon": "TIME",
    },
    "SET_PERCENT": {
        "name": "Change Value Over Time (Relative)",
        "description": "Change value over time (relative)",
        "icon_name": "nx_scale_layer_set_percent",
        "blender_icon": "PERCENTAGE",
    },
    "ABSOLUTE": {
        "name": "Set Value",
        "description": "Set absolute value",
        "icon_name": "nx_scale_layer_absolute",
        "blender_icon": "SNAP_INCREMENT",
    },
    "FALLOFF": {
        "name": "Set by Falloff (TODO)",
        "description": "Scale by falloff field (not yet supported)",
        "icon_name": "nx_scale_layer_falloff",
        "blender_icon": "SMOOTHCURVE",
    },
    "SPEED": {
        "name": "Scale by Speed",
        "description": "Scale based on particle speed",
        "icon_name": "nx_scale_layer_speed",
        "blender_icon": "ANIM",
    },
    "ACCEL": {
        "name": "Scale by Acceleration",
        "description": "Scale based on particle acceleration",
        "icon_name": "nx_scale_layer_accel",
        "blender_icon": "IPO_EASE_IN_OUT",
    },
    "MAP": {
        "name": "Scale by Map",
        "description": "Map scale from distance",
        "icon_name": "nx_scale_layer_map",
        "blender_icon": "MOD_THICKNESS",
    },
}

_SCALE_LAYER_ITEMS = []
_PARAMETER_ITEMS = []
_NOISE_TYPE_ITEMS = []
_TIMING_MODE_ITEMS = []

_TIMING_MODE_DEFS = [
    ("BIRTH", "On Birth", "Apply at particle birth", "nx_scale_timing_birth"),
    ("PARTICLE", "Particle Age", "Apply per particle age", "nx_scale_timing_particle"),
    ("FRAME", "Frame Time", "Apply per frame", "nx_scale_timing_frame"),
    ("FALLOFF", "Falloff", "Apply by falloff", ""),
]

_PARAMETER_DEFS = [
    ("GEOM", "Particle Scale", "Particle Scale", "nx_scale_param_geom"),
    ("RADIUS", "Particle Radius", "Particle Radius", "nx_scale_param_radius"),
    ("MASS", "Particle Mass", "Particle Mass", "nx_scale_param_mass"),
]

_PARAMETER_SUFFIX = {
    "GEOM": "Scale",
    "RADIUS": "Radius",
    "MASS": "Mass",
}

_SUFFIX_RE = re.compile(r"\s*\[(?:Scale|Radius|Mass)\]$")

_NOISE_TYPE_DEFS = [
    ("SIMPLEX", "Simplex", "Simplex noise", "nx_noise_simplex"),
    ("CURL", "Curl", "Curl noise", "nx_noise_curl"),
    ("TURBULENCE", "Turbulence", "Classic turbulence noise", "nx_noise_turbulence"),
    ("WAVY_TURBULENCE", "Wavy Turbulence", "Wavy turbulence noise", "nx_noise_wavy_turbulence"),
    ("VORONOISE", "VoroNoise", "Voronoi-based noise", "nx_noise_voronoise"),
    ("FBM", "FBM", "FBM", "nx_noise_fbm"),
    ("CUBIC", "Cubic", "Cubic noise", "nx_noise_cubic"),
]

_NOISE_ICON_MAP = {eid: icon_name for eid, _, _, icon_name in _NOISE_TYPE_DEFS}

_ALL_GRADIENT_IDS = (
    "ID_NX_SCALE_SCALE_NOISE_GRADIENT",
    "ID_NX_SCALE_RADIUS_NOISE_GRADIENT",
    "ID_NX_SCALE_MASS_NOISE_GRADIENT",
)

_ALL_SPLINE_IDS = (
    "ID_NX_SCALE_SPLINE",
    "ID_NX_SCALE_RADIUS_SPLINE",
    "ID_NX_SCALE_MASS_SPLINE",
)


# (modifier_name, layer_uid, channel_prefix) -> (poly_handle, mesh_name, vertex_count, tri_count)
_scale_map_poly_cache: dict[tuple[str, str, str], tuple[int, str, int, int]] = {}
_scale_map_active_keys: dict[str, set[tuple[str, str, str]]] = {}


def clear_scale_map_poly_cache(modifier_name=None, *, free_resources=True):
    keys = (
        [k for k in _scale_map_poly_cache if k[0] == modifier_name]
        if modifier_name is not None
        else list(_scale_map_poly_cache)
    )
    if not keys:
        if modifier_name is None:
            _scale_map_active_keys.clear()
        else:
            _scale_map_active_keys.pop(modifier_name, None)
        return

    if free_resources:
        from ..libs import theron

        for key in keys:
            poly_handle, _name, _vc, _tc = _scale_map_poly_cache.pop(key)
            theron.free_polygon_object(poly_handle)
    else:
        for key in keys:
            _scale_map_poly_cache.pop(key, None)

    if modifier_name is None:
        _scale_map_active_keys.clear()
    else:
        _scale_map_active_keys.pop(modifier_name, None)


def _get_curve_spec():
    from ..utils.curve import CurveSpec

    return CurveSpec(
        slot_name="scale_ease",
        label="Ease",
        default_points=[(0.0, 0.0), (1.0, 1.0)],
        theron_ids=_ALL_SPLINE_IDS,
        slot_suffix_attr="layer_uid",
    )


SCALE_EASE_CURVE_SPECS = None
SCALE_NOISE_GRADIENT_SPECS = None


def _ensure_curve_specs():
    global SCALE_EASE_CURVE_SPECS
    if SCALE_EASE_CURVE_SPECS is None:
        SCALE_EASE_CURVE_SPECS = [_get_curve_spec()]
    return SCALE_EASE_CURVE_SPECS


def _get_gradient_spec_list():
    from ..utils.gradient import GradientSpec

    return [
        GradientSpec(
            slot_name="scale_noise_gradient",
            label="Contrast",
            default_stops=[
                (0.0, (1.0, 1.0, 1.0, 1.0)),
                (1.0, (0.0, 0.0, 0.0, 1.0)),
            ],
            theron_ids=_ALL_GRADIENT_IDS,
            slot_suffix_attr="layer_uid",
        )
    ]


def _ensure_gradient_specs():
    global SCALE_NOISE_GRADIENT_SPECS
    if SCALE_NOISE_GRADIENT_SPECS is None:
        SCALE_NOISE_GRADIENT_SPECS = _get_gradient_spec_list()
    return SCALE_NOISE_GRADIENT_SPECS


def _create_layer_nodes(obj, uid):
    from ..utils.curve import create_item_curves
    from ..utils.gradient import create_item_gradients

    create_item_gradients(obj, uid, _ensure_gradient_specs())
    create_item_curves(obj, uid, _ensure_curve_specs())


def _remove_layer_nodes(obj, uid):
    from ..utils.curve import remove_item_curves
    from ..utils.gradient import remove_item_gradients

    remove_item_gradients(obj, uid, _ensure_gradient_specs())
    remove_item_curves(obj, uid, _ensure_curve_specs())


def _scale_layer_base_name(item) -> str:
    type_name = SCALE_LAYER_DEFS.get(item.item_type, {}).get("name", "Layer")
    return _build_suffixed_name(type_name, item.parameter)


def _on_scale_layer_add(context, obj, item):
    del context
    item.layer_uid = os.urandom(4).hex()
    _create_layer_nodes(obj, item.layer_uid)
    layers = obj.nexus_modifier.scale_layers
    auto_rename.initialize_added(item, layers, _scale_layer_base_name(item))


def _on_scale_layer_remove(context, obj, item):
    if item.layer_uid:
        _remove_layer_nodes(obj, item.layer_uid)


def build_scale_enum_items():
    global _SCALE_LAYER_ITEMS, _PARAMETER_ITEMS, _NOISE_TYPE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _SCALE_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(SCALE_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _SCALE_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = layer_def.get("blender_icon", "NONE")
            _SCALE_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    _PARAMETER_ITEMS = []
    for idx, (eid, label, desc, icon_name) in enumerate(_PARAMETER_DEFS):
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _PARAMETER_ITEMS.append((eid, label, desc, icon_id, idx))
        else:
            _PARAMETER_ITEMS.append((eid, label, desc, "NONE", idx))

    _NOISE_TYPE_ITEMS = []
    for idx, (eid, label, desc, icon_name) in enumerate(_NOISE_TYPE_DEFS):
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _NOISE_TYPE_ITEMS.append((eid, label, desc, icon_id, idx))
        else:
            _NOISE_TYPE_ITEMS.append((eid, label, desc, "NONE", idx))

    global _TIMING_MODE_ITEMS
    _TIMING_MODE_ITEMS = []
    for idx, (eid, label, desc, icon_name) in enumerate(_TIMING_MODE_DEFS):
        icon_id = get_icon(icon_name) if icon_name else 0
        if icon_id and icon_id > 0:
            _TIMING_MODE_ITEMS.append((eid, label, desc, icon_id, idx))
        else:
            _TIMING_MODE_ITEMS.append((eid, label, desc, "NONE", idx))

    register_nodetree(
        "scale_layers",
        _SCALE_LAYER_ITEMS,
        "scale_layers",
        "scale_layers_index",
        on_add=_on_scale_layer_add,
        on_remove=_on_scale_layer_remove,
        separator_after={"NOISE"},
    )


def _get_scale_layer_items(self, context):
    return _SCALE_LAYER_ITEMS


def _get_parameter_items(self, context):
    return _PARAMETER_ITEMS


def _get_noise_type_items(self, context):
    return _NOISE_TYPE_ITEMS


def _get_timing_mode_items(self, context):
    return _TIMING_MODE_ITEMS


def _build_suffixed_name(base_name, parameter):
    stripped = _SUFFIX_RE.sub("", base_name)
    suffix = _PARAMETER_SUFFIX.get(parameter, "")
    if suffix:
        return f"{stripped} [{suffix}]"
    return stripped


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


_on_item_type_update = auto_rename.on_trigger(
    base_name_fn=_scale_layer_base_name,
    collection_attr="scale_layers",
    pre=_update_layer_viewport,
)

_on_parameter_update = _on_item_type_update


class NexusScaleLayerItem(bpy.types.PropertyGroup):
    """Union pattern PropertyGroup for scale layers.

    All per-operation properties are defined here and conditionally
    shown based on item_type.
    """

    name: StringProperty(
        name="Name",
        description="Scale layer name",
        default="",
        update=auto_rename.on_name_update(),
    )

    is_renamed: BoolProperty(
        name="",
        default=False,
        options={"HIDDEN"},
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this scale layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of scale operation",
        items=_get_scale_layer_items,
        default=0,
        update=_on_item_type_update,
    )

    blend_mode: EnumProperty(
        name="Blend",
        description="How this layer blends with previous layers",
        items=SCALE_BLEND_SPEC.enum_items(),
        default="NORMAL",
    )

    blend_strength: FloatProperty(
        name="Strength",
        description="Strength of this layer's effect",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter: EnumProperty(
        name="Particle Data",
        description="Which particle attribute to affect",
        items=_get_parameter_items,
        default=1,
        update=_on_parameter_update,
    )

    timing_mode: EnumProperty(
        name="Timing",
        description="When the operation is applied",
        items=_get_timing_mode_items,
        default=1,
    )

    remap_falloff: BoolProperty(
        name="Remap Falloff Value",
        description="Remap falloff values",
        default=False,
    )

    layer_uid: StringProperty(
        name="",
        default="",
        options={"HIDDEN"},
    )

    # -- GEOM (Scale) channel properties (vectors) -------------------------

    scale_absolute: FloatVectorProperty(
        name="Scale Value",
        description="Absolute scale value",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.0,
        step=1,
    )

    scale_delta: FloatVectorProperty(
        name="Scale Change",
        description="Scale change per step",
        size=3,
        default=(0.05, 0.05, 0.05),
        step=1,
    )

    scale_delta_var: FloatProperty(
        name="Variation",
        description="Random variation in scale change",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_jiggle_var: FloatProperty(
        name="Jiggle Variation",
        description="Random jiggle variation amount",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_percent: FloatProperty(
        name="Scale Percentage",
        description="Percentage change per step",
        default=5.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    scale_use_limit: BoolProperty(
        name="Clamp to Scale Limit",
        description="Clamp scale to min/max limits",
        default=True,
    )

    scale_limit_min: FloatVectorProperty(
        name="Lower Scale Limit",
        description="Minimum allowed scale",
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0,
        step=10,
    )

    scale_limit_max: FloatVectorProperty(
        name="Upper Scale Limit",
        description="Maximum allowed scale",
        size=3,
        default=(10.0, 10.0, 10.0),
        min=0.0,
        step=10,
    )

    scale_clamp_random: BoolProperty(
        name="Clamp Within Range",
        description="Clamp random values within range",
        default=False,
    )

    scale_range_min: FloatVectorProperty(
        name="Scale Start",
        description="Minimum range value",
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0,
        step=10,
    )

    scale_range_min_var: FloatProperty(
        name="Variation",
        description="Random variation in range minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_range_max: FloatVectorProperty(
        name="Scale End",
        description="Maximum range value",
        size=3,
        default=(10.0, 10.0, 10.0),
        min=0.0,
        step=10,
    )

    scale_range_max_var: FloatProperty(
        name="Variation",
        description="Random variation in range maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_noise_type: EnumProperty(
        name="Noise Type",
        description="Noise algorithm to use",
        items=_get_noise_type_items,
        default=4,
    )

    scale_noise_seed: IntProperty(
        name="Seed",
        description="Random seed for noise",
        default=1,
        min=0,
    )

    scale_noise_scale: FloatProperty(
        name="Scale",
        description="Overall noise scale",
        default=100.0,
        min=0.0,
        soft_max=1000.0,
        subtype="PERCENTAGE",
    )

    scale_noise_persistence: FloatProperty(
        name="Persistence",
        description="Amplitude decay per octave",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_noise_lacunarity: FloatProperty(
        name="Lacunarity",
        description="Frequency multiplier per octave",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )

    scale_noise_frequency: FloatProperty(
        name="Frequency",
        description="Noise frequency",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        subtype="PERCENTAGE",
    )

    scale_noise_octaves: IntProperty(
        name="Octaves",
        description="Number of noise octaves",
        default=1,
        min=0,
        soft_max=20,
    )

    scale_start: nexus_time_property(
        "scale_start",
        name="Start Time",
        description="Start time for the operation",
        default=0.0,
        collection_path="scale_layers",
    )

    scale_end: nexus_time_property(
        "scale_end",
        name="End Time",
        description="End time for the operation",
        default=2.0,
        collection_path="scale_layers",
    )

    scale_time_var: FloatProperty(
        name="Variation",
        description="Random variation in timing",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_spline_clamp: EnumProperty(
        name="Clamp Mode",
        description="Spline boundary behavior",
        items=[
            ("CLAMP", "Clamp", "Clamp at boundaries"),
            ("CYCLE", "Repeat", "Repeat the spline"),
            ("CONTINUE", "Continue", "Continue past boundaries"),
        ],
        default="CLAMP",
    )

    scale_map_dist: FloatProperty(
        name="Max Distance",
        description="Maximum mapping distance",
        default=0.5,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
    )

    scale_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group to use for scaling",
        default="",
    )

    scale_vertex_group_obj: PointerProperty(
        name="Vertex Group Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
    )

    # -- RADIUS channel properties (scalars) --------------------------------

    radius_absolute: FloatProperty(
        name="Radius Value",
        description="Absolute radius value",
        default=0.01,
        min=0.0,
        soft_max=0.2,
        unit="LENGTH",
    )

    radius_delta: FloatProperty(
        name="Radius Change",
        description="Radius change per step",
        default=0.002,
        soft_min=-0.05,
        soft_max=0.05,
        unit="LENGTH",
    )

    radius_delta_var: FloatProperty(
        name="Variation",
        description="Random variation in radius change",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_jiggle_var: FloatProperty(
        name="Jiggle Variation",
        description="Random jiggle variation amount",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_percent: FloatProperty(
        name="Radius Percentage",
        description="Percentage change per step",
        default=5.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    radius_use_limit: BoolProperty(
        name="Clamp to Radius Limit",
        description="Clamp radius to min/max limits",
        default=True,
    )

    radius_limit_min: FloatProperty(
        name="Lower Radius Limit",
        description="Minimum allowed radius",
        default=0.0,
        min=0.0,
        soft_max=0.5,
        unit="LENGTH",
    )

    radius_limit_max: FloatProperty(
        name="Upper Radius Limit",
        description="Maximum allowed radius",
        default=0.2,
        min=0.0,
        soft_max=0.5,
        unit="LENGTH",
    )

    radius_clamp_random: BoolProperty(
        name="Clamp Within Range",
        description="Clamp random values within range",
        default=False,
    )

    radius_range_min: FloatProperty(
        name="Radius Start",
        description="Minimum range value",
        default=0.0,
        min=0.0,
        soft_max=0.5,
        unit="LENGTH",
    )

    radius_range_min_var: FloatProperty(
        name="Variation",
        description="Random variation in range minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_range_max: FloatProperty(
        name="Radius End",
        description="Maximum range value",
        default=0.1,
        min=0.0,
        soft_max=0.5,
        unit="LENGTH",
    )

    radius_range_max_var: FloatProperty(
        name="Variation",
        description="Random variation in range maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_noise_type: EnumProperty(
        name="Noise Type",
        description="Noise algorithm to use",
        items=_get_noise_type_items,
        default=4,
    )

    radius_noise_seed: IntProperty(
        name="Seed",
        description="Random seed for noise",
        default=1,
        min=0,
    )

    radius_noise_scale: FloatProperty(
        name="Scale",
        description="Overall noise scale",
        default=100.0,
        min=0.0,
        soft_max=1000.0,
        subtype="PERCENTAGE",
    )

    radius_noise_persistence: FloatProperty(
        name="Persistence",
        description="Amplitude decay per octave",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_noise_lacunarity: FloatProperty(
        name="Lacunarity",
        description="Frequency multiplier per octave",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )

    radius_noise_frequency: FloatProperty(
        name="Frequency",
        description="Noise frequency",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        subtype="PERCENTAGE",
    )

    radius_noise_octaves: IntProperty(
        name="Octaves",
        description="Number of noise octaves",
        default=1,
        min=0,
        soft_max=20,
    )

    radius_start: nexus_time_property(
        "radius_start",
        name="Start Time",
        description="Start time for the operation",
        default=0.0,
        collection_path="scale_layers",
    )

    radius_end: nexus_time_property(
        "radius_end",
        name="End Time",
        description="End time for the operation",
        default=2.0,
        collection_path="scale_layers",
    )

    radius_time_var: FloatProperty(
        name="Variation",
        description="Random variation in timing",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_spline_clamp: EnumProperty(
        name="Clamp Mode",
        description="Spline boundary behavior",
        items=[
            ("CLAMP", "Clamp", "Clamp at boundaries"),
            ("CYCLE", "Repeat", "Repeat the spline"),
            ("CONTINUE", "Continue", "Continue past boundaries"),
        ],
        default="CLAMP",
    )

    radius_map_dist: FloatProperty(
        name="Max Distance",
        description="Maximum mapping distance",
        default=0.5,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
    )

    radius_vertex_group_obj: PointerProperty(
        name="Vertex Group Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
    )

    radius_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group to use for scaling",
        default="",
    )

    # -- MASS channel properties (scalars, no unit) -------------------------

    mass_absolute: FloatProperty(
        name="Mass Value",
        description="Absolute mass value",
        default=1.0,
        min=0.0,
        soft_max=20.0,
    )

    mass_delta: FloatProperty(
        name="Mass Change",
        description="Mass change per step",
        default=0.1,
        soft_min=-5.0,
        soft_max=5.0,
    )

    mass_delta_var: FloatProperty(
        name="Variation",
        description="Random variation in mass change",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_jiggle_var: FloatProperty(
        name="Jiggle Variation",
        description="Random jiggle variation amount",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_percent: FloatProperty(
        name="Mass Percentage",
        description="Percentage change per step",
        default=5.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    mass_use_limit: BoolProperty(
        name="Clamp to Mass Limit",
        description="Clamp mass to min/max limits",
        default=True,
    )

    mass_limit_min: FloatProperty(
        name="Lower Mass Limit",
        description="Minimum allowed mass",
        default=0.0,
        min=0.0,
        soft_max=50.0,
    )

    mass_limit_max: FloatProperty(
        name="Upper Mass Limit",
        description="Maximum allowed mass",
        default=20.0,
        min=0.0,
        soft_max=50.0,
    )

    mass_clamp_random: BoolProperty(
        name="Clamp Within Range",
        description="Clamp random values within range",
        default=False,
    )

    mass_range_min: FloatProperty(
        name="Mass Start",
        description="Minimum range value",
        default=0.0,
        min=0.0,
        step=10,
    )

    mass_range_min_var: FloatProperty(
        name="Variation",
        description="Random variation in range minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_range_max: FloatProperty(
        name="Mass End",
        description="Maximum range value",
        default=10.0,
        min=0.0,
        step=10,
    )

    mass_range_max_var: FloatProperty(
        name="Variation",
        description="Random variation in range maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_noise_type: EnumProperty(
        name="Noise Type",
        description="Noise algorithm to use",
        items=_get_noise_type_items,
        default=4,
    )

    mass_noise_seed: IntProperty(
        name="Seed",
        description="Random seed for noise",
        default=1,
        min=0,
    )

    mass_noise_scale: FloatProperty(
        name="Scale",
        description="Overall noise scale",
        default=100.0,
        min=0.0,
        soft_max=1000.0,
        subtype="PERCENTAGE",
    )

    mass_noise_persistence: FloatProperty(
        name="Persistence",
        description="Amplitude decay per octave",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_noise_lacunarity: FloatProperty(
        name="Lacunarity",
        description="Frequency multiplier per octave",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )

    mass_noise_frequency: FloatProperty(
        name="Frequency",
        description="Noise frequency",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        subtype="PERCENTAGE",
    )

    mass_noise_octaves: IntProperty(
        name="Octaves",
        description="Number of noise octaves",
        default=1,
        min=0,
        soft_max=20,
    )

    mass_start: nexus_time_property(
        "mass_start",
        name="Start Time",
        description="Start time for the operation",
        default=0.0,
        collection_path="scale_layers",
    )

    mass_end: nexus_time_property(
        "mass_end",
        name="End Time",
        description="End time for the operation",
        default=2.0,
        collection_path="scale_layers",
    )

    mass_time_var: FloatProperty(
        name="Variation",
        description="Random variation in timing",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_spline_clamp: EnumProperty(
        name="Clamp Mode",
        description="Spline boundary behavior",
        items=[
            ("CLAMP", "Clamp", "Clamp at boundaries"),
            ("CYCLE", "Repeat", "Repeat the spline"),
            ("CONTINUE", "Continue", "Continue past boundaries"),
        ],
        default="CLAMP",
    )

    mass_map_dist: FloatProperty(
        name="Max Distance",
        description="Maximum mapping distance",
        default=0.5,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
    )

    mass_vertex_group_obj: PointerProperty(
        name="Vertex Group Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
    )

    mass_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group to use for scaling",
        default="",
    )

    def get_list_icon(self) -> int:
        """Return a dynamic icon ID for the UIList row, or 0 for default."""
        if self.item_type != "NOISE":
            return 0
        prefix = _get_param_prefix(self)
        noise_type = getattr(self, f"{prefix}noise_type", "")
        icon_name = _NOISE_ICON_MAP.get(noise_type, "")
        if not icon_name:
            return 0
        from ..icons import get_icon

        return get_icon(icon_name) or 0


def _get_param_prefix(item):
    if item.parameter == "RADIUS":
        return "radius_"
    if item.parameter == "MASS":
        return "mass_"
    return "scale_"


def _draw_layer_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "blend_strength")

    col.separator(type="LINE")

    col.prop(item, "parameter")

    return col


def _draw_timing_section(col, item, prefix):
    if item.timing_mode in ("PARTICLE", "FRAME"):
        col.separator(type="LINE")

        draw_time_prop(col, item, f"{prefix}start")
        draw_time_prop(col, item, f"{prefix}end")
        col.prop(item, f"{prefix}time_var")

        col.separator(type="LINE")

        _draw_ease_curve(col, item, prefix)


def _draw_limit_section(col, item, prefix, *, show_clamp_random=True):
    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Limits")

    col.prop(item, f"{prefix}use_limit")

    sub = col.column()
    sub.enabled = getattr(item, f"{prefix}use_limit")
    sub.prop(item, f"{prefix}limit_min")
    sub.prop(item, f"{prefix}limit_max")
    if show_clamp_random:
        sub.prop(item, f"{prefix}clamp_random")


def _draw_ease_curve(col, item, prefix):
    """Draw the ease curve widget for operations with timing."""
    import bpy

    obj = bpy.context.object
    if not obj or not item.layer_uid:
        return
    from ..utils.curve import NexusCurve

    col.prop(item, f"{prefix}spline_clamp")
    NexusCurve(obj, f"scale_ease_{item.layer_uid}").draw_ui(col, "Ease")


def _draw_noise_gradient(col, item):
    """Draw the noise contrast gradient for the NOISE operation."""
    import bpy

    obj = bpy.context.object
    if not obj or not item.layer_uid:
        return
    from ..utils.gradient import NexusGradient

    NexusGradient(obj, f"scale_noise_gradient_{item.layer_uid}").draw_ui(col, "Contrast")


def _draw_range_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, "timing_mode")

    col.separator(type="LINE")

    if item.timing_mode != "BIRTH":
        col.prop(item, f"{p}range_min")
        col.prop(item, f"{p}range_min_var")

    col.prop(item, f"{p}range_max")
    col.prop(item, f"{p}range_max_var")

    _draw_timing_section(col, item, p)


def _draw_noise_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}noise_type")

    col.separator(type="LINE")

    col.prop(item, f"{p}range_min")
    col.prop(item, f"{p}range_min_var")
    col.prop(item, f"{p}range_max")
    col.prop(item, f"{p}range_max_var")

    col.separator(type="LINE")

    col.prop(item, f"{p}noise_seed")

    col.separator(type="LINE")

    _draw_noise_gradient(col, item)

    col.separator(type="LINE")

    col.prop(item, f"{p}noise_scale")
    col.prop(item, f"{p}noise_persistence")
    col.prop(item, f"{p}noise_lacunarity")
    col.prop(item, f"{p}noise_frequency")
    col.prop(item, f"{p}noise_octaves")


def _draw_set_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}delta")
    col.prop(item, f"{p}delta_var")

    _draw_limit_section(col, item, p)


def _draw_set_percent_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}percent")

    _draw_limit_section(col, item, p)


def _draw_absolute_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}absolute")
    col.prop(item, f"{p}delta_var")

    _draw_limit_section(col, item, p)


def _draw_falloff_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, "remap_falloff")

    _draw_limit_section(col, item, p, show_clamp_random=False)


def _draw_speed_accel_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}delta")
    col.prop(item, f"{p}delta_var")

    _draw_limit_section(col, item, p)


def _draw_map_settings(layout, item):
    col = _draw_layer_header(layout, item)
    p = _get_param_prefix(item)

    col.separator(type="LINE")

    col.prop(item, f"{p}vertex_group_obj")
    vgroup_obj = getattr(item, f"{p}vertex_group_obj")
    if vgroup_obj is not None:
        col.prop_search(
            item,
            f"{p}vertex_group",
            vgroup_obj,
            "vertex_groups",
            text="Vertex Group",
        )
    col.prop(item, f"{p}map_dist")

    col.separator(type="LINE")

    col.prop(item, f"{p}range_max")
    col.prop(item, f"{p}range_max_var")

    _draw_timing_section(col, item, p)


LAYER_DRAW_FUNCS = {
    "RANGE": _draw_range_settings,
    "NOISE": _draw_noise_settings,
    "SET": _draw_set_settings,
    "SET_PERCENT": _draw_set_percent_settings,
    "ABSOLUTE": _draw_absolute_settings,
    "FALLOFF": _draw_falloff_settings,
    "SPEED": _draw_speed_accel_settings,
    "ACCEL": _draw_speed_accel_settings,
    "MAP": _draw_map_settings,
}


def draw_scale_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


SCALE_LAYER_TYPE_IDS = {
    "SET": "ID_XP_SCALE_TREE_CHOICE_SET",
    "SET_PERCENT": "ID_XP_SCALE_TREE_CHOICE_SET_PERCENT",
    "ABSOLUTE": "ID_XP_SCALE_TREE_CHOICE_ABSOLUTE",
    "FALLOFF": "ID_XP_SCALE_TREE_CHOICE_FALLOFF",
    "SPEED": "ID_XP_SCALE_TREE_CHOICE_SPEED",
    "ACCEL": "ID_XP_SCALE_TREE_CHOICE_ACCEL",
    "RANGE": "ID_XP_SCALE_TREE_CHOICE_RANGE",
    "NOISE": "ID_XP_SCALE_TREE_CHOICE_NOISE",
    "MAP": "ID_XP_SCALE_TREE_CHOICE_MAP",
}

SCALE_TIMING_MODE_IDS = {
    "BIRTH": "ID_NX_SCALE_TIMING_BIRTH",
    "PARTICLE": "ID_NX_SCALE_TIMING_PARTICLE",
    "FRAME": "ID_NX_SCALE_TIMING_FRAME",
    "FALLOFF": "ID_NX_SCALE_TIMING_FALLOFF",
}

SCALE_PARAM_IDS = {
    "GEOM": "ID_NX_SCALE_PARAM_GEOM",
    "RADIUS": "ID_NX_SCALE_PARAM_RADIUS",
    "MASS": "ID_NX_SCALE_PARAM_MASS",
}

NOISE_TYPE_INDEX = {
    "SIMPLEX": 0,
    "CURL": 1,
    "TURBULENCE": 2,
    "WAVY_TURBULENCE": 3,
    "VORONOISE": 4,
    "FBM": 5,
    "CUBIC": 6,
}

SPLINE_CLAMP_VALUES = {
    "CLAMP": 1,
    "CYCLE": 2,
    "CONTINUE": 4,
}

_PCT = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_UNIT = TRANSFORM_FACTORS[Transform.UNIT_SCALE]


def _sync_channel(theron, get, nc, item, param, *, obj=None, depsgraph=None):
    if param == "GEOM":
        id_pfx = "ID_NX_SCALE"
        prop_pfx = "scale"
        is_vector = True
        uf = 1.0
    elif param == "RADIUS":
        id_pfx = "ID_NX_SCALE_RADIUS"
        prop_pfx = "radius"
        is_vector = False
        uf = _UNIT
    else:
        id_pfx = "ID_NX_SCALE_MASS"
        prop_pfx = "mass"
        is_vector = False
        uf = 1.0

    val = getattr(item, f"{prop_pfx}_absolute")
    if is_vector:
        theron.set_vector(nc, get(f"{id_pfx}_ABSOLUTE"), val[0], val[1], val[2])
    else:
        theron.set_float(nc, get(f"{id_pfx}_ABSOLUTE"), val * uf)

    val = getattr(item, f"{prop_pfx}_delta")
    if is_vector:
        theron.set_vector(nc, get(f"{id_pfx}_DELTA"), val[0], val[1], val[2])
    else:
        theron.set_float(nc, get(f"{id_pfx}_DELTA"), val * uf)

    theron.set_float(
        nc,
        get(f"{id_pfx}_DELTA_VAR"),
        getattr(item, f"{prop_pfx}_delta_var") * _PCT,
    )

    theron.set_float(
        nc,
        get(f"{id_pfx}_JIGGLE_VAR"),
        getattr(item, f"{prop_pfx}_jiggle_var") * _PCT,
    )

    if param == "GEOM":
        pct_id = "ID_NX_SCALE_SCALE_PERCENT"
    else:
        pct_id = f"{id_pfx}_PERCENT"
    theron.set_float(
        nc,
        get(pct_id),
        getattr(item, f"{prop_pfx}_percent") * _PCT,
    )

    theron.set_int32(
        nc,
        get(f"{id_pfx}_USELIMIT"),
        int(getattr(item, f"{prop_pfx}_use_limit")),
    )

    val = getattr(item, f"{prop_pfx}_limit_min")
    if is_vector:
        theron.set_vector(
            nc,
            get(f"{id_pfx}_SCALELIMIT_MIN"),
            val[0],
            val[1],
            val[2],
        )
    else:
        theron.set_float(nc, get(f"{id_pfx}_SCALELIMIT_MIN"), val * uf)

    val = getattr(item, f"{prop_pfx}_limit_max")
    if is_vector:
        theron.set_vector(
            nc,
            get(f"{id_pfx}_SCALELIMIT_MAX"),
            val[0],
            val[1],
            val[2],
        )
    else:
        theron.set_float(nc, get(f"{id_pfx}_SCALELIMIT_MAX"), val * uf)

    if param == "GEOM":
        sr_id = "ID_NX_SCALE_SCALE_SCALERANDOM"
    else:
        sr_id = f"{id_pfx}_SCALERANDOM"
    theron.set_int32(
        nc,
        get(sr_id),
        int(getattr(item, f"{prop_pfx}_clamp_random")),
    )

    val = getattr(item, f"{prop_pfx}_range_min")
    if param == "GEOM":
        rm_id = "ID_NX_SCALE_SCALE_RANGE_MIN"
    else:
        rm_id = f"{id_pfx}_RANGE_MIN"
    if is_vector:
        theron.set_vector(nc, get(rm_id), val[0], val[1], val[2])
    else:
        theron.set_float(nc, get(rm_id), val * uf)

    if param == "GEOM":
        rmv_id = "ID_NX_SCALE_SCALE_RANGE_MIN_VAR"
    else:
        rmv_id = f"{id_pfx}_RANGE_MIN_VAR"
    theron.set_float(
        nc,
        get(rmv_id),
        getattr(item, f"{prop_pfx}_range_min_var") * _PCT,
    )

    val = getattr(item, f"{prop_pfx}_range_max")
    if param == "GEOM":
        rx_id = "ID_NX_SCALE_SCALE_RANGE_MAX"
    else:
        rx_id = f"{id_pfx}_RANGE_MAX"
    if is_vector:
        theron.set_vector(nc, get(rx_id), val[0], val[1], val[2])
    else:
        theron.set_float(nc, get(rx_id), val * uf)

    if param == "GEOM":
        rxv_id = "ID_NX_SCALE_SCALE_RANGE_MAX_VAR"
    else:
        rxv_id = f"{id_pfx}_RANGE_MAX_VAR"
    theron.set_float(
        nc,
        get(rxv_id),
        getattr(item, f"{prop_pfx}_range_max_var") * _PCT,
    )

    timing_val = get(SCALE_TIMING_MODE_IDS.get(item.timing_mode, "ID_NX_SCALE_TIMING_BIRTH"))
    theron.set_int32(nc, get("ID_NX_SCALE_TIMING_MODE"), timing_val)

    noise_idx = NOISE_TYPE_INDEX.get(
        getattr(item, f"{prop_pfx}_noise_type"),
        0,
    )
    if param == "GEOM":
        nt_id = "ID_NX_SCALE_SCALE_NOISE_TYPE"
    else:
        nt_id = f"{id_pfx}_NOISE_TYPE"
    theron.set_int32(nc, get(nt_id), noise_idx)

    if param == "GEOM":
        ns_id = "ID_NX_SCALE_SCALE_NOISE_SEED"
    else:
        ns_id = f"{id_pfx}_NOISE_SEED"
    theron.set_int32(
        nc,
        get(ns_id),
        getattr(item, f"{prop_pfx}_noise_seed"),
    )

    if param == "GEOM":
        nsc_id = "ID_NX_SCALE_SCALE_NOISE_SCALE"
    else:
        nsc_id = f"{id_pfx}_NOISE_SCALE"
    theron.set_float(
        nc,
        get(nsc_id),
        getattr(item, f"{prop_pfx}_noise_scale") * _PCT,
    )

    if param == "GEOM":
        np_id = "ID_NX_SCALE_SCALE_NOISE_PERSISTENCE"
    else:
        np_id = f"{id_pfx}_NOISE_PERSISTENCE"
    theron.set_float(
        nc,
        get(np_id),
        getattr(item, f"{prop_pfx}_noise_persistence") * _PCT,
    )

    if param == "GEOM":
        nf_id = "ID_NX_SCALE_SCALE_NOISE_FREQUENCY"
    else:
        nf_id = f"{id_pfx}_NOISE_FREQUENCY"
    theron.set_float(
        nc,
        get(nf_id),
        getattr(item, f"{prop_pfx}_noise_frequency") * _PCT,
    )

    if param == "GEOM":
        nl_id = "ID_NX_SCALE_SCALE_NOISE_LACUNARITY"
    else:
        nl_id = f"{id_pfx}_NOISE_LACUNARITY"
    theron.set_float(
        nc,
        get(nl_id),
        getattr(item, f"{prop_pfx}_noise_lacunarity"),
    )

    if param == "GEOM":
        no_id = "ID_NX_SCALE_SCALE_NOISE_OCTAVES"
    else:
        no_id = f"{id_pfx}_NOISE_OCTAVES"
    theron.set_int32(
        nc,
        get(no_id),
        getattr(item, f"{prop_pfx}_noise_octaves"),
    )

    start_mode = get_prop_time_mode(item, f"{prop_pfx}_start")
    start_val = getattr(item, f"{prop_pfx}_start")
    start_n, start_d = to_time_fraction(float(start_val), mode=start_mode)
    theron.set_time(nc, get(f"{id_pfx}_START"), start_n, start_d)

    end_mode = get_prop_time_mode(item, f"{prop_pfx}_end")
    end_val = getattr(item, f"{prop_pfx}_end")
    end_n, end_d = to_time_fraction(float(end_val), mode=end_mode)
    theron.set_time(nc, get(f"{id_pfx}_END"), end_n, end_d)

    theron.set_float(
        nc,
        get(f"{id_pfx}_TIME_VAR_PERCENT"),
        getattr(item, f"{prop_pfx}_time_var") * _PCT,
    )

    if param == "GEOM":
        md_id = "ID_NX_SCALE_SCALE_MAP_DIST"
    else:
        md_id = f"{id_pfx}_MAP_DIST"
    theron.set_float(
        nc,
        get(md_id),
        getattr(item, f"{prop_pfx}_map_dist") * _UNIT,
    )

    if item.item_type == "MAP":
        from ..pipeline_manager.identity import ensure_object_uid
        from ..utils import extract_mesh_data

        if obj is None or depsgraph is None:
            return

        vgroup_obj = getattr(item, f"{prop_pfx}_vertex_group_obj", None)
        if vgroup_obj is None or vgroup_obj.type != "MESH":
            return

        mod_uid = ensure_object_uid(obj)
        cache_key = (mod_uid, item.layer_uid, prop_pfx)
        _scale_map_active_keys.setdefault(mod_uid, set()).add(cache_key)

        mesh_data = extract_mesh_data(vgroup_obj, depsgraph)
        if mesh_data is None:
            return
        vertices, polygons, vertex_count, tri_count, world_matrix = mesh_data

        cached = _scale_map_poly_cache.get(cache_key)
        if cached is not None:
            poly_handle, prev_name, prev_verts, prev_tris = cached
            if prev_name != vgroup_obj.name:
                theron.free_polygon_object(poly_handle)
                poly_handle = theron.create_polygon_object_with_data(vertices, polygons)
                if poly_handle is None:
                    _scale_map_poly_cache.pop(cache_key, None)
                    return
                _scale_map_poly_cache[cache_key] = (
                    poly_handle,
                    vgroup_obj.name,
                    vertex_count,
                    tri_count,
                )
            else:
                if vertex_count != prev_verts or tri_count != prev_tris:
                    theron.resize_polygon_object(poly_handle, vertex_count, tri_count)
                    _scale_map_poly_cache[cache_key] = (
                        poly_handle,
                        vgroup_obj.name,
                        vertex_count,
                        tri_count,
                    )
                theron.update_polygon_object_points(poly_handle, vertices)
        else:
            poly_handle = theron.create_polygon_object_with_data(vertices, polygons)
            if poly_handle is None:
                return
            _scale_map_poly_cache[cache_key] = (
                poly_handle,
                vgroup_obj.name,
                vertex_count,
                tri_count,
            )
        theron.set_matrix(poly_handle, world_matrix)

        if param == "GEOM":
            obj_link_id = "ID_NX_SCALE_SCALE_MAP_OBJECT"
        else:
            obj_link_id = f"{id_pfx}_MAP_OBJECT"
        theron.set_link(nc, get(obj_link_id), poly_handle)

        vgroup_name = getattr(item, f"{prop_pfx}_vertex_group", "")
        vgroup = vgroup_obj.vertex_groups.get(vgroup_name) if vgroup_name else None
        if vgroup is None:
            return

        vgi = vgroup.index
        weights = np.fromiter(
            (
                next((g.weight for g in v.groups if g.group == vgi), 0.0)
                for v in vgroup_obj.data.vertices
            ),
            dtype=np.float32,
            count=vertex_count,
        )

        if param == "GEOM":
            map_data_id = "ID_NX_SCALE_SCALE_MAP_LINK"
        else:
            map_data_id = f"{id_pfx}_MAP_LINK"
        theron.set_memory(
            nc,
            get(map_data_id),
            weights.ctypes.data_as(ctypes.c_void_p),
            weights.nbytes,
        )


def _sync_scale_params_ctx(theron, get, nc, item, item_orig, obj, _scene, depsgraph):
    param_val = get(SCALE_PARAM_IDS.get(item_orig.parameter, "ID_NX_SCALE_PARAM_GEOM"))
    theron.set_int32(nc, get("ID_NX_SCALE_PARAMETER"), param_val)

    theron.set_int32(
        nc,
        get("ID_NX_SCALE_REMAP_FALLOFF"),
        int(item.remap_falloff),
    )

    _sync_channel(theron, get, nc, item, item_orig.parameter, obj=obj, depsgraph=depsgraph)

    theron.set_int32(
        nc,
        get("ID_NX_SCALE_SCALE_SPLINE_QTABS"),
        SPLINE_CLAMP_VALUES.get(item.scale_spline_clamp, 1),
    )
    theron.set_int32(
        nc,
        get("ID_NX_SCALE_RADIUS_SPLINE_QTABS"),
        SPLINE_CLAMP_VALUES.get(item.radius_spline_clamp, 1),
    )
    theron.set_int32(
        nc,
        get("ID_NX_SCALE_MASS_SPLINE_QTABS"),
        SPLINE_CLAMP_VALUES.get(item.mass_spline_clamp, 1),
    )


def _pre_scale_tree_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del scene, depsgraph, collection_source
    if obj is None:
        return
    from ..pipeline_manager.identity import ensure_object_uid

    _scale_map_active_keys[ensure_object_uid(obj)] = set()


def _post_scale_tree_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del scene, depsgraph, collection_source
    if obj is None:
        return

    from ..pipeline_manager.identity import ensure_object_uid

    mod_uid = ensure_object_uid(obj)
    active_keys = _scale_map_active_keys.pop(mod_uid, set())
    stale_keys = [
        key for key in _scale_map_poly_cache if key[0] == mod_uid and key not in active_keys
    ]
    if not stale_keys:
        return

    from ..libs import theron

    for key in stale_keys:
        poly_handle, _name, _vc, _tc = _scale_map_poly_cache.pop(key)
        theron.free_polygon_object(poly_handle)


_SCALE_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_SCALE_OPERATION_TREE",
    collection_attr="scale_layers",
    pre_syncer=_pre_scale_tree_sync,
    post_syncer=_post_scale_tree_sync,
    type_id_map=SCALE_LAYER_TYPE_IDS,
    enabled_disables_blend=True,
    blend_spec=SCALE_BLEND_SPEC,
    pre_dispatch_syncer_ctx=_sync_scale_params_ctx,
    curve_specs=_ensure_curve_specs,
    gradient_specs=_ensure_gradient_specs,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_SCALE",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="scale_layers",
            prop=CollectionProperty(
                name="Scale Layers",
                type=NexusScaleLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="scale_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_layer_viewport,
            ),
        ),
    ),
    item_classes=(NexusScaleLayerItem,),
    enum_builders=(build_scale_enum_items,),
    nodetree_sync=(_SCALE_TREE_SPEC,),
)


register_collection_preset(
    "NX_SCALE",
    CollectionPresetSpec(
        collection_attr="scale_layers",
        menu_id="scale_layers",
        curve_specs=_ensure_curve_specs,
        gradient_specs=_ensure_gradient_specs,
        suffix_attr="layer_uid",
    ),
)


def add_default_scale_layer(obj):
    props = obj.nexus_modifier
    item = props.scale_layers.add()
    item.item_type = "RANGE"
    item.enabled = True
    item.blend_strength = 100.0
    item.layer_uid = os.urandom(4).hex()
    _create_layer_nodes(obj, item.layer_uid)
    auto_rename.initialize_added(item, props.scale_layers, _scale_layer_base_name(item))
    props.scale_layers_index = 0
