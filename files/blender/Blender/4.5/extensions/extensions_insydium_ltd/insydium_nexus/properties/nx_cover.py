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
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
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
from ..libs.nexus_time import draw_time_prop, nexus_time_property
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
)
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform
from ..ui import NodeTreeDef, combine_nodetree_sync, make_allowed_types_poll
from ..utils.curve import CurveSpec, NexusCurve, create_item_curves, generate_curve_id

_COVER_OBJECT_MODE_ITEMS = []
_COVER_OPERATION_ITEMS = []
_COVER_SPEED_MODE_ITEMS = []
_COVER_PARTICLE_SPEED_MODE_ITEMS = []
_COVER_HOLDING_MODE_ITEMS = []

_COVER_ATTRACT_MODE_ITEMS = [
    ("VELOCITY", "Velocity", "Control particle velocity directly", 0),
    ("ACCELERATION", "Acceleration", "Apply acceleration to particles", 1),
]

_COVER_ARRIVE_MODE_ITEMS = [
    ("SLOWDOWN", "Slowdown", "Particle slows down as it approaches target", 0),
    ("ATTRACT", "Attract", "Particle is attracted without slowing", 1),
]

_COVER_TEXTURE_MODE_ITEMS = [
    (
        "HIGHER",
        "Higher",
        "Place particles where texture value is higher than threshold",
        0,
    ),
    (
        "LOWER",
        "Lower",
        "Place particles where texture value is lower than threshold",
        1,
    ),
]


def build_cover_enum_items():
    global _COVER_OBJECT_MODE_ITEMS, _COVER_OPERATION_ITEMS, _COVER_SPEED_MODE_ITEMS
    global _COVER_PARTICLE_SPEED_MODE_ITEMS, _COVER_HOLDING_MODE_ITEMS

    from ..icons import get_icon

    _COVER_OBJECT_MODE_ITEMS = [
        (
            "SEQUENCE",
            "Sequence",
            "Assign objects to particles in sequence",
            get_icon("nx_cover_objmode_sequence"),
            0,
        ),
        (
            "NEAREST",
            "Nearest Object",
            "Assign the nearest object to each particle",
            get_icon("nx_cover_objmode_nearest"),
            1,
        ),
        (
            "FURTHEST",
            "Furthest Object",
            "Assign the furthest object to each particle",
            get_icon("nx_cover_objmode_furthest"),
            2,
        ),
        (
            "INDEX",
            "Object Index",
            "Assign a specific object by index",
            get_icon("nx_cover_objmode_index"),
            3,
        ),
        (
            "RANDOM",
            "Random Object",
            "Assign a random object to each particle",
            get_icon("nx_cover_objmode_random"),
            4,
        ),
    ]

    _COVER_OPERATION_ITEMS = [
        (
            "AREA",
            "Polygon Area",
            "Place particles based on polygon area weighting",
            get_icon("nx_cover_op_polyarea"),
            0,
        ),
        (
            "CENTER",
            "Polygon Center",
            "Place particles at polygon centers",
            get_icon("nx_cover_op_polycenter"),
            1,
        ),
        (
            "POINTS",
            "Points",
            "Place particles at mesh vertices",
            get_icon("nx_cover_op_points"),
            2,
        ),
        (
            "EDGES",
            "Edges",
            "Place particles along mesh edges",
            get_icon("nx_cover_op_edges"),
            3,
        ),
        (
            "VOLUME",
            "Volume",
            "Place particles within the mesh volume",
            get_icon("nx_cover_op_volume"),
            4,
        ),
        # (
        #     "TEXTURE",
        #     "Texture",
        #     "Place particles based on texture values",
        #     get_icon("nx_cover_op_texture"),
        #     5,
        # ),
        (
            "RAY",
            "Ray Intersection",
            "Place particles where rays intersect the mesh",
            get_icon("nx_cover_op_ray"),
            6,
        ),
    ]

    _COVER_SPEED_MODE_ITEMS = [
        (
            "PARTICLE",
            "Use Speed",
            "Use the particle's current speed to reach the target",
            get_icon("nx_cover_speed_usespeed"),
            0,
        ),
        (
            "TIME",
            "Time to Target",
            "Specify a fixed time to reach the target",
            get_icon("nx_cover_speed_timetarget"),
            1,
        ),
    ]

    _COVER_PARTICLE_SPEED_MODE_ITEMS = [
        (
            "PARTICLE",
            "Particle",
            "Use the particle's own speed",
            get_icon("nx_cover_pspeed_particle"),
            0,
        ),
        (
            "FIXED",
            "Fixed",
            "Use a fixed speed value",
            get_icon("nx_cover_pspeed_fixed"),
            1,
        ),
        (
            "FORCE",
            "Force",
            "Apply a force towards the target",
            get_icon("nx_cover_pspeed_force"),
            2,
        ),
    ]

    _COVER_HOLDING_MODE_ITEMS = [
        (
            "ATTRACT",
            "Attract",
            "Continuously attract particles to target position",
            get_icon("nx_cover_hold_attract"),
            0,
        ),
        (
            "FREE",
            "Free",
            "Particles are free once they reach the target",
            get_icon("nx_cover_hold_free"),
            1,
        ),
        (
            "SPRING",
            "Spring",
            "Particles are held by a spring force",
            get_icon("nx_cover_hold_spring"),
            2,
        ),
        (
            "STICK",
            "Stick",
            "Particles stick to the target position",
            get_icon("nx_cover_hold_stick"),
            3,
        ),
    ]


def _get_cover_object_mode_items(self, context):
    return _COVER_OBJECT_MODE_ITEMS


def _get_cover_operation_items(self, context):
    return _COVER_OPERATION_ITEMS


def _get_cover_speed_mode_items(self, context):
    return _COVER_SPEED_MODE_ITEMS


def _get_cover_particle_speed_mode_items(self, context):
    return _COVER_PARTICLE_SPEED_MODE_ITEMS


def _get_cover_holding_mode_items(self, context):
    return _COVER_HOLDING_MODE_ITEMS


def _get_cover_attract_mode_items(self, context):
    return _COVER_ATTRACT_MODE_ITEMS


def _get_cover_arrive_mode_items(self, context):
    return _COVER_ARRIVE_MODE_ITEMS


def _get_cover_texture_mode_items(self, context):
    return _COVER_TEXTURE_MODE_ITEMS


_COVER_TEXTURE_RES_ITEMS = [
    ("64", "64", "64x64 texture resolution"),
    ("128", "128", "128x128 texture resolution"),
    ("256", "256", "256x256 texture resolution"),
    ("512", "512", "512x512 texture resolution"),
    ("1024", "1024", "1024x1024 texture resolution"),
    ("2048", "2048", "2048x2048 texture resolution"),
]


COVER_BRAKING_CURVE_SPECS = [
    CurveSpec(
        "braking",
        "Braking",
        [(0.0, 0.0), (1.0, 1.0)],
        theron_ids=("ID_NX_COVER_BRAKING",),
        slot_suffix_attr="curve_id",
        sync_condition=lambda item, _item_orig: item.cover_use_braking,
    ),
]


def _on_cover_item_obj_update(self, context):
    if self.obj is None:
        return
    if not self.curve_id:
        self.curve_id = generate_curve_id()
        obj = self.id_data
        create_item_curves(obj, self, COVER_BRAKING_CURVE_SPECS)


class NexusCoverItem(bpy.types.PropertyGroup):
    curve_id: StringProperty(name="", default="", options={"HIDDEN"})

    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
        update=_on_cover_item_obj_update,
    )
    enabled: BoolProperty(name="Enabled", default=True)

    cover_operation: EnumProperty(
        name="Operation",
        description="How particles are placed on the surface",
        items=_get_cover_operation_items,
    )

    cover_strength: FloatProperty(
        name="Strength",
        description="Strength of the cover effect",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    cover_tolerance: FloatProperty(
        name="Tolerance",
        description="Distance tolerance for considering a particle as covering",
        default=0.1,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    cover_inherit: BoolProperty(
        name="Inherit Parent",
        description="Inherit settings from the first object in the list",
        default=False,
    )

    cover_speed_mode: EnumProperty(
        name="Speed Mode",
        description="How particles move towards the target",
        items=_get_cover_speed_mode_items,
    )

    cover_time_cover: nexus_time_property(
        "cover_time_cover",
        name="Time to Cover",
        description="Time to reach the target position",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        collection_path="cover_objects",
    )

    cover_time_cover_var: nexus_time_property(
        "cover_time_cover_var",
        name="Time Variation",
        description="Random variation in time to cover",
        default=0.0,
        min=0.0,
        soft_max=5.0,
        collection_path="cover_objects",
    )

    cover_time_release: nexus_time_property(
        "cover_time_release",
        name="Release Time",
        description="Time before particle is released from target",
        default=60.0,
        min=0.0,
        soft_max=10.0,
        collection_path="cover_objects",
    )

    cover_time_release_var: nexus_time_property(
        "cover_time_release_var",
        name="Release Variation",
        description="Random variation in release time",
        default=0.0,
        min=0.0,
        soft_max=5.0,
        collection_path="cover_objects",
    )

    cover_particle_speed_mode: EnumProperty(
        name="Particle Speed Mode",
        description="How particle speed is determined",
        items=_get_cover_particle_speed_mode_items,
    )

    cover_particle_speed_fixed: FloatProperty(
        name="Fixed Speed",
        description="Fixed speed value for particles",
        default=1.5,
        min=0.0,
        soft_max=5.0,
        unit="VELOCITY",
    )

    cover_holding_mode: EnumProperty(
        name="Holding Mode",
        description="How particles are held at the target",
        items=_get_cover_holding_mode_items,
    )

    cover_holding_rot: BoolProperty(
        name="Rotate With Object",
        description="Particles rotate with the target object",
        default=False,
    )

    cover_attract_mode: EnumProperty(
        name="Mode",
        description="How attraction affects particles",
        items=_get_cover_attract_mode_items,
    )

    cover_arrive_mode: EnumProperty(
        name="Arrive Mode",
        description="How particles arrive at the target",
        items=_get_cover_arrive_mode_items,
    )

    cover_attract_dist: FloatProperty(
        name="Distance",
        description="Distance at which particles start slowing down",
        default=0.5,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    cover_attract_min_speed: FloatProperty(
        name="Min Speed",
        description="Minimum speed when approaching target",
        default=0.01,
        min=0.0,
        soft_max=10.0,
        unit="VELOCITY",
    )

    cover_attract_max_speed: FloatProperty(
        name="Max Speed",
        description="Maximum speed when approaching target",
        default=1.5,
        min=0.0,
        soft_max=10.0,
        unit="VELOCITY",
    )

    cover_spring_length: FloatProperty(
        name="Spring Length",
        description="Rest length of the spring",
        default=0.005,
        min=0.0,
        soft_max=0.1,
        unit="LENGTH",
    )

    cover_spring_stiffness: FloatProperty(
        name="Stiffness",
        description="Stiffness of the spring",
        default=1.5,
        min=0.0,
        soft_max=10.0,
    )

    cover_spring_damping: FloatProperty(
        name="Damping",
        description="Damping factor of the spring",
        default=5.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    cover_use_braking: BoolProperty(
        name="Use Braking",
        description="Apply braking when approaching target",
        default=False,
    )

    cover_braking_dist: FloatProperty(
        name="Braking Distance",
        description="Distance at which braking starts",
        default=0.5,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    cover_braking_min_speed: FloatProperty(
        name="Min Speed",
        description="Minimum speed during braking",
        default=0.05,
        min=0.0,
        soft_max=10.0,
        unit="VELOCITY",
    )

    cover_braking_max_speed: FloatProperty(
        name="Max Speed",
        description="Maximum speed during braking",
        default=1.5,
        min=0.0,
        soft_max=10.0,
        unit="VELOCITY",
    )

    cover_align_normals: BoolProperty(
        name="Align to Normals",
        description="Align particles to surface normals",
        default=False,
    )

    cover_align_strength: FloatProperty(
        name="Alignment Strength",
        description="Strength of normal alignment",
        default=10.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    cover_change_color: BoolProperty(
        name="Change Color",
        description="Change particle color when covering",
        default=False,
    )

    cover_color: FloatVectorProperty(
        name="Cover Color",
        description="Color to apply when covering",
        default=(1.0, 0.745, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    cover_color_timing: FloatProperty(
        name="Color Timing",
        description="Time multiplier for color transition",
        default=100.0,
        min=0.0,
        max=500.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    cover_set_to_texture: BoolProperty(
        name="Set to Texture",
        description="Use texture color for particles",
        default=False,
    )

    cover_change_release_color: BoolProperty(
        name="Change Release Color",
        description="Change particle color on release",
        default=False,
    )

    cover_release_color: FloatVectorProperty(
        name="Release Color",
        description="Color to apply on release",
        default=(1.0, 0.745, 0.0),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    cover_texture_res: EnumProperty(
        name="Texture Resolution",
        description="Resolution for texture sampling",
        items=_COVER_TEXTURE_RES_ITEMS,
        default="128",
    )

    cover_texture_tolerance: FloatProperty(
        name="Texture Tolerance",
        description="Tolerance for texture threshold comparison",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    cover_texture_threshold: FloatVectorProperty(
        name="Texture Threshold",
        description="Threshold color for texture comparison",
        default=(0.5, 0.5, 0.5),
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=3,
    )

    cover_texture_mode: EnumProperty(
        name="Texture Mode",
        description="How to compare texture values",
        items=_get_cover_texture_mode_items,
    )

    cover_texture_attempts: IntProperty(
        name="Max Attempts",
        description="Maximum attempts to find valid texture position",
        default=25,
        min=1,
        max=100,
    )

    cover_align_color_expanded: BoolProperty(
        name="Alignment / Color",
        description="Expand alignment and color settings",
        default=True,
    )

    cover_movement_expanded: BoolProperty(
        name="Movement",
        description="Expand movement settings",
        default=True,
    )

    cover_holding_expanded: BoolProperty(
        name="Holding",
        description="Expand holding settings",
        default=True,
    )

    cover_braking_expanded: BoolProperty(
        name="Braking",
        description="Expand braking settings",
        default=True,
    )


_COVER_OPERATION_MAP = {
    "AREA": "OP_AREA",
    "CENTER": "OP_CENTER",
    "POINTS": "OP_POINTS",
    "EDGES": "OP_EDGES",
    "VOLUME": "OP_VOLUME",
    "TEXTURE": "OP_TEXTURE",
    "RAY": "OP_RAY",
}

_COVER_SPEED_MODE_MAP = {
    "PARTICLE": "SPEED_PARTICLE",
    "TIME": "SPEED_TIME",
}

_COVER_PARTICLE_SPEED_MODE_MAP = {
    "PARTICLE": "SPEED_MODE_PARTICLE",
    "FIXED": "SPEED_MODE_FIXED",
    "FORCE": "SPEED_MODE_FORCE",
}

_COVER_HOLDING_MODE_MAP = {
    "ATTRACT": "HOLDING_MODE_ATTRACT",
    "FREE": "HOLDING_MODE_FREE",
    "SPRING": "HOLDING_MODE_SPRING",
    "STICK": "HOLDING_MODE_STICK",
}

_COVER_ATTRACT_MODE_MAP = {
    "VELOCITY": "ID_NX_COVER_ATTRACT_MODE_VEL",
    "FORCE": "ID_NX_COVER_ATTRACT_MODE_FORCE",
}

_COVER_ARRIVE_MODE_MAP = {
    "SLOWDOWN": "ID_NX_COVER_ATTRACT_MODE_ARRIVE",
    "ATTRACT": "ID_NX_COVER_ATTRACT_MODE_ATTRACT",
}

_COVER_TEXTURE_MODE_MAP = {
    "HIGHER": "ID_NX_TEXTURE_MODE_HIGHER",
    "LOWER": "ID_NX_TEXTURE_MODE_LOWER",
}

_COVER_TEXTURE_RES_MAP = {
    "64": "ID_NX_COVER_TEXTURE_RES_64",
    "128": "ID_NX_COVER_TEXTURE_RES_128",
    "256": "ID_NX_COVER_TEXTURE_RES_256",
    "512": "ID_NX_COVER_TEXTURE_RES_512",
    "1024": "ID_NX_COVER_TEXTURE_RES_1024",
    "2048": "ID_NX_COVER_TEXTURE_RES_2048",
}

_cover_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

COVER_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="cover_objects",
    cache_dict=_cover_poly_cache,
)

_cover_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

COVER_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="cover_objects",
    cache_dict=_cover_line_cache,
)

_cover_object_links = make_cached_link_resolver(
    poly_spec=COVER_POLY_SPEC,
    line_spec=COVER_LINE_SPEC,
)

_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]

_COVER_PARAM_SPECS = (
    SyncSpec.param("enum", "cover_operation", "ID_NX_COVER_OP", enum_map=_COVER_OPERATION_MAP),
    SyncSpec.param(
        "enum", "cover_speed_mode", "ID_NX_COVER_SPEED_MODE", enum_map=_COVER_SPEED_MODE_MAP
    ),
    SyncSpec.param(
        "enum",
        "cover_particle_speed_mode",
        "ID_NX_COVER_PARTICLE_SPEED_MODE",
        enum_map=_COVER_PARTICLE_SPEED_MODE_MAP,
    ),
    SyncSpec.param(
        "enum",
        "cover_holding_mode",
        "ID_NX_COVER_HOLDING_MODE",
        enum_map=_COVER_HOLDING_MODE_MAP,
    ),
    SyncSpec.param(
        "enum",
        "cover_attract_mode",
        "ID_NX_COVER_ATTRACT_MODE",
        enum_map=_COVER_ATTRACT_MODE_MAP,
    ),
    SyncSpec.param(
        "enum",
        "cover_arrive_mode",
        "ID_NX_COVER_ARRIVE_MODE",
        enum_map=_COVER_ARRIVE_MODE_MAP,
    ),
    SyncSpec.param(
        "enum", "cover_texture_res", "ID_NX_TEXTURE_RES", enum_map=_COVER_TEXTURE_RES_MAP
    ),
    SyncSpec.param(
        "enum",
        "cover_texture_mode",
        "ID_NX_TEXTURE_MODE",
        enum_map=_COVER_TEXTURE_MODE_MAP,
    ),
    SyncSpec.param("float", "cover_strength", "ID_NX_COVER_STRENGTH", scale=_pct),
    SyncSpec.param("float", "cover_spring_damping", "ID_NX_COVER_SPRING_DAMPING", scale=_pct),
    SyncSpec.param("float", "cover_align_strength", "ID_NX_ALIGN_NORMALS_STRENGTH", scale=_pct),
    SyncSpec.param("float", "cover_texture_tolerance", "ID_NX_TEXTURE_TOLERANCE", scale=_pct),
    SyncSpec.param("float", "cover_tolerance", "ID_NX_COVER_TOLERANCE", scale=_unit),
    SyncSpec.param(
        "float",
        "cover_particle_speed_fixed",
        "ID_NX_COVER_PARTICLE_SPEED_FIXED",
        scale=_unit,
    ),
    SyncSpec.param("float", "cover_attract_dist", "ID_NX_COVER_ATTRACT_DIST", scale=_unit),
    SyncSpec.param(
        "float", "cover_attract_min_speed", "ID_NX_COVER_ATTRACT_MIN_SPEED", scale=_unit
    ),
    SyncSpec.param(
        "float", "cover_attract_max_speed", "ID_NX_COVER_ATTRACT_MAX_SPEED", scale=_unit
    ),
    SyncSpec.param("float", "cover_spring_length", "ID_NX_COVER_SPRING_LENGTH", scale=_unit),
    SyncSpec.param("float", "cover_braking_dist", "ID_NX_COVER_BRAKING_DIST", scale=_unit),
    SyncSpec.param(
        "float", "cover_braking_min_speed", "ID_NX_COVER_BRAKING_MIN_SPEED", scale=_unit
    ),
    SyncSpec.param(
        "float", "cover_braking_max_speed", "ID_NX_COVER_BRAKING_MAX_SPEED", scale=_unit
    ),
    SyncSpec.param("float", "cover_spring_stiffness", "ID_NX_COVER_SPRING_STIFFNESS"),
    SyncSpec.param("float", "cover_color_timing", "ID_NX_COVER_CHANGE_COLOR_FLOAT"),
    SyncSpec.param("bool", "cover_inherit", "ID_NX_COVER_INHERIT"),
    SyncSpec.param("bool", "cover_use_braking", "ID_NX_COVER_PARTICLE_BRAKING_BOOL"),
    SyncSpec.param("bool", "cover_holding_rot", "ID_NX_COVER_HOLDING_ROT"),
    SyncSpec.param("bool", "cover_change_color", "ID_NX_COVER_CHANGE_COLOR"),
    SyncSpec.param("bool", "cover_set_to_texture", "ID_NX_COVER_SET_TO_TEXTURE"),
    SyncSpec.param("bool", "cover_change_release_color", "ID_NX_COVER_CHANGE_RELEASE_COLOR"),
    SyncSpec.param("bool", "cover_align_normals", "ID_NX_ALIGN_NORMALS"),
    SyncSpec.param("time", "cover_time_cover", "ID_NX_COVER_TIME_COVER"),
    SyncSpec.param("time", "cover_time_cover_var", "ID_NX_COVER_TIME_COVER_VAR"),
    SyncSpec.param("time", "cover_time_release", "ID_NX_COVER_TIME_RELEASE"),
    SyncSpec.param("time", "cover_time_release_var", "ID_NX_COVER_TIME_VARIATION"),
    SyncSpec.param("vector", "cover_color", "ID_NX_COVER_COLOR"),
    SyncSpec.param("vector", "cover_release_color", "ID_NX_COVER_RELEASE_COLOR"),
    SyncSpec.param("vector", "cover_texture_threshold", "ID_NX_TEXTURE_THRESHOLD"),
    SyncSpec.param("int", "cover_texture_attempts", "ID_NX_TEXTURE_ATTEMPTS"),
)

NexusCoverItem._sync_specs = _COVER_PARAM_SPECS


COVER_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_COVER_OBJECTS_TREE",
    collection_attr="cover_objects",
    pre_syncer=_cover_object_links.pre_syncer,
    post_syncer=_cover_object_links.post_syncer,
    node_link_resolver=_cover_object_links.node_link_resolver,
    skip_if_no_link=True,
    curve_specs=COVER_BRAKING_CURVE_SPECS,
)
_COVER_OBJECTS = NodeTreeDef(
    "Objects",
    item_type=NexusCoverItem,
    allowed_types=["MESH", "CURVE"],
    nodetree_sync=COVER_OBJECTS_TREE_SPEC,
)
_cover_tree_props = _COVER_OBJECTS.properties("cover_objects")

NX_COVER_UI_CONFIG = {
    **_COVER_OBJECTS.ui_config("cover_objects"),
}


def draw_cover_item_settings(layout, item):
    obj = item.obj
    if obj is None or obj.type not in {"MESH", "CURVE"}:
        return

    col = layout.column()
    col.use_property_split = True

    col.prop(item, "cover_operation")

    if item.cover_operation == "TEXTURE":
        col.prop(item, "cover_texture_res")
        col.prop(item, "cover_texture_tolerance")
        col.prop(item, "cover_texture_threshold")
        col.prop(item, "cover_texture_mode")
        col.prop(item, "cover_texture_attempts")
        col.separator(type="LINE")

    col.prop(item, "cover_strength")
    col.prop(item, "cover_tolerance")

    col.separator(type="LINE")
    col.prop(item, "cover_inherit")

    if item.cover_inherit:
        return

    # Alignment / Color section
    box = layout.box()
    header = box.row()
    header.use_property_split = False
    header.prop(
        item,
        "cover_align_color_expanded",
        icon="TRIA_DOWN" if item.cover_align_color_expanded else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    header.label(text="Alignment / Color")

    if item.cover_align_color_expanded:
        acol = box.column()
        acol.use_property_split = True

        row = acol.row()
        row.prop(item, "cover_holding_rot")
        row.enabled = not item.cover_align_normals

        acol.separator(type="LINE")

        row = acol.row()
        row.prop(item, "cover_align_normals")
        row.enabled = not item.cover_holding_rot

        row = acol.row()
        row.prop(item, "cover_align_strength")
        row.enabled = item.cover_align_normals

        acol.separator(type="LINE")
        acol.prop(item, "cover_change_color")

        if item.cover_operation == "TEXTURE":
            row = acol.row()
            row.prop(item, "cover_set_to_texture")
            row.enabled = item.cover_change_color

        row = acol.row()
        row.prop(item, "cover_color")
        row.enabled = item.cover_change_color and not (
            item.cover_operation == "TEXTURE" and item.cover_set_to_texture
        )

        row = acol.row()
        row.prop(item, "cover_color_timing")
        row.enabled = item.cover_change_color

        acol.separator(type="LINE")
        acol.prop(item, "cover_change_release_color")

        row = acol.row()
        row.prop(item, "cover_release_color")
        row.enabled = item.cover_change_release_color

    layout.separator(type="LINE")

    # Movement section
    box = layout.box()
    header = box.row()
    header.use_property_split = False
    header.prop(
        item,
        "cover_movement_expanded",
        icon="TRIA_DOWN" if item.cover_movement_expanded else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    header.label(text="Movement")

    if item.cover_movement_expanded:
        mcol = box.column()
        mcol.use_property_split = True
        mcol.enabled = item.cover_operation != "TEXTURE"

        mcol.prop(item, "cover_speed_mode")

        mcol.separator(type="LINE")

        row = mcol.row()
        row.prop(item, "cover_particle_speed_mode")
        row.enabled = item.cover_speed_mode == "PARTICLE"

        row = mcol.row()
        row.prop(item, "cover_particle_speed_fixed")
        row.enabled = (
            item.cover_speed_mode == "PARTICLE" and item.cover_particle_speed_mode == "FIXED"
        )

        row = mcol.row()
        draw_time_prop(row, item, "cover_time_cover")
        row.enabled = item.cover_speed_mode == "TIME"

        row = mcol.row()
        draw_time_prop(row, item, "cover_time_cover_var")
        row.enabled = item.cover_speed_mode == "TIME"

        mcol.separator(type="LINE")
        draw_time_prop(mcol, item, "cover_time_release")
        draw_time_prop(mcol, item, "cover_time_release_var")

    layout.separator(type="LINE")

    # Holding section
    box = layout.box()
    header = box.row()
    header.use_property_split = False
    header.prop(
        item,
        "cover_holding_expanded",
        icon="TRIA_DOWN" if item.cover_holding_expanded else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    header.label(text="Holding")

    if item.cover_holding_expanded:
        hcol = box.column()
        hcol.use_property_split = True
        hcol.enabled = item.cover_operation != "TEXTURE"

        hcol.prop(item, "cover_holding_mode")

        hcol.separator(type="LINE")

        # Attract mode properties
        row = hcol.row()
        row.prop(item, "cover_attract_mode")
        row.enabled = item.cover_holding_mode == "ATTRACT"

        row = hcol.row()
        row.prop(item, "cover_arrive_mode")
        row.enabled = item.cover_holding_mode == "ATTRACT"

        row = hcol.row()
        row.prop(item, "cover_attract_dist")
        row.enabled = item.cover_holding_mode == "ATTRACT" and item.cover_arrive_mode == "SLOWDOWN"

        row = hcol.row()
        row.prop(item, "cover_attract_min_speed")
        row.enabled = item.cover_holding_mode == "ATTRACT"

        row = hcol.row()
        row.prop(item, "cover_attract_max_speed")
        row.enabled = item.cover_holding_mode == "ATTRACT"

        hcol.separator(type="LINE")

        # Spring mode properties
        row = hcol.row()
        row.prop(item, "cover_spring_length")
        row.enabled = item.cover_holding_mode == "SPRING"

        row = hcol.row()
        row.prop(item, "cover_spring_stiffness")
        row.enabled = item.cover_holding_mode == "SPRING"

        row = hcol.row()
        row.prop(item, "cover_spring_damping")
        row.enabled = item.cover_holding_mode == "SPRING"

    layout.separator(type="LINE")

    # Braking section
    box = layout.box()
    header = box.row()
    header.use_property_split = False
    header.prop(
        item,
        "cover_braking_expanded",
        icon="TRIA_DOWN" if item.cover_braking_expanded else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    header.label(text="Braking")

    if item.cover_braking_expanded:
        bcol = box.column()
        bcol.use_property_split = True
        bcol.enabled = item.cover_speed_mode == "PARTICLE" and item.cover_operation != "TEXTURE"

        bcol.prop(item, "cover_use_braking")

        row = bcol.row()
        row.prop(item, "cover_braking_dist")
        row.enabled = item.cover_use_braking

        row = bcol.row()
        row.prop(item, "cover_braking_min_speed")
        row.enabled = item.cover_use_braking

        row = bcol.row()
        row.prop(item, "cover_braking_max_speed")
        row.enabled = item.cover_use_braking

        NexusCurve(item.id_data, f"braking_{item.curve_id}").draw_ui(
            bcol, "Braking", enabled=item.cover_use_braking
        )


def get_cover_ui_config():
    config = dict(NX_COVER_UI_CONFIG)
    config["cover_objects"]["draw_item_settings"] = draw_cover_item_settings
    return config


COVER_OBJECT_MODE_ENUM_MAP = {
    "SEQUENCE": "MODE_SEQUENCE",
    "NEAREST": "MODE_NEAREST",
    "FURTHEST": "MODE_FURTHEST",
    "INDEX": "MODE_INDEX",
    "RANDOM": "MODE_RAND",
}


SPEC = ModifierPropertySpec(
    modifier_type="NX_COVER",
    item_classes=(NexusCoverItem,),
    enum_builders=(build_cover_enum_items,),
    enum_defaults={"ID_NX_COVER_OBJECT_MODE": "SEQUENCE"},
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_COVER_OBJECT_MODE",
            prop=EnumProperty(
                name="Object Mode",
                description="How to assign objects to particles",
                items=_get_cover_object_mode_items,
            ),
            enum_map=COVER_OBJECT_MODE_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_COVER_INDEX",
            prop=IntProperty(
                name="Object Index",
                description="Index of the target object when mode is Index",
                default=0,
                min=0,
                soft_max=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_COVER_RANDOM_SEED",
            prop=IntProperty(
                name="Random Seed",
                description="Seed for random object assignment",
                default=0,
                min=0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_COVER_CYCLE",
            prop=BoolProperty(
                name="Cycle",
                description="Cycle through objects when all have been covered",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="cover_objects",
            prop=_cover_tree_props["cover_objects"],
        ),
        PropertyDescriptor(
            name="cover_objects_index",
            prop=_cover_tree_props["cover_objects_index"],
        ),
        PropertyDescriptor(
            name="cover_objects_drop_target",
            prop=_cover_tree_props.get("cover_objects_drop_target"),
            preset=False,
        ),
    ),
    nodetree_sync=combine_nodetree_sync(_COVER_OBJECTS),
)


# Scene-link list; not preset-captured. Cleanup-only so per-item braking
# curves are released on reset.
register_collection_cleanup(
    "NX_COVER",
    CollectionPresetSpec(
        collection_attr="cover_objects",
        curve_specs=COVER_BRAKING_CURVE_SPECS,
        suffix_attr="curve_id",
    ),
)
