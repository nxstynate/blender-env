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

import math

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.cache_spec import (
    CacheKind,
    CacheSpec,
)
from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_cleanup
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
)
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform
from ..ui import NodeTreeDef, combine_nodetree_sync, make_allowed_types_poll
from ..utils.curve import make_layer_curve_callbacks

_FOLLOW_GEO_MODE_ITEMS = []
_FOLLOW_GEO_SPLINE_DIRECTION_ITEMS = []
_FOLLOW_GEO_SPLINE_MODE_ITEMS = []
_FOLLOW_GEO_SPLINE_RELEASE_MODE_ITEMS = []
_FOLLOW_GEO_ON_RELEASE_ITEMS = []
_FOLLOW_GEO_SURFACE_RELEASE_MODE_ITEMS = []
_FOLLOW_GEO_TIME_MODE_ITEMS = []
_FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_ITEMS = []
_FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_ITEMS = []
_FOLLOW_GEO_EXTENDED_DATA_ITEMS = []


_FOLLOW_GEO_TAB_ITEMS = [
    ("CONNECTION", "Connection", "Connection settings", 0),
    ("RELEASE", "Release", "Release settings", 1),
]

_FOLLOW_GEO_SPLINE_TAB_ITEMS = [
    ("CONNECTION", "Connection", "Connection settings", 0),
    ("OFFSET", "Extended Data", "Offset and twist settings", 1),
    ("RELEASE", "Release", "Release settings", 2),
    ("SPLINE_DATA", "Spline Data", "Multi segment and starting mode settings", 3),
]

EXTENDED_DATA_DEFS = {
    "OFFSET": {
        "name": "Offset",
        "description": "Offset distance from spline",
        "icon_name": "nx_follow_geo_layer_offset",
    },
    "TWIST": {
        "name": "Twist",
        "description": "Twist around the spline",
        "icon_name": "nx_follow_geo_layer_twist",
    },
}


def _get_offset_curve_specs():
    from ..utils.curve import CurveSpec

    return [
        CurveSpec(
            "follow_geo_offset_spline",
            "Offset Along Length",
            [(0.0, 1.0), (1.0, 1.0)],
            theron_ids=("ID_NX_FS_SPLINE_OFFSET_SPLINE",),
            slot_suffix_attr="layer_uid",
        )
    ]


def _get_twist_curve_specs():
    from ..utils.curve import CurveSpec

    return [
        CurveSpec(
            "follow_geo_twist_spline",
            "Radius Along Length",
            [(0.0, 1.0), (1.0, 1.0)],
            theron_ids=("ID_NX_FS_SPLINE_TWIST_SPLINE",),
            slot_suffix_attr="layer_uid",
        )
    ]


_on_extended_add, _on_extended_remove = make_layer_curve_callbacks(
    {
        "OFFSET": _get_offset_curve_specs,
        "TWIST": _get_twist_curve_specs,
    }
)


def build_follow_geo_enum_items():
    global _FOLLOW_GEO_MODE_ITEMS
    global _FOLLOW_GEO_SPLINE_DIRECTION_ITEMS
    global _FOLLOW_GEO_SPLINE_MODE_ITEMS
    global _FOLLOW_GEO_SPLINE_RELEASE_MODE_ITEMS
    global _FOLLOW_GEO_ON_RELEASE_ITEMS
    global _FOLLOW_GEO_SURFACE_RELEASE_MODE_ITEMS
    global _FOLLOW_GEO_TIME_MODE_ITEMS
    global _FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_ITEMS
    global _FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_ITEMS

    from ..icons import get_icon

    _FOLLOW_GEO_MODE_ITEMS = [
        (
            "SURFACE",
            "Surface",
            "Follow geometry surface",
            get_icon("nx_follow_geo_mode_surface"),
            0,
        ),
        (
            "EDGE",
            "Edge",
            "Follow splines and edges",
            get_icon("nx_follow_geo_mode_edge"),
            1,
        ),
    ]

    _FOLLOW_GEO_SPLINE_DIRECTION_ITEMS = [
        (
            "FORWARDS",
            "Forwards",
            "Move forwards along spline",
            get_icon("nx_follow_geo_spline_direction_forward"),
            0,
        ),
        (
            "BACKWARDS",
            "Backwards",
            "Move backwards along spline",
            get_icon("nx_follow_geo_spline_direction_backwards"),
            1,
        ),
    ]

    _FOLLOW_GEO_SPLINE_MODE_ITEMS = [
        (
            "GUIDE",
            "Guide",
            "Spline acts as a guide",
            get_icon("nx_follow_geo_spline_mode_guide"),
            0,
        ),
        (
            "FORCE",
            "Force",
            "Spline acts as a force",
            get_icon("nx_follow_geo_spline_mode_force"),
            1,
        ),
    ]

    _FOLLOW_GEO_SPLINE_RELEASE_MODE_ITEMS = [
        (
            "SPLINE_END",
            "Spline End",
            "Release at end of spline",
            get_icon("nx_follow_geo_spline_release_spline_end"),
            0,
        ),
        (
            "FALLOFF",
            "Falloff",
            "Release by falloff",
            get_icon("nx_follow_geo_spline_release_falloff"),
            1,
        ),
        (
            "TIME",
            "Time",
            "Release after a set time",
            get_icon("nx_follow_geo_spline_release_time"),
            2,
        ),
        (
            "SELECTION",
            "Selection",
            "Release by selection",
            get_icon("nx_follow_geo_spline_release_selection"),
            3,
        ),
    ]

    _FOLLOW_GEO_ON_RELEASE_ITEMS = [
        (
            "DO_NOTHING",
            "Do Nothing",
            "Particle continues normally after release",
            get_icon("nx_follow_geo_on_release_do_nothing"),
            0,
        ),
        (
            "LOOP",
            "Loop",
            "Particle loops back to spline start",
            get_icon("nx_follow_geo_on_release_loop"),
            1,
        ),
        (
            "REVERSE",
            "Reverse",
            "Particle reverses direction along spline",
            get_icon("nx_follow_geo_on_release_reverse"),
            2,
        ),
        (
            "KILL",
            "Kill",
            "Particle is killed on release",
            get_icon("nx_follow_geo_on_release_kill"),
            3,
        ),
        (
            "CHANGE_GROUP",
            "Change Group",
            "Particle changes group on release",
            get_icon("nx_follow_geo_on_release_change_group"),
            4,
        ),
    ]

    _FOLLOW_GEO_SURFACE_RELEASE_MODE_ITEMS = [
        (
            "NONE",
            "None",
            "Never release",
            get_icon("nx_follow_geo_on_release_do_nothing"),
            0,
        ),
        # ("SELECTION", "Selection", "Release by selection",
        #     get_icon("nx_follow_geo_spline_release_selection"), 1),
        # ("FALLOFF", "Falloff", "Release by falloff",
        #     get_icon("nx_follow_geo_spline_release_falloff"), 2),
        (
            "TIME",
            "Time",
            "Release after a set time",
            get_icon("nx_follow_geo_spline_release_time"),
            3,
        ),
    ]

    _FOLLOW_GEO_TIME_MODE_ITEMS = [
        (
            "PARTICLE",
            "Particle Age",
            "Time based on particle age",
            get_icon("nx_follow_geo_time_mode_particle"),
            0,
        ),
        (
            "FRAME",
            "Frame Time",
            "Time based on frame count",
            get_icon("nx_follow_geo_spline_release_time"),
            1,
        ),
    ]

    _FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_ITEMS = [
        ("FLAT", "Flat", "No falloff", get_icon("nx_falloff_type_flat"), 0),
        ("LINEAR", "Linear", "Linear falloff", get_icon("nx_falloff_type_linear"), 1),
        ("QUADRATIC", "Quadratic", "Quadratic falloff", get_icon("nx_falloff_type_quadratic"), 2),
        ("CUBIC", "Cubic", "Cubic falloff", get_icon("nx_falloff_type_cubic"), 3),
    ]

    _FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_ITEMS = [
        ("FLAT", "Flat", "No falloff", get_icon("nx_falloff_type_flat"), 0),
        ("LINEAR", "Linear", "Linear falloff", get_icon("nx_falloff_type_linear"), 1),
        ("QUADRATIC", "Quadratic", "Quadratic falloff", get_icon("nx_falloff_type_quadratic"), 2),
        ("CUBIC", "Cubic", "Cubic falloff", get_icon("nx_falloff_type_cubic"), 3),
    ]


def build_follow_geo_extended_enum_items():
    global _FOLLOW_GEO_EXTENDED_DATA_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _FOLLOW_GEO_EXTENDED_DATA_ITEMS = []
    for idx, (type_id, layer_def) in enumerate(EXTENDED_DATA_DEFS.items()):
        icon_id = get_icon(layer_def["icon_name"])
        if icon_id and icon_id > 0:
            _FOLLOW_GEO_EXTENDED_DATA_ITEMS.append(
                (type_id, layer_def["name"], layer_def["description"], icon_id, idx)
            )
        else:
            _FOLLOW_GEO_EXTENDED_DATA_ITEMS.append(
                (type_id, layer_def["name"], layer_def["description"], "NONE", idx)
            )

    register_nodetree(
        "follow_geo_extended",
        _FOLLOW_GEO_EXTENDED_DATA_ITEMS,
        "follow_geo_extended",
        "follow_geo_extended_index",
        on_add=_on_extended_add,
        on_remove=_on_extended_remove,
    )


def _get_follow_geo_mode_items(self, context):
    return _FOLLOW_GEO_MODE_ITEMS


def _get_follow_geo_spline_direction_items(self, context):
    return _FOLLOW_GEO_SPLINE_DIRECTION_ITEMS


def _get_follow_geo_spline_mode_items(self, context):
    return _FOLLOW_GEO_SPLINE_MODE_ITEMS


def _get_follow_geo_spline_release_mode_items(self, context):
    return _FOLLOW_GEO_SPLINE_RELEASE_MODE_ITEMS


def _get_follow_geo_on_release_items(self, context):
    return _FOLLOW_GEO_ON_RELEASE_ITEMS


def _get_follow_geo_surface_release_mode_items(self, context):
    return _FOLLOW_GEO_SURFACE_RELEASE_MODE_ITEMS


def _get_follow_geo_attract_falloff_type_items(self, context):
    return _FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_ITEMS


def _get_follow_geo_follow_falloff_type_items(self, context):
    return _FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_ITEMS


def _get_extended_data_items(self, context):
    return _FOLLOW_GEO_EXTENDED_DATA_ITEMS


def _get_follow_geo_time_mode_items(self, context):
    return _FOLLOW_GEO_TIME_MODE_ITEMS


class NexusFollowGeoExtendedItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="")
    enabled: BoolProperty(name="Enabled", default=True)
    item_type: EnumProperty(
        name="Type",
        items=_get_extended_data_items,
        default=0,
    )
    layer_uid: StringProperty(name="", default="")


def _on_follow_geo_obj_update(self, context):
    """Auto-add a default Offset extended data layer when a CURVE is assigned."""
    if self.obj is not None and self.obj.type == "CURVE" and len(self.follow_geo_extended) == 0:
        obj = self.id_data
        if obj is None or not isinstance(obj, bpy.types.Object):
            return

        item = self.follow_geo_extended.add()
        item.item_type = "OFFSET"

        from ..utils import generate_unique_name

        existing = [i.name for i in self.follow_geo_extended if i.name]
        item.name = generate_unique_name("Offset", existing)

        _on_extended_add(context, obj, item)
        self.follow_geo_extended_index = 0


class NexusFollowGeoItem(bpy.types.PropertyGroup):
    preset_uid: StringProperty(name="", default="", options={"HIDDEN"})

    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
        update=_on_follow_geo_obj_update,
    )
    enabled: BoolProperty(name="Enabled", default=True)

    follow_geo_mode: EnumProperty(
        name="Mode",
        description="Follow geometry mode",
        items=_get_follow_geo_mode_items,
    )
    follow_geo_tab: EnumProperty(
        name="Section",
        description="Follow geometry settings section",
        items=_FOLLOW_GEO_TAB_ITEMS,
    )
    follow_geo_spline_tab: EnumProperty(
        name="Section",
        description="Spline settings section",
        items=_FOLLOW_GEO_SPLINE_TAB_ITEMS,
    )
    follow_geo_pull: FloatProperty(
        name="Pull",
        description="Pull strength towards surface",
        default=200.0,
        min=0.0,
        soft_max=100.0,
        max=1000.0,
        subtype="PERCENTAGE",
    )
    follow_geo_pull_var: FloatProperty(
        name="Variation",
        description="Random variation in pull strength",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_push: FloatProperty(
        name="Push",
        description="Push strength away from surface",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        max=1000.0,
        subtype="PERCENTAGE",
    )
    follow_geo_push_var: FloatProperty(
        name="Variation",
        description="Random variation in push strength",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_offset: FloatProperty(
        name="Offset",
        description="Distance offset from surface",
        default=0.0,
        unit="LENGTH",
    )
    follow_geo_offset_var: FloatProperty(
        name="Variation",
        description="Random variation in offset distance",
        default=0.0,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_distance: FloatProperty(
        name="Distance",
        description="Maximum influence distance",
        default=0.1,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_friction: FloatProperty(
        name="Friction",
        description="Surface friction applied to particles",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_fov: FloatProperty(
        name="FOV",
        description="Field of view angle for surface detection",
        default=math.radians(270),
        min=0.0,
        max=math.radians(360),
        subtype="ANGLE",
    )
    follow_geo_edge: FloatProperty(
        name="Edge",
        description="Edge following strength",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        max=1000.0,
        subtype="PERCENTAGE",
    )
    follow_geo_smoothing: FloatProperty(
        name="Smoothing",
        description="Edge smoothing amount",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        max=1000.0,
        subtype="PERCENTAGE",
    )
    # -- Spline connection --
    follow_geo_spline_direction: EnumProperty(
        name="Direction",
        description="Direction of travel along spline",
        items=_get_follow_geo_spline_direction_items,
    )
    follow_geo_spline_mode: EnumProperty(
        name="Mode",
        description="How the spline affects particles",
        items=_get_follow_geo_spline_mode_items,
    )
    follow_geo_activate_range: FloatProperty(
        name="Activate Range",
        description="Distance at which spline begins to affect particles",
        default=2.0,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_strength: FloatProperty(
        name="Strength",
        description="Overall spline influence strength",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_attract_strength_pct: FloatProperty(
        name="Attract Strength",
        description="Percentage strength of attraction to spline",
        default=10.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_attract_strength: FloatProperty(
        name="Attract Strength",
        description="Distance-based attraction strength",
        default=0.0,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_attract_variation: FloatProperty(
        name="Variation",
        description="Random variation in attraction strength",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_attract_falloff: FloatProperty(
        name="Attract Falloff",
        description="Falloff of attraction over distance",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_attract_falloff_type: EnumProperty(
        name="Attract Falloff Type",
        description="Type of falloff curve for attraction",
        items=_get_follow_geo_attract_falloff_type_items,
        default=3,
    )
    follow_geo_follow_strength_pct: FloatProperty(
        name="Follow Strength",
        description="Percentage strength of following along spline",
        default=40.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_follow_strength: FloatProperty(
        name="Follow Strength",
        description="Distance-based following strength",
        default=0.0,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_follow_variation: FloatProperty(
        name="Variation",
        description="Random variation in following strength",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_follow_falloff: FloatProperty(
        name="Follow Falloff",
        description="Falloff of following over distance",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_follow_falloff_type: EnumProperty(
        name="Follow Falloff Type",
        description="Type of falloff curve for following",
        items=_get_follow_geo_follow_falloff_type_items,
        default=3,
    )
    follow_geo_align: FloatProperty(
        name="Align",
        description="Alignment of particle direction to spline tangent",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    # TODO: Rail object sync not yet implemented in Theron
    follow_geo_rail_object: PointerProperty(
        name="Rail",
        description="Object used as a rail spline",
        type=bpy.types.Object,
    )
    follow_geo_rail_segment_index: IntProperty(
        name="Segment Index",
        description="Index of the rail spline segment",
        default=1,
        min=1,
    )
    # -- Spline data --
    follow_geo_multi_segment: EnumProperty(
        name="Multi Segment",
        description="How to handle multiple spline segments",
        items=[
            ("ANY", "Any Segment", "Use any segment", 0),
            ("SPECIFIC", "Specific Segment", "Use a specific segment", 1),
            ("SEQUENCE", "Segments In Sequence", "Follow segments in sequence", 2),
            ("NEAREST", "Nearest Segment", "Use nearest segment", 3),
        ],
        default="ANY",
    )
    follow_geo_segment_index: IntProperty(
        name="Segment",
        description="Specific segment index to follow",
        default=1,
        min=1,
    )
    follow_geo_starting_mode: EnumProperty(
        name="Starting Mode",
        description="How to determine the starting point on the spline",
        items=[
            ("NEAREST_POINT", "Nearest Point", "Start at the nearest point on spline", 0),
            ("NEAREST_VERTEX", "Nearest Vertex", "Start at the nearest vertex", 1),
            ("SPECIFIC_VERTEX", "Specific Vertex", "Start at a specific vertex index", 2),
            ("POSITION", "Position Along Spline", "Start at a percentage along the spline", 3),
        ],
        default="NEAREST_POINT",
    )
    follow_geo_start_position: FloatProperty(
        name="Position",
        description="Starting position along the spline as a percentage",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_start_position_var: FloatProperty(
        name="Variation",
        description="Random variation in starting position",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_start_specific_index: IntProperty(
        name="Index",
        description="Specific vertex index to start from",
        default=0,
        min=0,
    )
    follow_geo_offset_value: FloatProperty(
        name="Offset Value",
        description="Offset distance from spline",
        default=0.2,
        min=0.0,
        unit="LENGTH",
    )
    follow_geo_offset_blend: FloatProperty(
        name="Offset Blend",
        description="Blend between X and Y offset",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_twist_direction: EnumProperty(
        name="Twist Direction",
        description="Direction of twist around the spline",
        items=[
            ("CLOCKWISE", "Clockwise", "Twist clockwise", 0),
            ("ANTI_CLOCKWISE", "Anti-clockwise", "Twist anti-clockwise", 1),
        ],
        default="CLOCKWISE",
    )
    follow_geo_twists: IntProperty(
        name="Twists",
        description="Number of twist loops around the spline",
        default=0,
        min=0,
        soft_max=100,
    )
    follow_geo_twist_radius: FloatProperty(
        name="Twist Radius",
        description="Radius of the twist spiral",
        default=0.1,
        min=0.0,
        unit="LENGTH",
    )
    # -- Extended data layers --
    follow_geo_extended: CollectionProperty(type=NexusFollowGeoExtendedItem)
    follow_geo_extended_index: IntProperty(
        name="Active Extended Layer Index",
        default=0,
        min=0,
    )
    # -- Surface release --
    follow_geo_surface_release_mode: EnumProperty(
        name="Release Mode",
        description="Condition for releasing particles from surface",
        items=_get_follow_geo_surface_release_mode_items,
    )
    follow_geo_surface_release_amount: FloatProperty(
        name="Amount",
        description="Release amount percentage",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_surface_time_mode: EnumProperty(
        name="Time Mode",
        description="How release time is measured for surface mode",
        items=_get_follow_geo_time_mode_items,
    )
    follow_geo_surface_release_time: nexus_time_property(
        "follow_geo_surface_release_time",
        name="Release Time",
        description="Time before particle is released from surface",
        default=30.0,
        collection_path="follow_geo_objects",
    )
    follow_geo_surface_release_time_var: nexus_time_property(
        "follow_geo_surface_release_time_var",
        name="Variation",
        description="Random variation in release time",
        default=0.0,
        collection_path="follow_geo_objects",
    )
    # -- Spline release --
    follow_geo_spline_release_mode: EnumProperty(
        name="Release Mode",
        description="Condition for releasing particles from spline",
        items=_get_follow_geo_spline_release_mode_items,
    )
    follow_geo_on_release: EnumProperty(
        name="On Release",
        description="Action to take when particle is released",
        items=_get_follow_geo_on_release_items,
    )
    follow_geo_release_distance: FloatProperty(
        name="Distance",
        description="Release distance as percentage along spline",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    follow_geo_spline_time_mode: EnumProperty(
        name="Time Mode",
        description="How release time is measured for spline mode",
        items=_get_follow_geo_time_mode_items,
    )
    follow_geo_spline_release_time: nexus_time_property(
        "follow_geo_spline_release_time",
        name="Release Time",
        description="Time before particle is released from spline",
        default=0.0,
        collection_path="follow_geo_objects",
    )
    follow_geo_spline_release_time_var: nexus_time_property(
        "follow_geo_spline_release_time_var",
        name="Variation",
        description="Random variation in release time",
        default=0.0,
        collection_path="follow_geo_objects",
    )


_FOLLOW_GEO_MODE_MAP = {
    "SURFACE": "ID_NX_FS_MODE_SURFACE",
    "EDGE": "ID_NX_FS_MODE_EDGE",
}

_FOLLOW_GEO_SPLINE_DIR_MAP = {
    "FORWARDS": "ID_NX_FS_SPLINE_MOVE_DIRECTION_FORWARDS",
    "BACKWARDS": "ID_NX_FS_SPLINE_MOVE_DIRECTION_BACKWARDS",
}

_FOLLOW_GEO_SPLINE_MODE_MAP = {
    "GUIDE": "ID_NX_FS_SPLINE_MOVE_MODE_GUIDE",
    "FORCE": "ID_NX_FS_SPLINE_MOVE_MODE_FORCE",
}

_FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_MAP = {
    "FLAT": "ID_NX_FS_SPLINE_ATTRACT_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_NX_FS_SPLINE_ATTRACT_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_NX_FS_SPLINE_ATTRACT_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_NX_FS_SPLINE_ATTRACT_FALLOFF_TYPE_CUBIC",
}

_FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_MAP = {
    "FLAT": "ID_NX_FS_SPLINE_FOLLOW_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_NX_FS_SPLINE_FOLLOW_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_NX_FS_SPLINE_FOLLOW_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_NX_FS_SPLINE_FOLLOW_FALLOFF_TYPE_CUBIC",
}

_FOLLOW_GEO_MULTI_SEGMENT_MAP = {
    "ANY": "ID_NX_FS_SPLINE_MUTLI_MODE_ANY",
    "SPECIFIC": "ID_NX_FS_SPLINE_MUTLI_MODE_SPECIFIC",
    "SEQUENCE": "ID_NX_FS_SPLINE_MUTLI_MODE_SEQUENCE",
    "NEAREST": "ID_NX_FS_SPLINE_MUTLI_MODE_CLOSEST",
}

_FOLLOW_GEO_STARTING_MODE_MAP = {
    "NEAREST_POINT": "ID_NX_FS_SPLINE_START_MODE_NEAREST_POINT",
    "NEAREST_VERTEX": "ID_NX_FS_SPLINE_START_MODE_NEAREST_VERTEX",
    "SPECIFIC_VERTEX": "ID_NX_FS_SPLINE_START_MODE_SPECIFIC_VERTEX",
    "POSITION": "ID_NX_FS_SPLINE_START_MODE_POSITION",
}

_FOLLOW_GEO_TWIST_DIR_MAP = {
    "CLOCKWISE": "ID_NX_FS_SPLINE_TWIST_DIRECTION_CLOCKWISE",
    "ANTI_CLOCKWISE": "ID_NX_FS_SPLINE_TWIST_DIRECTION_ANTICLOCKWISE",
}

_FOLLOW_GEO_SURFACE_RELEASE_MAP = {
    "NONE": "ID_NX_FS_SURFACE_RELEASE_MODE_NONE",
    "SELECTION": "ID_NX_FS_SURFACE_RELEASE_MODE_SELECTION",
    "FALLOFF": "ID_NX_FS_SURFACE_RELEASE_MODE_FIELD",
    "TIME": "ID_NX_FS_SURFACE_RELEASE_MODE_TIME",
}

_FOLLOW_GEO_SURFACE_TIME_MAP = {
    "PARTICLE": "ID_NX_FS_SURFACE_TIME_MODE_PARTICLE",
    "FRAME": "ID_NX_FS_SURFACE_TIME_MODE_FRAME",
}

_FOLLOW_GEO_SPLINE_RELEASE_MAP = {
    "SPLINE_END": "ID_NX_FS_SPLINE_RELEASE_MODE_END",
    "FALLOFF": "ID_NX_FS_SPLINE_RELEASE_MODE_FALLOFF",
    "TIME": "ID_NX_FS_SPLINE_RELEASE_MODE_TIME",
    "SELECTION": "ID_NX_FS_SPLINE_RELEASE_MODE_SELECTION",
}

_FOLLOW_GEO_ON_RELEASE_MAP = {
    "DO_NOTHING": "ID_NX_FS_SPLINE_RELEASE_MODE_DO_NOTHING",
    "LOOP": "ID_NX_FS_SPLINE_RELEASE_MODE_LOOP",
    "REVERSE": "ID_NX_FS_SPLINE_RELEASE_MODE_REVERSE",
    "KILL": "ID_NX_FS_SPLINE_RELEASE_MODE_KILL",
    "CHANGE_GROUP": "ID_NX_FS_SPLINE_RELEASE_MODE_CHANGE_GROUP",
}

_FOLLOW_GEO_SPLINE_TIME_MAP = {
    "PARTICLE": "ID_NX_FS_SPLINE_TIME_MODE_PARTICLE",
    "FRAME": "ID_NX_FS_SPLINE_TIME_MODE_FRAME",
}

_FOLLOW_GEO_EXTENDED_TYPE_IDS = {
    "OFFSET": "ID_NX_FS_SURFACE_ADD_OFFSET_CHOICE_OFFSET",
    "TWIST": "ID_NX_FS_SURFACE_ADD_OFFSET_CHOICE_TWIST",
}

_follow_geo_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

FOLLOW_GEO_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="follow_geo_objects",
    cache_dict=_follow_geo_poly_cache,
)

_follow_geo_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

FOLLOW_GEO_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="follow_geo_objects",
    cache_dict=_follow_geo_line_cache,
)

_follow_geo_object_links = make_cached_link_resolver(
    poly_spec=FOLLOW_GEO_POLY_SPEC,
    line_spec=FOLLOW_GEO_LINE_SPEC,
)

_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]

_FOLLOW_GEO_BASE_PARAM_SPECS = (
    SyncSpec.param("enum", "follow_geo_mode", "ID_NX_FS_MODE", enum_map=_FOLLOW_GEO_MODE_MAP),
    SyncSpec.param("float", "follow_geo_pull", "ID_NX_FS_PULL", scale=_pct),
    SyncSpec.param("float", "follow_geo_pull_var", "ID_NX_FS_PULL_VAR", scale=_pct),
    SyncSpec.param("float", "follow_geo_push", "ID_NX_FS_PUSH", scale=_pct),
    SyncSpec.param("float", "follow_geo_push_var", "ID_NX_FS_PUSH_VAR", scale=_pct),
    SyncSpec.param("float", "follow_geo_offset", "ID_NX_FS_OFFSET", scale=_unit),
    SyncSpec.param("float", "follow_geo_offset_var", "ID_NX_FS_OFFSET_VAR", scale=_unit),
    SyncSpec.param("float", "follow_geo_distance", "ID_NX_FS_DISTANCE", scale=_unit),
    SyncSpec.param("float", "follow_geo_friction", "ID_NX_FS_FRICTION", scale=_pct),
    SyncSpec.param("float", "follow_geo_fov", "ID_NX_FS_FOV"),
    SyncSpec.param("float", "follow_geo_edge", "ID_NX_FS_EDGES", scale=_pct),
    SyncSpec.param("float", "follow_geo_smoothing", "ID_NX_FS_EDGES_SMOOTH", scale=_pct),
    SyncSpec.param(
        "enum",
        "follow_geo_spline_direction",
        "ID_NX_FS_SPLINE_MOVE_DIRECTION",
        enum_map=_FOLLOW_GEO_SPLINE_DIR_MAP,
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_spline_mode",
        "ID_NX_FS_SPLINE_MOVE_MODE",
        enum_map=_FOLLOW_GEO_SPLINE_MODE_MAP,
    ),
    SyncSpec.param("float", "follow_geo_activate_range", "ID_NX_FS_SPLINE_DISTANCE", scale=_unit),
    SyncSpec.param(
        "float", "follow_geo_strength", "ID_NX_FS_SPLINE_ATTRACT_GUIDE_MIX", scale=_pct
    ),
    SyncSpec.param(
        "float",
        "follow_geo_attract_strength_pct",
        "ID_NX_FS_SPLINE_ATTRACT_STRENGTH_PERCENTAGE",
        scale=_pct,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_attract_strength",
        "ID_NX_FS_SPLINE_ATTRACT_STRENGTH",
        scale=_unit,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_attract_variation",
        "ID_NX_FS_SPLINE_ATTRACT_VARIATION",
        scale=_pct,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_attract_falloff",
        "ID_NX_FS_SPLINE_ATTRACT_ATTRACT_FALLOFF",
        scale=_pct,
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_attract_falloff_type",
        "ID_NX_FS_SPLINE_ATTRACT_FALLOFF_TYPE",
        enum_map=_FOLLOW_GEO_ATTRACT_FALLOFF_TYPE_MAP,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_follow_strength_pct",
        "ID_NX_FS_SPLINE_FOLLOW_STRENGTH_PERCENTAGE",
        scale=_pct,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_follow_strength",
        "ID_NX_FS_SPLINE_FOLLOW_STRENGTH",
        scale=_unit,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_follow_variation",
        "ID_NX_FS_SPLINE_FOLLOW_VARIATION",
        scale=_pct,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_follow_falloff",
        "ID_NX_FS_SPLINE_FOLLOW_ATTRACT_FALLOFF",
        scale=_pct,
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_follow_falloff_type",
        "ID_NX_FS_SPLINE_FOLLOW_FALLOFF_TYPE",
        enum_map=_FOLLOW_GEO_FOLLOW_FALLOFF_TYPE_MAP,
    ),
    SyncSpec.param("float", "follow_geo_align", "ID_NX_FS_SPLINE_ALIGN", scale=_pct),
    SyncSpec.param("int", "follow_geo_rail_segment_index", "ID_NX_FS_SPLINE_RAIL_MULTI_INDEX"),
    SyncSpec.param(
        "enum",
        "follow_geo_multi_segment",
        "ID_NX_FS_SPLINE_MUTLI_MODE",
        enum_map=_FOLLOW_GEO_MULTI_SEGMENT_MAP,
    ),
    SyncSpec.param("int", "follow_geo_segment_index", "ID_NX_FS_SPLINE_MUTLI_SEG_INDEX"),
    SyncSpec.param(
        "enum",
        "follow_geo_starting_mode",
        "ID_NX_FS_SPLINE_MUTLI_START_MODE",
        enum_map=_FOLLOW_GEO_STARTING_MODE_MAP,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_start_position",
        "ID_NX_FS_SPLINE_START_MODE_POSITION_FLOAT",
        scale=_pct,
    ),
    SyncSpec.param(
        "float",
        "follow_geo_start_position_var",
        "ID_NX_FS_SPLINE_START_MODE_POSITION_FLOAT_VAR",
        scale=_pct,
    ),
    SyncSpec.param(
        "int", "follow_geo_start_specific_index", "ID_NX_FS_SPLINE_START_MODE_SPECIFIC_INDEX"
    ),
    SyncSpec.param(
        "float", "follow_geo_offset_value", "ID_NX_FS_SPLINE_OFFSET_SPLINEOFFSET", scale=_unit
    ),
    SyncSpec.param(
        "float", "follow_geo_offset_blend", "ID_NX_FS_SPLINE_OFFSET_SPLINEOFFSET_XY", scale=_pct
    ),
)

_FOLLOW_GEO_TWIST_PARAM_SPECS = (
    SyncSpec.param(
        "enum",
        "follow_geo_twist_direction",
        "ID_NX_FS_SPLINE_TWIST_DIRECTION",
        enum_map=_FOLLOW_GEO_TWIST_DIR_MAP,
    ),
    SyncSpec.param("int", "follow_geo_twists", "ID_NX_FS_SPLINE_TWIST_NUM_LOOPS"),
    SyncSpec.param(
        "float", "follow_geo_twist_radius", "ID_NX_FS_SPLINE_TWIST_RADIUS", scale=_unit
    ),
)

_FOLLOW_GEO_RELEASE_PARAM_SPECS = (
    SyncSpec.param(
        "enum",
        "follow_geo_surface_release_mode",
        "ID_NX_FS_SURFACE_RELEASE_MODE",
        enum_map=_FOLLOW_GEO_SURFACE_RELEASE_MAP,
    ),
    SyncSpec.param(
        "float", "follow_geo_surface_release_amount", "ID_NX_FS_SURFACE_RELEASE_FLOAT", scale=_pct
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_surface_time_mode",
        "ID_NX_FS_SURFACE_TIME_MODE",
        enum_map=_FOLLOW_GEO_SURFACE_TIME_MAP,
    ),
    SyncSpec.param("time", "follow_geo_surface_release_time", "ID_NX_FS_SURFACE_TIME_COVER"),
    SyncSpec.param(
        "time", "follow_geo_surface_release_time_var", "ID_NX_FS_SURFACE_TIME_COVER_VAR"
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_spline_release_mode",
        "ID_NX_FS_SPLINE_RELEASE_MODE",
        enum_map=_FOLLOW_GEO_SPLINE_RELEASE_MAP,
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_on_release",
        "ID_NX_FS_SPLINE_RELEASE_ACTION",
        enum_map=_FOLLOW_GEO_ON_RELEASE_MAP,
    ),
    SyncSpec.param(
        "float", "follow_geo_release_distance", "ID_NX_FS_SPLINE_RELEASE_DISTANCE", scale=_pct
    ),
    SyncSpec.param(
        "enum",
        "follow_geo_spline_time_mode",
        "ID_NX_FS_SPLINE_TIME_MODE",
        enum_map=_FOLLOW_GEO_SPLINE_TIME_MAP,
    ),
    SyncSpec.param("time", "follow_geo_spline_release_time", "ID_NX_FS_SPLINE_TIME_COVER"),
    SyncSpec.param("time", "follow_geo_spline_release_time_var", "ID_NX_FS_SPLINE_TIME_COVER_VAR"),
)

_FOLLOW_GEO_ITEM_SYNC_SPECS = (
    *_FOLLOW_GEO_BASE_PARAM_SPECS,
    *_FOLLOW_GEO_TWIST_PARAM_SPECS,
    *_FOLLOW_GEO_RELEASE_PARAM_SPECS,
)

NexusFollowGeoItem._sync_specs = _FOLLOW_GEO_ITEM_SYNC_SPECS


def _sync_extended_splines(obj, item_orig, item_eval, node_container, theron, get):
    from ..libs.nodetree_sync import resolve_evaluated_item
    from ..libs.resource_sync import sync_curve_specs

    ext_orig = item_orig.follow_geo_extended
    ext_eval = item_eval.follow_geo_extended
    synced_types = set()
    for index, ext_item_orig in enumerate(ext_orig):
        ext_item = resolve_evaluated_item(ext_eval, index, ext_item_orig)
        if not ext_item.enabled or not ext_item_orig.layer_uid:
            continue
        if ext_item_orig.item_type in synced_types:
            continue
        synced_types.add(ext_item_orig.item_type)
        if ext_item_orig.item_type == "OFFSET":
            curve_specs = _get_offset_curve_specs()
        elif ext_item_orig.item_type == "TWIST":
            curve_specs = _get_twist_curve_specs()
        else:
            continue
        sync_curve_specs(
            theron,
            get,
            node_container,
            obj,
            curve_specs,
            source=ext_item_orig,
            evaluated_source=ext_item,
        )


def _sync_follow_geo_node_params(theron, get, node_container, item, item_orig, obj):
    from ..libs.nodetree_sync import resolve_evaluated_item

    _sync_extended_splines(obj, item_orig, item, node_container, theron, get)

    obj_kind = item_orig.obj.type if item_orig.obj is not None else None
    if obj_kind == "CURVE" and len(item_orig.follow_geo_extended) > 0:
        sub_tree = theron.create_node_tree(
            node_container, get("ID_NX_FS_SURFACE_ADD_OFFSET_CHOICE_TREE")
        )
        if sub_tree is not None:
            prev_ext_node = None
            ext_eval = item.follow_geo_extended
            for index, ext_item_orig in enumerate(item_orig.follow_geo_extended):
                ext_item = resolve_evaluated_item(ext_eval, index, ext_item_orig)
                if not ext_item.enabled:
                    continue
                type_id_name = _FOLLOW_GEO_EXTENDED_TYPE_IDS.get(ext_item_orig.item_type)
                if type_id_name is None:
                    continue
                ext_node = theron.node_tree_insert(sub_tree, None, prev_ext_node)
                if ext_node is None:
                    continue
                theron.set_node_id(ext_node, get(type_id_name))
                prev_ext_node = ext_node


FOLLOW_GEO_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_FS_OBJECTS_TREE",
    collection_attr="follow_geo_objects",
    pre_syncer=_follow_geo_object_links.pre_syncer,
    post_syncer=_follow_geo_object_links.post_syncer,
    node_link_resolver=_follow_geo_object_links.node_link_resolver,
    skip_if_no_link=True,
    pre_dispatch_syncer=_sync_follow_geo_node_params,
)
_FOLLOW_GEO_OBJECTS = NodeTreeDef(
    "Objects",
    item_type=NexusFollowGeoItem,
    allowed_types=["MESH", "CURVE"],
    nodetree_sync=FOLLOW_GEO_OBJECTS_TREE_SPEC,
)
_follow_geo_tree_props = _FOLLOW_GEO_OBJECTS.properties("follow_geo_objects")

NX_FOLLOW_GEO_UI_CONFIG = {
    **_FOLLOW_GEO_OBJECTS.ui_config("follow_geo_objects"),
}


def get_follow_geo_ui_config():
    config = dict(NX_FOLLOW_GEO_UI_CONFIG)
    config["follow_geo_objects"]["draw_item_settings"] = draw_follow_geo_item_settings
    return config


def _draw_connection_settings(layout, item, is_edge):
    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")
    col.prop(item, "follow_geo_pull")
    col.prop(item, "follow_geo_pull_var")
    col.prop(item, "follow_geo_push")
    col.prop(item, "follow_geo_push_var")
    col.prop(item, "follow_geo_offset")
    col.prop(item, "follow_geo_offset_var")
    col.separator(type="LINE")
    col.prop(item, "follow_geo_distance")
    col.prop(item, "follow_geo_friction")
    col.prop(item, "follow_geo_fov")
    col.separator(type="LINE")

    sub = col.column()
    sub.enabled = is_edge
    sub.prop(item, "follow_geo_edge")
    sub.prop(item, "follow_geo_smoothing")


def _draw_release_settings(layout, item):
    from ..libs.nexus_time import draw_time_prop

    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")
    col.prop(item, "follow_geo_surface_release_mode")

    if item.follow_geo_surface_release_mode != "NONE":
        col.separator(type="LINE")

        col.prop(item, "follow_geo_surface_time_mode")
        draw_time_prop(col, item, "follow_geo_surface_release_time")
        draw_time_prop(col, item, "follow_geo_surface_release_time_var")


def _draw_spline_connection_settings(layout, item):
    is_force = item.follow_geo_spline_mode == "FORCE"

    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")
    col.prop(item, "follow_geo_spline_direction")
    col.prop(item, "follow_geo_spline_mode")
    col.prop(item, "follow_geo_activate_range")
    col.prop(item, "follow_geo_strength")
    col.separator(type="LINE")
    if is_force:
        col.prop(item, "follow_geo_attract_strength")
    else:
        col.prop(item, "follow_geo_attract_strength_pct")
    col.prop(item, "follow_geo_attract_variation")
    col.prop(item, "follow_geo_attract_falloff")
    col.prop(item, "follow_geo_attract_falloff_type")
    col.separator(type="LINE")
    if is_force:
        col.prop(item, "follow_geo_follow_strength")
    else:
        col.prop(item, "follow_geo_follow_strength_pct")
    col.prop(item, "follow_geo_follow_variation")
    col.prop(item, "follow_geo_follow_falloff")
    col.prop(item, "follow_geo_follow_falloff_type")
    col.separator(type="LINE")
    col.prop(item, "follow_geo_align")


def _draw_spline_offset_settings(layout, item):
    from ..ui import draw_nodetree

    def _draw_ext_settings(settings_layout, ext_item):
        col = settings_layout.column()
        col.use_property_split = True
        if ext_item.item_type == "OFFSET":
            col.separator(type="LINE")
            col.prop(item, "follow_geo_offset_value")
            col.prop(item, "follow_geo_offset_blend")
            if ext_item.layer_uid:
                from ..utils.curve import NexusCurve

                obj = bpy.context.object
                if obj:
                    NexusCurve(obj, f"follow_geo_offset_spline_{ext_item.layer_uid}").draw_ui(
                        col, "Offset Along Length"
                    )
        elif ext_item.item_type == "TWIST":
            col.separator(type="LINE")
            col.prop(item, "follow_geo_twist_direction")
            col.prop(item, "follow_geo_twists")
            col.prop(item, "follow_geo_twist_radius")
            if ext_item.layer_uid:
                from ..utils.curve import NexusCurve

                obj = bpy.context.object
                if obj:
                    NexusCurve(obj, f"follow_geo_twist_spline_{ext_item.layer_uid}").draw_ui(
                        col, "Radius Along Length"
                    )

    item_path = item.path_from_id()

    draw_nodetree(
        layout,
        item,
        "follow_geo_extended",
        "follow_geo_extended_index",
        label="Layers",
        draw_item_settings=_draw_ext_settings,
        menu_id="follow_geo_extended",
        data_path=item_path,
    )


def _draw_spline_release_settings(layout, item):
    from ..libs.nexus_time import draw_time_prop

    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")
    col.prop(item, "follow_geo_spline_release_mode")
    col.prop(item, "follow_geo_on_release")
    col.separator(type="LINE")
    col.prop(item, "follow_geo_release_distance")

    if item.follow_geo_spline_release_mode == "TIME":
        col.separator(type="LINE")
        col.prop(item, "follow_geo_spline_time_mode")
        draw_time_prop(col, item, "follow_geo_spline_release_time")
        draw_time_prop(col, item, "follow_geo_spline_release_time_var")


def _draw_spline_data_settings(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")
    col.prop(item, "follow_geo_multi_segment")
    if item.follow_geo_multi_segment == "SPECIFIC":
        col.prop(item, "follow_geo_segment_index")
    col.separator(type="LINE")
    col.prop(item, "follow_geo_starting_mode")
    if item.follow_geo_starting_mode == "POSITION":
        col.prop(item, "follow_geo_start_position")
        col.prop(item, "follow_geo_start_position_var")
    elif item.follow_geo_starting_mode == "SPECIFIC_VERTEX":
        col.prop(item, "follow_geo_start_specific_index")


def draw_follow_geo_item_settings(layout, item):
    if item.obj is None:
        return

    is_curve = item.obj.type == "CURVE"

    col = layout.column()
    col.use_property_split = True

    if is_curve:
        tab_row = layout.row(align=True)
        tab_row.use_property_split = False
        tab_row.prop(item, "follow_geo_spline_tab", expand=True)

        tab = item.follow_geo_spline_tab

        if tab == "CONNECTION":
            _draw_spline_connection_settings(layout, item)
        elif tab == "OFFSET":
            _draw_spline_offset_settings(layout, item)
        elif tab == "RELEASE":
            _draw_spline_release_settings(layout, item)
        elif tab == "SPLINE_DATA":
            _draw_spline_data_settings(layout, item)
    else:
        col.prop(item, "follow_geo_mode")

        tab_row = layout.row(align=True)
        tab_row.use_property_split = False
        tab_row.prop(item, "follow_geo_tab", expand=True)

        tab = item.follow_geo_tab
        if tab not in ("CONNECTION", "RELEASE"):
            tab = "CONNECTION"

        is_edge = item.follow_geo_mode == "EDGE"
        if tab == "CONNECTION":
            _draw_connection_settings(layout, item, is_edge)
        elif tab == "RELEASE":
            _draw_release_settings(layout, item)


SPEC = ModifierPropertySpec(
    modifier_type="NX_FOLLOW_GEO",
    item_classes=(NexusFollowGeoItem, NexusFollowGeoExtendedItem),
    enum_builders=(
        build_follow_geo_enum_items,
        build_follow_geo_extended_enum_items,
    ),
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="follow_geo_objects",
            prop=_follow_geo_tree_props["follow_geo_objects"],
        ),
        PropertyDescriptor(
            name="follow_geo_objects_index",
            prop=_follow_geo_tree_props["follow_geo_objects_index"],
        ),
        PropertyDescriptor(
            name="follow_geo_objects_drop_target",
            prop=_follow_geo_tree_props.get("follow_geo_objects_drop_target"),
            preset=False,
        ),
    ),
    nodetree_sync=combine_nodetree_sync(_FOLLOW_GEO_OBJECTS),
)


# Scene-link list; not preset-captured. Cleanup-only so nested
# `follow_geo_extended` curves are released on reset via `on_remove`.
def _follow_geo_extended_curve_specs(item):
    item_type = getattr(item, "item_type", None) if item is not None else None
    if item_type == "OFFSET":
        return _get_offset_curve_specs()
    if item_type == "TWIST":
        return _get_twist_curve_specs()
    return []


register_collection_cleanup(
    "NX_FOLLOW_GEO",
    CollectionPresetSpec(
        collection_attr="follow_geo_objects",
        nested_specs=(
            CollectionPresetSpec(
                collection_attr="follow_geo_extended",
                menu_id="follow_geo_extended",
                curve_specs=_follow_geo_extended_curve_specs,
                suffix_attr="layer_uid",
            ),
        ),
    ),
)
