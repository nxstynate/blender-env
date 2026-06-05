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
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform

LIMIT_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_LIMIT_BLEND_MODE",
    strength_id_name="ID_NX_LIMIT_BLEND_STRENGTH",
    id_map={
        "NORMAL": "ID_NX_LIMIT_BLEND_NORMAL",
        "ADD": "ID_NX_LIMIT_BLEND_ADD",
        "SUBTRACT": "ID_NX_LIMIT_BLEND_SUB",
        "MULTIPLY": "ID_NX_LIMIT_BLEND_MULT",
        "DIFFERENCE": "ID_NX_LIMIT_BLEND_DIFFERENCE",
        "SCREEN": "ID_NX_LIMIT_BLEND_SCREEN",
        "OVERLAY": "ID_NX_LIMIT_BLEND_OVERLAY",
        "MIN": "ID_NX_LIMIT_BLEND_MIN",
        "MAX": "ID_NX_LIMIT_BLEND_MAX",
    },
    labels={
        "NORMAL": ("Normal", "Standard blend"),
        "ADD": ("Add", "Add to previous"),
        "SUBTRACT": ("Subtract", "Subtract from previous"),
        "MULTIPLY": ("Multiply", "Multiply with previous"),
        "DIFFERENCE": ("Difference", "Difference blend"),
        "SCREEN": ("Screen", "Screen blend"),
        "OVERLAY": ("Overlay", "Overlay blend"),
        "MIN": ("Min", "Minimum of values"),
        "MAX": ("Max", "Maximum of values"),
    },
)

LIMIT_LAYER_DEFS = {
    "VELOCITY": {
        "name": "Velocity",
        "description": "Limit particle velocity per axis",
        "icon_name": "nx_limit_layer_velocity",
        "blender_icon": "FORCE_WIND",
    },
    "POSITION": {
        "name": "Position",
        "description": "Limit particle position per axis",
        "icon_name": "nx_limit_layer_position",
        "blender_icon": "PIVOT_CURSOR",
    },
    "SCALE": {
        "name": "Scale",
        "description": "Limit particle scale",
        "icon_name": "nx_limit_layer_scale",
        "blender_icon": "FULLSCREEN_ENTER",
    },
    "ROTATION": {
        "name": "Rotation",
        "description": "Limit particle rotation",
        "icon_name": "nx_limit_layer_rotation",
        "blender_icon": "DRIVER_ROTATIONAL_DIFFERENCE",
    },
    "SPEED": {
        "name": "Speed",
        "description": "Limit particle speed",
        "icon_name": "nx_limit_layer_speed",
        "blender_icon": "SORTTIME",
    },
    "RADIUS": {
        "name": "Radius",
        "description": "Limit particle radius",
        "icon_name": "nx_limit_layer_radius",
        "blender_icon": "MESH_CIRCLE",
    },
    "MASS": {
        "name": "Mass",
        "description": "Limit particle mass",
        "icon_name": "nx_limit_layer_mass",
        "blender_icon": "PHYSICS",
    },
    "USER": {
        "name": "User Value",
        "description": "Limit particle user value",
        "icon_name": "nx_limit_layer_user_value",
        "blender_icon": "PREFERENCES",
    },
}


_LIMIT_LAYER_ITEMS = []


def build_limit_enum_items():
    global _LIMIT_LAYER_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _LIMIT_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(LIMIT_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _LIMIT_LAYER_ITEMS.append(
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
            _LIMIT_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "limit_layers",
        _LIMIT_LAYER_ITEMS,
        "limit_layers",
        "limit_layers_index",
        separator_after={"ROTATION", "MASS"},
    )


def _get_limit_layer_items(self, context):
    return _LIMIT_LAYER_ITEMS


def _update_layer_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class NexusLimitLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Limit layer name",
        default="",
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this limit layer",
        default=True,
        update=_update_layer_viewport,
    )

    item_type: EnumProperty(
        name="Layer Type",
        description="Type of limit operation",
        items=_get_limit_layer_items,
        default=0,
        update=_update_layer_viewport,
    )

    blend_mode: EnumProperty(
        name="Blend Mode",
        description="How this layer blends with previous layers",
        items=LIMIT_BLEND_SPEC.enum_items(),
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

    velocity_type: EnumProperty(
        name="Coordinates",
        description="Coordinate system for velocity limits",
        items=[
            ("EMITTER", "Emitter", "Relative to emitter"),
            ("WORLD", "World", "World coordinates"),
        ],
        default=0,
    )

    velocity_range_min_x: FloatProperty(
        name="Range Min X",
        description="Minimum velocity restriction for X axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_min_y: FloatProperty(
        name="Range Min Y",
        description="Minimum velocity restriction for Y axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_min_z: FloatProperty(
        name="Range Min Z",
        description="Minimum velocity restriction for Z axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_min_var_x: FloatProperty(
        name="Variation X",
        description=("Random variation for minimum velocity restriction X axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_min_var_y: FloatProperty(
        name="Variation Y",
        description=("Random variation for minimum velocity restriction Y axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_min_var_z: FloatProperty(
        name="Variation Z",
        description=("Random variation for minimum velocity restriction Z axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_x: FloatProperty(
        name="Range Max X",
        description="Maximum velocity restriction for X axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_y: FloatProperty(
        name="Range Max Y",
        description="Maximum velocity restriction for Y axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_z: FloatProperty(
        name="Range Max Z",
        description="Maximum velocity restriction for Z axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_var_x: FloatProperty(
        name="Variation X",
        description=("Random variation for maximum velocity restriction X axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_var_y: FloatProperty(
        name="Variation Y",
        description=("Random variation for maximum velocity restriction Y axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_range_max_var_z: FloatProperty(
        name="Variation Z",
        description=("Random variation for maximum velocity restriction Z axis"),
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    velocity_axis_x: EnumProperty(
        name="X-Axis Restriction",
        description="Restriction mode for X axis",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "+X", "Restrict positive X direction"),
            ("MINUS", "-X", "Restrict negative X direction"),
        ],
        default="NONE",
    )

    velocity_axis_y: EnumProperty(
        name="Y-Axis Restriction",
        description="Restriction mode for Y axis",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "+Y", "Restrict positive Y direction"),
            ("MINUS", "-Y", "Restrict negative Y direction"),
        ],
        default="NONE",
    )

    velocity_axis_z: EnumProperty(
        name="Z-Axis Restriction",
        description="Restriction mode for Z axis",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "+Z", "Restrict positive Z direction"),
            ("MINUS", "-Z", "Restrict negative Z direction"),
        ],
        default="NONE",
    )

    velocity_banking: BoolProperty(
        name="No Banking",
        description="Disable velocity banking",
        default=False,
    )

    position_type: EnumProperty(
        name="Coordinate System",
        description="Coordinate system for position limits",
        items=[
            ("EMITTER", "Emitter", "Relative to emitter"),
            ("WORLD", "World", "World coordinates"),
            ("PARTICLE", "Particle", "Relative to particle birth position"),
        ],
        default=0,
    )

    position_axis_x: EnumProperty(
        name="X Restriction",
        description="Restriction mode for X axis position",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "X+", "Restrict positive X direction"),
            ("MINUS", "X-", "Restrict negative X direction"),
            ("RANGE", "Range", "Restrict to range"),
            ("FIXED", "Fixed", "Fix to a set position"),
        ],
        default="NONE",
    )

    position_axis_y: EnumProperty(
        name="Y Restriction",
        description="Restriction mode for Y axis position",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "Y+", "Restrict positive Y direction"),
            ("MINUS", "Y-", "Restrict negative Y direction"),
            ("RANGE", "Range", "Restrict to range"),
            ("FIXED", "Fixed", "Fix to a set position"),
        ],
        default="NONE",
    )

    position_axis_z: EnumProperty(
        name="Z Restriction",
        description="Restriction mode for Z axis position",
        items=[
            ("NONE", "None", "No restriction"),
            ("PLUS", "Z+", "Restrict positive Z direction"),
            ("MINUS", "Z-", "Restrict negative Z direction"),
            ("RANGE", "Range", "Restrict to range"),
            ("FIXED", "Fixed", "Fix to a set position"),
        ],
        default="NONE",
    )

    position_x_min: FloatProperty(
        name="X Min",
        description="Minimum X position",
        default=0.0,
        unit="LENGTH",
    )

    position_x_min_var: FloatProperty(
        name="X Min Variation",
        description="Random variation percentage for X minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_x_max: FloatProperty(
        name="X Max",
        description="Maximum X position",
        default=0.0,
        unit="LENGTH",
    )

    position_x_max_var: FloatProperty(
        name="X Max Variation",
        description="Random variation percentage for X maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_x_fixed_set: FloatProperty(
        name="X Fixed",
        description="Fixed X position",
        default=0.0,
        unit="LENGTH",
    )

    position_y_min: FloatProperty(
        name="Y Min",
        description="Minimum Y position",
        default=0.0,
        unit="LENGTH",
    )

    position_y_min_var: FloatProperty(
        name="Y Min Variation",
        description="Random variation percentage for Y minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_y_max: FloatProperty(
        name="Y Max",
        description="Maximum Y position",
        default=0.0,
        unit="LENGTH",
    )

    position_y_max_var: FloatProperty(
        name="Y Max Variation",
        description="Random variation percentage for Y maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_y_fixed_set: FloatProperty(
        name="Y Fixed",
        description="Fixed Y position",
        default=0.0,
        unit="LENGTH",
    )

    position_z_min: FloatProperty(
        name="Z Min",
        description="Minimum Z position",
        default=0.0,
        unit="LENGTH",
    )

    position_z_min_var: FloatProperty(
        name="Z Min Variation",
        description="Random variation percentage for Z minimum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_z_max: FloatProperty(
        name="Z Max",
        description="Maximum Z position",
        default=0.0,
        unit="LENGTH",
    )

    position_z_max_var: FloatProperty(
        name="Z Max Variation",
        description="Random variation percentage for Z maximum",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    position_z_fixed_set: FloatProperty(
        name="Z Fixed",
        description="Fixed Z position",
        default=0.0,
        unit="LENGTH",
    )

    scale_upper: BoolProperty(
        name="Range Max",
        description="Enable upper scale limit",
        default=False,
    )

    scale_upper_limit: FloatVectorProperty(
        name="Value",
        description="Maximum scale per axis",
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=100.0,
    )

    scale_upper_limit_var_x: FloatProperty(
        name="Variation X",
        description="Random variation for upper scale limit X axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_upper_limit_var_y: FloatProperty(
        name="Variation Y",
        description="Random variation for upper scale limit Y axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_upper_limit_var_z: FloatProperty(
        name="Variation Z",
        description="Random variation for upper scale limit Z axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_lower: BoolProperty(
        name="Range Min",
        description="Enable lower scale limit",
        default=False,
    )

    scale_lower_limit: FloatVectorProperty(
        name="Value",
        description="Minimum scale per axis",
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=100.0,
    )

    scale_lower_limit_var_x: FloatProperty(
        name="Variation X",
        description="Random variation for lower scale limit X axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_lower_limit_var_y: FloatProperty(
        name="Variation Y",
        description="Random variation for lower scale limit Y axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    scale_lower_limit_var_z: FloatProperty(
        name="Variation Z",
        description="Random variation for lower scale limit Z axis",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_link: BoolProperty(
        name="Link Channels",
        description="Link all rotation channels together",
        default=False,
    )

    rotation_mode: EnumProperty(
        name="Mode",
        description="Rotation limit mode",
        items=[
            ("WORLD", "World", "World space rotation limits"),
            ("RELATIVE", "Relative", "Relative rotation limits"),
        ],
        default="WORLD",
    )

    rotation_qtabs: EnumProperty(
        name="Channel",
        description="Active rotation channel tab",
        items=[
            ("H", "Heading", "Heading rotation channel"),
            ("P", "Pitch", "Pitch rotation channel"),
            ("B", "Banking", "Banking rotation channel"),
        ],
        default="H",
    )

    rotation_all_pos: BoolProperty(
        name="Positive",
        description="Enable positive rotation limit",
        default=False,
    )

    rotation_all_pos_limit: FloatProperty(
        name="Positive Limit",
        description="Maximum positive rotation",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_all_pos_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for positive limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_all_neg: BoolProperty(
        name="Negative",
        description="Enable negative rotation limit",
        default=False,
    )

    rotation_all_neg_limit: FloatProperty(
        name="Negative Limit",
        description="Maximum negative rotation",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_all_neg_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for negative limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_h_pos: BoolProperty(
        name="Positive",
        description="Enable positive heading limit",
        default=False,
    )

    rotation_h_pos_limit: FloatProperty(
        name="Positive Limit",
        description="Maximum positive heading",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_h_pos_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for positive heading limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_h_neg: BoolProperty(
        name="Negative",
        description="Enable negative heading limit",
        default=False,
    )

    rotation_h_neg_limit: FloatProperty(
        name="Negative Limit",
        description="Maximum negative heading",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_h_neg_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for negative heading limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_p_pos: BoolProperty(
        name="Positive",
        description="Enable positive pitch limit",
        default=False,
    )

    rotation_p_pos_limit: FloatProperty(
        name="Positive Limit",
        description="Maximum positive pitch",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_p_pos_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for positive pitch limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_p_neg: BoolProperty(
        name="Negative",
        description="Enable negative pitch limit",
        default=False,
    )

    rotation_p_neg_limit: FloatProperty(
        name="Negative Limit",
        description="Maximum negative pitch",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_p_neg_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for negative pitch limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_b_pos: BoolProperty(
        name="Positive",
        description="Enable positive bank limit",
        default=False,
    )

    rotation_b_pos_limit: FloatProperty(
        name="Positive Limit",
        description="Maximum positive bank",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_b_pos_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for positive bank limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    rotation_b_neg: BoolProperty(
        name="Negative",
        description="Enable negative bank limit",
        default=False,
    )

    rotation_b_neg_limit: FloatProperty(
        name="Negative Limit",
        description="Maximum negative bank",
        default=0.0,
        subtype="ANGLE",
    )

    rotation_b_neg_limit_var: FloatProperty(
        name="Variation",
        description="Random variation for negative bank limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    speed_lower: BoolProperty(
        name="Range Min",
        description="Enable lower speed limit",
        default=False,
    )

    speed_lower_value: FloatProperty(
        name="Value",
        description="Minimum speed",
        default=0.0,
        unit="VELOCITY",
    )

    speed_lower_var: FloatProperty(
        name="Variation",
        description="Random variation for lower speed limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    speed_higher: BoolProperty(
        name="Range Max",
        description="Enable upper speed limit",
        default=False,
    )

    speed_higher_value: FloatProperty(
        name="Value",
        description="Maximum speed",
        default=0.0,
        unit="VELOCITY",
    )

    speed_higher_var: FloatProperty(
        name="Variation",
        description="Random variation for upper speed limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_lower: BoolProperty(
        name="Range Min",
        description="Enable lower radius limit",
        default=False,
    )

    radius_lower_value: FloatProperty(
        name="Value",
        description="Minimum radius",
        default=0.0,
        unit="LENGTH",
    )

    radius_lower_var: FloatProperty(
        name="Variation",
        description="Random variation for lower radius limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    radius_higher: BoolProperty(
        name="Range Max",
        description="Enable upper radius limit",
        default=False,
    )

    radius_higher_value: FloatProperty(
        name="Value",
        description="Maximum radius",
        default=0.0,
        unit="LENGTH",
    )

    radius_higher_var: FloatProperty(
        name="Variation",
        description="Random variation for upper radius limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_lower: BoolProperty(
        name="Range Min",
        description="Enable lower mass limit",
        default=False,
    )

    mass_lower_value: FloatProperty(
        name="Value",
        description="Minimum mass",
        default=0.0,
    )

    mass_lower_var: FloatProperty(
        name="Variation",
        description="Random variation for lower mass limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    mass_higher: BoolProperty(
        name="Range Max",
        description="Enable upper mass limit",
        default=False,
    )

    mass_higher_value: FloatProperty(
        name="Value",
        description="Maximum mass",
        default=0.0,
    )

    mass_higher_var: FloatProperty(
        name="Variation",
        description="Random variation for upper mass limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    user_value_lower: BoolProperty(
        name="Range Min",
        description="Enable lower user value limit",
        default=False,
    )

    user_value_lower_value: FloatProperty(
        name="Value",
        description="Minimum user value",
        default=0.0,
    )

    user_value_lower_var: FloatProperty(
        name="Variation",
        description="Random variation for lower user value limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    user_value_higher: BoolProperty(
        name="Range Max",
        description="Enable upper user value limit",
        default=False,
    )

    user_value_higher_value: FloatProperty(
        name="Value",
        description="Maximum user value",
        default=0.0,
    )

    user_value_higher_var: FloatProperty(
        name="Variation",
        description="Random variation for upper user value limit",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )


def _draw_pct_vector(col, item, prop_prefix, label):
    sub = col.column(align=True)
    sub.prop(item, f"{prop_prefix}_x", text=label)
    sub.prop(item, f"{prop_prefix}_y", text=" ")
    sub.prop(item, f"{prop_prefix}_z", text=" ")


def _draw_layer_header(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "item_type")

    col.separator(type="LINE")

    col.prop(item, "blend_mode")
    col.prop(item, "blend_strength")

    return col


def _draw_velocity_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "velocity_type")

    col.separator(type="LINE")

    _draw_pct_vector(col, item, "velocity_range_min", "Range Min")
    _draw_pct_vector(col, item, "velocity_range_min_var", "Variation")

    col.separator(type="LINE")

    _draw_pct_vector(col, item, "velocity_range_max", "Range Max")
    _draw_pct_vector(col, item, "velocity_range_max_var", "Variation")

    col.separator(type="LINE")

    col.prop(item, "velocity_axis_x")
    col.prop(item, "velocity_axis_y")
    col.prop(item, "velocity_axis_z")

    col.prop(item, "velocity_banking")


def _draw_position_axis(col, item, axis):
    axis_lower = axis.lower()
    mode_prop = f"position_axis_{axis_lower}"
    mode = getattr(item, mode_prop)

    col.prop(item, mode_prop)

    if mode == "NONE":
        return

    if mode == "FIXED":
        col.prop(item, f"position_{axis_lower}_fixed_set")
        return

    if mode in ("PLUS", "RANGE"):
        col.prop(item, f"position_{axis_lower}_min")
        col.prop(item, f"position_{axis_lower}_min_var")

    if mode in ("MINUS", "RANGE"):
        col.prop(item, f"position_{axis_lower}_max")
        col.prop(item, f"position_{axis_lower}_max_var")


def _draw_position_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "position_type")

    for axis in ("X", "Y", "Z"):
        col.separator(type="LINE")

        _draw_position_axis(col, item, axis)


def _draw_scale_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "scale_lower")

    sub = col.column()
    sub.enabled = item.scale_lower
    sub.prop(item, "scale_lower_limit")
    _draw_pct_vector(sub, item, "scale_lower_limit_var", "Variation")

    col.separator(type="LINE")

    col.prop(item, "scale_upper")

    sub = col.column()
    sub.enabled = item.scale_upper
    sub.prop(item, "scale_upper_limit")
    _draw_pct_vector(sub, item, "scale_upper_limit_var", "Variation")


def _draw_rotation_channel(col, item, channel, label):
    pos_prop = f"rotation_{channel}_pos"
    pos_limit_prop = f"rotation_{channel}_pos_limit"
    pos_var_prop = f"rotation_{channel}_pos_limit_var"
    neg_prop = f"rotation_{channel}_neg"
    neg_limit_prop = f"rotation_{channel}_neg_limit"
    neg_var_prop = f"rotation_{channel}_neg_limit_var"

    col.prop(item, pos_prop, text=f"Limit {label} Positive")
    sub = col.column()
    sub.enabled = getattr(item, pos_prop)
    sub.prop(item, pos_limit_prop, text=f"Positive Limit {label}")
    sub.prop(item, pos_var_prop)

    col.prop(item, neg_prop, text=f"Limit {label} Negative")
    sub = col.column()
    sub.enabled = getattr(item, neg_prop)
    sub.prop(item, neg_limit_prop, text=f"Negative Limit {label}")
    sub.prop(item, neg_var_prop)


def _draw_rotation_settings(layout, item):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, "rotation_mode")

    col.separator(type="LINE")

    col.prop(item, "rotation_link")

    col.separator(type="LINE")

    if item.rotation_link:
        _draw_rotation_channel(col, item, "all", "All")
    else:
        row = col.row()
        row.use_property_split = False
        row.prop(item, "rotation_qtabs", expand=True)

        col.separator(type="LINE")

        channel_map = {
            "H": ("h", "H"),
            "P": ("p", "P"),
            "B": ("b", "B"),
        }
        channel, label = channel_map.get(item.rotation_qtabs, ("h", "H"))
        _draw_rotation_channel(col, item, channel, label)


def _draw_lower_higher_settings(layout, item, prefix):
    col = _draw_layer_header(layout, item)

    col.separator(type="LINE")

    col.prop(item, f"{prefix}_lower")

    sub = col.column()
    sub.enabled = getattr(item, f"{prefix}_lower")
    sub.prop(item, f"{prefix}_lower_value")
    sub.prop(item, f"{prefix}_lower_var")

    col.prop(item, f"{prefix}_higher")

    sub = col.column()
    sub.enabled = getattr(item, f"{prefix}_higher")
    sub.prop(item, f"{prefix}_higher_value")
    sub.prop(item, f"{prefix}_higher_var")


def _draw_speed_settings(layout, item):
    _draw_lower_higher_settings(layout, item, "speed")


def _draw_radius_settings(layout, item):
    _draw_lower_higher_settings(layout, item, "radius")


def _draw_mass_settings(layout, item):
    _draw_lower_higher_settings(layout, item, "mass")


def _draw_user_value_settings(layout, item):
    _draw_lower_higher_settings(layout, item, "user_value")


LAYER_DRAW_FUNCS = {
    "VELOCITY": _draw_velocity_settings,
    "POSITION": _draw_position_settings,
    "SCALE": _draw_scale_settings,
    "ROTATION": _draw_rotation_settings,
    "SPEED": _draw_speed_settings,
    "RADIUS": _draw_radius_settings,
    "MASS": _draw_mass_settings,
    "USER": _draw_user_value_settings,
}


def draw_limit_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


def add_default_limit_layer(obj):
    from ..utils import generate_unique_name

    props = obj.nexus_modifier
    item = props.limit_layers.add()
    item.item_type = "VELOCITY"
    item.enabled = True
    item.blend_strength = 100.0

    base_name = LIMIT_LAYER_DEFS["VELOCITY"]["name"]
    existing = [i.name for i in props.limit_layers if i.name]
    item.name = generate_unique_name(base_name, existing)

    props.limit_layers_index = 0


_UNIT = TRANSFORM_FACTORS[Transform.UNIT_SCALE]
_PCT = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

LIMIT_LAYER_TYPE_IDS = {
    "VELOCITY": "ID_NX_LIMIT_TREE_CHOICE_VELOCITY",
    "POSITION": "ID_NX_LIMIT_TREE_CHOICE_POSITION",
    "SCALE": "ID_NX_LIMIT_TREE_CHOICE_SCALE",
    "ROTATION": "ID_NX_LIMIT_TREE_CHOICE_ROTATION",
    "SPEED": "ID_NX_LIMIT_TREE_CHOICE_SPEED",
    "RADIUS": "ID_NX_LIMIT_TREE_CHOICE_RADIUS",
    "MASS": "ID_NX_LIMIT_TREE_CHOICE_MASS",
    "USER": "ID_NX_LIMIT_TREE_CHOICE_USER",
}

LIMIT_LAYER_OP_IDS = {
    "VELOCITY": "ID_NX_LIMIT_OP_VELOCITY",
    "POSITION": "ID_NX_LIMIT_OP_POSITION",
    "SCALE": "ID_NX_LIMIT_OP_SCALE",
    "ROTATION": "ID_NX_LIMIT_OP_ROT",
    "SPEED": "ID_NX_LIMIT_OP_SPEED",
    "RADIUS": "ID_NX_LIMIT_OP_RADIUS",
    "MASS": "ID_NX_LIMIT_OP_MASS",
    "USER": "ID_NX_LIMIT_OP_USER_VALUE",
}

_LIMIT_ITEM_SYNC_SPECS = (
    SyncSpec.param(
        "enum",
        "item_type",
        "ID_NX_LIMIT_LAYER_OP",
        enum_map=LIMIT_LAYER_OP_IDS,
    ),
)

NexusLimitLayerItem._sync_specs = _LIMIT_ITEM_SYNC_SPECS

VELOCITY_TYPE_IDS = {
    "EMITTER": "ID_NX_LIMIT_VELOCITY_TYPE_EMITTER",
    "WORLD": "ID_NX_LIMIT_VELOCITY_TYPE_WORLD",
    # "CUSTOM": "ID_NX_LIMIT_VELOCITY_TYPE_CUSTOM",  # TODO: link object not implemented
}

VELOCITY_AXIS_X_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_VELOCITY_AXIS_X_NONE",
    "PLUS": "ID_NX_LIMIT_VELOCITY_AXIS_X_PLUS",
    "MINUS": "ID_NX_LIMIT_VELOCITY_AXIS_X_MINUS",
}

VELOCITY_AXIS_Y_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_VELOCITY_AXIS_Y_NONE",
    "PLUS": "ID_NX_LIMIT_VELOCITY_AXIS_Y_PLUS",
    "MINUS": "ID_NX_LIMIT_VELOCITY_AXIS_Y_MINUS",
}

VELOCITY_AXIS_Z_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_VELOCITY_AXIS_Z_NONE",
    "PLUS": "ID_NX_LIMIT_VELOCITY_AXIS_Z_PLUS",
    "MINUS": "ID_NX_LIMIT_VELOCITY_AXIS_Z_MINUS",
}

POSITION_TYPE_IDS = {
    "EMITTER": "ID_NX_LIMIT_POSITION_TYPE_EMITTER",
    "WORLD": "ID_NX_LIMIT_POSITION_TYPE_WORLD",
    # "CUSTOM": "ID_NX_LIMIT_POSITION_TYPE_CUSTOM",  # TODO: link object not implemented
    "PARTICLE": "ID_NX_LIMIT_POSITION_TYPE_PARTICLE",
}

POSITION_AXIS_X_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_POSITION_AXIS_X_NONE",
    "PLUS": "ID_NX_LIMIT_POSITION_AXIS_X_PLUS",
    "MINUS": "ID_NX_LIMIT_POSITION_AXIS_X_MINUS",
    "RANGE": "ID_NX_LIMIT_POSITION_AXIS_X_RANGE",
    "FIXED": "ID_NX_LIMIT_POSITION_AXIS_X_FIXED",
}

POSITION_AXIS_Y_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_POSITION_AXIS_Y_NONE",
    "PLUS": "ID_NX_LIMIT_POSITION_AXIS_Y_PLUS",
    "MINUS": "ID_NX_LIMIT_POSITION_AXIS_Y_MINUS",
    "RANGE": "ID_NX_LIMIT_POSITION_AXIS_Y_RANGE",
    "FIXED": "ID_NX_LIMIT_POSITION_AXIS_Y_FIXED",
}

POSITION_AXIS_Z_MODE_IDS = {
    "NONE": "ID_NX_LIMIT_POSITION_AXIS_Z_NONE",
    "PLUS": "ID_NX_LIMIT_POSITION_AXIS_Z_PLUS",
    "MINUS": "ID_NX_LIMIT_POSITION_AXIS_Z_MINUS",
    "RANGE": "ID_NX_LIMIT_POSITION_AXIS_Z_RANGE",
    "FIXED": "ID_NX_LIMIT_POSITION_AXIS_Z_FIXED",
}

ROTATION_MODE_IDS = {
    "WORLD": "ID_NX_LIMIT_ROTATION_MODE_WORLD",
    "RELATIVE": "ID_NX_LIMIT_ROTATION_MODE_RELATIVE",
}

_POSITION_AXIS_MODE_IDS = {
    "x": POSITION_AXIS_X_MODE_IDS,
    "y": POSITION_AXIS_Y_MODE_IDS,
    "z": POSITION_AXIS_Z_MODE_IDS,
}


def _sync_velocity_layer(theron, get, nc, item, _item_orig, _obj):
    vel_type_val = get(
        VELOCITY_TYPE_IDS.get(item.velocity_type, "ID_NX_LIMIT_VELOCITY_TYPE_EMITTER")
    )
    theron.set_int32(nc, get("ID_NX_LIMIT_VELOCITY_TYPE"), vel_type_val)

    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_VELOCITY_AXIS_MIN"),
        item.velocity_range_min_x * _PCT,
        item.velocity_range_min_y * _PCT,
        item.velocity_range_min_z * _PCT,
    )
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_VELOCITY_AXIS_MIN_VAR"),
        item.velocity_range_min_var_x * _PCT,
        item.velocity_range_min_var_y * _PCT,
        item.velocity_range_min_var_z * _PCT,
    )

    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_VELOCITY_AXIS_MAX"),
        item.velocity_range_max_x * _PCT,
        item.velocity_range_max_y * _PCT,
        item.velocity_range_max_z * _PCT,
    )
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_VELOCITY_AXIS_MAX_VAR"),
        item.velocity_range_max_var_x * _PCT,
        item.velocity_range_max_var_y * _PCT,
        item.velocity_range_max_var_z * _PCT,
    )

    x_mode_id = VELOCITY_AXIS_X_MODE_IDS.get(
        item.velocity_axis_x, "ID_NX_LIMIT_VELOCITY_AXIS_X_NONE"
    )
    theron.set_int32(nc, get("ID_NX_LIMIT_VELOCITY_AXIS_X"), get(x_mode_id))

    y_mode_id = VELOCITY_AXIS_Y_MODE_IDS.get(
        item.velocity_axis_y, "ID_NX_LIMIT_VELOCITY_AXIS_Y_NONE"
    )
    theron.set_int32(nc, get("ID_NX_LIMIT_VELOCITY_AXIS_Y"), get(y_mode_id))

    z_mode_id = VELOCITY_AXIS_Z_MODE_IDS.get(
        item.velocity_axis_z, "ID_NX_LIMIT_VELOCITY_AXIS_Z_NONE"
    )
    theron.set_int32(nc, get("ID_NX_LIMIT_VELOCITY_AXIS_Z"), get(z_mode_id))

    theron.set_bool(nc, get("ID_NX_LIMIT_VELOCITY_BANKING"), item.velocity_banking)

    # TODO: CUSTOM link object support


def _sync_position_layer(theron, get, nc, item, _item_orig, _obj):
    pos_type_val = get(
        POSITION_TYPE_IDS.get(item.position_type, "ID_NX_LIMIT_POSITION_TYPE_EMITTER")
    )
    theron.set_int32(nc, get("ID_NX_LIMIT_POSITION_TYPE"), pos_type_val)

    _sync_position_axis(theron, get, nc, item, "x")
    _sync_position_axis(theron, get, nc, item, "y")
    _sync_position_axis(theron, get, nc, item, "z")

    # TODO: CUSTOM link object support


def _sync_position_axis(theron, get, nc, item, axis):
    axis_upper = axis.upper()
    mode_ids = _POSITION_AXIS_MODE_IDS[axis]
    mode = getattr(item, f"position_axis_{axis}")
    theron.set_int32(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}"),
        get(mode_ids.get(mode, f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_NONE")),
    )
    theron.set_float(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_MIN"),
        getattr(item, f"position_{axis}_min") * _UNIT,
    )
    theron.set_float(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_MIN_VAR"),
        getattr(item, f"position_{axis}_min_var") * _PCT,
    )
    theron.set_float(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_MAX"),
        getattr(item, f"position_{axis}_max") * _UNIT,
    )
    theron.set_float(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_MAX_VAR"),
        getattr(item, f"position_{axis}_max_var") * _PCT,
    )
    theron.set_float(
        nc,
        get(f"ID_NX_LIMIT_POSITION_AXIS_{axis_upper}_FIXED_SET"),
        getattr(item, f"position_{axis}_fixed_set") * _UNIT,
    )


def _sync_scale_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_SCALE_UPPER"), item.scale_upper)
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_SCALE_UPPER_LIMIT"),
        item.scale_upper_limit[0],
        item.scale_upper_limit[1],
        item.scale_upper_limit[2],
    )
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_SCALE_UPPER_LIMIT_VAR"),
        item.scale_upper_limit_var_x * _PCT,
        item.scale_upper_limit_var_y * _PCT,
        item.scale_upper_limit_var_z * _PCT,
    )
    theron.set_bool(nc, get("ID_NX_LIMIT_SCALE_LOWER"), item.scale_lower)
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_SCALE_LOWER_LIMIT"),
        item.scale_lower_limit[0],
        item.scale_lower_limit[1],
        item.scale_lower_limit[2],
    )
    theron.set_vector(
        nc,
        get("ID_NX_LIMIT_SCALE_LOWER_LIMIT_VAR"),
        item.scale_lower_limit_var_x * _PCT,
        item.scale_lower_limit_var_y * _PCT,
        item.scale_lower_limit_var_z * _PCT,
    )


def _sync_rotation_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_LINK"), item.rotation_link)
    theron.set_int32(
        nc,
        get("ID_NX_LIMIT_ROTATION_MODE"),
        get(ROTATION_MODE_IDS.get(item.rotation_mode, "ID_NX_LIMIT_ROTATION_MODE_WORLD")),
    )

    if item.rotation_link:
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_ALL_POS"), item.rotation_all_pos)
        theron.set_float(
            nc, get("ID_NX_LIMIT_ROTATION_ALL_POS_LIMIT"), item.rotation_all_pos_limit
        )
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_ALL_POS_LIMIT_VAR"),
            item.rotation_all_pos_limit_var * _PCT,
        )
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_ALL_NEG"), item.rotation_all_neg)
        theron.set_float(
            nc, get("ID_NX_LIMIT_ROTATION_ALL_NEG_LIMIT"), item.rotation_all_neg_limit
        )
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_ALL_NEG_LIMIT_VAR"),
            item.rotation_all_neg_limit_var * _PCT,
        )
    else:
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_H_POS"), item.rotation_h_pos)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_H_POS_LIMIT"), item.rotation_h_pos_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_H_POS_LIMIT_VAR"),
            item.rotation_h_pos_limit_var * _PCT,
        )
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_H_NEG"), item.rotation_h_neg)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_H_NEG_LIMIT"), item.rotation_h_neg_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_H_NEG_LIMIT_VAR"),
            item.rotation_h_neg_limit_var * _PCT,
        )

        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_P_POS"), item.rotation_p_pos)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_P_POS_LIMIT"), item.rotation_p_pos_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_P_POS_LIMIT_VAR"),
            item.rotation_p_pos_limit_var * _PCT,
        )
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_P_NEG"), item.rotation_p_neg)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_P_NEG_LIMIT"), item.rotation_p_neg_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_P_NEG_LIMIT_VAR"),
            item.rotation_p_neg_limit_var * _PCT,
        )

        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_B_POS"), item.rotation_b_pos)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_B_POS_LIMIT"), item.rotation_b_pos_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_B_POS_LIMIT_VAR"),
            item.rotation_b_pos_limit_var * _PCT,
        )
        theron.set_bool(nc, get("ID_NX_LIMIT_ROTATION_B_NEG"), item.rotation_b_neg)
        theron.set_float(nc, get("ID_NX_LIMIT_ROTATION_B_NEG_LIMIT"), item.rotation_b_neg_limit)
        theron.set_float(
            nc,
            get("ID_NX_LIMIT_ROTATION_B_NEG_LIMIT_VAR"),
            item.rotation_b_neg_limit_var * _PCT,
        )


def _sync_speed_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_SPEED_LOWER"), item.speed_lower)
    theron.set_float(nc, get("ID_NX_LIMIT_SPEED_LOWER_VALUE"), item.speed_lower_value * _UNIT)
    theron.set_float(nc, get("ID_NX_LIMIT_SPEED_LOWER_VALUE_VAR"), item.speed_lower_var * _PCT)
    theron.set_bool(nc, get("ID_NX_LIMIT_SPEED_HIGHER"), item.speed_higher)
    theron.set_float(nc, get("ID_NX_LIMIT_SPEED_HIGHER_VALUE"), item.speed_higher_value * _UNIT)
    theron.set_float(nc, get("ID_NX_LIMIT_SPEED_HIGHER_VALUE_VAR"), item.speed_higher_var * _PCT)


def _sync_radius_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_RADIUS_LOWER"), item.radius_lower)
    theron.set_float(nc, get("ID_NX_LIMIT_RADIUS_LOWER_VALUE"), item.radius_lower_value * _UNIT)
    theron.set_float(nc, get("ID_NX_LIMIT_RADIUS_LOWER_VALUE_VAR"), item.radius_lower_var * _PCT)
    theron.set_bool(nc, get("ID_NX_LIMIT_RADIUS_HIGHER"), item.radius_higher)
    theron.set_float(nc, get("ID_NX_LIMIT_RADIUS_HIGHER_VALUE"), item.radius_higher_value * _UNIT)
    theron.set_float(nc, get("ID_NX_LIMIT_RADIUS_HIGHER_VALUE_VAR"), item.radius_higher_var * _PCT)


def _sync_mass_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_MASS_LOWER"), item.mass_lower)
    theron.set_float(nc, get("ID_NX_LIMIT_MASS_LOWER_VALUE"), item.mass_lower_value)
    theron.set_float(nc, get("ID_NX_LIMIT_MASS_LOWER_VALUE_VAR"), item.mass_lower_var * _PCT)
    theron.set_bool(nc, get("ID_NX_LIMIT_MASS_HIGHER"), item.mass_higher)
    theron.set_float(nc, get("ID_NX_LIMIT_MASS_HIGHER_VALUE"), item.mass_higher_value)
    theron.set_float(nc, get("ID_NX_LIMIT_MASS_HIGHER_VALUE_VAR"), item.mass_higher_var * _PCT)


def _sync_user_layer(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_LIMIT_USER_VALUE_LOWER"), item.user_value_lower)
    theron.set_float(nc, get("ID_NX_LIMIT_USER_VALUE_LOWER_VALUE"), item.user_value_lower_value)
    theron.set_float(
        nc, get("ID_NX_LIMIT_USER_VALUE_LOWER_VALUE_VAR"), item.user_value_lower_var * _PCT
    )
    theron.set_bool(nc, get("ID_NX_LIMIT_USER_VALUE_HIGHER"), item.user_value_higher)
    theron.set_float(nc, get("ID_NX_LIMIT_USER_VALUE_HIGHER_VALUE"), item.user_value_higher_value)
    theron.set_float(
        nc, get("ID_NX_LIMIT_USER_VALUE_HIGHER_VALUE_VAR"), item.user_value_higher_var * _PCT
    )


_LIMIT_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_LIMIT_OPERATION_TREE",
    collection_attr="limit_layers",
    type_id_map=LIMIT_LAYER_TYPE_IDS,
    enabled_disables_blend=True,
    blend_spec=LIMIT_BLEND_SPEC,
    per_type_syncers={
        "VELOCITY": _sync_velocity_layer,
        "POSITION": _sync_position_layer,
        "SCALE": _sync_scale_layer,
        "ROTATION": _sync_rotation_layer,
        "SPEED": _sync_speed_layer,
        "RADIUS": _sync_radius_layer,
        "MASS": _sync_mass_layer,
        "USER": _sync_user_layer,
    },
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_LIMIT",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="limit_layers",
            prop=CollectionProperty(
                name="Limit Layers",
                type=NexusLimitLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="limit_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
                update=_update_layer_viewport,
            ),
        ),
    ),
    item_classes=(NexusLimitLayerItem,),
    enum_builders=(build_limit_enum_items,),
    nodetree_sync=(_LIMIT_TREE_SPEC,),
)


register_collection_preset(
    "NX_LIMIT",
    CollectionPresetSpec(
        collection_attr="limit_layers",
        menu_id="limit_layers",
    ),
)
