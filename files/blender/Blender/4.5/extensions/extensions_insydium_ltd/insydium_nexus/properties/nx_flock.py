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
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)

from ..libs.cache_spec import CacheKind, CacheSpec
from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
    sync_enum_mapped,
    sync_params,
)
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform
from ..ui import NodeTreeDef, combine_nodetree_sync, make_allowed_types_poll

REACTOR_COLORS = {
    "PURSUIT": (0.42, 0.60, 0.92, 1.0),
    "FLEE": (0.94, 0.54, 0.31, 1.0),
    "ARRIVE": (0.84, 0.62, 1.0, 1.0),
    "ORBIT": (0.78, 0.92, 0.42, 1.0),
}


def _create_reactor_object(context, flock_obj, reaction_type):
    """Create a reactor Empty object parented to the flock modifier."""
    base_name = f"{flock_obj.name}.Reactor.{reaction_type.title()}"

    reactor = bpy.data.objects.new(base_name, None)
    reactor.empty_display_size = 0

    for collection in flock_obj.users_collection:
        collection.objects.link(reactor)
        break
    else:
        context.collection.objects.link(reactor)

    reactor.parent = flock_obj
    reactor.matrix_parent_inverse = flock_obj.matrix_world.inverted()

    reactor.location = (0, 2.5, 0)

    reactor["nexus_object_type"] = "NX_FLOCK_REACTOR"
    reactor["nexus_reactor_type"] = reaction_type
    reactor["nexus_reactor_color"] = REACTOR_COLORS.get(reaction_type, (1.0, 1.0, 1.0, 1.0))[:3]

    return reactor


def _remove_reactor_object(context, reactor_obj):
    if reactor_obj is None:
        return

    for collection in reactor_obj.users_collection:
        collection.objects.unlink(reactor_obj)

    bpy.data.objects.remove(reactor_obj, do_unlink=True)


def _on_flock_reaction_add(context, flock_obj, item):
    reactor = _create_reactor_object(context, flock_obj, item.item_type)
    item.reactor_object = reactor


def _on_flock_reaction_remove(context, flock_obj, item):
    if item.reactor_object:
        _remove_reactor_object(context, item.reactor_object)
        item.reactor_object = None


FLOCK_BEHAVIOR_DEFS = {
    "COHESION": {
        "name": "Cohesion",
        "description": "Move toward the center of nearby flock members",
        "icon_name": "nx_flock_behavior_cohesion",
        "blender_icon": "PIVOT_MEDIAN",
    },
    "SEPARATION": {
        "name": "Separation",
        "description": "Steer away from nearby flock members to avoid crowding",
        "icon_name": "nx_flock_behavior_separation",
        "blender_icon": "FULLSCREEN_EXIT",
    },
    "ALIGNMENT": {
        "name": "Alignment",
        "description": "Align velocity with nearby flock members",
        "icon_name": "nx_flock_behavior_alignment",
        "blender_icon": "ORIENTATION_GLOBAL",
    },
    "CHAOS": {
        "name": "Chaos",
        "description": "Add random turbulent motion",
        "icon_name": "nx_flock_behavior_chaos",
        "blender_icon": "MOD_NOISE",
    },
    "SWARMING": {
        "name": "Swarming",
        "description": "Happiness-based speed modulation for swarm behavior",
        "icon_name": "nx_flock_behavior_swarming",
        "blender_icon": "GROUP_VERTEX",
    },
}


_FLOCK_BEHAVIOR_ITEMS = []


def build_flock_enum_items():
    global _FLOCK_BEHAVIOR_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _FLOCK_BEHAVIOR_ITEMS = []

    for idx, (type_id, behavior_def) in enumerate(FLOCK_BEHAVIOR_DEFS.items()):
        icon_name = behavior_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _FLOCK_BEHAVIOR_ITEMS.append(
                (
                    type_id,
                    behavior_def["name"],
                    behavior_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = behavior_def.get("blender_icon", "NONE")
            _FLOCK_BEHAVIOR_ITEMS.append(
                (
                    type_id,
                    behavior_def["name"],
                    behavior_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "flock_behaviors",
        _FLOCK_BEHAVIOR_ITEMS,
        "flock_behaviors",
        "flock_behaviors_index",
    )


def _get_flock_behavior_items(self, context):
    return _FLOCK_BEHAVIOR_ITEMS


class NexusFlockBehaviorItem(bpy.types.PropertyGroup):
    """
    Union pattern PropertyGroup: all possible properties defined,
    appropriate ones shown based on item_type.
    """

    name: bpy.props.StringProperty(
        name="Name",
        description="Behavior name",
        default="",
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this behavior",
        default=True,
    )

    item_type: EnumProperty(
        name="Behavior Type",
        description="Type of flock behavior",
        items=_get_flock_behavior_items,
        default=0,  # Index-based default for callback enums
    )

    behavior_radius: FloatProperty(
        name="Radius",
        description="Search radius for nearby flock members",
        default=0.5,
        min=0.0,
        soft_max=20.0,
        unit="LENGTH",
    )

    behavior_strength: FloatProperty(
        name="Strength",
        description="Influence strength of this behavior",
        default=80.0,
        min=-100.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    behavior_use_periphery: BoolProperty(
        name="Use Periphery",
        description="Limit visibility to a view angle (periphery)",
        default=False,
    )

    behavior_periphery: FloatProperty(
        name="View Angle",
        description="Peripheral vision angle",
        default=radians(60.0),
        min=0.0,
        max=radians(360.0),
        subtype="ANGLE",
    )

    cohesion_option: EnumProperty(
        name="Cohesion Type",
        description="Method for calculating flock center",
        items=[
            ("POSITION", "Position", "Use geometric center of positions"),
            ("MASS", "Mass", "Use mass-weighted center"),
        ],
        default="POSITION",
    )

    chaos_scale: FloatProperty(
        name="Scale",
        description="Scale of the chaos noise pattern",
        default=200.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    chaos_frequency: FloatProperty(
        name="Frequency",
        description="Frequency of the chaos noise pattern",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        subtype="PERCENTAGE",
    )

    swarming_swapped: BoolProperty(
        name="Others Make Me Happy",
        description="Swap happiness calculation (crowded = happy)",
        default=False,
    )

    swarming_ratio: FloatProperty(
        name="Happiness Ratio",
        description="Percentage of happiness threshold",
        default=60.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    swarming_speed_happy: FloatProperty(
        name="Speed When Happy",
        description="Speed multiplier when happy",
        default=75.0,
        min=0.0,
        soft_max=500.0,
        subtype="PERCENTAGE",
    )

    swarming_speed_sad: FloatProperty(
        name="Speed When Unhappy",
        description="Speed multiplier when unhappy",
        default=125.0,
        min=0.0,
        soft_max=500.0,
        subtype="PERCENTAGE",
    )

    swarming_choice: EnumProperty(
        name="Swarming Type",
        description="Method for determining swarm membership",
        items=[
            ("EMITTER", "Emitter", "Consider particles from the same emitter"),
            ("GROUP", "Group", "Consider particles in the same group"),
            ("OBJECT", "Object", "Consider particles near a specific object"),
        ],
        default="EMITTER",
    )


def _draw_periphery_section(layout, item, prefix="behavior"):
    use_periphery_prop = f"{prefix}_use_periphery"
    periphery_prop = f"{prefix}_periphery"

    layout.separator(type="LINE")

    header = layout.row()
    header.use_property_split = False
    header.label(text="Periphery")

    col = layout.column()
    col.use_property_split = True
    col.prop(item, use_periphery_prop, text="Use Periphery")

    row = col.row()
    row.enabled = getattr(item, use_periphery_prop)
    row.prop(item, periphery_prop, text="View Angle")


def _draw_cohesion_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "cohesion_option")
    col.prop(item, "behavior_radius", text="Cohesion Radius")
    col.prop(item, "behavior_strength", text="Cohesion")

    _draw_periphery_section(col, item)


def _draw_separation_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "behavior_radius", text="Separation Radius")
    col.prop(item, "behavior_strength", text="Separation")

    _draw_periphery_section(col, item)


def _draw_alignment_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "behavior_radius", text="Align Radius")
    col.prop(item, "behavior_strength", text="Alignment")

    _draw_periphery_section(col, item)


def _draw_chaos_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "behavior_strength", text="Weight")
    col.prop(item, "chaos_scale", text="Scale")
    col.prop(item, "chaos_frequency", text="Frequency")


def _draw_swarming_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "swarming_swapped")
    col.prop(item, "behavior_radius", text="Radius")
    col.prop(item, "swarming_ratio")
    col.prop(item, "swarming_speed_happy")
    col.prop(item, "swarming_speed_sad")
    col.prop(item, "swarming_choice")

    _draw_periphery_section(col, item)


BEHAVIOR_DRAW_FUNCS = {
    "COHESION": _draw_cohesion_settings,
    "SEPARATION": _draw_separation_settings,
    "ALIGNMENT": _draw_alignment_settings,
    "CHAOS": _draw_chaos_settings,
    "SWARMING": _draw_swarming_settings,
}


def draw_flock_behavior_settings(layout, item):
    draw_func = BEHAVIOR_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown behavior type", icon="ERROR")


FLOCK_REACTION_DEFS = {
    "PURSUIT": {
        "name": "Pursuit",
        "description": "Pursue and chase a target",
        "icon_name": "nx_flock_reaction_pursuit",
        "blender_icon": "TRACKING_FORWARDS",
    },
    "FLEE": {
        "name": "Flee",
        "description": "Flee away from a target",
        "icon_name": "nx_flock_reaction_flee",
        "blender_icon": "TRACKING_BACKWARDS",
    },
    "ARRIVE": {
        "name": "Arrive",
        "description": "Slow down when arriving at target",
        "icon_name": "nx_flock_reaction_arrive",
        "blender_icon": "SNAP_VERTEX",
    },
    "ORBIT": {
        "name": "Orbit",
        "description": "Orbit around a target",
        "icon_name": "nx_flock_reaction_orbit",
        "blender_icon": "ORIENTATION_GIMBAL",
    },
}


_FLOCK_REACTION_ITEMS = []


def build_flock_reaction_enum_items():
    global _FLOCK_REACTION_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _FLOCK_REACTION_ITEMS = []

    for idx, (type_id, reaction_def) in enumerate(FLOCK_REACTION_DEFS.items()):
        icon_name = reaction_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _FLOCK_REACTION_ITEMS.append(
                (
                    type_id,
                    reaction_def["name"],
                    reaction_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = reaction_def.get("blender_icon", "NONE")
            _FLOCK_REACTION_ITEMS.append(
                (
                    type_id,
                    reaction_def["name"],
                    reaction_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "flock_reactions",
        _FLOCK_REACTION_ITEMS,
        "flock_reactions",
        "flock_reactions_index",
        on_add=_on_flock_reaction_add,
        on_remove=_on_flock_reaction_remove,
        child_pointer_prop="reactor_object",
    )


def _get_flock_reaction_items(self, context):
    return _FLOCK_REACTION_ITEMS


class NexusFlockReactionItem(bpy.types.PropertyGroup):
    """
    Union pattern PropertyGroup: all possible properties defined,
    appropriate ones shown based on item_type.
    """

    name: bpy.props.StringProperty(
        name="Name",
        description="Reaction name",
        default="",
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this reaction",
        default=True,
    )

    item_type: EnumProperty(
        name="Reaction Type",
        description="Type of flock reaction",
        items=_get_flock_reaction_items,
        default=0,
    )

    reactor_object: PointerProperty(
        name="Reactor Object",
        type=bpy.types.Object,
        description="The Empty object representing this reaction's position",
    )

    reactor_display: EnumProperty(
        name="Display",
        items=[
            ("CROSS", "Cross", "Display as cross/axes"),
            ("SPHERE", "Sphere", "Display as sphere"),
            ("BOX", "Box", "Display as box"),
            ("NONE", "None", "No display"),
        ],
        default="SPHERE",
    )

    reactor_settings_expanded: BoolProperty(
        name="Settings",
        description="Expand reactor-specific settings",
        default=True,
    )

    pursuit_target: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Target object to pursue",
    )

    flee_target: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Target object to flee from",
    )

    arrive_target: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Target object to arrive at",
    )

    orbit_target: PointerProperty(
        name="Target",
        type=bpy.types.Object,
        description="Target object to orbit around",
    )

    reaction_weight: FloatProperty(
        name="Weight",
        description="Influence weight of this reaction",
        default=10.0,
        min=0.0,
        soft_max=1000.0,
        subtype="PERCENTAGE",
    )

    reaction_activation_mode: EnumProperty(
        name="Activation",
        description="How the reaction is activated",
        items=[
            ("DISTANCE", "Distance", "Activate based on distance to target"),
            ("INFINITE", "Infinite", "Always active regardless of distance"),
        ],
        default="INFINITE",
    )

    reaction_activation_distance: FloatProperty(
        name="Distance",
        description="Activation distance from target",
        default=0.5,
        min=0.0,
        soft_max=100.0,
        unit="LENGTH",
    )

    reaction_timing_mode: EnumProperty(
        name="Timing",
        description="When the reaction is active",
        items=[
            ("ALWAYS", "Always", "Always active"),
            ("BEFORE", "Before", "Active before a specific frame"),
            ("AFTER", "After", "Active after a specific frame"),
            ("ON", "On", "Active only on a specific frame"),
            ("PULSE", "Pulse", "Periodic activation"),
            ("BETWEEN", "Between", "Active between two frames"),
        ],
        default="ALWAYS",
    )

    reaction_timing_frame1: FloatProperty(
        name="Frame 1",
        description="First timing frame",
        default=1.0,
    )

    reaction_timing_frame2: FloatProperty(
        name="Frame 2",
        description="Second timing frame (for Between mode)",
        default=100.0,
    )

    pursuit_type: EnumProperty(
        name="Target Type",
        description="How to determine the pursuit target",
        items=[
            ("STATIC_POS", "Static Position", "Pursue a fixed position"),
            ("CENTER_POS", "Center Position", "Pursue the center position of targets"),
            ("CENTER_MASS", "Center of Mass", "Pursue the center of mass"),
            ("NEAREST", "Nearest", "Pursue the nearest target"),
        ],
        default="STATIC_POS",
    )

    pursuit_mode: EnumProperty(
        name="Mode",
        description="Source for pursuit targets",
        items=[
            ("EMITTER", "Emitter", "Use particles from emitter"),
            ("GROUP", "Group", "Use particles from group"),
        ],
        default="EMITTER",
    )

    pursuit_offset: FloatVectorProperty(
        name="Offset",
        description="Offset from target position",
        default=(0.0, 0.0, 0.0),
        subtype="TRANSLATION",
        unit="LENGTH",
    )

    pursuit_distance: FloatProperty(
        name="Stop Distance",
        description="Distance at which to stop pursuing",
        default=0.5,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    flee_type: EnumProperty(
        name="Target Type",
        description="How to determine the flee target",
        items=[
            ("STATIC_POS", "Static Position", "Flee from a fixed position"),
            ("CENTER_POS", "Center Position", "Flee from center position"),
            ("CENTER_MASS", "Center of Mass", "Flee from center of mass"),
            ("NEAREST", "Nearest", "Flee from nearest target"),
        ],
        default="STATIC_POS",
    )

    flee_mode: EnumProperty(
        name="Mode",
        description="Source for flee targets",
        items=[
            ("EMITTER", "Emitter", "Use particles from emitter"),
            ("GROUP", "Group", "Use particles from group"),
        ],
        default="EMITTER",
    )

    flee_offset: FloatVectorProperty(
        name="Offset",
        description="Offset from target position",
        default=(0.0, 0.0, 0.0),
        subtype="TRANSLATION",
        unit="LENGTH",
    )

    flee_distance: FloatProperty(
        name="Safe Distance",
        description="Distance at which to stop fleeing",
        default=0.5,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    arrive_speed: FloatProperty(
        name="Arrival Speed",
        description="Speed when arriving at target",
        default=0.5,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    orbit_strength: FloatProperty(
        name="Orbit Strength",
        description="Strength of orbital motion",
        default=0.1,
        min=0.0,
        soft_max=10.0,
    )


def _draw_reaction_common_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "reactor_display", text="Display")

    col.separator(type="LINE")

    col.prop(item, "reaction_weight", text="Reactions Weight")

    col.separator(type="LINE")

    col.prop(item, "reaction_activation_mode", text="Activation Range")

    row = col.row()
    row.enabled = item.reaction_activation_mode == "DISTANCE"
    row.prop(item, "reaction_activation_distance")

    col.separator(type="LINE")

    col.prop(item, "reaction_timing_mode")

    row = col.row()
    row.enabled = item.reaction_timing_mode in (
        "BEFORE",
        "AFTER",
        "ON",
        "PULSE",
        "BETWEEN",
    )
    row.prop(item, "reaction_timing_frame1", text="At Frame")

    row = col.row()
    row.enabled = item.reaction_timing_mode == "BETWEEN"
    row.prop(item, "reaction_timing_frame2", text="To Frame")


def _draw_pursuit_settings(layout, item):
    _draw_reaction_common_settings(layout, item)

    layout.separator(type="LINE")

    box = layout.box()
    header = box.row()
    header.use_property_split = False
    icon = "TRIA_DOWN" if item.reactor_settings_expanded else "TRIA_RIGHT"
    header.prop(item, "reactor_settings_expanded", icon=icon, icon_only=True, emboss=False)
    header.label(text="Pursuit")

    if item.reactor_settings_expanded:
        col = box.column()
        col.use_property_split = True

        col.prop(item, "pursuit_type")

        row = col.row()
        row.enabled = item.pursuit_type != "STATIC_POS"
        row.prop(item, "pursuit_mode")

        row = col.row()
        row.enabled = item.pursuit_type != "STATIC_POS"
        row.prop(item, "pursuit_target", text="Target")

        row = col.row()
        row.enabled = False  # Offset only enabled for FIRST/LAST which aren't in UI
        row.prop(item, "pursuit_offset")

        row = col.row()
        row.enabled = item.pursuit_type == "NEAREST"
        row.prop(item, "pursuit_distance", text="Distance")


def _draw_flee_settings(layout, item):
    _draw_reaction_common_settings(layout, item)

    layout.separator(type="LINE")

    box = layout.box()
    header = box.row()
    header.use_property_split = False
    icon = "TRIA_DOWN" if item.reactor_settings_expanded else "TRIA_RIGHT"
    header.prop(item, "reactor_settings_expanded", icon=icon, icon_only=True, emboss=False)
    header.label(text="Flee")

    if item.reactor_settings_expanded:
        col = box.column()
        col.use_property_split = True

        col.prop(item, "flee_type")

        row = col.row()
        row.enabled = item.flee_type != "STATIC_POS"
        row.prop(item, "flee_mode")

        row = col.row()
        row.enabled = item.flee_type != "STATIC_POS"
        row.prop(item, "flee_target", text="Target")

        row = col.row()
        row.enabled = False  # Offset only enabled for FIRST/LAST which aren't in UI
        row.prop(item, "flee_offset")

        row = col.row()
        row.enabled = item.flee_type == "NEAREST"
        row.prop(item, "flee_distance", text="Distance")


def _draw_arrive_settings(layout, item):
    _draw_reaction_common_settings(layout, item)

    layout.separator(type="LINE")

    box = layout.box()
    header = box.row()
    header.use_property_split = False
    icon = "TRIA_DOWN" if item.reactor_settings_expanded else "TRIA_RIGHT"
    header.prop(item, "reactor_settings_expanded", icon=icon, icon_only=True, emboss=False)
    header.label(text="Arrive")

    if item.reactor_settings_expanded:
        col = box.column()
        col.use_property_split = True

        col.prop(item, "arrive_target", text="Target")
        col.prop(item, "arrive_speed", text="Speed")


def _draw_orbit_settings(layout, item):
    _draw_reaction_common_settings(layout, item)

    layout.separator(type="LINE")

    box = layout.box()
    header = box.row()
    header.use_property_split = False
    icon = "TRIA_DOWN" if item.reactor_settings_expanded else "TRIA_RIGHT"
    header.prop(item, "reactor_settings_expanded", icon=icon, icon_only=True, emboss=False)
    header.label(text="Orbit")

    if item.reactor_settings_expanded:
        col = box.column()
        col.use_property_split = True

        col.prop(item, "orbit_target", text="Target")
        col.prop(item, "orbit_strength", text="Strength")


REACTION_DRAW_FUNCS = {
    "PURSUIT": _draw_pursuit_settings,
    "FLEE": _draw_flee_settings,
    "ARRIVE": _draw_arrive_settings,
    "ORBIT": _draw_orbit_settings,
}


def draw_flock_reaction_settings(layout, item):
    draw_func = REACTION_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown reaction type", icon="ERROR")


class NexusFlockAvoidanceItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object", type=bpy.types.Object, poll=make_allowed_types_poll(["MESH"])
    )
    enabled: BoolProperty(name="Enabled", default=True)


_BEHAVIOR_NODE_IDS = {
    "COHESION": "ID_NX_BEHAVIOUR_COHESION",
    "SEPARATION": "ID_NX_BEHAVIOUR_SEPARATION",
    "ALIGNMENT": "ID_NX_BEHAVIOUR_ALIGNMENT",
    "CHAOS": "ID_NX_BEHAVIOUR_CHAOS",
    "SWARMING": "ID_NX_BEHAVIOUR_SWARMING",
}

_REACTOR_TYPE_IDS = {
    "PURSUIT": "ID_NX_FLOCK_REACTOR_TYPE_PURSUIT",
    "FLEE": "ID_NX_FLOCK_REACTOR_TYPE_FLEE",
    "ARRIVE": "ID_NX_FLOCK_REACTOR_TYPE_ARRIVE",
    "ORBIT": "ID_NX_FLOCK_REACTOR_TYPE_ORBIT",
}

_COHESION_OPTION_IDS = {
    "POSITION": "ID_NX_FLOCK_COHESION_OPTION_POSITION",
    "MASS": "ID_NX_FLOCK_COHESION_OPTION_MASS",
}

_SWARMING_CHOICE_IDS = {
    "EMITTER": "ID_NX_FLOCK_SWARMING_CHOICE_EMITTER",
    "GROUP": "ID_NX_FLOCK_SWARMING_CHOICE_GROUP",
    "OBJECT": "ID_NX_FLOCK_SWARMING_CHOICE_OBJECT",
}

_REACTOR_ACTIVATION_IDS = {
    "INFINITE": "ID_NX_FLOCK_REACTOR_ACTIVATION_MODE_INFINITE",
    "DISTANCE": "ID_NX_FLOCK_REACTOR_ACTIVATION_MODE_DISTANCE",
}

_REACTOR_TIMING_IDS = {
    "ALWAYS": "ID_NX_FLOCK_REACTOR_TIMING_MODE_ALWAYS",
    "BEFORE": "ID_NX_FLOCK_REACTOR_TIMING_MODE_BEFORE",
    "AFTER": "ID_NX_FLOCK_REACTOR_TIMING_MODE_AFTER",
    "ON": "ID_NX_FLOCK_REACTOR_TIMING_MODE_ON",
    "PULSE": "ID_NX_FLOCK_REACTOR_TIMING_MODE_PULSE",
    "BETWEEN": "ID_NX_FLOCK_REACTOR_TIMING_MODE_BETWEEN",
}

_REACTOR_DISPLAY_IDS = {
    "CROSS": "ID_NX_FLOCK_REACTOR_DISPLAY_CROSS",
    "BOX": "ID_NX_FLOCK_REACTOR_DISPLAY_BOX",
    "SPHERE": "ID_NX_FLOCK_REACTOR_DISPLAY_SPHERE",
    "NONE": "ID_NX_FLOCK_REACTOR_DISPLAY_NONE",
}

_flock_avoidance_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

FLOCK_AVOIDANCE_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="flock_avoidance_objects",
    cache_dict=_flock_avoidance_poly_cache,
)

_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]
_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]


def _half_periphery(value, item, _obj, _scene, _depsgraph):
    return value * 0.5 if item.behavior_use_periphery else 0.0


def _frame_to_seconds(value, _item, _obj, scene, _depsgraph):
    fps = scene.render.fps if scene is not None else 24.0
    return value / fps


_COHESION_PARAM_SPECS = (
    SyncSpec.param("float", "behavior_radius", "ID_NX_FLOCK_COHESION_RADIUS", scale=_unit),
    SyncSpec.param("float", "behavior_strength", "ID_NX_FLOCK_COHESION_STRENGTH", scale=_pct),
    SyncSpec.param("bool", "behavior_use_periphery", "ID_NX_FLOCK_COHESION_USE_PERIPHERY"),
    SyncSpec.param(
        "float",
        "behavior_periphery",
        "ID_NX_FLOCK_COHESION_PERIPHERY",
        transform=_half_periphery,
    ),
)

_SEPARATION_PARAM_SPECS = (
    SyncSpec.param("float", "behavior_radius", "ID_NX_FLOCK_SEPARATION_RADIUS", scale=_unit),
    SyncSpec.param("float", "behavior_strength", "ID_NX_FLOCK_SEPARATION_STRENGTH", scale=_pct),
    SyncSpec.param("bool", "behavior_use_periphery", "ID_NX_FLOCK_SEPARATION_USE_PERIPHERY"),
    SyncSpec.param(
        "float",
        "behavior_periphery",
        "ID_NX_FLOCK_SEPARATION_PERIPHERY",
        transform=_half_periphery,
    ),
)

_ALIGNMENT_PARAM_SPECS = (
    SyncSpec.param("float", "behavior_radius", "ID_NX_FLOCK_ALIGN_RADIUS", scale=_unit),
    SyncSpec.param("float", "behavior_strength", "ID_NX_FLOCK_ALIGN_STRENGTH", scale=_pct),
    SyncSpec.param("bool", "behavior_use_periphery", "ID_NX_FLOCK_ALIGNMENT_USE_PERIPHERY"),
    SyncSpec.param(
        "float",
        "behavior_periphery",
        "ID_NX_FLOCK_ALIGNMENT_PERIPHERY",
        transform=_half_periphery,
    ),
)

_CHAOS_PARAM_SPECS = (
    SyncSpec.param("float", "behavior_strength", "ID_NX_FLOCK_CHAOS_STRENGTH", scale=_pct),
    SyncSpec.param("float", "chaos_scale", "ID_NX_FLOCK_CHAOS_SCALE", scale=_pct),
    SyncSpec.param("float", "chaos_frequency", "ID_NX_FLOCK_CHAOS_FREQUENCY", scale=_pct),
)

_SWARMING_PARAM_SPECS = (
    SyncSpec.param("bool", "swarming_swapped", "ID_NX_FLOCK_SWARMING_SWAPPED"),
    SyncSpec.param("float", "behavior_radius", "ID_NX_FLOCK_SWARMING_RADIUS", scale=_unit),
    SyncSpec.param("float", "swarming_ratio", "ID_NX_FLOCK_SWARMING_RATIO", scale=_pct),
    SyncSpec.param(
        "float", "swarming_speed_happy", "ID_NX_FLOCK_SWARMING_SPEED_HAPPY", scale=_pct
    ),
    SyncSpec.param("float", "swarming_speed_sad", "ID_NX_FLOCK_SWARMING_SPEED_SAD", scale=_pct),
    SyncSpec.param("bool", "behavior_use_periphery", "ID_NX_FLOCK_SWARMING_USE_PERIPHERY"),
    SyncSpec.param(
        "float",
        "behavior_periphery",
        "ID_NX_FLOCK_SWARMING_PERIPHERY",
        transform=_half_periphery,
    ),
)

_REACTOR_COMMON_PARAM_SPECS = (
    SyncSpec.param("float", "reaction_weight", "ID_NX_FLOCK_REACTOR_WEIGHT", scale=_pct),
    SyncSpec.param(
        "enum",
        "reaction_activation_mode",
        "ID_NX_FLOCK_REACTOR_ACTIVATION_MODE",
        enum_map=_REACTOR_ACTIVATION_IDS,
    ),
    SyncSpec.param(
        "float",
        "reaction_activation_distance",
        "ID_NX_FLOCK_REACTOR_ACTIVATION_DISTANCE",
        scale=_unit,
    ),
    SyncSpec.param(
        "enum",
        "reaction_timing_mode",
        "ID_NX_FLOCK_REACTOR_TIMING_MODE",
        enum_map=_REACTOR_TIMING_IDS,
    ),
    SyncSpec.param(
        "float",
        "reaction_timing_frame1",
        "ID_NX_FLOCK_REACTOR_TIMING_MODE_TIME1",
        transform=_frame_to_seconds,
    ),
    SyncSpec.param(
        "float",
        "reaction_timing_frame2",
        "ID_NX_FLOCK_REACTOR_TIMING_MODE_TIME2",
        transform=_frame_to_seconds,
    ),
    SyncSpec.param(
        "enum", "reactor_display", "ID_NX_FLOCK_REACTOR_DISPLAY", enum_map=_REACTOR_DISPLAY_IDS
    ),
    SyncSpec.param("enum", "item_type", "ID_NX_FLOCK_REACTOR_TYPE", enum_map=_REACTOR_TYPE_IDS),
)

_PURSUIT_PARAM_SPECS = (
    SyncSpec.param("float", "pursuit_distance", "ID_NX_FLOCK_REACTOR_PURSUIT_DIST", scale=_unit),
    SyncSpec.param("vector", "pursuit_offset", "ID_NX_FLOCK_REACTOR_PURSUIT_OFFSET", scale=_unit),
)

_FLEE_PARAM_SPECS = (
    SyncSpec.param("float", "flee_distance", "ID_NX_FLOCK_REACTOR_FLEE_DIST", scale=_unit),
    SyncSpec.param("vector", "flee_offset", "ID_NX_FLOCK_REACTOR_FLEE_OFFSET", scale=_unit),
)

_ARRIVE_PARAM_SPECS = (
    SyncSpec.param("float", "arrive_speed", "ID_NX_FLOCK_REACTOR_ARRIVE_SPEED", scale=_unit),
)

_ORBIT_PARAM_SPECS = (
    SyncSpec.param("float", "orbit_strength", "ID_NX_FLOCK_REACTOR_ORBIT_SPEED"),
)


def _sync_cohesion(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _COHESION_PARAM_SPECS)
    sync_enum_mapped(
        theron,
        get,
        nc,
        "ID_NX_FLOCK_COHESION_OPTION",
        item.cohesion_option,
        _COHESION_OPTION_IDS,
    )


def _sync_separation(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _SEPARATION_PARAM_SPECS)


def _sync_alignment(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _ALIGNMENT_PARAM_SPECS)


def _sync_chaos(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _CHAOS_PARAM_SPECS)


def _sync_swarming(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _SWARMING_PARAM_SPECS)
    sync_enum_mapped(
        theron,
        get,
        nc,
        "ID_NX_FLOCK_SWARMING_CHOICE",
        item.swarming_choice,
        _SWARMING_CHOICE_IDS,
    )


FLOCK_BEHAVIOR_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_FLOCK_TREE",
    collection_attr="flock_behaviors",
    type_id_map=_BEHAVIOR_NODE_IDS,
    per_type_syncers={
        "COHESION": _sync_cohesion,
        "SEPARATION": _sync_separation,
        "ALIGNMENT": _sync_alignment,
        "CHAOS": _sync_chaos,
        "SWARMING": _sync_swarming,
    },
)


def _sync_reactor_common(theron, get, nc, item, item_orig, _obj, scene, _depsgraph):
    sync_params(
        theron,
        get,
        nc,
        item,
        _REACTOR_COMMON_PARAM_SPECS,
        scene=scene,
        depsgraph=_depsgraph,
    )

    reactor_obj = item_orig.reactor_object
    if reactor_obj is not None:
        pos = reactor_obj.matrix_world.translation
        theron.set_vector(
            nc,
            get("ID_NX_FLOCK_OBJECT_GROUP"),
            pos.x * _unit,
            pos.y * _unit,
            pos.z * _unit,
        )


def _sync_pursuit(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _PURSUIT_PARAM_SPECS)


def _sync_flee(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _FLEE_PARAM_SPECS)


def _sync_arrive(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _ARRIVE_PARAM_SPECS)


def _sync_orbit(theron, get, nc, item, _item_orig, _obj):
    sync_params(theron, get, nc, item, _ORBIT_PARAM_SPECS)


_REACTOR_PER_TYPE = {
    "PURSUIT": _sync_pursuit,
    "FLEE": _sync_flee,
    "ARRIVE": _sync_arrive,
    "ORBIT": _sync_orbit,
}


FLOCK_REACTOR_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_FLOCK_REACTOR_TREE",
    collection_attr="flock_reactions",
    type_id_map=_REACTOR_TYPE_IDS,
    pre_dispatch_syncer_ctx=_sync_reactor_common,
    per_type_syncers=_REACTOR_PER_TYPE,
)


_flock_avoidance_links = make_cached_link_resolver(poly_spec=FLOCK_AVOIDANCE_POLY_SPEC)


FLOCK_AVOIDANCE_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_FLOCK_AVOIDGEO_TREE",
    collection_attr="flock_avoidance_objects",
    pre_syncer=_flock_avoidance_links.pre_syncer,
    post_syncer=_flock_avoidance_links.post_syncer,
    node_link_resolver=_flock_avoidance_links.node_link_resolver,
    skip_if_no_link=True,
)
_FLOCK_AVOIDANCE_OBJECTS = NodeTreeDef(
    "Geometry",
    item_type=NexusFlockAvoidanceItem,
    allowed_types=["MESH"],
    nodetree_sync=FLOCK_AVOIDANCE_TREE_SPEC,
)


_avoidance_tree_props = _FLOCK_AVOIDANCE_OBJECTS.properties("flock_avoidance_objects")


NX_FLOCK_UI_CONFIG = {
    "ID_NX_FLOCK_NATLIMITS_ANGLE": {"use_property_split": True},
    "ID_NX_FLOCK_NATLIMITS_LERP": {"use_property_split": True},
    **_FLOCK_AVOIDANCE_OBJECTS.ui_config("flock_avoidance_objects"),
}


def get_flock_ui_config():
    config = dict(NX_FLOCK_UI_CONFIG)

    config["flock_behaviors"] = {
        "type": "nodetree",
        "index_prop": "flock_behaviors_index",
        "label": "Behaviors",
        "draw_item_settings": draw_flock_behavior_settings,
        "menu_id": "flock_behaviors",
    }

    config["flock_reactions"] = {
        "type": "nodetree",
        "index_prop": "flock_reactions_index",
        "label": "Reactions",
        "draw_item_settings": draw_flock_reaction_settings,
        "menu_id": "flock_reactions",
    }

    return config


def add_default_behaviors(props):
    from ..utils import generate_unique_name

    default_behaviors = ["COHESION", "SEPARATION", "ALIGNMENT", "CHAOS"]

    for behavior_type in default_behaviors:
        item = props.flock_behaviors.add()
        item.item_type = behavior_type
        item.enabled = True

        behavior_def = FLOCK_BEHAVIOR_DEFS.get(behavior_type, {})
        base_name = behavior_def.get("name", behavior_type)
        existing_names = [i.name for i in props.flock_behaviors if i.name]
        item.name = generate_unique_name(base_name, existing_names)

        if behavior_type == "COHESION":
            item.behavior_radius = 0.5
            item.behavior_strength = 25.0
            item.behavior_periphery = radians(90.0)
        elif behavior_type == "SEPARATION":
            item.behavior_radius = 0.25
            item.behavior_strength = 80.0
            item.behavior_use_periphery = True
        elif behavior_type == "ALIGNMENT":
            item.behavior_radius = 0.2
            item.behavior_strength = 1.0
            item.behavior_use_periphery = True
        elif behavior_type == "CHAOS":
            item.behavior_strength = 100.0
            item.chaos_scale = 200.0
            item.chaos_frequency = 100.0

    props.flock_behaviors_index = 0


SPEC = ModifierPropertySpec(
    modifier_type="NX_FLOCK",
    item_classes=(
        NexusFlockBehaviorItem,
        NexusFlockReactionItem,
        NexusFlockAvoidanceItem,
    ),
    enum_builders=(build_flock_enum_items, build_flock_reaction_enum_items),
    enum_defaults={
        "flock_tab": "BEHAVIORS",
        "ID_NX_FLOCK_AVOIDGEO_MODE": "SOFT",
        "reaction_activation_mode": "INFINITE",
        "reaction_timing_mode": "ALWAYS",
        "pursuit_type": "STATIC_POS",
        "pursuit_mode": "EMITTER",
        "flee_type": "STATIC_POS",
        "flee_mode": "EMITTER",
    },
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_FLOCK_WEIGHT",
            prop=FloatProperty(
                name="Weight",
                description="Overall weight of the flock modifier",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_MIN_SPEED",
            prop=FloatProperty(
                name="Min Speed",
                description="Minimum particle speed",
                default=0.0,
                min=0.0,
                soft_max=20.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_MAX_SPEED",
            prop=FloatProperty(
                name="Max Speed",
                description="Maximum particle speed",
                default=1.5,
                min=0.0,
                soft_max=20.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_NATLIMITS_ENABLED",
            prop=BoolProperty(
                name="Enable Natural Limits",
                description="Limit maximum turning angle per step",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_NATLIMITS_ANGLE",
            prop=FloatProperty(
                name="Maximum Angle",
                description="Maximum turning angle per step",
                default=radians(90.0),
                min=0.0,
                max=radians(360.0),
                subtype="ANGLE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_NATLIMITS_LERP",
            prop=FloatProperty(
                name="Blend Percentage",
                description="Blend factor when angle exceeds limit",
                default=85.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="flock_tab",
            prop=EnumProperty(
                name="Flock Section",
                description="Active flock section",
                items=[
                    ("BEHAVIORS", "Behaviors", "Flock behavior settings"),
                    ("REACTIONS", "Reactions", "Flock reaction settings"),
                    ("AVOIDANCE", "Avoidance", "Geometry avoidance settings"),
                ],
                default="BEHAVIORS",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_AVOIDGEO_WEIGHT",
            prop=FloatProperty(
                name="Weight",
                description="Weight of geometry avoidance",
                default=100.0,
                min=0.0,
                soft_max=1000.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_AVOIDGEO_DIST",
            prop=FloatProperty(
                name="Distance",
                description="Avoidance distance from geometry",
                default=0.5,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_FLOCK_AVOIDGEO_MODE",
            prop=EnumProperty(
                name="Mode",
                description="Avoidance mode",
                items=[
                    ("SOFT", "Soft", "Soft avoidance - gradually deflect"),
                    ("HARD", "Hard", "Hard avoidance - immediate deflection"),
                ],
                default="SOFT",
            ),
            enum_map={
                "SOFT": "ID_NX_FLOCK_AVOIDGEO_MODE_SOFT",
                "HARD": "ID_NX_FLOCK_AVOIDGEO_MODE_HARD",
            },
        ),
        PropertyDescriptor(
            name="flock_behaviors",
            prop=CollectionProperty(
                name="Behaviors",
                type=NexusFlockBehaviorItem,
            ),
        ),
        PropertyDescriptor(
            name="flock_behaviors_index",
            prop=IntProperty(
                name="Active Behavior Index",
                default=0,
                min=0,
            ),
        ),
        PropertyDescriptor(
            name="flock_reactions",
            prop=CollectionProperty(
                name="Reactions",
                type=NexusFlockReactionItem,
            ),
        ),
        PropertyDescriptor(
            name="flock_reactions_index",
            prop=IntProperty(
                name="Active Reaction Index",
                default=0,
                min=0,
            ),
        ),
        PropertyDescriptor(
            name="flock_avoidance_objects",
            prop=_avoidance_tree_props["flock_avoidance_objects"],
        ),
        PropertyDescriptor(
            name="flock_avoidance_objects_index",
            prop=_avoidance_tree_props["flock_avoidance_objects_index"],
        ),
        PropertyDescriptor(
            name="flock_avoidance_objects_drop_target",
            prop=_avoidance_tree_props.get("flock_avoidance_objects_drop_target"),
            preset=False,
        ),
    ),
    nodetree_sync=combine_nodetree_sync(
        FLOCK_BEHAVIOR_TREE_SPEC,
        FLOCK_REACTOR_TREE_SPEC,
        _FLOCK_AVOIDANCE_OBJECTS,
    ),
)


# `flock_avoidance_objects` is a pure scene-link list and is intentionally
# excluded from preset capture — it carries no per-item config payload.
register_collection_preset(
    "NX_FLOCK",
    CollectionPresetSpec(
        collection_attr="flock_behaviors",
        menu_id="flock_behaviors",
    ),
)


# Reactor target lives on `reactor_object.matrix_world`, which preset apply
# can't restore. Drop every row; registration stays so apply/INSYDIUM Default
# still fire `on_remove` to clean up stale reactor helpers.
def _flock_reaction_drop(_item_or_data) -> bool:
    return False


register_collection_preset(
    "NX_FLOCK",
    CollectionPresetSpec(
        collection_attr="flock_reactions",
        menu_id="flock_reactions",
        item_capture_condition=_flock_reaction_drop,
        item_apply_condition=_flock_reaction_drop,
    ),
)
