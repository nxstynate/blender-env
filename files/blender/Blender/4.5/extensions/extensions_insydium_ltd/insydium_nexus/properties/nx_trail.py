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

from math import pi, radians

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_cleanup
from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nexus_time import draw_time_prop, nexus_time_property
from ..libs.resource_spec import CurveSpec, GradientSpec
from ..ui import NodeTreeDef, make_allowed_types_poll
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, srgb_to_linear

_TRAIL_TAB_ITEMS = [
    ("GENERAL", "General", "Colour, length, freeze", 0),
    ("THICKNESS", "Thickness", "Thickness and colour data", 1),
    ("SPLINE", "Spline", "Spline generation settings", 2),
]

_DISPLAY_ITEMS = [
    ("LINES", "Lines", "Viewport-only line overlay (zero-copy from GPU)", 0),
    ("SPLINES", "Splines", "Generate Blender Curves objects for rendering", 1),
]

_COLOR_MODE_ITEMS = [
    ("STANDARD", "Standard", "Single colour", 0),
    ("GRADIENT", "Gradient", "Gradient sampled along trail length", 1),
]

_THICKNESS_MODE_ITEMS = [
    ("NONE", "Do Not Set Thickness", "Do not create thickness data", 0),
    ("VALUE", "Set From Value", "Use a uniform trail thickness value", 1),
    ("SPLINE", "Use Spline", "Sample thickness from a spline over the trail", 2),
    ("RADIUS_CURRENT", "Use Radius (Current)", "Use the current particle radius", 3),
    ("RADIUS_VARIABLE", "Use Radius (Variable)", "Record particle radius per trail point", 4),
]

_TRAIL_COLOR_MODE_ITEMS = [
    ("PARTICLE", "Particle Color", "Use the particle's current colour", 0),
    ("PER_VERTEX", "Per-Vertex Color", "Store colour for each trail vertex", 1),
]

_LENGTH_MODE_ITEMS = [
    ("TIME", "Time", "Trail length measured in time", 0),
    ("DISTANCE", "Distance", "Trail length measured in distance", 1),
]

_ALGORITHM_ITEMS = [
    ("NO_CONNECTIONS", "No Connections", "Per-particle history rings (default)", 0),
    ("STRAIGHT_SEQUENCE", "Straight Sequence", "Link consecutive particles in emission order", 1),
    ("SEGMENTED_SEQUENCE", "Segmented Sequence", "Linked chains separated by gaps", 2),
    ("MULTIPLE_SEQUENCE", "Multiple Sequence", "Multiple splines from the particle source", 3),
    ("ALL_POINTS", "All Points", "Link every pair of particles in the source", 4),
    (
        "NEAREST_INDEX",
        "Nearest Index",
        "Link consecutive particles in ascending particle-ID order",
        5,
    ),
    (
        "NEAREST_DISTANCE",
        "Nearest Distance",
        "Link particles within a distance window",
        6,
    ),
    (
        "CLUSTER",
        "Cluster",
        "Group particles by transitive proximity and link within clusters",
        7,
    ),
]

_MULTIPLE_MODE_ITEMS = [
    ("ALTERNATING", "Alternating", "Take particles for each spline in turn", 0),
    ("SEQUENTIAL", "Sequential", "Use contiguous chunks of particles per spline", 1),
]

_DESTINATION_GROUPS_ITEMS = [
    ("USE_ALL", "Use All Groups", "Connect to any particle regardless of group", 0),
    ("ONLY_SAME_GROUP", "Only Same Group", "Connect only to particles in the same group", 1),
    (
        "ONLY_DIFFERENT_GROUPS",
        "Only Different Groups",
        "Connect only to particles in other groups",
        2,
    ),
    ("SPECIFIC_GROUP", "Specific Group", "Connect only to particles in the chosen group", 3),
    (
        "ALL_EXCEPT_SPECIFIC_GROUP",
        "All Except Specific Group",
        "Connect to particles not in the chosen group",
        4,
    ),
]

_trail_poll_group = make_allowed_types_poll(["NX_GROUP"])

_FREEZE_MODE_ITEMS = [
    ("NONE", "Do Not Freeze", "Particles keep moving when trail caps", 0),
    ("FREEZE_PARTICLE", "Freeze Particle", "Stop particle motion when trail caps", 1),
    ("FREEZE_TRAIL", "Freeze Trail", "Stop trail recording but keep particle moving", 2),
]

_SPLINE_TYPE_ITEMS = [
    ("LINEAR", "Linear", "Generate exact polyline splines", 0),
    ("BEZIER", "Bezier", "Generate smoothed Bezier splines", 1),
    ("BSPLINE", "B-Spline", "Generate smooth B-Spline curves", 2),
]

_SPLINE_INTERMEDIATE_ITEMS = [
    ("NONE", "None", "Use the resolved trail points directly", 0),
    ("UNIFORM", "Uniform", "Insert an even number of points along each segment", 1),
    ("ADAPTIVE", "Adaptive", "Insert points near corners above the Angle threshold", 2),
]


TRAIL_COLOR_GRADIENT_SLOT = "trail_color_gradient"
TRAIL_THICKNESS_SPLINE_SLOT = "trail_thickness_spline"

TRAIL_COLOR_GRADIENT_SPEC = GradientSpec(
    slot_name=TRAIL_COLOR_GRADIENT_SLOT,
    label="Color",
    default_stops=[
        (0.0, srgb_to_linear(XP_COLOR_MODS_BLUE)),
        (1.0, srgb_to_linear(XP_COLOR_MODS_RED)),
    ],
    slot_suffix_attr="layer_uid",
)

TRAIL_THICKNESS_SPLINE_SPEC = CurveSpec(
    slot_name=TRAIL_THICKNESS_SPLINE_SLOT,
    label="Thickness Spline",
    default_points=[
        (0.0, 1.0),
        (1.0, 0.0),
    ],
    slot_suffix_attr="layer_uid",
)

TRAIL_GRADIENT_SPECS = [TRAIL_COLOR_GRADIENT_SPEC]
TRAIL_CURVE_SPECS = [TRAIL_THICKNESS_SPLINE_SPEC]


def ensure_trail_source_resources(obj, item):
    from ..utils.curve import create_item_curves
    from ..utils.gradient import create_item_gradients

    if not item.layer_uid:
        return
    create_item_gradients(obj, item.layer_uid, TRAIL_GRADIENT_SPECS)
    create_item_curves(obj, item.layer_uid, TRAIL_CURVE_SPECS)


def remove_trail_source_resources(obj, item):
    from ..utils.curve import remove_item_curves
    from ..utils.gradient import remove_item_gradients

    if not item.layer_uid:
        return
    remove_item_gradients(obj, item.layer_uid, TRAIL_GRADIENT_SPECS)
    remove_item_curves(obj, item.layer_uid, TRAIL_CURVE_SPECS)


def build_trail_enum_items():
    from ..ui import register_nodetree

    register_nodetree(
        "trail_emitters",
        [],
        "trail_emitters",
        "trail_emitters_index",
        on_remove=lambda _context, obj, item: remove_trail_source_resources(obj, item),
    )


def _on_source_obj_update(self, _context):
    if self.obj is None:
        return
    if self.layer_uid:
        return
    import uuid

    self.layer_uid = uuid.uuid4().hex[:8]
    owner = self.id_data
    if owner is not None:
        ensure_trail_source_resources(owner, self)


class NexusTrailEmitterItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Emitter",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["NX_EMITTER"]),
        update=_on_source_obj_update,
    )
    enabled: BoolProperty(name="Enabled", default=True)
    source_name: StringProperty(name="Name", default="Trail Source")
    layer_uid: StringProperty(name="", default="", options={"HIDDEN"})

    trail_tab: EnumProperty(
        name="Section",
        description="Trail source settings section",
        items=_TRAIL_TAB_ITEMS,
        default=0,
    )

    trail_color_mode: EnumProperty(
        name="Color Mode",
        description="How trail colour is determined",
        items=_COLOR_MODE_ITEMS,
        default="STANDARD",
    )
    trail_color: FloatVectorProperty(
        name="Color",
        description="Trail colour",
        subtype="COLOR",
        size=4,
        default=srgb_to_linear(XP_COLOR_MODS_BLUE),
        min=0.0,
        max=1.0,
    )

    trail_length_mode: EnumProperty(
        name="Length Mode",
        description="How trail length is measured",
        items=_LENGTH_MODE_ITEMS,
        default="TIME",
    )
    trail_algorithm: EnumProperty(
        name="Connections",
        description="How trail segments are constructed from particles",
        items=_ALGORITHM_ITEMS,
        default="NO_CONNECTIONS",
    )
    trail_segment_length: IntProperty(
        name="Segment Length",
        description="Length of each segment (1 = two adjacent particles linked)",
        default=1,
        min=1,
    )
    trail_gap_length: IntProperty(
        name="Gap Length",
        description="Length of the gap between segments",
        default=1,
        min=1,
    )
    trail_multiple_mode: EnumProperty(
        name="Mode",
        description="How particles are partitioned into splines",
        items=_MULTIPLE_MODE_ITEMS,
        default="ALTERNATING",
    )
    trail_sequences: IntProperty(
        name="Sequences",
        description="Number of interleaved splines (Alternating mode)",
        default=1,
        min=1,
    )
    trail_sequence_length: IntProperty(
        name="Length",
        description="Number of particles per spline (Sequential mode)",
        default=1,
        min=1,
    )
    trail_max_connections: IntProperty(
        name="Max Connections",
        description="Maximum number of outgoing links per particle (Nearest Index)",
        default=1,
        min=1,
    )
    trail_skip_particles: IntProperty(
        name="Skip Particles",
        description="Skip every (Skip Particles + 1)-th particle's outgoing links (Nearest Index)",
        default=0,
        min=0,
    )
    trail_destination_groups: EnumProperty(
        name="Destination Groups",
        description="Which particle groups can be connection targets",
        items=_DESTINATION_GROUPS_ITEMS,
        default="USE_ALL",
    )
    trail_group_ref: PointerProperty(
        name="Group",
        description="Target group for Specific / All Except Specific modes",
        type=bpy.types.Object,
        poll=_trail_poll_group,
    )
    trail_min_distance: FloatProperty(
        name="Min Distance",
        description="Particles closer than this are not connected (Nearest Distance)",
        subtype="DISTANCE",
        default=0.0,
        min=0.0,
        soft_max=10.0,
    )
    trail_max_distance: FloatProperty(
        name="Max Distance",
        description="Particles farther apart than this are not connected (Nearest Distance)",
        subtype="DISTANCE",
        default=0.1,
        min=0.0,
        soft_max=10.0,
    )
    trail_max_number: IntProperty(
        name="Max Number",
        description="Maximum number of connections per particle (0 = uncapped) (Nearest Distance)",
        default=0,
        min=0,
        max=64,
    )
    trail_cluster_distance: FloatProperty(
        name="Cluster Distance",
        description="Particles within this distance of one another share a cluster (Cluster)",
        subtype="DISTANCE",
        default=0.1,
        min=0.0,
        soft_max=10.0,
    )
    trail_min_particles_in_cluster: IntProperty(
        name="Min Particles in Cluster",
        description="Minimum cluster size required to emit links (Cluster)",
        default=2,
        min=2,
        soft_max=64,
    )
    trail_full_scene: BoolProperty(
        name="Full Scene",
        description="Trail extends for the full scene duration",
        default=True,
    )
    trail_frame_sampling: IntProperty(
        name="Frame Sampling",
        description="Record a trail point every N frames",
        default=1,
        min=1,
        soft_max=10,
    )
    trail_length: nexus_time_property(
        "trail_length",
        name="Length",
        description="Trail length in time",
        default=30.0,
        soft_max=600.0,
        collection_path="trail_emitters",
    )
    trail_length_distance: FloatProperty(
        name="Length",
        description="Trail length in distance",
        subtype="DISTANCE",
        default=1.0,
        min=0.0,
        soft_max=10.0,
    )
    trail_variation: FloatProperty(
        name="Variation",
        description="Random variation in trail length",
        subtype="PERCENTAGE",
        default=0.0,
        min=0.0,
        max=100.0,
    )

    trail_freeze_mode: EnumProperty(
        name="Freeze Mode",
        description="What happens when the trail reaches its length limit",
        items=_FREEZE_MODE_ITEMS,
        default=0,
    )
    trail_freeze_movement: BoolProperty(
        name="Freeze Movement",
        description="Freeze particle movement when frozen",
        default=False,
    )
    trail_freeze_scale: BoolProperty(
        name="Freeze Scale",
        description="Freeze particle scale when frozen",
        default=False,
    )

    trail_no_thickness_color_data: BoolProperty(
        name="No Thickness/Color Data",
        description="Omit thickness and colour data from the trail",
        default=False,
    )

    trail_thickness_mode: EnumProperty(
        name="Thickness Mode",
        description="How trail thickness is determined",
        items=_THICKNESS_MODE_ITEMS,
        default=0,
    )
    trail_thickness_value: FloatProperty(
        name="Thickness",
        description="Uniform trail thickness value",
        subtype="DISTANCE",
        default=0.01,
        min=0.0,
        soft_max=0.1,
    )
    trail_thickness_variation: FloatProperty(
        name="Thickness Variation",
        description="Random variation in trail thickness",
        subtype="DISTANCE",
        default=0.0,
        min=0.0,
        soft_max=0.1,
    )
    trail_thickness_spline_max: FloatProperty(
        name="Spline Max",
        description="Maximum thickness when sampling from spline",
        subtype="DISTANCE",
        default=0.01,
        min=0.0,
        soft_max=0.1,
    )
    trail_thickness_spline_time: nexus_time_property(
        "trail_thickness_spline_time",
        name="Spline Time",
        description="Time over which the thickness spline is sampled",
        default=30.0,
        min=1.0,
        soft_max=600.0,
        collection_path="trail_emitters",
    )

    trail_vertex_color_mode: EnumProperty(
        name="Trail Color Mode",
        description="How per-point trail colour is sourced",
        items=_TRAIL_COLOR_MODE_ITEMS,
        default="PARTICLE",
    )

    trail_spline_type: EnumProperty(
        name="Spline Type",
        description="Type of spline to generate",
        items=_SPLINE_TYPE_ITEMS,
        default="LINEAR",
    )
    trail_spline_close: BoolProperty(
        name="Close Spline",
        description="Close the generated spline",
        default=False,
    )
    trail_spline_intermediate: EnumProperty(
        name="Intermediate Points",
        description="How intermediate points are inserted",
        items=_SPLINE_INTERMEDIATE_ITEMS,
        default="NONE",
    )
    trail_spline_number: IntProperty(
        name="Number",
        description="Number of intermediate points per segment",
        default=0,
        min=0,
        soft_max=20,
    )
    trail_spline_angle: FloatProperty(
        name="Angle",
        description="Angle threshold for adaptive intermediate points",
        subtype="ANGLE",
        default=radians(15.0),
        min=0.0,
        max=pi,
    )
    trail_spline_use_max_length: BoolProperty(
        name="Use Max Length",
        description="Limit the maximum length of generated splines",
        default=False,
    )
    trail_spline_max_length: FloatProperty(
        name="Max Length",
        description="Maximum length of generated splines",
        subtype="DISTANCE",
        default=1.0,
        min=0.001,
        soft_max=10.0,
    )


def _draw_general_tab(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "trail_color_mode")
    if item.trail_color_mode == "STANDARD":
        col.prop(item, "trail_color")
    elif item.trail_color_mode == "GRADIENT" and item.layer_uid:
        from ..utils.gradient import NexusGradient, resolve_gradient_slot_name

        slot = resolve_gradient_slot_name(TRAIL_COLOR_GRADIENT_SPEC, item.layer_uid)
        if slot:
            NexusGradient(item.id_data, slot).draw_ui(col, "Color")

    col.separator(type="LINE")

    col.prop(item, "trail_length_mode")
    if item.trail_length_mode == "TIME":
        col.prop(item, "trail_full_scene")
        if not item.trail_full_scene:
            draw_time_prop(col, item, "trail_length")
    else:
        col.prop(item, "trail_length_distance")

    col.prop(item, "trail_frame_sampling")
    col.prop(item, "trail_variation")

    col.separator(type="LINE")

    col.prop(item, "trail_algorithm")
    if item.trail_algorithm == "SEGMENTED_SEQUENCE":
        col.prop(item, "trail_segment_length")
        col.prop(item, "trail_gap_length")
    elif item.trail_algorithm == "MULTIPLE_SEQUENCE":
        col.prop(item, "trail_multiple_mode")
        if item.trail_multiple_mode == "ALTERNATING":
            col.prop(item, "trail_sequences")
        else:
            col.prop(item, "trail_sequence_length")
    elif item.trail_algorithm == "NEAREST_INDEX":
        col.prop(item, "trail_max_connections")
        col.prop(item, "trail_skip_particles")
    elif item.trail_algorithm == "NEAREST_DISTANCE":
        col.prop(item, "trail_min_distance")
        col.prop(item, "trail_max_distance")
        col.prop(item, "trail_max_number")
    elif item.trail_algorithm == "CLUSTER":
        col.prop(item, "trail_cluster_distance")
        col.prop(item, "trail_min_particles_in_cluster")

    if item.trail_algorithm in {"NEAREST_INDEX", "NEAREST_DISTANCE", "CLUSTER"}:
        col.prop(item, "trail_destination_groups")
        if item.trail_destination_groups in {"SPECIFIC_GROUP", "ALL_EXCEPT_SPECIFIC_GROUP"}:
            col.prop(item, "trail_group_ref")

    col.separator(type="LINE")

    col.prop(item, "trail_freeze_mode")
    if item.trail_freeze_mode != "NONE":
        col.prop(item, "trail_freeze_movement")
        col.prop(item, "trail_freeze_scale")


def _draw_thickness_tab(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.prop(item, "trail_no_thickness_color_data")

    sub = col.column()
    sub.enabled = not item.trail_no_thickness_color_data
    sub.prop(item, "trail_thickness_mode")

    mode = item.trail_thickness_mode
    if mode == "VALUE":
        sub.prop(item, "trail_thickness_value")
        sub.prop(item, "trail_thickness_variation")
    elif mode == "SPLINE":
        if item.layer_uid:
            from ..utils.curve import NexusCurve, resolve_curve_slot_name

            slot = resolve_curve_slot_name(TRAIL_THICKNESS_SPLINE_SPEC, item.layer_uid)
            if slot:
                NexusCurve(item.id_data, slot).draw_ui(sub, "Thickness")
        sub.prop(item, "trail_thickness_spline_max")
        draw_time_prop(sub, item, "trail_thickness_spline_time")

    col.separator(type="LINE")
    color_row = col.column()
    color_row.enabled = not item.trail_no_thickness_color_data
    color_row.prop(item, "trail_vertex_color_mode")


def _draw_spline_tab(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.prop(item, "trail_spline_type")
    col.prop(item, "trail_spline_close")
    col.prop(item, "trail_spline_intermediate")

    inter = item.trail_spline_intermediate
    if inter == "UNIFORM":
        col.prop(item, "trail_spline_number")
    elif inter == "ADAPTIVE":
        col.prop(item, "trail_spline_angle")

    col.separator(type="LINE")
    col.prop(item, "trail_spline_use_max_length")
    if item.trail_spline_use_max_length:
        col.prop(item, "trail_spline_max_length")


def draw_trail_emitter_item_settings(layout, item):
    if item.obj is None:
        return

    layout.separator(factor=0.5)
    row = layout.row(align=True)
    row.use_property_split = False
    row.prop(item, "trail_tab", expand=True)

    tab = item.trail_tab
    if tab == "GENERAL":
        _draw_general_tab(layout, item)
    elif tab == "THICKNESS":
        _draw_thickness_tab(layout, item)
    elif tab == "SPLINE":
        _draw_spline_tab(layout, item)


_TRAIL_EMITTERS = NodeTreeDef(
    "Emitters",
    item_type=NexusTrailEmitterItem,
    allowed_types=["NX_EMITTER"],
)

NX_TRAIL_UI_CONFIG = {
    **_TRAIL_EMITTERS.ui_config("trail_emitters"),
}


def get_trail_ui_config():
    config = {}
    for k, v in NX_TRAIL_UI_CONFIG.items():
        config[k] = dict(v)
    config["trail_emitters"]["draw_item_settings"] = draw_trail_emitter_item_settings
    return config


_trail_emitter_props = _TRAIL_EMITTERS.properties("trail_emitters")

SPEC = ModifierPropertySpec(
    modifier_type="NX_TRAIL",
    item_classes=(NexusTrailEmitterItem,),
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="trail_display",
            prop=EnumProperty(
                name="Display",
                description="How trails are displayed in the viewport",
                items=_DISPLAY_ITEMS,
                default="LINES",
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="trail_emitters",
            prop=_trail_emitter_props["trail_emitters"],
            preset=False,
            no_sync=True,
        ),
        PropertyDescriptor(
            name="trail_emitters_index",
            prop=_trail_emitter_props["trail_emitters_index"],
            preset=False,
            no_sync=True,
        ),
        *(
            (
                PropertyDescriptor(
                    name="trail_emitters_drop_target",
                    prop=_trail_emitter_props["trail_emitters_drop_target"],
                    preset=False,
                    no_sync=True,
                ),
            )
            if "trail_emitters_drop_target" in _trail_emitter_props
            else ()
        ),
    ),
    enum_builders=(build_trail_enum_items,),
)


register_collection_cleanup(
    "NX_TRAIL",
    CollectionPresetSpec(
        collection_attr="trail_emitters",
        curve_specs=TRAIL_CURVE_SPECS,
        gradient_specs=TRAIL_GRADIENT_SPECS,
        suffix_attr="layer_uid",
    ),
)
