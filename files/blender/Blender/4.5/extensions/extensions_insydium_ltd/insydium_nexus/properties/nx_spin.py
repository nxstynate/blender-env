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
from ..ui.nodetree import auto_rename

SPIN_LAYER_DEFS = {
    "RANGE": {
        "name": "Range",
        "description": "Interpolate rotation over time",
        "icon_name": "nx_spin_layer_mode_range",
        "blender_icon": "SEQ_HISTOGRAM",
    },
    "SPIN": {
        "name": "Spin",
        "description": "Continuous spinning",
        "icon_name": "nx_spin_layer_mode_spin",
        "blender_icon": "FORCE_MAGNETIC",
    },
    "INCR_SPIN": {
        "name": "Incremental Spin",
        "description": "Incremental/accelerating spin",
        "icon_name": "nx_spin_layer_mode_incremental_spin",
        "blender_icon": "CON_ROTLIKE",
    },
    "ROT": {
        "name": "Rotate",
        "description": "Set particle rotation",
        "icon_name": "nx_spin_layer_mode_rotate",
        "blender_icon": "ORIENTATION_GIMBAL",
    },
    "TANG": {
        "name": "Tangential",
        "description": "Align to velocity direction",
        "icon_name": "nx_spin_layer_mode_tangential",
        "blender_icon": "CURVE_PATH",
    },
    "FACING": {
        "name": "Facing",
        "description": "Face camera, object or screen",
        "icon_name": "nx_spin_layer_mode_facing",
        "blender_icon": "HIDE_OFF",
    },
    "ROLL": {
        "name": "Roll",
        "description": "Physics-based rolling from velocity",
        "icon_name": "nx_spin_layer_mode_roll",
        "blender_icon": "MESH_CIRCLE",
    },
}

_SPIN_LAYER_ITEMS = []
_SPIN_TIME_MODE_ITEMS = []
_INCR_TIME_MODE_ITEMS = []
_RANGE_TIME_MODE_ITEMS = []

SPIN_LAYER_TYPE_IDS = {
    "SPIN": "ID_XP_SPIN_TREE_CHOICE_SPIN",
    "INCR_SPIN": "ID_XP_SPIN_TREE_CHOICE_INCR_SPIN",
    "ROT": "ID_XP_SPIN_TREE_CHOICE_ROT",
    "TANG": "ID_XP_SPIN_TREE_CHOICE_TANG",
    "FACING": "ID_XP_SPIN_TREE_CHOICE_FACING",
    "ROLL": "ID_XP_SPIN_TREE_CHOICE_ROLL",
    "RANGE": "ID_XP_SPIN_TREE_CHOICE_RANGE",
}

SPIN_BLEND_MODE_IDS = {
    "NORMAL": "ID_NX_SPIN_BLEND_NORMAL",
    "ADD": "ID_NX_SPIN_BLEND_ADD",
    "SUB": "ID_NX_SPIN_BLEND_SUB",
    "MULT": "ID_NX_SPIN_BLEND_MULT",
    "DIFFERENCE": "ID_NX_SPIN_BLEND_DIFFERENCE",
    "SCREEN": "ID_NX_SPIN_BLEND_SCREEN",
    "OVERLAY": "ID_NX_SPIN_BLEND_OVERLAY",
    "MIN": "ID_NX_SPIN_BLEND_MIN",
    "MAX": "ID_NX_SPIN_BLEND_MAX",
}

SPIN_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_SPIN_BLEND_MODE",
    strength_id_name="ID_NX_SPIN_BLEND_STRENGTH",
    id_map=SPIN_BLEND_MODE_IDS,
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


def _get_curve_spec():
    from ..utils.curve import CurveSpec

    return CurveSpec(
        slot_name="spin_ease",
        label="Ease",
        default_points=[(0.0, 0.0), (1.0, 1.0)],
        theron_ids=("ID_NX_SPIN_RANGE_SPLINE",),
        slot_suffix_attr="layer_uid",
    )


SPIN_EASE_CURVE_SPECS = None


def _ensure_curve_specs():
    global SPIN_EASE_CURVE_SPECS
    if SPIN_EASE_CURVE_SPECS is None:
        SPIN_EASE_CURVE_SPECS = [_get_curve_spec()]
    return SPIN_EASE_CURVE_SPECS


def _create_layer_curves(obj, uid):
    from ..utils.curve import create_item_curves

    create_item_curves(obj, uid, _ensure_curve_specs())


def _remove_layer_curves(obj, uid):
    from ..utils.curve import remove_item_curves

    remove_item_curves(obj, uid, _ensure_curve_specs())


_spin_layer_base_name = auto_rename.base_name_from_defs(SPIN_LAYER_DEFS)


def _on_spin_layer_add(context, obj, item):
    del context
    item.layer_uid = os.urandom(4).hex()
    _create_layer_curves(obj, item.layer_uid)
    layers = obj.nexus_modifier.spin_layers
    auto_rename.initialize_added(item, layers, _spin_layer_base_name(item))


def _on_spin_layer_remove(context, obj, item):
    if item.layer_uid:
        _remove_layer_curves(obj, item.layer_uid)


_SPIN_TIME_MODE_DEFS = [
    ("PER_FRAME", "Per Frame", "Spin amount per frame", "nx_spin_timing_frame"),
    ("PER_SECOND", "Per Second", "Spin amount per second", ""),
    ("ON_BIRTH", "On Birth", "Spin applied once at birth", "nx_spin_timing_birth"),
]

_INCR_TIME_MODE_DEFS = [
    ("PER_FRAME", "Per Frame", "Spin increment per frame", "nx_spin_timing_frame"),
    ("PER_SECOND", "Per Second", "Spin increment per second", ""),
]

_RANGE_TIME_MODE_DEFS = [
    ("BIRTH", "On Birth", "Interpolate from birth time", "nx_spin_timing_birth"),
    ("PARTICLE", "Particle Age", "Interpolate by particle age", "nx_spin_timing_particle"),
    ("FRAME", "Frame Time", "Interpolate by frame", "nx_spin_timing_frame"),
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


def build_spin_enum_items():
    global _SPIN_LAYER_ITEMS, _SPIN_TIME_MODE_ITEMS, _INCR_TIME_MODE_ITEMS
    global _RANGE_TIME_MODE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _SPIN_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(SPIN_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _SPIN_LAYER_ITEMS.append(
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
            _SPIN_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    _SPIN_TIME_MODE_ITEMS = _build_icon_enum(_SPIN_TIME_MODE_DEFS, get_icon)
    _INCR_TIME_MODE_ITEMS = _build_icon_enum(_INCR_TIME_MODE_DEFS, get_icon)
    _RANGE_TIME_MODE_ITEMS = _build_icon_enum(_RANGE_TIME_MODE_DEFS, get_icon)

    register_nodetree(
        "spin_layers",
        _SPIN_LAYER_ITEMS,
        "spin_layers",
        "spin_layers_index",
        on_add=_on_spin_layer_add,
        on_remove=_on_spin_layer_remove,
        separator_after={"RANGE"},
    )


def _get_spin_layer_items(self, context):
    return _SPIN_LAYER_ITEMS


def _get_spin_time_mode_items(self, context):
    return _SPIN_TIME_MODE_ITEMS


def _get_incr_time_mode_items(self, context):
    return _INCR_TIME_MODE_ITEMS


def _get_range_time_mode_items(self, context):
    return _RANGE_TIME_MODE_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


_on_item_type_update = auto_rename.on_trigger(
    base_name_fn=_spin_layer_base_name,
    collection_attr="spin_layers",
    pre=_update_layer_viewport,
)


class NexusSpinLayerItem(bpy.types.PropertyGroup):
    """Union pattern PropertyGroup for spin layers.

    All per-operation properties are defined here and conditionally
    shown based on item_type.
    """

    name: StringProperty(
        name="Name",
        description="Spin layer name",
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
        description="Enable this spin layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of spin operation",
        items=_get_spin_layer_items,
        default=0,
        update=_on_item_type_update,
    )

    blend_mode: EnumProperty(
        name="Blend",
        description="How this layer blends with previous layers",
        items=SPIN_BLEND_SPEC.enum_items(),
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

    # -- SPIN properties ------------------------------------------------------

    spin_time_mode: EnumProperty(
        name="Time Mode",
        description="How spin is applied over time",
        items=_get_spin_time_mode_items,
        default=0,
    )

    spin_relative_mode: EnumProperty(
        name="Relative To",
        description="Coordinate space for spin",
        items=[
            ("WORLD", "World", "World space"),
            ("PARTICLE", "Particle", "Particle local space"),
        ],
        default="WORLD",
    )

    spin_amount: FloatVectorProperty(
        name="Spin Amount",
        description="Spin rotation per step",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    spin_variation: FloatVectorProperty(
        name="Variation",
        description="Random variation in spin amount",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    spin_clamp: FloatVectorProperty(
        name="Clamp",
        description="Maximum accumulated spin",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    # -- INCR_SPIN properties -------------------------------------------------

    incr_time_mode: EnumProperty(
        name="Time Mode",
        description="How incremental spin is applied over time",
        items=_get_incr_time_mode_items,
        default=0,
    )

    incr_relative_mode: EnumProperty(
        name="Relative To",
        description="Coordinate space for incremental spin",
        items=[
            ("WORLD", "World", "World space"),
            ("PARTICLE", "Particle", "Particle local space"),
        ],
        default="WORLD",
    )

    incr_amount: FloatVectorProperty(
        name="Spin Amount",
        description="Incremental spin per step",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    incr_variation: FloatVectorProperty(
        name="Variation",
        description="Random variation in incremental amount",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    incr_clamp: FloatVectorProperty(
        name="Clamp",
        description="Maximum accumulated incremental spin",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    incr_clamp_variation: FloatVectorProperty(
        name="Clamp Variation",
        description="Random variation in clamp values",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    # -- ROT properties -------------------------------------------------------

    rot_mode: EnumProperty(
        name="Rotation Mode",
        description="Rotation application mode",
        items=[
            ("ABSOLUTE", "Absolute", "Set rotation to value"),
            ("RELATIVE", "Relative", "Add rotation to current"),
        ],
        default="ABSOLUTE",
    )

    rot_amount: FloatVectorProperty(
        name="Rotation Amount",
        description="Rotation amount",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    rot_variation: FloatVectorProperty(
        name="Variation",
        description="Random variation in rotation",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    rot_use_time: BoolProperty(
        name="Use Time",
        description="Interpolate rotation over time",
        default=False,
    )

    rot_time: nexus_time_property(
        "rot_time",
        name="Time",
        description="Time to reach target rotation",
        default=0.0,
        min=0.0,
        soft_max=1000.0,
        collection_path="spin_layers",
    )

    # -- TANG properties ------------------------------------------------------

    tang_axis_mode: EnumProperty(
        name="Tangential Axis",
        description="Tangent alignment axis",
        items=[
            ("X", "X", "Align X axis to velocity"),
            ("Y", "Y", "Align Y axis to velocity"),
            ("Z", "Z", "Align Z axis to velocity"),
        ],
        default="Y",
    )

    tang_amount: FloatVectorProperty(
        name="Rotation Offset",
        description="Additional rotation offset",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    tang_variation: FloatVectorProperty(
        name="Variation",
        description="Random variation in offset",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    tang_spin_enabled: BoolProperty(
        name="Axis Spin",
        description="Enable spin around tangent axis",
        default=False,
    )

    tang_spin_speed: FloatProperty(
        name="Spin Amount",
        description="Rotation speed around tangent axis",
        default=0.0,
        subtype="ANGLE",
    )

    tang_spin_speed_var: FloatProperty(
        name="Variation",
        description="Random variation in spin speed",
        default=0.0,
        min=0.0,
        subtype="ANGLE",
    )

    # -- FACING properties ----------------------------------------------------

    facing_mode: EnumProperty(
        name="Mode",
        description="What to face towards",
        items=[
            ("CAMERA", "Face Camera", "Face active camera"),
            ("OBJECT", "Face Object", "Face target object"),
            ("SCREEN", "Face Screen", "Face screen plane"),
        ],
        default="CAMERA",
    )

    facing_object: PointerProperty(
        name="Target",
        description="Object to face towards",
        type=bpy.types.Object,
    )

    # -- RANGE properties -----------------------------------------------------

    range_time_mode: EnumProperty(
        name="Spin Time",
        description="Time basis for interpolation",
        items=_get_range_time_mode_items,
        default=1,
    )

    range_relative_mode: EnumProperty(
        name="Orientation",
        description="Coordinate space for rotation",
        items=[
            ("WORLD", "World", "World space"),
            ("PARTICLE", "Particle", "Particle local space"),
        ],
        default="WORLD",
    )

    range_start: FloatVectorProperty(
        name="Spin Start",
        description="Rotation at start of range",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    range_start_var: FloatVectorProperty(
        name="Variation",
        description="Random variation in start rotation",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    range_end: FloatVectorProperty(
        name="Spin End",
        description="Rotation at end of range",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    range_end_var: FloatVectorProperty(
        name="Variation",
        description="Random variation in end rotation",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype="EULER",
    )

    range_time_start: nexus_time_property(
        "range_time_start",
        name="Start Time",
        description="Start time for interpolation",
        default=0.0,
        collection_path="spin_layers",
    )

    range_time_end: nexus_time_property(
        "range_time_end",
        name="End Time",
        description="End time for interpolation",
        default=60.0,
        collection_path="spin_layers",
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


def _draw_ease_curve(col, item):
    obj = bpy.context.object
    if not obj or not item.layer_uid:
        return
    from ..utils.curve import NexusCurve

    col.prop(item, "range_spline_clamp")
    NexusCurve(obj, f"spin_ease_{item.layer_uid}").draw_ui(col, "Ease")


def _draw_spin_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "spin_time_mode")
    col.prop(item, "spin_relative_mode")

    col.separator(type="LINE")

    col.prop(item, "spin_amount")
    col.prop(item, "spin_variation")

    col.separator(type="LINE")

    col.prop(item, "spin_clamp")


def _draw_incr_spin_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "incr_time_mode")
    col.prop(item, "incr_relative_mode")

    col.separator(type="LINE")

    col.prop(item, "incr_amount")
    col.prop(item, "incr_variation")
    col.prop(item, "incr_clamp")
    col.prop(item, "incr_clamp_variation")


def _draw_rot_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "rot_mode")

    col.separator(type="LINE")

    col.prop(item, "rot_amount")
    col.prop(item, "rot_variation")

    col.separator(type="LINE")

    col.prop(item, "rot_use_time")
    sub = col.column()
    sub.enabled = item.rot_use_time
    draw_time_prop(sub, item, "rot_time")


def _draw_tang_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "tang_axis_mode")

    col.separator(type="LINE")

    col.prop(item, "tang_amount")
    col.prop(item, "tang_variation")

    col.separator(type="LINE")

    col.prop(item, "tang_spin_enabled")
    sub = col.column()
    sub.enabled = item.tang_spin_enabled
    sub.prop(item, "tang_spin_speed")
    sub.prop(item, "tang_spin_speed_var")


def _draw_facing_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "facing_mode")

    if item.facing_mode == "OBJECT":
        col.prop(item, "facing_object")


def _draw_roll_settings(layout, item):
    _draw_layer_header(layout, item)


def _draw_range_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "range_time_mode")
    col.prop(item, "range_relative_mode")

    col.separator(type="LINE")

    col.prop(item, "range_start")
    col.prop(item, "range_start_var")

    col.separator(type="LINE")

    col.prop(item, "range_end")
    col.prop(item, "range_end_var")

    if item.range_time_mode in ("PARTICLE", "FRAME"):
        col.separator(type="LINE")

        draw_time_prop(col, item, "range_time_start")
        draw_time_prop(col, item, "range_time_end")
        col.prop(item, "range_time_var")

        col.separator(type="LINE")

        _draw_ease_curve(col, item)


LAYER_DRAW_FUNCS = {
    "SPIN": _draw_spin_settings,
    "INCR_SPIN": _draw_incr_spin_settings,
    "ROT": _draw_rot_settings,
    "TANG": _draw_tang_settings,
    "FACING": _draw_facing_settings,
    "ROLL": _draw_roll_settings,
    "RANGE": _draw_range_settings,
}


def draw_spin_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


SPIN_TIME_MODE_IDS = {
    "PER_FRAME": "ID_NX_SPIN_SPIN_TIME_MODE_PER_FRAME",
    "PER_SECOND": "ID_NX_SPIN_SPIN_TIME_MODE_PER_SECOND",
    "ON_BIRTH": "ID_NX_SPIN_SPIN_TIME_MODE_ON_BIRTH",
}

SPIN_RELATIVE_MODE_IDS = {
    "WORLD": "ID_NX_SPIN_RELATIVE_MODE_WORLD",
    "PARTICLE": "ID_NX_SPIN_RELATIVE_MODE_PARTICLE",
}

INCR_TIME_MODE_IDS = {
    "PER_FRAME": "ID_NX_SPIN_SPIN_INCR_TIME_MODE_PER_FRAME",
    "PER_SECOND": "ID_NX_SPIN_SPIN_INCR_TIME_MODE_PER_SECOND",
}

INCR_RELATIVE_MODE_IDS = {
    "WORLD": "ID_NX_SPIN_INCR_RELATIVE_MODE_WORLD",
    "PARTICLE": "ID_NX_SPIN_INCR_RELATIVE_MODE_PARTICLE",
}

ROT_MODE_IDS = {
    "ABSOLUTE": "ID_NX_SPIN_ROT_ROT_MODE_ABSOLUTE",
    "RELATIVE": "ID_NX_SPIN_ROT_ROT_MODE_RELATIVE",
}

TANG_AXIS_MODE_IDS = {
    "X": "ID_NX_SPIN_TANG_AXIS_MODE_X",
    "Y": "ID_NX_SPIN_TANG_AXIS_MODE_Z",
    "Z": "ID_NX_SPIN_TANG_AXIS_MODE_Y",
}

FACING_MODE_IDS = {
    "CAMERA": "ID_NX_SPIN_FACING_MODE_CAMERA",
    "OBJECT": "ID_NX_SPIN_FACING_MODE_OBJECT",
    "SCREEN": "ID_NX_SPIN_FACING_MODE_SCREEN",
}

RANGE_TIME_MODE_IDS = {
    "BIRTH": "ID_NX_SPIN_RANGE_TIME_MODE_BIRTH",
    "PARTICLE": "ID_NX_SPIN_RANGE_TIME_MODE_PARTICLE",
    "FRAME": "ID_NX_SPIN_RANGE_TIME_MODE_FRAME",
}

RANGE_RELATIVE_MODE_IDS = {
    "WORLD": "ID_NX_SPIN_RANGE_RELATIVE_MODE_WORLD",
    "PARTICLE": "ID_NX_SPIN_RANGE_RELATIVE_MODE_PARTICLE",
}

SPLINE_CLAMP_IDS = {
    "CLAMP": "ID_NX_SPIN_RANGE_SPLINE_QTABS_CLAMP",
    "CYCLE": "ID_NX_SPIN_RANGE_SPLINE_QTABS_CYCLE",
    "CONTINUE": "ID_NX_SPIN_RANGE_SPLINE_QTABS_CONTINUE",
}

_PCT = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]


def _sync_spin_layer(theron, get, nc, item, _item_orig, _obj):
    time_mode_val = get(
        SPIN_TIME_MODE_IDS.get(item.spin_time_mode, "ID_NX_SPIN_SPIN_TIME_MODE_PER_FRAME")
    )
    theron.set_int32(nc, get("ID_NX_SPIN_SPIN_TIME_MODE"), time_mode_val)

    rel_mode_val = get(
        SPIN_RELATIVE_MODE_IDS.get(item.spin_relative_mode, "ID_NX_SPIN_RELATIVE_MODE_WORLD")
    )
    theron.set_int32(nc, get("ID_NX_SPIN_RELATIVE_MODE"), rel_mode_val)

    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_AMOUNT"),
        item.spin_amount[2],
        item.spin_amount[0],
        item.spin_amount[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_VARIATION"),
        item.spin_variation[2],
        item.spin_variation[0],
        item.spin_variation[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_CLAMP"),
        item.spin_clamp[2],
        item.spin_clamp[0],
        item.spin_clamp[1],
    )


def _sync_incr_spin_layer(theron, get, nc, item, _item_orig, _obj):
    time_mode_val = get(
        INCR_TIME_MODE_IDS.get(item.incr_time_mode, "ID_NX_SPIN_SPIN_INCR_TIME_MODE_PER_FRAME")
    )
    theron.set_int32(nc, get("ID_NX_SPIN_SPIN_INCR_TIME_MODE"), time_mode_val)

    rel_mode_val = get(
        INCR_RELATIVE_MODE_IDS.get(item.incr_relative_mode, "ID_NX_SPIN_INCR_RELATIVE_MODE_WORLD")
    )
    theron.set_int32(nc, get("ID_NX_SPIN_INCR_RELATIVE_MODE"), rel_mode_val)

    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_INCR_AMOUNT"),
        item.incr_amount[2],
        item.incr_amount[0],
        item.incr_amount[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_INCR_VARIATION"),
        item.incr_variation[2],
        item.incr_variation[0],
        item.incr_variation[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_INCR_CLAMP"),
        item.incr_clamp[2],
        item.incr_clamp[0],
        item.incr_clamp[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_SPIN_INCR_CLAMP_VARIATION"),
        item.incr_clamp_variation[2],
        item.incr_clamp_variation[0],
        item.incr_clamp_variation[1],
    )


def _sync_rot_layer(theron, get, nc, item, _item_orig, _obj):
    rot_mode_val = get(ROT_MODE_IDS.get(item.rot_mode, "ID_NX_SPIN_ROT_ROT_MODE_ABSOLUTE"))
    theron.set_int32(nc, get("ID_NX_SPIN_ROT_ROT_MODE"), rot_mode_val)

    theron.set_vector(
        nc,
        get("ID_NX_SPIN_ROT_AMOUNT"),
        item.rot_amount[2],
        item.rot_amount[0],
        item.rot_amount[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_ROT_VARIATION"),
        item.rot_variation[2],
        item.rot_variation[0],
        item.rot_variation[1],
    )

    theron.set_bool(nc, get("ID_NX_SPIN_ROT_USE_TIME"), item.rot_use_time)

    mode = get_prop_time_mode(item, "rot_time")
    num, den = to_time_fraction(item.rot_time, mode=mode)
    theron.set_time(nc, get("ID_NX_SPIN_ROT_TIME"), num, den)


def _sync_tang_layer(theron, get, nc, item, _item_orig, _obj):
    axis_mode_val = get(TANG_AXIS_MODE_IDS.get(item.tang_axis_mode, "ID_NX_SPIN_TANG_AXIS_MODE_X"))
    theron.set_int32(nc, get("ID_NX_SPIN_TANG_AXIS_MODE"), axis_mode_val)

    theron.set_vector(
        nc,
        get("ID_NX_SPIN_TANG_AMOUNT"),
        item.tang_amount[2],
        item.tang_amount[0],
        item.tang_amount[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_TANG_VARIATION"),
        item.tang_variation[2],
        item.tang_variation[0],
        item.tang_variation[1],
    )

    theron.set_int32(nc, get("ID_NX_SPIN_TANG_SPIN"), int(item.tang_spin_enabled))
    theron.set_float(nc, get("ID_NX_SPIN_TANG_SPIN_FLOAT"), item.tang_spin_speed)
    theron.set_float(nc, get("ID_NX_SPIN_TANG_SPIN_FLOAT_VAR"), item.tang_spin_speed_var)


def _sync_facing_layer(theron, get, nc, item, _item_orig, _obj):
    facing_mode_val = get(FACING_MODE_IDS.get(item.facing_mode, "ID_NX_SPIN_FACING_MODE_CAMERA"))
    theron.set_int32(nc, get("ID_NX_SPIN_FACING_MODE"), facing_mode_val)

    theron.set_vector(nc, get("ID_NX_SPIN_FACING_OBJ"), 0.0, 0.0, 0.0)


def _sync_range_layer(theron, get, nc, item, _item_orig, obj):
    time_mode_val = get(
        RANGE_TIME_MODE_IDS.get(item.range_time_mode, "ID_NX_SPIN_RANGE_TIME_MODE_BIRTH")
    )
    theron.set_int32(nc, get("ID_NX_SPIN_RANGE_TIME_MODE"), time_mode_val)

    rel_mode_val = get(
        RANGE_RELATIVE_MODE_IDS.get(
            item.range_relative_mode, "ID_NX_SPIN_RANGE_RELATIVE_MODE_WORLD"
        )
    )
    theron.set_int32(nc, get("ID_NX_SPIN_RANGE_RELATIVE_MODE"), rel_mode_val)

    theron.set_vector(
        nc,
        get("ID_NX_SPIN_RANGE_START"),
        item.range_start[2],
        item.range_start[0],
        item.range_start[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_RANGE_START_VAR"),
        item.range_start_var[2],
        item.range_start_var[0],
        item.range_start_var[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_RANGE_END"),
        item.range_end[2],
        item.range_end[0],
        item.range_end[1],
    )
    theron.set_vector(
        nc,
        get("ID_NX_SPIN_RANGE_END_VAR"),
        item.range_end_var[2],
        item.range_end_var[0],
        item.range_end_var[1],
    )

    mode_s = get_prop_time_mode(item, "range_time_start")
    num_s, den_s = to_time_fraction(item.range_time_start, mode=mode_s)
    theron.set_time(nc, get("ID_NX_SPIN_RANGE_TIME_START"), num_s, den_s)

    mode_e = get_prop_time_mode(item, "range_time_end")
    num_e, den_e = to_time_fraction(item.range_time_end, mode=mode_e)
    theron.set_time(nc, get("ID_NX_SPIN_RANGE_TIME_END"), num_e, den_e)

    theron.set_float(
        nc,
        get("ID_NX_SPIN_RANGE_TIME_VAR"),
        item.range_time_var * _PCT,
    )

    spline_clamp_id = SPLINE_CLAMP_IDS.get(
        item.range_spline_clamp, "ID_NX_SPIN_RANGE_SPLINE_QTABS_CLAMP"
    )
    theron.set_int32(nc, get("ID_NX_SPIN_RANGE_SPLINE_QTABS"), get(spline_clamp_id))


_SPIN_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_SPIN_OPERATION_TREE",
    collection_attr="spin_layers",
    type_id_map=SPIN_LAYER_TYPE_IDS,
    enabled_disables_blend=True,
    blend_spec=SPIN_BLEND_SPEC,
    curve_specs=_ensure_curve_specs,
    per_type_syncers={
        "SPIN": _sync_spin_layer,
        "INCR_SPIN": _sync_incr_spin_layer,
        "ROT": _sync_rot_layer,
        "TANG": _sync_tang_layer,
        "FACING": _sync_facing_layer,
        "RANGE": _sync_range_layer,
    },
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_SPIN",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="spin_layers",
            prop=CollectionProperty(
                name="Spin Layers",
                type=NexusSpinLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="spin_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_layer_viewport,
            ),
        ),
    ),
    item_classes=(NexusSpinLayerItem,),
    enum_builders=(build_spin_enum_items,),
    nodetree_sync=(_SPIN_TREE_SPEC,),
)


register_collection_preset(
    "NX_SPIN",
    CollectionPresetSpec(
        collection_attr="spin_layers",
        menu_id="spin_layers",
        curve_specs=_ensure_curve_specs,
        suffix_attr="layer_uid",
    ),
)


def add_default_spin_layer(obj):
    props = obj.nexus_modifier
    item = props.spin_layers.add()
    item.item_type = "RANGE"
    item.enabled = True
    item.blend_strength = 100.0
    item.layer_uid = os.urandom(4).hex()
    _create_layer_curves(obj, item.layer_uid)
    auto_rename.initialize_added(item, props.spin_layers, _spin_layer_base_name(item))
    props.spin_layers_index = 0
