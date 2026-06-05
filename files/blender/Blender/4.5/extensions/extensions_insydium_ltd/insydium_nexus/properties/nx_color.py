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
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import draw_time_prop, nexus_time_property
from ..libs.nodetree_sync import BlendSpec, NodeTreeSyncSpec
from ..libs.theron_sync import TRANSFORM_FACTORS, Transform
from ..ui.nodetree import auto_rename
from ..utils.gradient import (
    GradientSpec,
    NexusGradient,
    create_item_gradients,
    remove_item_gradients,
)

COLOR_LAYER_DEFS = {
    "GRADIENT_PARAMETER": {
        "name": "Gradient by Parameter",
        "description": "Color particles based on a simulation parameter",
        "icon_name": "nx_color_layer_gradient_parameter",
        "blender_icon": "COLOR",
    },
    "NOISE": {
        "name": "Noise",
        "description": "Color particles using noise",
        "icon_name": "nx_color_layer_noise",
        "blender_icon": "MOD_NOISE",
    },
    "SET_COLOR": {
        "name": "Set Color",
        "description": "Set particles to a specific color",
        "icon_name": "nx_color_layer_set_color",
        "blender_icon": "SNAP_FACE",
    },
    "INC_DEC": {
        "name": "Increment/Decrement",
        "description": "Gradually change particle color channels",
        "icon_name": "nx_color_layer_inc_dec",
        "blender_icon": "ARROW_LEFTRIGHT",
    },
    "TIME": {
        "name": "Time-Dependent",
        "description": "Color particles based on elapsed time",
        "icon_name": "nx_color_layer_time",
        "blender_icon": "TIME",
    },
    "DISTANCE_OBJECT": {
        "name": "Distance from Object",
        "description": "Color based on distance from an object",
        "icon_name": "nx_color_layer_distance_object",
        "blender_icon": "EMPTY_AXIS",
    },
    "DISTANCE_CAMERA": {
        "name": "Distance from Camera",
        "description": "Color based on distance from camera",
        "icon_name": "nx_color_layer_distance_camera",
        "blender_icon": "CAMERA_DATA",
    },
}


_COLOR_LAYER_ITEMS = []
_RATE_MODE_ITEMS = []


def _is_color_gradient_layer(_item_eval, item_orig) -> bool:
    return item_orig.item_type in {
        "GRADIENT_PARAMETER",
        "TIME",
        "DISTANCE_OBJECT",
        "DISTANCE_CAMERA",
    }


def _is_color_noise_layer(_item_eval, item_orig) -> bool:
    return item_orig.item_type == "NOISE"


COLOR_LAYER_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="color_layer",
        label="Gradient",
        default_stops=[
            (0.0, (0.078, 0.0, 1.0, 1.0)),
            (0.333, (0.0, 0.549, 1.0, 1.0)),
            (0.666, (0.549, 0.862, 1.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
        theron_ids=("ID_NX_COLOUR_GRADIENT",),
        slot_suffix_attr="layer_uid",
        sync_condition=_is_color_gradient_layer,
    ),
    GradientSpec(
        slot_name="color_noise",
        label="Gradient",
        default_stops=[
            (0.0, (1.0, 1.0, 1.0, 1.0)),
            (1.0, (0.0, 0.0, 0.0, 1.0)),
        ],
        theron_ids=("ID_NX_COLOUR_NOISE_GRADIENT",),
        slot_suffix_attr="layer_uid",
        sync_condition=_is_color_noise_layer,
    ),
]


def build_color_enum_items():
    global _COLOR_LAYER_ITEMS, _RATE_MODE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    rate_defs = [
        ("INSTANT", "Instant", "", "nx_color_change_rate_instant"),
        ("FRAME_TIME", "Frame Time", "", "nx_color_rate_frame_time"),
        ("CUSTOM", "Custom", "", "nx_color_change_rate_custom"),
    ]
    _RATE_MODE_ITEMS = []
    for idx, (eid, label, desc, icon_name) in enumerate(rate_defs):
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _RATE_MODE_ITEMS.append((eid, label, desc, icon_id, idx))
        else:
            _RATE_MODE_ITEMS.append((eid, label, desc, "NONE", idx))

    _COLOR_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(COLOR_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _COLOR_LAYER_ITEMS.append(
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
            _COLOR_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "color_layers",
        _COLOR_LAYER_ITEMS,
        "color_layers",
        "color_layers_index",
        on_add=_on_color_layer_add,
        on_remove=_on_color_layer_remove,
        separator_after={"SET_COLOR", "INC_DEC"},
    )


def _get_color_layer_items(self, context):
    return _COLOR_LAYER_ITEMS


def _get_rate_mode_items(self, context):
    return _RATE_MODE_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _create_layer_gradients(obj, uid):
    create_item_gradients(obj, uid, COLOR_LAYER_GRADIENT_SPECS)


def _remove_layer_gradients(obj, uid):
    remove_item_gradients(obj, uid, COLOR_LAYER_GRADIENT_SPECS)


def _on_color_layer_add(context, obj, item):
    del context
    item.layer_uid = os.urandom(4).hex()
    _create_layer_gradients(obj, item.layer_uid)
    layers = obj.nexus_modifier.color_layers
    auto_rename.initialize_added(item, layers, _color_layer_base_name(item))


def _on_color_layer_remove(context, obj, item):
    if item.layer_uid:
        _remove_layer_gradients(obj, item.layer_uid)


def _color_layer_base_name(item) -> str:
    return COLOR_LAYER_DEFS.get(item.item_type, {}).get("name", "Layer")


_on_color_layer_type_update = auto_rename.on_trigger(
    base_name_fn=_color_layer_base_name,
    collection_attr="color_layers",
    pre=_update_layer_viewport,
)


def _poll_camera(self, obj):
    return obj.type == "CAMERA"


COLOR_BLEND_MODE_IDS = {
    "NORMAL": "ID_NX_COLOUR_BLEND_NORMAL",
    "ADD": "ID_NX_COLOUR_BLEND_ADD",
    "SUBTRACT": "ID_NX_COLOUR_BLEND_SUB",
    "MULTIPLY": "ID_NX_COLOUR_BLEND_MULT",
    "DIFFERENCE": "ID_NX_COLOUR_BLEND_DIFFERENCE",
    "SCREEN": "ID_NX_COLOUR_BLEND_SCREEN",
    "OVERLAY": "ID_NX_COLOUR_BLEND_OVERLAY",
    "MIN": "ID_NX_COLOUR_BLEND_MIN",
    "MAX": "ID_NX_COLOUR_BLEND_MAX",
}

COLOR_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_COLOUR_BLEND",
    strength_id_name="ID_NX_COLOUR_STRENGTH",
    id_map=COLOR_BLEND_MODE_IDS,
    strength_attr="layer_strength",
    labels={
        "NORMAL": ("Normal", ""),
        "MIN": ("Min", ""),
        "SUBTRACT": ("Subtract", ""),
        "MULTIPLY": ("Multiply", ""),
        "OVERLAY": ("Overlay", ""),
        "MAX": ("Max", ""),
        "ADD": ("Add", ""),
        "SCREEN": ("Screen", ""),
        "DIFFERENCE": ("Difference", ""),
    },
)


class NexusColorLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Color layer name",
        default="",
        update=auto_rename.on_name_update(),
    )

    is_renamed: BoolProperty(
        name="",
        default=True,
        options={"HIDDEN"},
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this color layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of color operation",
        items=_get_color_layer_items,
        default=0,
        update=_on_color_layer_type_update,
    )

    layer_uid: bpy.props.StringProperty(
        name="",
        default="",
        options={"HIDDEN"},
    )

    layer_tab: EnumProperty(
        name="Tab",
        items=[
            ("GENERAL", "General", ""),
            ("FALLOFF", "Falloff", ""),
        ],
        default="GENERAL",
    )

    blend_mode: EnumProperty(
        name="Blend Mode",
        description="How this layer blends with previous layers",
        items=COLOR_BLEND_SPEC.enum_items(),
        default="NORMAL",
    )

    layer_strength: FloatProperty(
        name="Strength",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    rate_mode: EnumProperty(
        name="Rate Mode",
        items=_get_rate_mode_items,
        default=0,
    )

    rate_strength: FloatProperty(
        name="Rate Multiplier",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    threshold: FloatProperty(
        name="Threshold",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    color_type: EnumProperty(
        name="Color Type",
        items=[
            ("COLOR", "Color", ""),
            ("SHADER", "Shader", "Not available in Blender"),
        ],
        default="COLOR",
    )

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
        default=(1.0, 0.745, 0.0),
    )

    inc_dec_r: FloatProperty(
        name="Red Rate of Change",
        default=0.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    inc_dec_g: FloatProperty(
        name="Green Rate of Change",
        default=0.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    inc_dec_b: FloatProperty(
        name="Blue Rate of Change",
        default=0.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter_mode: EnumProperty(
        name="Parameter",
        items=[
            ("AGE", "Age", ""),
            ("DIRECTION", "Direction", ""),
            ("DIST_TRAVELED", "Distance Traveled", ""),
            ("DENSITY", "Density", ""),
            ("LIFE", "Life", ""),
            ("MASS", "Mass", ""),
            ("NEIGHBOR", "Neighbor", ""),
            ("RADIUS", "Radius", ""),
            ("SPEED", "Speed", ""),
            ("FIELD", "Falloff", ""),
            ("RANDOM", "Random", ""),
        ],
        default="SPEED",
    )

    parameter_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        soft_max=500.0,
    )

    parameter_max: FloatProperty(
        name="Max",
        default=100.0,
        min=0.0,
        soft_max=500.0,
    )

    parameter_dist_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    parameter_dist_max: FloatProperty(
        name="Max",
        default=10.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    parameter_speed_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    parameter_speed_max: FloatProperty(
        name="Max",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    parameter_radius_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    parameter_radius_max: FloatProperty(
        name="Max",
        default=0.1,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    parameter_falloff_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter_falloff_max: FloatProperty(
        name="Max",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter_random_min: FloatProperty(
        name="Min",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter_random_max: FloatProperty(
        name="Max",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    parameter_random_fixed: BoolProperty(
        name="Use Fixed Point",
        default=True,
    )

    parameter_axis: EnumProperty(
        name="Axis",
        items=[
            ("X", "X", "Heading"),
            ("Y", "Y", "Pitch"),
            ("Z", "Z", "Bank"),
        ],
        default="X",
    )

    parameter_nb_radius: FloatProperty(
        name="Neighbor Radius",
        default=0.25,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    gradient_time: nexus_time_property(
        "gradient_time",
        name="Time to Completion",
        description="Time to complete the gradient transition",
        default=3.0,
        min=0.0,
        soft_max=30.0,
        collection_path="color_layers",
    )

    gradient_complete: EnumProperty(
        name="On Complete",
        items=[
            ("NONE", "Do Nothing", ""),
            ("WRAP", "Wrap to Start", ""),
            ("REVERSE", "Reverse", ""),
        ],
        default="NONE",
    )

    gradient_object: PointerProperty(
        name="Object",
        type=bpy.types.Object,
    )

    gradient_camera: PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=_poll_camera,
    )

    gradient_dist_min: FloatProperty(
        name="Nearest Distance",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        unit="LENGTH",
    )

    gradient_dist_max: FloatProperty(
        name="Furthest Distance",
        default=5.0,
        min=0.0,
        soft_max=100.0,
        unit="LENGTH",
    )

    gradient_cam_fov: BoolProperty(
        name="FOV",
        default=False,
    )

    noise_type: EnumProperty(
        name="Noise Type",
        items=[
            ("SIMPLEX", "Simplex", ""),
            ("CURL", "Curl", ""),
            ("TURBULENCE", "Turbulence", ""),
            ("WAVY_TURBULENCE", "Wavy Turbulence", ""),
            ("VORONOISE", "VoroNoise", ""),
            ("FBM", "FBM", ""),
            ("CUBIC", "Cubic", ""),
        ],
        default="VORONOISE",
    )

    noise_timing: EnumProperty(
        name="Timing",
        items=[
            ("FRAME_TIME", "Frame Time", ""),
            ("PARTICLE_AGE", "Particle Age", ""),
        ],
        default="FRAME_TIME",
    )

    noise_color_channel: EnumProperty(
        name="Color Channel",
        items=[
            ("GRADIENT", "Gradient", "Use gradient to map noise to color"),
            ("NOISE", "Noise", "Use noise directly for RGB channels"),
        ],
        default="GRADIENT",
    )

    noise_seed: IntProperty(
        name="Seed",
        default=1,
        min=0,
    )

    noise_scale: FloatProperty(
        name="Scale",
        default=100.0,
        min=0.0,
        soft_max=1000.0,
        subtype="PERCENTAGE",
    )

    noise_persistence: FloatProperty(
        name="Persistence",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    noise_lacunarity: FloatProperty(
        name="Lacunarity",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )

    noise_frequency: FloatProperty(
        name="Frequency",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        subtype="PERCENTAGE",
    )

    noise_octaves: IntProperty(
        name="Octaves",
        default=1,
        min=0,
        max=20,
    )

    noise_low_clip: FloatProperty(
        name="Low Clip",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    noise_high_clip: FloatProperty(
        name="High Clip",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    noise_brightness: FloatProperty(
        name="Brightness",
        default=0.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    noise_contrast: FloatProperty(
        name="Contrast",
        default=100.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )


def _draw_layer_gradient(layout, item, label="Gradient"):
    obj = bpy.context.object
    if obj and item.layer_uid:
        NexusGradient(obj, f"color_layer_{item.layer_uid}").draw_ui(layout, label)


def _draw_noise_gradient(layout, item):
    obj = bpy.context.object
    if obj and item.layer_uid:
        NexusGradient(obj, f"color_noise_{item.layer_uid}").draw_ui(layout, "Gradient")


def _draw_common_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "layer_strength")

    col.separator(type="LINE")

    col.prop(item, "rate_mode")

    row = col.row()
    row.enabled = item.rate_mode == "CUSTOM"
    row.prop(item, "rate_strength")

    col.prop(item, "threshold")

    return col


def _draw_set_color_settings(layout, item):
    col = _draw_common_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "color_type")

    if item.color_type == "COLOR":
        col.prop(item, "color")

    _draw_layer_gradient(col, item)


def _draw_inc_dec_settings(layout, item):
    col = _draw_common_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "inc_dec_r")
    col.prop(item, "inc_dec_g")
    col.prop(item, "inc_dec_b")


def _draw_gradient_parameter_settings(layout, item):
    col = _draw_common_header(layout, item)

    _draw_layer_gradient(col, item)

    col.separator(type="LINE")

    col.prop(item, "parameter_mode")

    mode = item.parameter_mode

    if mode in ("AGE", "DENSITY", "LIFE", "MASS"):
        col.prop(item, "parameter_min")
        col.prop(item, "parameter_max")

    elif mode == "NEIGHBOR":
        col.prop(item, "parameter_min")
        col.prop(item, "parameter_max")
        col.prop(item, "parameter_nb_radius")

    elif mode == "DIST_TRAVELED":
        col.prop(item, "parameter_dist_min")
        col.prop(item, "parameter_dist_max")

    elif mode == "SPEED":
        col.prop(item, "parameter_speed_min")
        col.prop(item, "parameter_speed_max")

    elif mode == "RADIUS":
        col.prop(item, "parameter_radius_min")
        col.prop(item, "parameter_radius_max")

    elif mode == "FIELD":
        col.prop(item, "parameter_falloff_min")
        col.prop(item, "parameter_falloff_max")

    elif mode == "RANDOM":
        col.prop(item, "parameter_random_min")
        col.prop(item, "parameter_random_max")
        col.prop(item, "parameter_random_fixed")

    elif mode == "DIRECTION":
        col.prop(item, "parameter_axis")


def _draw_time_settings(layout, item):
    col = _draw_common_header(layout, item)

    _draw_layer_gradient(col, item)

    col.separator(type="LINE")

    draw_time_prop(col, item, "gradient_time")
    col.prop(item, "gradient_complete")


def _draw_distance_object_settings(layout, item):
    col = _draw_common_header(layout, item)

    _draw_layer_gradient(col, item)

    col.separator(type="LINE")

    col.prop(item, "gradient_object")
    col.prop(item, "gradient_dist_min")
    col.prop(item, "gradient_dist_max")


def _draw_distance_camera_settings(layout, item):
    col = _draw_common_header(layout, item)

    _draw_layer_gradient(col, item)

    col.separator(type="LINE")

    col.prop(item, "gradient_camera")
    col.prop(item, "gradient_dist_min")
    col.prop(item, "gradient_dist_max")
    col.prop(item, "gradient_cam_fov")


def _draw_noise_settings(layout, item):
    col = _draw_common_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "noise_type")
    col.prop(item, "noise_timing")
    col.prop(item, "noise_color_channel")

    col.separator(type="LINE")

    if item.noise_color_channel == "GRADIENT":
        _draw_noise_gradient(col, item)

    col.separator(type="LINE")

    col.prop(item, "noise_seed")

    col.separator(type="LINE")

    col.prop(item, "noise_scale")
    col.prop(item, "noise_persistence")
    col.prop(item, "noise_lacunarity")
    col.prop(item, "noise_frequency")
    col.prop(item, "noise_octaves")

    col.separator(type="LINE")

    col.prop(item, "noise_low_clip")
    col.prop(item, "noise_high_clip")

    col.separator(type="LINE")

    col.prop(item, "noise_brightness")
    col.prop(item, "noise_contrast")


LAYER_DRAW_FUNCS = {
    "GRADIENT_PARAMETER": _draw_gradient_parameter_settings,
    "NOISE": _draw_noise_settings,
    "SET_COLOR": _draw_set_color_settings,
    "INC_DEC": _draw_inc_dec_settings,
    "TIME": _draw_time_settings,
    "DISTANCE_OBJECT": _draw_distance_object_settings,
    "DISTANCE_CAMERA": _draw_distance_camera_settings,
}


def draw_color_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


NX_COLOR_UI_CONFIG = {}


def add_default_color_layer(obj):
    props = obj.nexus_modifier
    item = props.color_layers.add()
    item.item_type = "GRADIENT_PARAMETER"
    item.enabled = True
    item.layer_uid = os.urandom(4).hex()

    _create_layer_gradients(obj, item.layer_uid)
    auto_rename.initialize_added(item, props.color_layers, _color_layer_base_name(item))
    props.color_layers_index = 0


COLOR_LAYER_TYPE_IDS = {
    "SET_COLOR": "ID_NX_COLOUR_ADD_LAYER_COLOR",
    "INC_DEC": "ID_NX_COLOUR_ADD_LAYER_COLOR_INC_DEC",
    "GRADIENT_PARAMETER": "ID_NX_COLOUR_ADD_LAYER_COLOR_PARAMETER",
    "TIME": "ID_NX_COLOUR_ADD_LAYER_COLOR_TIME",
    "DISTANCE_OBJECT": "ID_NX_COLOUR_ADD_LAYER_COLOR_OBJ",
    "DISTANCE_CAMERA": "ID_NX_COLOUR_ADD_LAYER_COLOR_CAM",
    "NOISE": "ID_NX_COLOUR_ADD_LAYER_COLOR_NOISE",
}

COLOR_RATE_MODE_IDS = {
    "FRAME_TIME": "ID_NX_COLOUR_RATE_MODE_FRAME",
    "INSTANT": "ID_NX_COLOUR_RATE_MODE_INSTANT",
    "CUSTOM": "ID_NX_COLOUR_RATE_MODE_CUSTOM",
}

COLOR_PARAMETER_MODE_IDS = {
    "AGE": "ID_NX_COLOUR_OP_GRADIENT_PARAM_AGE",
    "DIRECTION": "ID_NX_COLOUR_OP_GRADIENT_PARAM_DIRECTION",
    "DIST_TRAVELED": "ID_NX_COLOUR_OP_GRADIENT_PARAM_DISTTRAVELLED",
    "DENSITY": "ID_NX_COLOUR_OP_GRADIENT_PARAM_DENSITY",
    "LIFE": "ID_NX_COLOUR_OP_GRADIENT_PARAM_LIFE",
    "MASS": "ID_NX_COLOUR_OP_GRADIENT_PARAM_MASS",
    "NEIGHBOR": "ID_NX_COLOUR_OP_GRADIENT_PARAM_NEIGHBOUR",
    "RADIUS": "ID_NX_COLOUR_OP_GRADIENT_PARAM_RADIUS",
    "SPEED": "ID_NX_COLOUR_OP_GRADIENT_PARAM_SPEED",
    "FIELD": "ID_NX_COLOUR_OP_GRADIENT_PARAM_FALLOFF",
    "RANDOM": "ID_NX_COLOUR_OP_GRADIENT_PARAM_RANDOM",
}

COLOR_NOISE_TYPE_IDS = {
    "SIMPLEX": "ID_NX_COLOUR_NOISE_TYPE_SIMPLEX",
    "CURL": "ID_NX_COLOUR_NOISE_TYPE_CURL",
    "TURBULENCE": "ID_NX_COLOUR_NOISE_TYPE_TURBULENCE",
    "WAVY_TURBULENCE": "ID_NX_COLOUR_NOISE_TYPE_WAVE_TURBULENCE",
    "VORONOISE": "ID_NX_COLOUR_NOISE_TYPE_VORONOISE",
    "FBM": "ID_NX_COLOUR_NOISE_TYPE_FBM",
    "CUBIC": "ID_NX_COLOUR_NOISE_TYPE_CUBIC",
}

COLOR_AXIS_IDS = {
    "X": "ID_NX_COLOUR_PARAMETER_DIR_AXIS_H",
    "Y": "ID_NX_COLOUR_PARAMETER_DIR_AXIS_P",
    "Z": "ID_NX_COLOUR_PARAMETER_DIR_AXIS_B",
}

COLOR_NOISE_TIMING_IDS = {
    "FRAME_TIME": "ID_NX_COLOUR_NOISE_TIMING_FRAME",
    "PARTICLE_AGE": "ID_NX_COLOUR_NOISE_TIMING_PARTICLE",
}

COLOR_NOISE_CHANNEL_IDS = {
    "GRADIENT": "ID_NX_COLOUR_NOISE_COLOUR_CHANNEL_SINGLE",
    "NOISE": "ID_NX_COLOUR_NOISE_COLOUR_CHANNEL_MULTIPLE",
}

COLOR_GRADIENT_COMPLETE_IDS = {
    "NONE": "ID_NX_COLOUR_GRAD_COMPLETE_NONE",
    "WRAP": "ID_NX_COLOUR_GRAD_COMPLETE_WRAP",
    "REVERSE": "ID_NX_COLOUR_GRAD_COMPLETE_REVERSE",
}

_NODE_ID_OFFSET = 2000

_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]


def _sync_set_color(theron, get, nc, item, _item_orig, _obj):
    color_type_val = (
        get("ID_NX_COLOUR_TYPE_COLOR")
        if item.color_type == "COLOR"
        else get("ID_NX_COLOUR_TYPE_SHADER")
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_TYPE"), color_type_val)

    c = item.color
    theron.set_vector(nc, get("ID_NX_COLOUR_COLOR"), float(c[0]), float(c[1]), float(c[2]))


def _sync_inc_dec(theron, get, nc, item, _item_orig, _obj):
    theron.set_int32(nc, get("ID_NX_COLOUR_TYPE"), get("ID_NX_COLOUR_TYPE_COLOR"))

    theron.set_float(nc, get("ID_NX_COLOUR_INC_DEC_R"), item.inc_dec_r * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_INC_DEC_G"), item.inc_dec_g * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_INC_DEC_B"), item.inc_dec_b * _pct)


def _sync_gradient_parameter(theron, get, nc, item, _item_orig, obj):
    mode_val = get(
        COLOR_PARAMETER_MODE_IDS.get(item.parameter_mode, "ID_NX_COLOUR_OP_GRADIENT_PARAM_SPEED")
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_PARAMETER_MODE"), mode_val)

    axis_val = get(COLOR_AXIS_IDS.get(item.parameter_axis, "ID_NX_COLOUR_PARAMETER_DIR_AXIS_H"))
    theron.set_int32(nc, get("ID_NX_COLOUR_PARAMETER_AXIS"), axis_val)
    theron.set_bool(nc, get("ID_NX_COLOUR_PARAMETER_RANDOM_FIXED"), item.parameter_random_fixed)

    mode = item.parameter_mode

    if mode in ("AGE", "DENSITY", "LIFE", "MASS"):
        theron.set_float(nc, get("ID_NX_COLOUR_PARAMETER_MIN"), item.parameter_min)
        theron.set_float(nc, get("ID_NX_COLOUR_PARAMETER_MAX"), item.parameter_max)

    elif mode == "NEIGHBOR":
        theron.set_float(nc, get("ID_NX_COLOUR_PARAMETER_MIN"), item.parameter_min)
        theron.set_float(nc, get("ID_NX_COLOUR_PARAMETER_MAX"), item.parameter_max)
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_NB_RADIUS"), item.parameter_nb_radius * _unit
        )

    elif mode == "DIST_TRAVELED":
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_DIST_MIN"), item.parameter_dist_min * _unit
        )
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_DIST_MAX"), item.parameter_dist_max * _unit
        )

    elif mode == "SPEED":
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_SPEED_MIN"), item.parameter_speed_min * _unit
        )
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_SPEED_MAX"), item.parameter_speed_max * _unit
        )

    elif mode == "RADIUS":
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_RADIUS_MIN"), item.parameter_radius_min * _unit
        )
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_RADIUS_MAX"), item.parameter_radius_max * _unit
        )

    elif mode == "FIELD":
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_FALLOFF_MIN"), item.parameter_falloff_min * _pct
        )
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_FALLOFF_MAX"), item.parameter_falloff_max * _pct
        )

    elif mode == "RANDOM":
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_RANDOM_MIN"), item.parameter_random_min * _pct
        )
        theron.set_float(
            nc, get("ID_NX_COLOUR_PARAMETER_RANDOM_MAX"), item.parameter_random_max * _pct
        )


def _sync_time(theron, get, nc, item, _item_orig, obj):
    from ..libs.nexus_time import get_prop_time_mode, to_time_fraction

    prop_mode = get_prop_time_mode(item, "gradient_time")
    num, den = to_time_fraction(float(item.gradient_time), mode=prop_mode)
    theron.set_time(nc, get("ID_NX_COLOUR_GRADIENT_TIME"), num, den)

    complete_val = get(
        COLOR_GRADIENT_COMPLETE_IDS.get(item.gradient_complete, "ID_NX_COLOUR_GRAD_COMPLETE_NONE")
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_GRADIENT_COMPLETE"), complete_val)


def _sync_distance_object(theron, get, nc, item, _item_orig, obj):
    # TODO(rich): Object linking when done
    theron.set_float(nc, get("ID_NX_COLOUR_GRADIENT_DIST_MIN"), item.gradient_dist_min * _unit)
    theron.set_float(nc, get("ID_NX_COLOUR_GRADIENT_DIST_MAX"), item.gradient_dist_max * _unit)


def _sync_distance_camera(theron, get, nc, item, _item_orig, obj):
    # TODO(Rich): Camera linking when done
    theron.set_float(nc, get("ID_NX_COLOUR_GRADIENT_DIST_MIN"), item.gradient_dist_min * _unit)
    theron.set_float(nc, get("ID_NX_COLOUR_GRADIENT_DIST_MAX"), item.gradient_dist_max * _unit)
    theron.set_bool(nc, get("ID_NX_COLOUR_GRADIENT_CAM_FOV"), item.gradient_cam_fov)


def _sync_noise(theron, get, nc, item, _item_orig, obj):
    noise_type_val = get(
        COLOR_NOISE_TYPE_IDS.get(item.noise_type, "ID_NX_COLOUR_NOISE_TYPE_SIMPLEX")
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_NOISE_TYPE"), noise_type_val)

    timing_val = get(
        COLOR_NOISE_TIMING_IDS.get(item.noise_timing, "ID_NX_COLOUR_NOISE_TIMING_FRAME")
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_NOISE_TIMING"), timing_val)

    channel_val = get(
        COLOR_NOISE_CHANNEL_IDS.get(
            item.noise_color_channel, "ID_NX_COLOUR_NOISE_COLOUR_CHANNEL_SINGLE"
        )
    )
    theron.set_int32(nc, get("ID_NX_COLOUR_NOISE_COLOUR_CHANNEL"), channel_val)

    theron.set_int32(nc, get("ID_NX_COLOUR_NOISE_SEED"), item.noise_seed)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_SCALE"), item.noise_scale * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_PERSISTENCE"), item.noise_persistence * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_LACUNARITY"), item.noise_lacunarity)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_FREQUENCY"), item.noise_frequency * _pct)
    theron.set_int32(nc, get("ID_NX_COLOUR_NOISE_OCTAVES"), item.noise_octaves)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_LOW_CLIP"), item.noise_low_clip * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_HIGH_CLIP"), item.noise_high_clip * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_BRIGHTNESS"), item.noise_brightness * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_NOISE_CONTRAST"), item.noise_contrast * _pct)


def _sync_color_common(theron, get, nc, item, _item_orig, _obj):
    rate_id = get(COLOR_RATE_MODE_IDS.get(item.rate_mode, "ID_NX_COLOUR_RATE_MODE_FRAME"))
    theron.set_int32(nc, get("ID_NX_COLOUR_RATE_MODE"), rate_id)
    theron.set_float(nc, get("ID_NX_COLOUR_RATE_STRENGTH"), item.rate_strength * _pct)
    theron.set_float(nc, get("ID_NX_COLOUR_THRESHOLD"), item.threshold * _pct)


_COLOR_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_COLOUR_OBJECTS_TREE",
    collection_attr="color_layers",
    type_id_map=COLOR_LAYER_TYPE_IDS,
    node_id_offset=_NODE_ID_OFFSET,
    layer_op_id_name="ID_NX_COLOUR_LAYER_OP",
    blend_spec=COLOR_BLEND_SPEC,
    enabled_disables_blend=True,
    pre_dispatch_syncer=_sync_color_common,
    gradient_specs=COLOR_LAYER_GRADIENT_SPECS,
    per_type_syncers={
        "SET_COLOR": _sync_set_color,
        "INC_DEC": _sync_inc_dec,
        "GRADIENT_PARAMETER": _sync_gradient_parameter,
        "TIME": _sync_time,
        "DISTANCE_OBJECT": _sync_distance_object,
        "DISTANCE_CAMERA": _sync_distance_camera,
        "NOISE": _sync_noise,
    },
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_COLOR",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_COLOUR_CHANGE_BIRTH",
            prop=BoolProperty(
                name="Change On Birth Only",
                description="Only apply color change when particle is born",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="color_layers",
            prop=CollectionProperty(
                name="Color Layers",
                type=NexusColorLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="color_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
            ),
        ),
    ),
    item_classes=(NexusColorLayerItem,),
    enum_builders=(build_color_enum_items,),
    nodetree_sync=(_COLOR_TREE_SPEC,),
)


register_collection_preset(
    "NX_COLOR",
    CollectionPresetSpec(
        collection_attr="color_layers",
        menu_id="color_layers",
        gradient_specs=COLOR_LAYER_GRADIENT_SPECS,
        suffix_attr="layer_uid",
    ),
)
