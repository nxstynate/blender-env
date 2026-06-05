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

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
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
from ..ui.nodetree import auto_rename

SPEED_LAYER_DEFS = {
    "RANGE": {
        "name": "Range",
        "description": "Interpolate speed over time",
        "icon_name": "nx_speed_layer_mode_range",
        "blender_icon": "SEQ_HISTOGRAM",
    },
    "INCR": {
        "name": "Incremental",
        "description": "Incremental speed change",
        "icon_name": "nx_speed_layer_mode_incremental",
        "blender_icon": "SORT_ASC",
    },
    "ABSOLUTE": {
        "name": "Absolute",
        "description": "Set absolute speed",
        "icon_name": "nx_speed_layer_mode_absolute",
        "blender_icon": "ARROW_LEFTRIGHT",
    },
    "ACCEL": {
        "name": "Exponential",
        "description": "Exponential speed change",
        "icon_name": "nx_speed_layer_mode_acceleration",
        "blender_icon": "TRACKING_FORWARDS",
    },
    "SPLINE": {
        "name": "Use Spline",
        "description": "Speed from spline curve",
        "icon_name": "nx_speed_layer_mode_spline",
        "blender_icon": "CURVE_DATA",
    },
}

_SPEED_LAYER_ITEMS = []
_RANGE_TIME_MODE_ITEMS = []

SPEED_LAYER_TYPE_IDS = {
    "INCR": "ID_NX_SPEED_OP_INCR",
    "ABSOLUTE": "ID_NX_SPEED_OP_ABSOLUTE",
    "ACCEL": "ID_NX_SPEED_OP_ACCEL",
    "SPLINE": "ID_NX_SPEED_OP_SPLINE",
    "RANGE": "ID_NX_SPEED_OP_RANGE",
}

SPEED_BLEND_MODE_IDS = {
    "NORMAL": "ID_NX_SPEED_BLEND_NORMAL",
    "ADD": "ID_NX_SPEED_BLEND_ADD",
    "SUB": "ID_NX_SPEED_BLEND_SUB",
    "MULT": "ID_NX_SPEED_BLEND_MULT",
    "DIFFERENCE": "ID_NX_SPEED_BLEND_DIFFERENCE",
    "SCREEN": "ID_NX_SPEED_BLEND_SCREEN",
    "OVERLAY": "ID_NX_SPEED_BLEND_OVERLAY",
    "MIN": "ID_NX_SPEED_BLEND_MIN",
    "MAX": "ID_NX_SPEED_BLEND_MAX",
}

SPEED_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_SPEED_BLEND_MODE",
    strength_id_name="ID_NX_SPEED_BLEND_STRENGTH",
    id_map=SPEED_BLEND_MODE_IDS,
    labels={
        "NORMAL": ("Normal", "Standard blend"),
        "ADD": ("Add", "Add to previous"),
        "SUB": ("Subtract", "Subtract from previous"),
        "MULT": ("Multiply", "Multiply with previous"),
        "DIFFERENCE": ("Difference", "Difference blend"),
        "SCREEN": ("Screen", "Screen blend"),
        "OVERLAY": ("Overlay", "Overlay blend"),
        "MIN": ("Min", "Minimum of values"),
        "MAX": ("Max", "Maximum of values"),
    },
)


def _get_curve_specs():
    from ..utils.curve import CurveSpec

    return [
        CurveSpec(
            slot_name="speed_spline",
            label="Speed Spline",
            default_points=[(0.0, 0.0), (1.0, 1.0)],
            theron_ids=("ID_NX_SPEED_SPLINE",),
            slot_suffix_attr="layer_uid",
        ),
        CurveSpec(
            slot_name="speed_ease",
            label="Ease",
            default_points=[(0.0, 0.0), (1.0, 1.0)],
            theron_ids=("ID_NX_SPEED_RANGE_SPLINE",),
            slot_suffix_attr="layer_uid",
        ),
    ]


SPEED_CURVE_SPECS = None


def _ensure_curve_specs():
    global SPEED_CURVE_SPECS
    if SPEED_CURVE_SPECS is None:
        SPEED_CURVE_SPECS = _get_curve_specs()
    return SPEED_CURVE_SPECS


def _create_layer_curves(obj, uid):
    from ..utils.curve import create_item_curves

    create_item_curves(obj, uid, _ensure_curve_specs())


def _remove_layer_curves(obj, uid):
    from ..utils.curve import remove_item_curves

    remove_item_curves(obj, uid, _ensure_curve_specs())


_speed_layer_base_name = auto_rename.base_name_from_defs(SPEED_LAYER_DEFS)


def _on_speed_layer_add(context, obj, item):
    del context
    item.layer_uid = os.urandom(4).hex()
    _create_layer_curves(obj, item.layer_uid)
    layers = obj.nexus_modifier.speed_layers
    auto_rename.initialize_added(item, layers, _speed_layer_base_name(item))


def _on_speed_layer_remove(context, obj, item):
    if item.layer_uid:
        _remove_layer_curves(obj, item.layer_uid)


_RANGE_TIME_MODE_DEFS = [
    ("BIRTH", "On Birth", "Interpolate from birth time", "nx_speed_timing_birth"),
    ("PARTICLE", "Particle Age", "Interpolate by particle age", "nx_speed_timing_particle"),
    ("FRAME", "Frame Time", "Interpolate by frame", "nx_speed_timing_frame"),
]


def _build_icon_enum(defs, get_icon):
    items = []
    for idx, (eid, label, desc, icon_name) in enumerate(defs):
        icon_id = get_icon(icon_name) if icon_name else 0
        if icon_id and icon_id > 0:
            items.append((eid, label, desc, icon_id, idx))
        else:
            items.append((eid, label, desc, "NONE", idx))
    return items


def build_speed_enum_items():
    global _SPEED_LAYER_ITEMS, _RANGE_TIME_MODE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _SPEED_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(SPEED_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _SPEED_LAYER_ITEMS.append(
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
            _SPEED_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    _RANGE_TIME_MODE_ITEMS = _build_icon_enum(_RANGE_TIME_MODE_DEFS, get_icon)

    register_nodetree(
        "speed_layers",
        _SPEED_LAYER_ITEMS,
        "speed_layers",
        "speed_layers_index",
        on_add=_on_speed_layer_add,
        on_remove=_on_speed_layer_remove,
        separator_after={"RANGE"},
    )


def _get_speed_layer_items(self, context):
    return _SPEED_LAYER_ITEMS


def _get_range_time_mode_items(self, context):
    return _RANGE_TIME_MODE_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


_on_item_type_update = auto_rename.on_trigger(
    base_name_fn=_speed_layer_base_name,
    collection_attr="speed_layers",
    pre=_update_layer_viewport,
)


class NexusSpeedLayerItem(bpy.types.PropertyGroup):
    """Union pattern PropertyGroup for speed layers.

    All per-operation properties are defined here and conditionally
    shown based on item_type.
    """

    name: StringProperty(
        name="Name",
        description="Speed layer name",
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
        description="Enable this speed layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of speed operation",
        items=_get_speed_layer_items,
        default=0,
        update=_on_item_type_update,
    )

    blend_mode: EnumProperty(
        name="Blend",
        description="How this layer blends with previous layers",
        items=SPEED_BLEND_SPEC.enum_items(),
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

    layer_uid: StringProperty(
        name="",
        default="",
        options={"HIDDEN"},
    )

    # -- INCR / ABSOLUTE properties --------------------------------------------

    delta: FloatProperty(
        name="Speed Value",
        description="Speed value",
        default=1.5,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    delta_var: FloatProperty(
        name="Variation",
        description="Speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    accel: FloatProperty(
        name="Acceleration",
        description="Acceleration value",
        default=5.0,
    )

    clamp_min: BoolProperty(
        name="Clamp Min",
        description="Enable minimum speed clamp",
        default=False,
    )

    speed_min: FloatProperty(
        name="Particle Speed Min",
        description="Minimum particle speed",
        default=0.0,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    speed_min_var: FloatProperty(
        name="Variation",
        description="Min speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    clamp_max: BoolProperty(
        name="Clamp Max",
        description="Enable maximum speed clamp",
        default=False,
    )

    speed_max: FloatProperty(
        name="Particle Speed Max",
        description="Maximum particle speed",
        default=5.0,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    speed_max_var: FloatProperty(
        name="Variation",
        description="Max speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    spline_float: FloatProperty(
        name="Speed Max",
        description="Maximum speed multiplier for spline",
        default=3.0,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    spline_float_var: FloatProperty(
        name="Variation",
        description="Spline speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    range_time_mode: EnumProperty(
        name="Speed Time",
        description="Time basis for interpolation",
        items=_get_range_time_mode_items,
        default=1,
    )

    range_start: FloatProperty(
        name="Speed Start",
        description="Start speed",
        default=0.0,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    range_start_var: FloatProperty(
        name="Variation",
        description="Start speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    range_end: FloatProperty(
        name="Speed End",
        description="End speed",
        default=1.5,
        unit="LENGTH",
        subtype="DISTANCE",
    )

    range_end_var: FloatProperty(
        name="Variation",
        description="End speed variation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    range_time_start: nexus_time_property(
        "range_time_start",
        name="Start Time",
        description="Start time for interpolation",
        default=0.0,
        collection_path="speed_layers",
    )

    range_time_end: nexus_time_property(
        "range_time_end",
        name="End Time",
        description="End time for interpolation",
        default=60.0,
        collection_path="speed_layers",
    )

    range_time_var: FloatProperty(
        name="Time Variation",
        description="Random variation in timing",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    range_spline_clamp: EnumProperty(
        name="Clamp Mode",
        description="Spline boundary behavior",
        items=[
            ("CLAMP", "Clamp", "Clamp at boundaries"),
            ("CYCLE", "Repeat", "Repeat the spline"),
            ("CONTINUE", "Continue", "Continue past boundaries"),
        ],
        default="CLAMP",
    )


def _draw_layer_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "blend_strength")

    return col


def _draw_clamp_section(col, item):
    col.separator(type="LINE")

    col.prop(item, "clamp_min")
    sub = col.column()
    sub.enabled = item.clamp_min
    sub.prop(item, "speed_min")
    sub.prop(item, "speed_min_var")

    col.prop(item, "clamp_max")
    sub = col.column()
    sub.enabled = item.clamp_max
    sub.prop(item, "speed_max")
    sub.prop(item, "speed_max_var")


def _draw_spline_curve(col, item):
    obj = bpy.context.object
    if not obj or not item.layer_uid:
        return
    from ..utils.curve import NexusCurve

    NexusCurve(obj, f"speed_spline_{item.layer_uid}").draw_ui(col, "Speed Spline")


def _draw_ease_curve(col, item):
    obj = bpy.context.object
    if not obj or not item.layer_uid:
        return
    from ..utils.curve import NexusCurve

    col.prop(item, "range_spline_clamp")
    NexusCurve(obj, f"speed_ease_{item.layer_uid}").draw_ui(col, "Ease")


def _draw_incr_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "delta")
    col.prop(item, "delta_var")

    _draw_clamp_section(col, item)


def _draw_absolute_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "delta")
    col.prop(item, "delta_var")

    _draw_clamp_section(col, item)


def _draw_accel_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "accel")

    _draw_clamp_section(col, item)


def _draw_spline_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    _draw_spline_curve(col, item)

    col.prop(item, "spline_float")
    col.prop(item, "spline_float_var")


def _draw_range_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "range_time_mode")

    col.separator(type="LINE")

    if item.range_time_mode == "BIRTH":
        col.prop(item, "range_end")
        col.prop(item, "range_end_var")
    else:
        col.prop(item, "range_start")
        col.prop(item, "range_start_var")

        col.separator(type="LINE")

        col.prop(item, "range_end")
        col.prop(item, "range_end_var")

        col.separator(type="LINE")

        draw_time_prop(col, item, "range_time_start")
        draw_time_prop(col, item, "range_time_end")
        col.prop(item, "range_time_var")

        col.separator(type="LINE")

        _draw_ease_curve(col, item)

        _draw_clamp_section(col, item)


LAYER_DRAW_FUNCS = {
    "INCR": _draw_incr_settings,
    "ABSOLUTE": _draw_absolute_settings,
    "ACCEL": _draw_accel_settings,
    "SPLINE": _draw_spline_settings,
    "RANGE": _draw_range_settings,
}


def draw_speed_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


RANGE_TIME_MODE_IDS = {
    "BIRTH": "ID_NX_SPEED_RANGE_TIME_MODE_BIRTH",
    "PARTICLE": "ID_NX_SPEED_RANGE_TIME_MODE_PARTICLE",
    "FRAME": "ID_NX_SPEED_RANGE_TIME_MODE_FRAME",
}

SPLINE_CLAMP_IDS = {
    "CLAMP": "ID_NX_SPEED_RANGE_SPLINE_QTABS_CLAMP",
    "CYCLE": "ID_NX_SPEED_RANGE_SPLINE_QTABS_CYCLE",
    "CONTINUE": "ID_NX_SPEED_RANGE_SPLINE_QTABS_CONTINUE",
}

_PCT = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_UNIT = TRANSFORM_FACTORS[Transform.UNIT_SCALE]
_ACCEL_SCALE = 0.001


def _sync_speed_params(theron, get, nc, item, item_orig, obj):
    layer_op_name = SPEED_LAYER_TYPE_IDS.get(item_orig.item_type)
    if layer_op_name is not None:
        theron.set_int32(nc, get("ID_NX_SPEED_LAYER_OP"), get(layer_op_name))

    theron.set_float(nc, get("ID_NX_SPEED_ACCEL"), item.accel * _ACCEL_SCALE)
    theron.set_float(nc, get("ID_NX_SPEED_DELTA"), item.delta * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_DELTA_VAR"), item.delta_var * _PCT)

    theron.set_bool(nc, get("ID_NX_SPEED_CLAMP_MIN"), item.clamp_min)
    theron.set_float(nc, get("ID_NX_SPEED_MIN"), item.speed_min * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_MIN_VAR"), item.speed_min_var * _PCT)
    theron.set_bool(nc, get("ID_NX_SPEED_CLAMP_MAX"), item.clamp_max)
    theron.set_float(nc, get("ID_NX_SPEED_MAX"), item.speed_max * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_MAX_VAR"), item.speed_max_var * _PCT)

    theron.set_float(nc, get("ID_NX_SPEED_SPLINE_FLOAT"), item.spline_float * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_SPLINE_FLOAT_VAR"), item.spline_float_var * _PCT)

    range_time_mode_val = get(
        RANGE_TIME_MODE_IDS.get(item.range_time_mode, "ID_NX_SPEED_RANGE_TIME_MODE_BIRTH")
    )
    theron.set_int32(nc, get("ID_NX_SPEED_RANGE_TIME_MODE"), range_time_mode_val)
    theron.set_float(nc, get("ID_NX_SPEED_RANGE_START"), item.range_start * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_RANGE_START_VAR"), item.range_start_var * _PCT)
    theron.set_float(nc, get("ID_NX_SPEED_RANGE_END"), item.range_end * _UNIT)
    theron.set_float(nc, get("ID_NX_SPEED_RANGE_END_VAR"), item.range_end_var * _PCT)

    mode_s = get_prop_time_mode(item, "range_time_start")
    num_s, den_s = to_time_fraction(item.range_time_start, mode=mode_s)
    theron.set_time(nc, get("ID_NX_SPEED_RANGE_TIME_START"), num_s, den_s)

    mode_e = get_prop_time_mode(item, "range_time_end")
    num_e, den_e = to_time_fraction(item.range_time_end, mode=mode_e)
    theron.set_time(nc, get("ID_NX_SPEED_RANGE_TIME_END"), num_e, den_e)

    theron.set_float(nc, get("ID_NX_SPEED_RANGE_TIME_VAR"), item.range_time_var * _PCT)

    spline_clamp_val = get(
        SPLINE_CLAMP_IDS.get(item.range_spline_clamp, "ID_NX_SPEED_RANGE_SPLINE_QTABS_CLAMP")
    )
    theron.set_int32(nc, get("ID_NX_SPEED_RANGE_SPLINE_QTABS"), spline_clamp_val)


_SPEED_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_SPEED_OPERATION_TREE",
    collection_attr="speed_layers",
    type_id_map=SPEED_LAYER_TYPE_IDS,
    node_id_offset=2000,
    enabled_disables_blend=True,
    blend_spec=SPEED_BLEND_SPEC,
    pre_dispatch_syncer=_sync_speed_params,
    curve_specs=_ensure_curve_specs,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_SPEED",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="speed_layers",
            prop=CollectionProperty(
                name="Speed Layers",
                type=NexusSpeedLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="speed_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_layer_viewport,
            ),
        ),
    ),
    item_classes=(NexusSpeedLayerItem,),
    enum_builders=(build_speed_enum_items,),
    nodetree_sync=(_SPEED_TREE_SPEC,),
)


register_collection_preset(
    "NX_SPEED",
    CollectionPresetSpec(
        collection_attr="speed_layers",
        menu_id="speed_layers",
        curve_specs=_ensure_curve_specs,
        suffix_attr="layer_uid",
    ),
)


def add_default_speed_layer(obj):
    props = obj.nexus_modifier
    item = props.speed_layers.add()
    item.item_type = "INCR"
    item.enabled = True
    item.blend_strength = 100.0
    item.layer_uid = os.urandom(4).hex()
    _create_layer_curves(obj, item.layer_uid)
    auto_rename.initialize_added(item, props.speed_layers, _speed_layer_base_name(item))
    props.speed_layers_index = 0
