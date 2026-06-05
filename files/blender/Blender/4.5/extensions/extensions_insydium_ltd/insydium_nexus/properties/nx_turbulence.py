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

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import BlendSpec, NodeTreeSyncSpec
from ..libs.theron_sync import SyncSpec
from ..ui.nodetree import auto_rename

TURBULENCE_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_TURBULENCE_BLEND_MODE",
    strength_id_name="ID_NX_TURBULENCE_BLEND_STRENGTH",
    id_map={
        "NORMAL": "ID_NX_TURBULENCE_BLEND_NORMAL",
        "MIN": "ID_NX_TURBULENCE_BLEND_MIN",
        "SUB": "ID_NX_TURBULENCE_BLEND_SUB",
        "MULT": "ID_NX_TURBULENCE_BLEND_MULT",
        "OVERLAY": "ID_NX_TURBULENCE_BLEND_OVERLAY",
        "MAX": "ID_NX_TURBULENCE_BLEND_MAX",
        "ADD": "ID_NX_TURBULENCE_BLEND_ADD",
        "SCREEN": "ID_NX_TURBULENCE_BLEND_SCREEN",
        "DIFFERENCE": "ID_NX_TURBULENCE_BLEND_DIFFERENCE",
    },
    labels={
        "NORMAL": ("Normal", "Normal blend"),
        "MIN": ("Min", "Minimum blend"),
        "SUB": ("Subtract", "Subtractive blend"),
        "MULT": ("Multiply", "Multiplicative blend"),
        "OVERLAY": ("Overlay", "Overlay blend"),
        "MAX": ("Max", "Maximum blend"),
        "ADD": ("Add", "Additive blend"),
        "SCREEN": ("Screen", "Screen blend"),
        "DIFFERENCE": ("Difference", "Difference blend"),
    },
)

TURBULENCE_LAYER_DEFS = {
    "SIMPLEX": {
        "name": "Simplex",
        "description": "Simplex noise",
        "icon_name": "nx_noise_simplex",
        "blender_icon": "FORCE_TURBULENCE",
    },
    "CURL": {
        "name": "Curl",
        "description": "Curl noise",
        "icon_name": "nx_noise_curl",
        "blender_icon": "FORCE_VORTEX",
    },
    "TURBULENCE": {
        "name": "Turbulence",
        "description": "Classic turbulence noise",
        "icon_name": "nx_noise_turbulence",
        "blender_icon": "FORCE_WIND",
    },
    "WAVY_TURBULENCE": {
        "name": "Wavy Turbulence",
        "description": "Wavy turbulence noise",
        "icon_name": "nx_noise_wavy_turbulence",
        "blender_icon": "FORCE_HARMONIC",
    },
    "VORONOISE": {
        "name": "Voronoise",
        "description": "Voronoi-based noise",
        "icon_name": "nx_noise_voronoise",
        "blender_icon": "MESH_ICOSPHERE",
    },
    "FBM": {
        "name": "fBm",
        "description": "Fractional Brownian motion",
        "icon_name": "nx_noise_fbm",
        "blender_icon": "MOD_NOISE",
    },
    "CUBIC": {
        "name": "Cubic",
        "description": "Cubic noise",
        "icon_name": "nx_noise_cubic",
        "blender_icon": "MESH_CUBE",
    },
}


_TURBULENCE_LAYER_ITEMS = []
_TURBULENCE_DIRECTION_MODE_ITEMS = []


def build_turbulence_enum_items():
    global _TURBULENCE_LAYER_ITEMS, _TURBULENCE_DIRECTION_MODE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _TURBULENCE_DIRECTION_MODE_ITEMS = [
        (
            "DIR",
            "Direction",
            "Affect particle direction",
            get_icon("nx_turbulence_mode_direction"),
            0,
        ),
        (
            "ACCELERATION",
            "Acceleration",
            "Affect particle acceleration",
            get_icon("nx_turbulence_mode_acceleration"),
            1,
        ),
    ]

    _TURBULENCE_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(TURBULENCE_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _TURBULENCE_LAYER_ITEMS.append(
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
            _TURBULENCE_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "turbulence_layers",
        _TURBULENCE_LAYER_ITEMS,
        "turbulence_layers",
        "turbulence_layers_index",
        on_add=_on_turbulence_layer_add,
    )


def _get_turbulence_layer_items(self, context):
    return _TURBULENCE_LAYER_ITEMS


def _get_turbulence_direction_mode_items(self, context):
    return _TURBULENCE_DIRECTION_MODE_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


_turbulence_layer_base_name = auto_rename.base_name_from_defs(TURBULENCE_LAYER_DEFS)


_on_item_type_update = auto_rename.on_trigger(
    base_name_fn=_turbulence_layer_base_name,
    collection_attr="turbulence_layers",
    pre=_update_layer_viewport,
)


def _on_turbulence_layer_add(context, obj, item):
    del context
    if obj is None:
        item.is_renamed = False
        return
    layers = obj.nexus_modifier.turbulence_layers
    auto_rename.initialize_added(item, layers, _turbulence_layer_base_name(item))


class NexusTurbulenceLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Turbulence layer name",
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
        description="Enable this turbulence layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Noise Type",
        description="Noise algorithm for this layer",
        items=_get_turbulence_layer_items,
        default=0,
        update=_on_item_type_update,
    )

    blend_mode: EnumProperty(
        name="Blend",
        description="How this layer blends with previous layers",
        items=TURBULENCE_BLEND_SPEC.enum_items(),
        default="NORMAL",
    )

    blend_strength: FloatProperty(
        name="Strength",
        description="Blend strength for this layer",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    direction_mode: EnumProperty(
        name="Mode",
        description="How turbulence affects particles",
        items=_get_turbulence_direction_mode_items,
        default=1,
    )

    seed: IntProperty(
        name="Seed",
        description="Random seed for noise",
        default=0,
        min=0,
    )

    strength: FloatProperty(
        name="Strength",
        description="Turbulence strength",
        default=5.0,
        soft_min=0.0,
        soft_max=100.0,
        step=100,
    )

    offset: FloatVectorProperty(
        name="Noise Offset",
        description="Noise offset",
        default=(0.0, 0.0, 0.0),
        soft_min=-100.0,
        soft_max=100.0,
        step=10,
        size=3,
        subtype="XYZ",
    )

    scale: FloatProperty(
        name="Scale",
        description="Overall turbulence scale",
        default=100.0,
        min=0.0,
        soft_max=1000.0,
        step=100,
        subtype="PERCENTAGE",
    )

    scale_vec: FloatVectorProperty(
        name="Axis Direction Scale",
        description="Per-axis turbulence scale",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=3,
        subtype="XYZ",
    )

    persistence: FloatProperty(
        name="Persistence",
        description="Amplitude decay per octave",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    lacunarity: FloatProperty(
        name="Lacunarity",
        description="Frequency multiplier per octave",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )

    frequency: FloatProperty(
        name="Frequency",
        description="Noise frequency",
        default=1.0,
        min=0.0,
        soft_max=2.0,
        subtype="FACTOR",
    )

    octaves: IntProperty(
        name="Octaves",
        description="Number of noise octaves",
        default=1,
        min=0,
        max=20,
    )

    curl_blend: FloatProperty(
        name="Blend",
        description="Curl noise blend factor",
        default=0.8,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    curl_add: FloatProperty(
        name="Add",
        description="Curl noise additive factor",
        default=0.2,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )


def _draw_layer_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "blend_strength")

    col.separator(type="LINE")

    col.prop(item, "direction_mode")

    col.separator(type="LINE")

    return col


def _draw_noise_settings(col, item):
    col.prop(item, "seed")

    col.separator()

    col.prop(item, "strength")
    col.prop(item, "offset")
    col.prop(item, "scale")
    col.prop(item, "scale_vec")

    col.separator()

    col.prop(item, "persistence")

    row = col.row()
    row.use_property_split = True
    row.enabled = item.item_type != "SIMPLEX"
    row.prop(item, "lacunarity")

    col.prop(item, "frequency")
    col.prop(item, "octaves")


def _draw_standard_noise_settings(layout, item):
    col = _draw_layer_header(layout, item)
    _draw_noise_settings(col, item)


def _draw_curl_noise_settings(layout, item):
    col = _draw_layer_header(layout, item)
    _draw_noise_settings(col, item)

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Curl Settings")

    col.prop(item, "curl_blend")
    col.prop(item, "curl_add")


LAYER_DRAW_FUNCS = {
    "SIMPLEX": _draw_standard_noise_settings,
    "CURL": _draw_curl_noise_settings,
    "TURBULENCE": _draw_standard_noise_settings,
    "WAVY_TURBULENCE": _draw_standard_noise_settings,
    "VORONOISE": _draw_standard_noise_settings,
    "FBM": _draw_standard_noise_settings,
    "CUBIC": _draw_standard_noise_settings,
}


def draw_turbulence_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


def add_default_turbulence_layer(props):
    item = props.turbulence_layers.add()
    item.item_type = "VORONOISE"
    item.enabled = True
    auto_rename.initialize_added(item, props.turbulence_layers, _turbulence_layer_base_name(item))

    props.turbulence_layers_index = 0


def _update_turbulence_layers_index(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


_NOISE_TYPE_IDS = {
    "SIMPLEX": "ID_NX_TURBULENCE_NOISE_TYPE_SIMPLEX",
    "CURL": "ID_NX_TURBULENCE_NOISE_TYPE_CURL",
    "TURBULENCE": "ID_NX_TURBULENCE_NOISE_TYPE_TURBULENCE",
    "WAVY_TURBULENCE": "ID_NX_TURBULENCE_NOISE_TYPE_WAVY_TURBULENCE",
    "VORONOISE": "ID_NX_TURBULENCE_NOISE_TYPE_VORONOISE",
    "FBM": "ID_NX_TURBULENCE_NOISE_TYPE_FBM",
    "CUBIC": "ID_NX_TURBULENCE_NOISE_TYPE_CUBIC",
}

_DIR_MODE_IDS = {
    "DIR": "ID_NX_TURBULENCE_DIRECTION_MODE_DIR",
    "ACCELERATION": "ID_NX_TURBULENCE_DIRECTION_MODE_ACCELERATION",
}

_TURBULENCE_ITEM_SYNC_SPECS = (
    SyncSpec.param(
        "enum",
        "direction_mode",
        "ID_NX_TURBULENCE_DIRECTION_MODE",
        enum_map=_DIR_MODE_IDS,
    ),
    SyncSpec.param("int", "seed", "ID_NX_TURBULENCE_SEED"),
    SyncSpec.param("float", "strength", "ID_NX_TURBULENCE_STR"),
    SyncSpec.param("vector", "offset", "ID_NX_TURBULENCE_OFFSET"),
    SyncSpec.param("float", "scale", "ID_NX_TURBULENCE_SCALE", scale=0.01),
    SyncSpec.param("vector", "scale_vec", "ID_NX_TURBULENCE_SCALE_VEC"),
    SyncSpec.param("float", "persistence", "ID_NX_TURBULENCE_PERSISTENCE"),
    SyncSpec.param("float", "lacunarity", "ID_NX_TURBULENCE_LACUNARITY"),
    SyncSpec.param("float", "frequency", "ID_NX_TURBULENCE_FREQUENCY"),
    SyncSpec.param("int", "octaves", "ID_NX_TURBULENCE_OCTAVES"),
    SyncSpec.param("float", "curl_blend", "ID_NX_TURBULENCE_CURL_BLEND"),
    SyncSpec.param("float", "curl_add", "ID_NX_TURBULENCE_CURL_ADD"),
)

NexusTurbulenceLayerItem._sync_specs = _TURBULENCE_ITEM_SYNC_SPECS


_TURBULENCE_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_TURBULENCE_OPERATION_TREE",
    collection_attr="turbulence_layers",
    type_id_map=_NOISE_TYPE_IDS,
    default_type_id="ID_NX_TURBULENCE_NOISE_TYPE_SIMPLEX",
    layer_op_id_name="ID_NX_TURBULENCE_LAYER_OP",
    blend_spec=TURBULENCE_BLEND_SPEC,
    enabled_disables_blend=True,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_TURBULENCE",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="turbulence_layers",
            prop=CollectionProperty(
                name="Turbulence Layers",
                type=NexusTurbulenceLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="turbulence_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_turbulence_layers_index,
            ),
        ),
    ),
    item_classes=(NexusTurbulenceLayerItem,),
    enum_builders=(build_turbulence_enum_items,),
    enum_defaults={
        "direction_mode": "ACCELERATION",
    },
    nodetree_sync=(_TURBULENCE_TREE_SPEC,),
)


register_collection_preset(
    "NX_TURBULENCE",
    CollectionPresetSpec(
        collection_attr="turbulence_layers",
        menu_id="turbulence_layers",
    ),
)
