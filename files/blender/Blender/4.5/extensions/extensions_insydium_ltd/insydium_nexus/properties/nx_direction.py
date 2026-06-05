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

from math import radians

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import BlendSpec, NodeTreeSyncSpec
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform

DIRECTION_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_DIRECT_BLEND_MODE",
    strength_id_name="ID_NX_DIRECT_BLEND_STRENGTH",
    id_map={
        "NORMAL": "ID_NX_DIRECT_BLEND_NORMAL",
        "ADD": "ID_NX_DIRECT_BLEND_ADD",
        "SUBTRACT": "ID_NX_DIRECT_BLEND_SUB",
        "MULTIPLY": "ID_NX_DIRECT_BLEND_MULT",
        "DIFFERENCE": "ID_NX_DIRECT_BLEND_DIFFERENCE",
        "SCREEN": "ID_NX_DIRECT_BLEND_SCREEN",
        "OVERLAY": "ID_NX_DIRECT_BLEND_OVERLAY",
        "MIN": "ID_NX_DIRECT_BLEND_MIN",
        "MAX": "ID_NX_DIRECT_BLEND_MAX",
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

DIRECTION_LAYER_DEFS = {
    "DIRECTION_FORCE": {
        "name": "Direction Force",
        "description": "Uses Direction/Twist/Attract strength values with falloff",
        "icon_name": "nx_direction_layer_force",
        "blender_icon": "FORCE_FORCE",
    },
    "RELATIVE": {
        "name": "Relative",
        "description": "Relative direction using Heading and Pitch angles",
        "icon_name": "nx_direction_layer_relative",
        "blender_icon": "ORIENTATION_LOCAL",
    },
    "ABSOLUTE": {
        "name": "Absolute",
        "description": "Absolute direction using Heading and Pitch angles",
        "icon_name": "nx_direction_layer_absolute",
        "blender_icon": "ORIENTATION_GLOBAL",
    },
    "CIRCULAR": {
        "name": "Circular",
        "description": "Circular motion with Y-Axis Kick",
        "icon_name": "nx_direction_layer_circular",
        "blender_icon": "CURVES",
    },
    "RING": {
        "name": "Ring",
        "description": "Ring/disc pattern with step-per-frame and angle limits",
        "icon_name": "nx_direction_layer_ring",
        "blender_icon": "MESH_CIRCLE",
    },
    "USE_MODIFIER_ROTATION": {
        "name": "Use Modifier Rotation",
        "description": "Uses the modifier object's rotation as direction",
        "icon_name": "nx_direction_layer_modrot",
        "blender_icon": "CON_ROTLIKE",
    },
}


_DIRECTION_LAYER_ITEMS = []
_FORCE_FALLOFF_ITEMS = []
_FORCE_MODE_ITEMS = []

_FORCE_MODE_DEFS = [
    ("VELOCITY", "Velocity", "Modify particle velocity directly", "nx_velocity"),
    ("ACCELERATION", "Acceleration", "Apply as acceleration force", "nx_acceleration"),
]

_FORCE_FALLOFF_DEFS = [
    ("FLAT", "Flat", "No falloff - constant strength", "nx_falloff_type_flat"),
    ("LINEAR", "Linear", "Linear falloff with distance", "nx_falloff_type_linear"),
    ("QUADRATIC", "Quadratic", "Quadratic (inverse square) falloff", "nx_falloff_type_quadratic"),
    ("CUBIC", "Cubic", "Cubic falloff", "nx_falloff_type_cubic"),
]


def build_direction_enum_items():
    global _DIRECTION_LAYER_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _DIRECTION_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(DIRECTION_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _DIRECTION_LAYER_ITEMS.append(
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
            _DIRECTION_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    global _FORCE_MODE_ITEMS
    _FORCE_MODE_ITEMS = []
    for idx, (type_id, name, desc, icon_name) in enumerate(_FORCE_MODE_DEFS):
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _FORCE_MODE_ITEMS.append((type_id, name, desc, icon_id, idx))
        else:
            _FORCE_MODE_ITEMS.append((type_id, name, desc, "NONE", idx))

    global _FORCE_FALLOFF_ITEMS
    _FORCE_FALLOFF_ITEMS = []
    for idx, (type_id, name, desc, icon_name) in enumerate(_FORCE_FALLOFF_DEFS):
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _FORCE_FALLOFF_ITEMS.append((type_id, name, desc, icon_id, idx))
        else:
            _FORCE_FALLOFF_ITEMS.append((type_id, name, desc, "NONE", idx))

    register_nodetree(
        "direction_layers",
        _DIRECTION_LAYER_ITEMS,
        "direction_layers",
        "direction_layers_index",
    )


def _get_force_mode_items(self, context):
    return _FORCE_MODE_ITEMS


def _get_force_falloff_items(self, context):
    return _FORCE_FALLOFF_ITEMS


def _get_direction_layer_items(self, context):
    return _DIRECTION_LAYER_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class NexusDirectionLayerItem(bpy.types.PropertyGroup):
    """
    Union pattern PropertyGroup: all possible properties defined,
    appropriate ones shown based on item_type.
    """

    name: bpy.props.StringProperty(
        name="Name",
        description="Direction layer name",
        default="",
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this direction layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of direction operation",
        items=_get_direction_layer_items,
        default=0,
        update=_update_layer_viewport,
    )

    blend_mode: EnumProperty(
        name="Blend Mode",
        description="How this layer blends with previous layers",
        items=DIRECTION_BLEND_SPEC.enum_items(),
        default="NORMAL",
    )

    blend_strength: FloatProperty(
        name="Blend Strength",
        description="Strength of this layer's effect",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    layer_force_mode: EnumProperty(
        name="Force Mode",
        description="How the direction affects particles",
        items=_get_force_mode_items,
        default=0,
    )

    random_seed: IntProperty(
        name="Random Seed",
        description="Seed for random variation",
        default=12345,
        min=0,
    )

    heading: FloatProperty(
        name="Heading",
        description="Heading angle (rotation around vertical axis)",
        default=0.0,
        soft_min=radians(-360.0),
        soft_max=radians(360.0),
        subtype="ANGLE",
    )

    heading_variation: FloatProperty(
        name="Heading Variation",
        description="Random variation in heading (+/- degrees)",
        default=0.0,
        min=0.0,
        max=radians(360.0),
        subtype="ANGLE",
    )

    pitch: FloatProperty(
        name="Pitch",
        description="Pitch angle (rotation around horizontal axis)",
        default=0.0,
        soft_min=radians(-360.0),
        soft_max=radians(360.0),
        subtype="ANGLE",
    )

    pitch_variation: FloatProperty(
        name="Pitch Variation",
        description="Random variation in pitch (+/- degrees)",
        default=0.0,
        min=0.0,
        max=radians(360.0),
        subtype="ANGLE",
    )

    direction_strength: FloatProperty(
        name="Direction Strength",
        description="Strength of the direction effect",
        default=15.0,
        soft_min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    y_kick: FloatProperty(
        name="Y-Axis Kick",
        description="Offset along Y-axis for circular motion",
        default=0.0,
        soft_min=-1.0,
        soft_max=1.0,
        subtype="DISTANCE",
    )

    y_kick_variation: FloatProperty(
        name="Y Kick Variation",
        description="Random variation in Y kick (+/-)",
        default=0.0,
        soft_min=-1.0,
        soft_max=1.0,
        subtype="DISTANCE",
    )

    step_per_frame: FloatProperty(
        name="Step Per Frame",
        description="Angular step per frame in degrees",
        default=radians(20.0),
        min=radians(-360.0),
        max=radians(360.0),
        subtype="ANGLE",
    )

    angle_limit: FloatProperty(
        name="Angle Limit",
        description="Maximum angle before looping or stopping",
        default=radians(90.0),
        min=0.0,
        max=radians(360.0),
        subtype="ANGLE",
    )

    limit_to_ring: FloatProperty(
        name="Limit To Ring",
        description="Constrain particles to ring path",
        default=100.0,
        soft_min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    ring_loop: BoolProperty(
        name="Loop",
        description="Loop back to start when angle limit is reached",
        default=False,
    )

    force_direction: FloatProperty(
        name="Direction",
        description="Direction strength for force mode",
        default=0.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    force_twist: FloatProperty(
        name="Twist",
        description="Twist strength for force mode",
        default=0.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    force_attract: FloatProperty(
        name="Attract",
        description="Attraction strength for force mode",
        default=0.0,
        soft_min=-100.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    force_falloff_type: EnumProperty(
        name="Falloff Type",
        description="How the force falls off with distance",
        items=_get_force_falloff_items,
        default=3,
    )

    layer_visible_in_editor: BoolProperty(
        name="Visible in Editor",
        description="Show viewport drawing for this layer",
        default=True,
        update=_update_layer_viewport,
    )


def _draw_layer_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "blend_strength")

    col.separator(type="LINE")

    col.prop(item, "layer_force_mode")
    col.prop(item, "random_seed")

    return col


def _draw_direction_force_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Force Settings")

    col.prop(item, "force_direction")
    col.prop(item, "force_twist")
    col.prop(item, "force_attract")
    col.prop(item, "force_falloff_type")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


def _draw_relative_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Direction")

    col.prop(item, "heading")
    col.prop(item, "heading_variation")
    col.prop(item, "pitch")
    col.prop(item, "pitch_variation")
    col.prop(item, "direction_strength")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


def _draw_absolute_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Direction")

    col.prop(item, "heading")
    col.prop(item, "heading_variation")
    col.prop(item, "pitch")
    col.prop(item, "pitch_variation")
    col.prop(item, "direction_strength")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


def _draw_circular_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Circular Motion")

    col.prop(item, "heading")
    col.prop(item, "heading_variation")
    col.prop(item, "direction_strength")

    col.separator(type="LINE")

    col.prop(item, "y_kick")
    col.prop(item, "y_kick_variation")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


def _draw_ring_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Ring Motion")

    col.prop(item, "step_per_frame")
    col.prop(item, "angle_limit")
    col.prop(item, "limit_to_ring")

    row = col.row()
    row.enabled = abs(item.angle_limit - radians(360.0)) < 0.001
    row.prop(item, "ring_loop")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


def _draw_use_modifier_rotation_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "direction_strength")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Display")

    col.prop(item, "layer_visible_in_editor")


LAYER_DRAW_FUNCS = {
    "DIRECTION_FORCE": _draw_direction_force_settings,
    "RELATIVE": _draw_relative_settings,
    "ABSOLUTE": _draw_absolute_settings,
    "CIRCULAR": _draw_circular_settings,
    "RING": _draw_ring_settings,
    "USE_MODIFIER_ROTATION": _draw_use_modifier_rotation_settings,
}


def draw_direction_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


def _update_direction_layers_index(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def add_default_direction_layer(obj):
    from ..utils import generate_unique_name

    props = obj.nexus_modifier
    item = props.direction_layers.add()
    item.item_type = "DIRECTION_FORCE"
    item.enabled = True

    base_name = DIRECTION_LAYER_DEFS["DIRECTION_FORCE"]["name"]
    existing = [i.name for i in props.direction_layers if i.name]
    item.name = generate_unique_name(base_name, existing)

    props.direction_layers_index = 0


NX_DIRECTION_UI_CONFIG = {}


def get_direction_ui_config():
    config = dict(NX_DIRECTION_UI_CONFIG)

    config["direction_layers"] = {
        "type": "nodetree",
        "index_prop": "direction_layers_index",
        "label": "Layers",
        "draw_item_settings": draw_direction_layer_settings,
        "menu_id": "direction_layers",
    }

    return config


DIRECTION_LAYER_TYPE_IDS = {
    "RELATIVE": 0,
    "ABSOLUTE": 1,
    "CIRCULAR": 3,
    "RING": 5,
    "USE_MODIFIER_ROTATION": 6,
    "DIRECTION_FORCE": 7,
}

DIRECTION_FORCE_MODE_IDS = {
    "VELOCITY": "ID_NX_DIRECT_LAYER_FORCE_VELOCITY",
    "ACCELERATION": "ID_NX_DIRECT_LAYER_FORCE_FORCE",
}

DIRECTION_FORCE_FALLOFF_IDS = {
    "FLAT": "ID_NX_DIRECT_FORCE_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_NX_DIRECT_FORCE_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_NX_DIRECT_FORCE_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_NX_DIRECT_FORCE_FALLOFF_TYPE_CUBIC",
}

_PCT = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_UNIT = TRANSFORM_FACTORS[Transform.UNIT_SCALE]

_DIRECTION_ITEM_SYNC_SPECS = (
    SyncSpec.param(
        "int",
        lambda item, _obj, _scene, _depsgraph: DIRECTION_LAYER_TYPE_IDS.get(item.item_type, 0),
        "ID_NX_DIRECT_LAYER_OP",
    ),
    SyncSpec.param("int", "random_seed", "ID_NX_DIRECT_RANSEED"),
    SyncSpec.param("float", "heading", "ID_NX_DIRECT_X"),
    SyncSpec.param("float", "heading_variation", "ID_NX_DIRECT_XVAR"),
    SyncSpec.param("float", "pitch", "ID_NX_DIRECT_Y"),
    SyncSpec.param("float", "pitch_variation", "ID_NX_DIRECT_YVAR"),
    SyncSpec.param("bool", lambda *_: True, "ID_NX_DIRECT_USEAOT"),
    SyncSpec.param("float", "direction_strength", "ID_NX_DIRECT_STRENGTH", scale=_PCT),
    SyncSpec.param("float", "y_kick", "ID_NX_DIRECT_YKICK", scale=_UNIT),
    SyncSpec.param("float", "y_kick_variation", "ID_NX_DIRECT_YKICK_VAR", scale=_UNIT),
    SyncSpec.param("float", "step_per_frame", "ID_NX_DIRECT_DISCANGLE"),
    SyncSpec.param("float", "angle_limit", "ID_NX_DIRECT_DISCLIMIT"),
    SyncSpec.param("float", "limit_to_ring", "ID_NX_DIRECT_DISC_FLOAT", scale=_PCT),
    SyncSpec.param("bool", "ring_loop", "ID_NX_DIRECT_DISC_LOOP_BOOL"),
    SyncSpec.param(
        "enum",
        "layer_force_mode",
        "ID_NX_DIRECT_LAYER_FORCE",
        enum_map=DIRECTION_FORCE_MODE_IDS,
    ),
    SyncSpec.param("float", "force_direction", "ID_NX_DIRECT_FORCE_DIRECTION", scale=_PCT),
    SyncSpec.param("float", "force_twist", "ID_NX_DIRECT_FORCE_TWIST", scale=_PCT),
    SyncSpec.param("float", "force_attract", "ID_NX_DIRECT_FORCE_ATTRACT", scale=_PCT),
    SyncSpec.param(
        "enum",
        "force_falloff_type",
        "ID_NX_DIRECT_FORCE_FALLOFF_TYPE",
        enum_map=DIRECTION_FORCE_FALLOFF_IDS,
    ),
)

NexusDirectionLayerItem._sync_specs = _DIRECTION_ITEM_SYNC_SPECS


_DIRECTION_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_DIRECT_OPERATION_TREE",
    collection_attr="direction_layers",
    type_id_map=DIRECTION_LAYER_TYPE_IDS,
    node_id_offset=2000,
    enabled_disables_blend=True,
    blend_spec=DIRECTION_BLEND_SPEC,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_DIRECTION",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="direction_layers",
            prop=CollectionProperty(
                name="Direction Layers",
                type=NexusDirectionLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="direction_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_direction_layers_index,
            ),
        ),
    ),
    item_classes=(NexusDirectionLayerItem,),
    enum_builders=(build_direction_enum_items,),
    enum_defaults={
        "blend_mode": "NORMAL",
        "layer_force_mode": "VELOCITY",
        "force_falloff_type": "CUBIC",
    },
    nodetree_sync=(_DIRECTION_TREE_SPEC,),
)


register_collection_preset(
    "NX_DIRECTION",
    CollectionPresetSpec(
        collection_attr="direction_layers",
        menu_id="direction_layers",
    ),
)
