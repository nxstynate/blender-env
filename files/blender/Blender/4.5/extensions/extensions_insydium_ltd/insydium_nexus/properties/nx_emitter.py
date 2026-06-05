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

import ctypes
import math

import bpy
import numpy as np
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)

from ..libs.cache_spec import (
    CacheKind,
    CacheSpec,
)
from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    AliasSpec,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nexus_time import nexus_time_property
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
    sync_enum_mapped,
    sync_params,
)
from ..libs.theron_sync import SyncSpec, SyncType, Transform
from ..ui import NodeTreeDef, combine_nodetree_sync, make_allowed_types_poll

NX_EMITTER_UI_CONFIG = {}

_SHAPE_ITEMS = []
_EMIT_TYPE_ITEMS = []

_ORIENTATION_ITEMS = [
    ("X_POS", "X+", "Emit in positive X direction", "", 0),
    ("X_NEG", "X-", "Emit in negative X direction", "", 1),
    ("Y_POS", "Y+", "Emit in positive Y direction", "", 2),
    ("Y_NEG", "Y-", "Emit in negative Y direction", "", 3),
    ("Z_POS", "Z+", "Emit in positive Z direction", "", 4),
    ("Z_NEG", "Z-", "Emit in negative Z direction", "", 5),
]

_SHOT_MODE_ITEMS = []
_DISPLAY_SHAPE_ITEMS = []

_COLOR_MODE_ITEMS = [
    ("SINGLE", "Single Color", "Use a single color for all particles", 0),
    ("GRADIENT", "Gradient", "Use a gradient to color particles", 1),
    ("SHADER", "Shader", "Use shader to color particles", 2),
    ("OBJECT", "Object Color", "Use object colors for particles", 3),
    ("NOISE", "Noise", "Use noise to color particles at birth", 4),
]

_NOISE_TYPE_ITEMS = [
    ("SIMPLEX", "Simplex", "Simplex noise", 0),
    ("FBM", "FBM", "Fractional Brownian Motion noise", 1),
    ("TURBULENCE", "Turbulence", "Turbulence noise", 2),
    ("WAVY_TURBULENCE", "Wavy Turbulence", "Wavy turbulence noise", 3),
    ("VORONOISE", "VoroNoise", "Voronoi noise", 4),
    ("CUBIC", "Cubic", "Cubic noise", 5),
]

_NOISE_CHANNEL_ITEMS = [
    ("GRADIENT", "Gradient", "Use gradient to map noise to color", 0),
    ("NOISE", "Noise", "Use noise directly for RGB channels", 1),
]

_GRADIENT_PARAMETER_ITEMS = [
    ("", "Particle", "", "OUTLINER_OB_POINTCLOUD", 0),
    ("AGE", "Age", "Color based on particle age", 0),
    ("SPEED", "Speed", "Color based on particle speed", 1),
    ("SPEED_WORLD", "Speed (World)", "Color based on world-space speed", 2),
    ("RADIUS", "Radius", "Color based on particle radius", 3),
    ("", "Fluid", "", "MOD_FLUIDSIM", 0),
    ("FLUID_DENSITY", "Fluid Density", "Color based on fluid density", 4),
    (
        "FLUID_DENSITY_VELOCITY",
        "Fluid Density/Velocity",
        "Color based on fluid density velocity",
        5,
    ),
    ("GRANULAR", "Granular", "Color based on granular value", 6),
    ("FLUID_SURFACE", "Fluid Surface", "Color based on fluid surface proximity", 7),
    ("", "Physical", "", "MOD_PHYSICS", 0),
    ("MASS", "Mass", "Color based on particle mass", 8),
    ("TEMPERATURE", "Temperature", "Color based on temperature", 9),
    ("SMOKE", "Smoke", "Color based on smoke density", 10),
    ("FIRE", "Fire", "Color based on fire intensity", 11),
    ("FUEL", "Fuel", "Color based on fuel amount", 12),
    ("", "Spatial", "", "ORIENTATION_GLOBAL", 0),
    ("DISTANCE_TRAVELED", "Distance Traveled", "Color based on distance traveled", 13),
    ("DIRECTION", "Direction", "Color based on velocity direction", 14),
    ("PP_DISTANCE", "P-P Distance", "Color based on particle-particle distance", 15),
    ("ROTATION", "Rotation", "Color based on particle rotation", 16),
]

_DIRECTION_ITEMS = [
    ("NORMAL", "Normal", "Emit along surface normal", 0),
    ("RANDOM", "Random", "Emit in random directions", 1),
    ("PHONG_NORMAL", "Phong Normal", "Emit along phong-interpolated normal", 2),
    ("X_POS", "X+", "Positive X axis", 3),
    ("X_NEG", "X-", "Negative X axis", 4),
    ("Y_POS", "Y+", "Positive Y axis", 5),
    ("Y_NEG", "Y-", "Negative Y axis", 6),
    ("Z_POS", "Z+", "Positive Z axis", 7),
    ("Z_NEG", "Z-", "Negative Z axis", 8),
]

_EXTENDED_DATA_TYPE_ITEMS = [
    ("ROTATION", "Rotation", "Particle rotation data", 0),
    ("EXPLOSIAFX", "ExplosiaFX", "Particle ExplosiaFX data", 1),
    ("SCALE", "Scale", "Particle scale data", 2),
    ("CUSTOM", "Custom Data", "Custom particle data", 3),
]

_LINES_LENGTH_MODE_ITEMS = [
    ("SPEED", "Speed", "Line length based on speed", 0),
    ("RADIUS", "Radius", "Line length based on radius", 1),
    ("FIXED", "Fixed", "Fixed line length", 2),
]

_PARTICLE_ROTATION_MODE_ITEMS = [
    ("NONE", "None", "No explicit particle rotation", 0),
    ("TANGENTIAL", "Tangential", "Align rotation to particle velocity", 1),
    # ("SET", "Set", "Use a fixed rotation", 2),
    # ("RANDOM", "Random", "Use random particle rotation", 3),
    # ("FACE_CAMERA", "Face Camera", "Orient particles toward the camera", 4),
    # ("FACE_OBJECT", "Face Object", "Orient particles toward a target object", 5),
    # ("FACE_SCREEN", "Face Screen", "Orient particles to screen-facing", 6),
    ("UP_VECTOR", "Up Vector", "Use an explicit up-vector based orientation", 7),
]

_GROUP_MODE_ITEMS = [
    ("RANDOM", "Random", "Assign particles to a random group", 0),
    ("SEQUENTIAL", "Sequential", "Assign particles to a group in sequence", 1),
    ("FIRST_GROUP", "First Group Only", "Assign particles to the first group only", 2),
]

_PARTICLE_UP_VECTOR_ITEMS = [
    ("X_POS", "X+", "Use positive X as particle up direction", 0),
    ("X_NEG", "X-", "Use negative X as particle up direction", 1),
    ("Y_POS", "Y+", "Use positive Y as particle up direction", 2),
    ("Y_NEG", "Y-", "Use negative Y as particle up direction", 3),
    ("Z_POS", "Z+", "Use positive Z as particle up direction", 4),
    ("Z_NEG", "Z-", "Use negative Z as particle up direction", 5),
]

_SSF_PRESET_ITEMS = [
    ("CUSTOM", "Custom", "Manually tune all SSF controls", 0),
    ("DEFAULT", "Default", "Reset SSF controls to their factory defaults", 4),
    ("DEEP_BLUE_WATER", "Deep Blue Water", "Darker water with strong absorption", 1),
    ("TRANSPARENT_WATER", "Transparent Water", "Clearer water with softer tint", 2),
    (
        "GREEN_SLIME",
        "Green Slime",
        "Thick goopy green slime",
        3,
    ),
]

_SSF_PRESET_VALUES = {
    "DEFAULT": {
        "emitter_particle_color": (0.0, 0.2, 0.8, 1.0),
        "emitter_ssf_use_anisotropy": True,
        "emitter_ssf_anisotropy_scale": 0.18,
        "emitter_ssf_anisotropy_max_stretch": 2.4,
        "emitter_ssf_blur_iterations": 3,
        "emitter_ssf_blur_radius": 8,
        "emitter_ssf_blur_depth_falloff": 50.0,
        "emitter_ssf_thickness_blur_iterations": 2,
        "emitter_ssf_absorption": 2.0,
        "emitter_ssf_fresnel_power": 5.0,
        "emitter_ssf_min_alpha": 0.3,
        "emitter_ssf_background_color": (0.55, 0.65, 0.78),
    },
    "DEEP_BLUE_WATER": {
        "emitter_particle_color": (0.08, 0.30, 0.95, 1.0),
        "emitter_ssf_use_anisotropy": True,
        "emitter_ssf_anisotropy_scale": 0.18,
        "emitter_ssf_anisotropy_max_stretch": 2.2,
        "emitter_ssf_blur_iterations": 4,
        "emitter_ssf_blur_radius": 10,
        "emitter_ssf_blur_depth_falloff": 55.0,
        "emitter_ssf_thickness_blur_iterations": 3,
        "emitter_ssf_absorption": 8.0,
        "emitter_ssf_fresnel_power": 2.2,
        "emitter_ssf_min_alpha": 0.30,
        "emitter_ssf_background_color": (0.06, 0.08, 0.10),
    },
    "TRANSPARENT_WATER": {
        "emitter_particle_color": (0.12, 0.45, 0.90, 1.0),
        "emitter_ssf_use_anisotropy": True,
        "emitter_ssf_anisotropy_scale": 0.16,
        "emitter_ssf_anisotropy_max_stretch": 2.0,
        "emitter_ssf_blur_iterations": 5,
        "emitter_ssf_blur_radius": 11,
        "emitter_ssf_blur_depth_falloff": 35.0,
        "emitter_ssf_thickness_blur_iterations": 2,
        "emitter_ssf_absorption": 4.0,
        "emitter_ssf_fresnel_power": 2.8,
        "emitter_ssf_min_alpha": 0.25,
        "emitter_ssf_background_color": (0.10, 0.12, 0.15),
    },
    "GREEN_SLIME": {
        "emitter_particle_color": (0.0, 1.0, 0.0, 1.0),
        "emitter_ssf_use_anisotropy": True,
        "emitter_ssf_anisotropy_scale": 0.18,
        "emitter_ssf_anisotropy_max_stretch": 2.4,
        "emitter_ssf_blur_iterations": 2,
        "emitter_ssf_blur_radius": 15,
        "emitter_ssf_blur_depth_falloff": 30.0,
        "emitter_ssf_thickness_blur_iterations": 5,
        "emitter_ssf_absorption": 2.0,
        "emitter_ssf_fresnel_power": 5.0,
        "emitter_ssf_min_alpha": 0.30,
        "emitter_ssf_background_color": (0.85, 0.92, 0.78),
    },
}

_OBJECT_EMIT_FROM_ITEMS = []

_EMITTER_SECTION_ITEMS = [
    ("EMITTER", "Emitter", "Emitter settings", 0),
    ("INITIAL_STATE", "Initial State", "Initial state settings", 1),
]

_EMITTER_TAB_ITEMS = [
    ("EMISSION", "Emission", "Emission settings", 0),
    ("MOTION_INHERITANCE", "Motion Inheritance", "Motion inheritance settings", 1),
]


def _get_emitter_section_items(self, context):
    return _EMITTER_SECTION_ITEMS


def _get_emitter_tab_items(self, context):
    return _EMITTER_TAB_ITEMS


def _get_shape_items(self, context):
    return _SHAPE_ITEMS


def _get_emit_type_items(self, context):
    return _EMIT_TYPE_ITEMS


def _get_shot_mode_items(self, context):
    return _SHOT_MODE_ITEMS


def _is_accelerated_viewport_active() -> bool:
    """True when the accelerated renderer is enabled and hasn't fallen back to Basic."""
    from ..utils import use_accelerated_viewport
    from ..viewport.registry import is_locked_to_basic

    try:
        return use_accelerated_viewport() and not is_locked_to_basic()
    except Exception:
        return False


def _get_display_shape_items(self, context):
    if _is_accelerated_viewport_active():
        return _DISPLAY_SHAPE_ITEMS
    return [item for item in _DISPLAY_SHAPE_ITEMS if item[0] != "SSF"]


def _get_color_mode_items(self, context):
    return _COLOR_MODE_ITEMS


def _get_group_mode_items(self, context):
    return _GROUP_MODE_ITEMS


def _get_gradient_parameter_items(self, context):
    return _GRADIENT_PARAMETER_ITEMS


def _get_direction_items(self, context):
    # No phong normal for primitive shapes
    return [item for item in _DIRECTION_ITEMS if item[0] != "PHONG_NORMAL"]


def _get_lines_length_mode_items(self, context):
    return _LINES_LENGTH_MODE_ITEMS


def _get_particle_rotation_mode_items(self, context):
    return _PARTICLE_ROTATION_MODE_ITEMS


def _get_particle_up_vector_items(self, context):
    return _PARTICLE_UP_VECTOR_ITEMS


def _get_object_emit_from_items(self, context):
    return _OBJECT_EMIT_FROM_ITEMS


def _get_object_direction_items(self, context):
    return _DIRECTION_ITEMS


def _get_extended_data_type_items(self, context):
    return _EXTENDED_DATA_TYPE_ITEMS


class NexusEmitterObjectItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object", type=bpy.types.Object, poll=make_allowed_types_poll(["MESH", "CURVE"])
    )
    enabled: BoolProperty(name="Enabled", default=True)

    emitter_object_emit_from: EnumProperty(
        name="Emit From",
        description="How particles are emitted from the object",
        items=_get_object_emit_from_items,
    )

    emitter_object_direction: EnumProperty(
        name="Direction",
        description="Direction of particle emission from object surface",
        items=_get_object_direction_items,
    )

    emitter_object_selection: bpy.props.StringProperty(
        name="Vertex Group", description="Select a vertex group"
    )

    emitter_object_stick: BoolProperty(
        name="Stick to Surface",
        description="Particles stick to the emitting surface",
        default=False,
    )

    emitter_object_particle_per_element: IntProperty(
        name="Particles Per Element",
        description="Number of particles emitted per mesh element",
        default=1,
        min=1,
        soft_max=100,
    )

    emitter_object_threshold: FloatProperty(
        name="Threshold",
        description="Threshold for vertex group values",
        default=0.5,
        min=0.0,
        max=1.0,
    )


_EMIT_FROM_MAP = {
    "POLY_CENTER": "ID_NX_EMITTER_OBJECT_EMIT_FROM_POLY_CENTER",
    "POLY_AREA": "ID_NX_EMITTER_OBJECT_EMIT_FROM_POLY_AREA",
    "POINTS": "ID_NX_EMITTER_OBJECT_EMIT_FROM_POINTS",
    "EDGES": "ID_NX_EMITTER_OBJECT_EMIT_FROM_EDGES",
    "NGON_CENTER": "ID_NX_EMITTER_OBJECT_EMIT_FROM_NGON_CENTER",
    "TEXTURE": "ID_NX_EMITTER_OBJECT_EMIT_FROM_TEXTURE",
}

_DIRECTION_MAP = {
    "NORMAL": "ID_NX_EMITTER_DIRECTION_NORMAL",
    "RANDOM": "ID_NX_EMITTER_DIRECTION_RANDOM",
    "FACES": "ID_NX_EMITTER_DIRECTION_FACES",
    "PHONG_NORMAL": "ID_NX_EMITTER_DIRECTION_PHONG_NORMAL",
    "X_POS": "ID_NX_EMITTER_DIRECTION_XPOS",
    "X_NEG": "ID_NX_EMITTER_DIRECTION_XNEG",
    "Y_POS": "ID_NX_EMITTER_DIRECTION_YPOS",
    "Y_NEG": "ID_NX_EMITTER_DIRECTION_YNEG",
    "Z_POS": "ID_NX_EMITTER_DIRECTION_ZPOS",
    "Z_NEG": "ID_NX_EMITTER_DIRECTION_ZNEG",
}

_emitter_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
_emitter_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

EMITTER_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="emitter_objects",
    cache_dict=_emitter_poly_cache,
)
EMITTER_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="emitter_objects",
    cache_dict=_emitter_line_cache,
)

_emitter_mesh_vertex_counts: dict[str, int] = {}


def _on_emitter_link_resolved(kind, target_obj, _handle, count_a, _count_b):
    if kind == "MESH":
        _emitter_mesh_vertex_counts[target_obj.name] = count_a


def _pre_emitter_objects_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del obj, scene, depsgraph, collection_source
    _emitter_mesh_vertex_counts.clear()


def _post_emitter_objects_sync(
    _spec, _container, _props, *, obj=None, scene=None, depsgraph=None, collection_source=None
):
    del obj, scene, depsgraph, collection_source
    _emitter_mesh_vertex_counts.clear()


_emitter_object_links = make_cached_link_resolver(
    poly_spec=EMITTER_POLY_SPEC,
    line_spec=EMITTER_LINE_SPEC,
    on_resolved=_on_emitter_link_resolved,
    extra_pre_syncer=_pre_emitter_objects_sync,
    extra_post_syncer=_post_emitter_objects_sync,
)

_EMITTER_OBJECT_PARAM_SPECS = (
    SyncSpec.param("float", "emitter_object_threshold", "ID_NX_EMITTER_OBJECT_THRESHOLD"),
)


def _sync_emitter_object_params(theron, get, nc, item, item_orig, _obj):
    sync_enum_mapped(
        theron,
        get,
        nc,
        "ID_NX_EMITTER_OBJECT_EMIT_FROM",
        item.emitter_object_emit_from,
        _EMIT_FROM_MAP,
    )
    sync_enum_mapped(
        theron,
        get,
        nc,
        "ID_NX_EMITTER_OBJECT_DIRECTION",
        item.emitter_object_direction,
        _DIRECTION_MAP,
    )

    target_obj = item_orig.obj
    if target_obj is not None and target_obj.type == "MESH":
        vgroup_name = item.emitter_object_selection
        vgroup = target_obj.vertex_groups.get(vgroup_name)
        vertex_count = _emitter_mesh_vertex_counts.get(target_obj.name)
        if vgroup is not None and vertex_count is not None:
            vgi = vgroup.index
            vertex_selection = np.fromiter(
                (
                    next((g.weight for g in v.groups if g.group == vgi), 0.0)
                    for v in target_obj.data.vertices
                ),
                dtype=np.float32,
                count=vertex_count,
            )
            theron.set_memory(
                nc,
                get("ID_NX_EMITTER_OBJECT_SELECTION"),
                vertex_selection.ctypes.data_as(ctypes.c_void_p),
                vertex_selection.nbytes,
            )

    sync_params(theron, get, nc, item, _EMITTER_OBJECT_PARAM_SPECS)


def _resolve_group_link(theron_mod, item, _obj, scene, _depsgraph):
    del theron_mod
    from ..handlers import pipeline as pipeline_manager

    group_obj = item.obj
    if group_obj is None or group_obj.get("nexus_modifier_type") != "NX_GROUP":
        return None
    return pipeline_manager.get_nexus_obj_handle(scene, group_obj)


def _resolve_modifier_link(theron_mod, item, _obj, scene, _depsgraph):
    del theron_mod
    from ..handlers import pipeline as pipeline_manager

    mod_obj = item.obj
    if mod_obj is None:
        return None
    return pipeline_manager.get_nexus_obj_handle(scene, mod_obj)


def _set_modifier_node_enabled(theron_mod, _get, node, _nc, item, _item_orig, _obj):
    theron_mod.set_node_enabled(node, item.enabled)


EMITTER_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EMITTER_OBJECTS",
    collection_attr="emitter_objects",
    pre_syncer=_emitter_object_links.pre_syncer,
    post_syncer=_emitter_object_links.post_syncer,
    node_link_resolver=_emitter_object_links.node_link_resolver,
    skip_if_no_link=True,
    pre_dispatch_syncer=_sync_emitter_object_params,
    condition=lambda props: props.ID_NX_EMITTER_SHAPE == "OBJECT",
)

EMITTER_GROUPS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EMITTER_GROUPS",
    collection_attr="emitter_groups",
    node_link_resolver=_resolve_group_link,
    skip_if_no_link=True,
)

EMITTER_MODIFIERS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EMITTER_MODIFIERS",
    collection_attr="emitter_modifier_objects",
    node_link_resolver=_resolve_modifier_link,
    skip_if_no_link=True,
    enabled_disables_blend=True,
    per_item_post_syncer=_set_modifier_node_enabled,
)
_EMITTER_OBJECTS = NodeTreeDef(
    "Objects",
    item_type=NexusEmitterObjectItem,
    allowed_types=["MESH", "CURVE"],
    nodetree_sync=EMITTER_OBJECTS_TREE_SPEC,
)
_emitter_objects_props = _EMITTER_OBJECTS.properties("emitter_objects")


class NexusEmitterExtendedDataItem(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)

    emitter_extended_data_type: EnumProperty(
        name="Type",
        description="Type of extended data",
        items=_get_extended_data_type_items,
        default=0,
    )


_EMITTER_EXTENDED_DATA = NodeTreeDef("Extended Data", item_type=NexusEmitterExtendedDataItem)
_emitter_ext_data_props = _EMITTER_EXTENDED_DATA.properties("emitter_extended_data")


class NexusEmitterGroupItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Group", type=bpy.types.Object, poll=make_allowed_types_poll(["NX_GROUP"])
    )
    enabled: BoolProperty(name="Enabled", default=True)


_EMITTER_GROUPS = NodeTreeDef(
    "Groups",
    item_type=NexusEmitterGroupItem,
    allowed_types=["NX_GROUP"],
    nodetree_sync=EMITTER_GROUPS_TREE_SPEC,
)
_emitter_groups_props = _EMITTER_GROUPS.properties("emitter_groups")


class NexusEmitterModifierItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)


_EMITTER_MODIFIER_OBJECTS = NodeTreeDef(
    "Modifiers",
    item_type=NexusEmitterModifierItem,
    nodetree_sync=EMITTER_MODIFIERS_TREE_SPEC,
)
_emitter_mod_objects_props = _EMITTER_MODIFIER_OBJECTS.properties("emitter_modifier_objects")


_EMITTER_ENUM_DEFAULTS = {
    "emitter_section": "EMITTER",
    "emitter_tab": "EMISSION",
    "ID_NX_EMITTER_SHAPE": "RECT",
    "ID_NX_EMITTER_EMITTYPE": "RATE",
    "ID_NX_EMITTER_MODE": "RANDOM",
    "ID_NX_EMITTER_DISPLAY_MODE": "POINTS",
    "ID_NX_EMITTER_COLOR_MODE": "SINGLE",
    "ID_NX_EMITTER_GRADIENT_PARAMETER": "SPEED",
    "ID_NX_EMITTER_NOISE_TYPE": "VORONOISE",
    "ID_NX_EMITTER_NOISE_CHANNEL": "GRADIENT",
    "ID_NX_EMITTER_DIRECTION": "NORMAL",
    "ID_NX_EMITTER_LINES_LENGTHMODE": "SPEED",
    "emitter_ssf_preset": "CUSTOM",
    "emitter_particle_rotation_mode": "UP_VECTOR",
    "emitter_particle_up_vector": "Z_POS",
    "emitter_object_emit_from": "POLY_CENTER",
    "emitter_object_direction": "NORMAL",
}


def _on_noise_param_update(self, context):
    """Regenerate noise preview when any noise parameter changes."""
    if context is None or context.object is None:
        return
    obj = context.object
    if obj.get("nexus_modifier_type") != "NX_EMITTER":
        return
    from ..utils.noise_preview import update_noise_preview

    update_noise_preview(obj)


def _on_emitter_visibility_update(self, context):
    """Force a sim resync when Show Particles flips."""
    if context is None or context.object is None:
        return
    obj = context.object
    if obj.get("nexus_modifier_type") != "NX_EMITTER":
        return
    import bpy

    from ..handlers import pipeline as pipeline_manager

    scene = getattr(context, "scene", None) or bpy.context.scene
    if scene is None:
        return

    # Pre-stamp the new visibility so the depsgraph handler's diff check
    # treats this change as already-handled and skips the redundant resync.
    state = pipeline_manager._scenes.get(pipeline_manager.scene_key(scene))
    if state is not None:
        from ..pipeline_manager.identity import get_object_uid

        uid = get_object_uid(obj)
        if uid is not None:
            try:
                hide_get = bool(obj.hide_get())
            except (RuntimeError, AttributeError):
                hide_get = False
            state.emitter_visibility[uid] = (
                bool(getattr(obj.nexus_modifier, "emitter_show_particles", True))
                and not bool(getattr(obj, "hide_viewport", False))
                and not hide_get
            )

    pipeline_manager._resync_current_frame(scene, bpy.context.evaluated_depsgraph_get())


def _on_color_mode_update(self, context):
    """Generate or clean up noise preview when color mode changes."""
    if context is None or context.object is None:
        return
    obj = context.object
    if obj.get("nexus_modifier_type") != "NX_EMITTER":
        return
    from ..utils.noise_preview import cleanup_preview, update_noise_preview

    props = obj.nexus_modifier
    if getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE") == "NOISE":
        update_noise_preview(obj)
    else:
        cleanup_preview(obj)


def _on_ssf_preset_update(self, context):
    """Apply SSF preset values when a non-custom preset is selected."""
    del context
    preset = str(getattr(self, "emitter_ssf_preset", "CUSTOM"))
    values = _SSF_PRESET_VALUES.get(preset)
    if not values:
        return
    for attr, value in values.items():
        setattr(self, attr, value)


def _is_noise_color_mode(props):
    return getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE") == "NOISE"


def build_emitter_enum_items():
    global _SHAPE_ITEMS, _EMIT_TYPE_ITEMS, _SHOT_MODE_ITEMS, _DISPLAY_SHAPE_ITEMS
    global _OBJECT_EMIT_FROM_ITEMS
    from ..icons import get_icon

    _SHAPE_ITEMS = [
        (
            "RECT",
            "Rectangle",
            "Rectangular emission area",
            get_icon("nx_emitter_shape_rectangle"),
            0,
        ),
        (
            "DISC",
            "Disc",
            "Circular emission area",
            get_icon("nx_emitter_shape_circle"),
            1,
        ),
        (
            "SPHERE",
            "Sphere",
            "Spherical emission volume",
            get_icon("nx_emitter_shape_sphere"),
            2,
        ),
        ("BOX", "Box", "Box emission volume", get_icon("nx_emitter_shape_box"), 3),
        (
            "OBJECT",
            "Object",
            "Emit from mesh object surface",
            get_icon("nx_emitter_shape_object"),
            4,
        ),
    ]

    _EMIT_TYPE_ITEMS = [
        (
            "RATE",
            "Rate",
            "Continuous emission at birth rate",
            get_icon("nx_emitter_emission_rate"),
            0,
        ),
        (
            "PULSE",
            "Pulse",
            "Pulsed emission",
            get_icon("nx_emitter_emission_pulse"),
            1,
        ),
        (
            "SHOT",
            "Shot",
            "Single burst of particles",
            get_icon("nx_emitter_emission_shot"),
            2,
        ),
    ]

    _SHOT_MODE_ITEMS = [
        (
            "RANDOM",
            "Random",
            "Random shot pattern",
            get_icon("nx_emitter_shotmode_random"),
            0,
        ),
        (
            "REGULAR",
            "Regular",
            "Regular grid pattern",
            get_icon("nx_emitter_shotmode_regular"),
            1,
        ),
        (
            "HEX",
            "Hexagonal",
            "Hexagonal pattern",
            get_icon("nx_emitter_shotmode_hexagon"),
            2,
        ),
    ]

    _DISPLAY_SHAPE_ITEMS = [
        (
            "POINTS",
            "Points",
            "Display particles as dots",
            get_icon("nx_emitter_display_dot"),
            0,
        ),
        (
            "SQUARE",
            "Square",
            "Display particles as squares",
            get_icon("nx_emitter_display_square"),
            1,
        ),
        (
            "DIRECTION",
            "Line",
            "Display particles as lines",
            get_icon("nx_emitter_display_line"),
            2,
        ),
        (
            "BOX3D",
            "Box 3D",
            "Display particles as 3D boxes",
            get_icon("nx_emitter_display_box"),
            3,
        ),
        (
            "BOX3D_FILLED",
            "Box 3D Filled",
            "Solid 3D boxes",
            get_icon("nx_emitter_display_box_filled"),
            4,
        ),
        (
            "CIRCLE",
            "Circle",
            "Display particles as circles",
            get_icon("nx_emitter_display_circle"),
            5,
        ),
        (
            "CIRCLE_FILLED",
            "Circle Filled",
            "Filled circles",
            get_icon("nx_emitter_display_circle_filled"),
            6,
        ),
        (
            "PYRAMID",
            "Pyramid",
            "Display particles as pyramids",
            get_icon("nx_emitter_display_pyramid"),
            7,
        ),
        (
            "PYRAMID_FILLED",
            "Pyramid Filled",
            "Solid pyramids",
            get_icon("nx_emitter_display_pyramid_filled"),
            8,
        ),
        (
            "ARROW",
            "Arrow",
            "Display particles as arrows",
            get_icon("nx_emitter_display_arrow"),
            9,
        ),
        (
            "ARROW_FILLED",
            "Arrow Filled",
            "Solid arrows",
            get_icon("nx_emitter_display_arrow_filled"),
            10,
        ),
        (
            "AXIS",
            "Axis",
            "Display particle local axes (X=red, Y=green, Z=blue)",
            get_icon("nx_emitter_display_axis"),
            11,
        ),
        (
            "SPHERE",
            "Sphere",
            "Display particles as solid 3D spheres",
            get_icon("nx_emitter_display_sphere"),
            13,
        ),
        (
            "SSF",
            "Screen Space Fluid",
            "Render particles as a screen-space fluid surface (OpenGL only)",
            get_icon("nx_emitter_display_sphere"),
            14,
        ),
        ("NONE", "None", "Hide particle display", 0, 12),
    ]

    _OBJECT_EMIT_FROM_ITEMS = [
        (
            "POLY_CENTER",
            "Polygon Center",
            "Emit from polygon centers",
            get_icon("nx_emitter_objemit_polycenter"),
            0,
        ),
        (
            "POLY_AREA",
            "Polygon Area",
            "Emit based on polygon area",
            get_icon("nx_emitter_objemit_polyarea"),
            1,
        ),
        (
            "POINTS",
            "Points",
            "Emit from mesh vertices",
            get_icon("nx_emitter_objemit_points"),
            2,
        ),
        (
            "EDGES",
            "Edges",
            "Emit from mesh edges",
            get_icon("nx_emitter_objemit_edges"),
            3,
        ),
    ]


def _register_emitter_rate():
    from ..libs.nexus_rate import register_rate_property

    register_rate_property("ID_NX_EMITTER_SHOT_COUNT")


SPEC = ModifierPropertySpec(
    modifier_type="NX_EMITTER",
    item_classes=(
        NexusEmitterObjectItem,
        NexusEmitterExtendedDataItem,
        NexusEmitterGroupItem,
        NexusEmitterModifierItem,
    ),
    enum_builders=(build_emitter_enum_items, _register_emitter_rate),
    enum_defaults=_EMITTER_ENUM_DEFAULTS,
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_EMITTER_BIRTHRATE",
            prop=IntProperty(
                name="Birthrate",
                description="Number of particles emitted per frame",
                default=1000,
                min=0,
                soft_max=10000,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_BIRTHRATE_VAR",
            prop=IntProperty(
                name="Variation",
                description="Random variation in birthrate",
                default=0,
                min=0,
                soft_max=1000,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SPEED",
            prop=FloatProperty(
                name="Speed",
                description="Initial particle speed",
                default=1.5,
                min=0.0,
                soft_max=100.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SPEED_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in initial speed",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE",
            prop=EnumProperty(
                name="Shape",
                description="Shape of the emission area",
                items=_get_shape_items,
            ),
            enum_map={
                "RECT": "ID_NX_EMITTER_SHAPE_RECT",
                "DISC": "ID_NX_EMITTER_SHAPE_CIRCLE",
                "SPHERE": "ID_NX_EMITTER_SHAPE_SPHERE",
                "BOX": "ID_NX_EMITTER_SHAPE_BOX",
                "OBJECT": "ID_NX_EMITTER_SHAPE_OBJECT",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE_RECT_W",
            prop=FloatProperty(
                name="Width",
                description="Width of rectangular emission area",
                default=1.0,
                min=0.001,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE_RECT_H",
            prop=FloatProperty(
                name="Height",
                description="Height of rectangular emission area",
                default=1.0,
                min=0.001,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Radius for disc and sphere shapes",
                default=0.5,
                min=0.001,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE_ANGLE",
            prop=FloatProperty(
                name="Angle",
                description="Angle for emission cone",
                default=0.0,
                min=-math.pi,
                max=math.pi,
                subtype="ANGLE",
            ),
        ),
        PropertyDescriptor(
            name="emitter_shape_box_size",
            prop=FloatVectorProperty(
                name="Size",
                description="Size of box emission volume",
                default=(1.0, 1.0, 1.0),
                min=0.001,
                soft_max=10.0,
                size=3,
                subtype="XYZ",
                unit="LENGTH",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_RADIUS_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in particle radius",
                default=0.0,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_RADIUS",
            prop=FloatProperty(
                name="Particle Radius",
                description="Physical radius of each particle",
                default=0.03,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_EMITTYPE",
            prop=EnumProperty(
                name="Emission",
                description="How particles are emitted",
                items=_get_emit_type_items,
            ),
            enum_map={
                "RATE": "ID_NX_EMITTER_EMITTYPE_RATE",
                "PULSE": "ID_NX_EMITTER_EMITTYPE_PULSE",
                "SHOT": "ID_NX_EMITTER_EMITTYPE_SHOT",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_MODE",
            prop=EnumProperty(
                name="Shot Mode",
                description="Distribution pattern for shot emission",
                items=_get_shot_mode_items,
            ),
            enum_map={
                "RANDOM": "ID_NX_EMITTER_MODE_RANDOM",
                "REGULAR": "ID_NX_EMITTER_MODE_REGULAR",
                "HEX": "ID_NX_EMITTER_MODE_HEXAGONAL",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHAPE_ROTATION",
            prop=EnumProperty(
                name="Plane",
                description="Direction particles are initially emitted",
                items=_ORIENTATION_ITEMS,
                default="Y_POS",
            ),
            enum_map={
                "Z_NEG": "EMORIENT_ZNEG",
                "Z_POS": "EMORIENT_ZPOS",
                "Y_NEG": "EMORIENT_YNEG",
                "Y_POS": "EMORIENT_YPOS",
                "X_NEG": "EMORIENT_XNEG",
                "X_POS": "EMORIENT_XPOS",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_DIRECTION",
            prop=EnumProperty(
                name="Direction",
                description="Direction particles are emitted from the shape surface",
                items=_get_direction_items,
            ),
            condition=lambda props: props.ID_NX_EMITTER_SHAPE in ("SPHERE", "BOX"),
            enum_map={
                "NORMAL": "ID_NX_EMITTER_DIRECTION_NORMAL",
                "RANDOM": "ID_NX_EMITTER_DIRECTION_RANDOM",
                "PHONG_NORMAL": "ID_NX_EMITTER_DIRECTION_PHONG_NORMAL",
                "X_POS": "ID_NX_EMITTER_DIRECTION_XPOS",
                "X_NEG": "ID_NX_EMITTER_DIRECTION_XNEG",
                "Y_POS": "ID_NX_EMITTER_DIRECTION_YPOS",
                "Y_NEG": "ID_NX_EMITTER_DIRECTION_YNEG",
                "Z_POS": "ID_NX_EMITTER_DIRECTION_ZPOS",
                "Z_NEG": "ID_NX_EMITTER_DIRECTION_ZNEG",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_EDGE_ONLY",
            prop=BoolProperty(
                name="Edge Only",
                description="Emit particles only from the edge of the shape",
                default=False,
            ),
            condition=lambda props: props.ID_NX_EMITTER_SHAPE in ("RECT", "DISC"),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_ORIGIN_ONLY",
            prop=BoolProperty(
                name="Origin Only",
                description="Emit particles only from the emitter origin",
                default=False,
            ),
            condition=lambda props: props.ID_NX_EMITTER_SHAPE in ("RECT", "DISC"),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SURFACE_ONLY",
            prop=BoolProperty(
                name="Surface Only",
                description="Emit particles only from the surface of the volume",
                default=False,
            ),
            condition=lambda props: props.ID_NX_EMITTER_SHAPE == "SPHERE",
            aliases=(
                AliasSpec(
                    theron_id="ID_NX_EMITTER_FACES_ONLY",
                    condition=lambda props: props.ID_NX_EMITTER_SHAPE == "BOX",
                ),
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHOT_COUNT",
            prop=IntProperty(
                name="Count",
                description="Number of particles per shot",
                default=100,
                min=1,
                soft_max=10000,
            ),
            sync_type=SyncType.RATE,
            condition=lambda props: props.ID_NX_EMITTER_EMITTYPE == "SHOT",
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHOT_START",
            prop=nexus_time_property(
                "ID_NX_EMITTER_SHOT_START",
                name="Start",
                description="Frame when shot begins",
                default=2.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
            condition=lambda props: props.ID_NX_EMITTER_EMITTYPE == "SHOT",
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SHOT_DURATION",
            prop=nexus_time_property(
                "ID_NX_EMITTER_SHOT_DURATION",
                name="Duration",
                description="Duration of shot",
                default=1.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
            condition=lambda props: props.ID_NX_EMITTER_EMITTYPE == "SHOT",
        ),
        PropertyDescriptor(
            name="emitter_shot_per_frame",
            prop=BoolProperty(
                name="Per Frame",
                description="Emit shot particles per frame rather than all at once",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_PULSE_LENGTH",
            prop=nexus_time_property(
                "ID_NX_EMITTER_PULSE_LENGTH",
                name="Length",
                description="Duration of each pulse",
                default=10.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
            condition=lambda props: props.ID_NX_EMITTER_EMITTYPE == "PULSE",
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_PULSE_INTERVAL",
            prop=nexus_time_property(
                "ID_NX_EMITTER_PULSE_INTERVAL",
                name="Interval",
                description="Time between pulses",
                default=10.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
            condition=lambda props: props.ID_NX_EMITTER_EMITTYPE == "PULSE",
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SPACING",
            prop=FloatProperty(
                name="Spacing",
                description="Spacing between particles relative to particle diameter",
                default=100.0,
                min=0.1,
                soft_min=1.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: props.ID_NX_EMITTER_MODE in ("REGULAR", "HEX"),
        ),
        # PropertyDescriptor(
        #     name="emitter_section",
        #     prop=EnumProperty(
        #         name="Emitter Section",
        #         description="Top-level emitter section",
        #         items=_get_emitter_section_items,
        #     ),
        # ),
        PropertyDescriptor(
            name="emitter_tab",
            prop=EnumProperty(
                name="Emitter Tab",
                description="Emitter settings section",
                items=_get_emitter_tab_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_MASS",
            prop=FloatProperty(
                name="Mass",
                description="Mass of each particle",
                default=1.0,
                min=0.0,
                soft_max=100.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_MASS_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in particle mass",
                default=0.0,
                min=0.0,
                soft_max=100.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_EMIT_ALL",
            prop=BoolProperty(
                name="Emit all Frames",
                description="Emit particles on every frame",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_EMIT_START",
            prop=nexus_time_property(
                "ID_NX_EMITTER_EMIT_START",
                name="Start Emit",
                description="Frame to start emitting particles",
                default=0.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_EMIT_END",
            prop=nexus_time_property(
                "ID_NX_EMITTER_EMIT_END",
                name="End Emit",
                description="Frame to stop emitting particles",
                default=0.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_FULL_LIFETIME",
            prop=BoolProperty(
                name="Full Lifespan",
                description="Particles live for the entire simulation",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LIFETIME",
            prop=nexus_time_property(
                "ID_NX_EMITTER_LIFETIME",
                name="Lifespan",
                description="Lifetime of each particle",
                default=90.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LIFETIME_VAR",
            prop=nexus_time_property(
                "ID_NX_EMITTER_LIFETIME_VAR",
                name="Variation",
                description="Random variation in particle lifespan",
                default=0.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="emitter_show_particles",
            prop=BoolProperty(
                name="Show Particles",
                description="Display particles in the viewport",
                default=True,
                update=_on_emitter_visibility_update,
            ),
        ),
        PropertyDescriptor(
            name="emitter_particle_size",
            prop=FloatProperty(
                name="Particle Size",
                description="Point size in pixels",
                default=3.0,
                min=0.0,
                max=20.0,
            ),
        ),
        PropertyDescriptor(
            name="emitter_particle_color",
            prop=FloatVectorProperty(
                name="Particle Color",
                description="Display color of particles",
                subtype="COLOR",
                size=4,
                default=(0.0, 0.2, 0.8, 1.0),
                min=0.0,
                max=1.0,
            ),
        ),
        PropertyDescriptor(
            name="create_point_cloud",
            prop=BoolProperty(
                name="Create Point Cloud",
                description="Creates a Blender Point Cloud object from the particle data",
                default=False,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="display_constraints",
            prop=BoolProperty(
                name="Display Constraints",
                description="Draw inter-particle constraint lines in the viewport",
                default=False,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="constraint_color_birth",
            prop=FloatVectorProperty(
                name="Birth",
                description="Constraint colour for Birth connections",
                subtype="COLOR",
                size=4,
                default=(1.0, 0.95, 0.3, 1.0),
                min=0.0,
                max=1.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="constraint_color_distance",
            prop=FloatVectorProperty(
                name="Distance",
                description="Constraint colour for Distance connections",
                subtype="COLOR",
                size=4,
                default=(0.3, 0.85, 0.55, 1.0),
                min=0.0,
                max=1.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="constraint_color_custom",
            prop=FloatVectorProperty(
                name="Custom",
                description="Constraint colour for Custom connections",
                subtype="COLOR",
                size=4,
                default=(0.85, 0.4, 0.85, 1.0),
                min=0.0,
                max=1.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="constraint_color_viscosity",
            prop=FloatVectorProperty(
                name="Viscosity",
                description="Constraint colour for Viscosity connections",
                subtype="COLOR",
                size=4,
                default=(0.3, 0.55, 0.95, 1.0),
                min=0.0,
                max=1.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_DISPLAY_MODE",
            prop=EnumProperty(
                name="Mode",
                description="How each particle is drawn in the viewport",
                items=_get_display_shape_items,
                default=0,
            ),
            enum_map={
                "POINTS": "ID_NX_EMITTER_DISPLAY_MODE_DOT",
                "SQUARE": "ID_NX_EMITTER_DISPLAY_MODE_BOX",
                "DIRECTION": "ID_NX_EMITTER_DISPLAY_MODE_LINE",
                "BOX3D": "ID_NX_EMITTER_DISPLAY_MODE_BOX3D",
                "BOX3D_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_BOX3D_FILLED",
                "CIRCLE": "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE",
                "CIRCLE_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE_FILLED",
                "PYRAMID": "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID",
                "PYRAMID_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID_FILLED",
                "ARROW": "ID_NX_EMITTER_DISPLAY_MODE_ARROW",
                "ARROW_FILLED": "ID_NX_EMITTER_DISPLAY_MODE_ARROW_FILLED",
                "SPHERE": "ID_NX_EMITTER_DISPLAY_MODE_SPHERE",
                "SSF": "ID_NX_EMITTER_DISPLAY_MODE_SSF",
                "AXIS": "ID_NX_EMITTER_DISPLAY_MODE_AXIS",
                "NONE": "ID_NX_EMITTER_DISPLAY_MODE_NONE",
            },
        ),
        PropertyDescriptor(
            name="emitter_ssf_preset",
            prop=EnumProperty(
                name="Preset",
                description="Screen-space fluid preset",
                items=_SSF_PRESET_ITEMS,
                default="CUSTOM",
                update=_on_ssf_preset_update,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_blur_iterations",
            prop=IntProperty(
                name="Blur Iterations",
                description="Number of bilateral depth blur iterations for SSF",
                default=3,
                min=0,
                max=10,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_blur_radius",
            prop=IntProperty(
                name="Blur Radius",
                description="Half-width in pixels of the SSF blur kernel",
                default=8,
                min=1,
                max=32,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_blur_depth_falloff",
            prop=FloatProperty(
                name="Depth Falloff",
                description="Depth weight strength used by the SSF bilateral blur",
                default=50.0,
                min=0.0,
                soft_max=1000.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_thickness_blur_iterations",
            prop=IntProperty(
                name="Thickness Blur",
                description="Gaussian blur iterations for accumulated SSF thickness",
                default=2,
                min=0,
                max=10,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_absorption",
            prop=FloatProperty(
                name="Absorption",
                description="Beer-Lambert absorption coefficient for SSF compositing",
                default=2.0,
                min=0.0,
                soft_max=20.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_fresnel_power",
            prop=FloatProperty(
                name="Fresnel Power",
                description="Exponent for SSF Fresnel rim lighting",
                default=5.0,
                min=0.0,
                soft_max=10.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_use_anisotropy",
            prop=BoolProperty(
                name="Anisotropic Particles",
                description="Stretch SSF particle impostors by velocity and speed",
                default=True,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_anisotropy_scale",
            prop=FloatProperty(
                name="Anisotropy Scale",
                description="How strongly speed increases anisotropic stretch",
                default=0.18,
                min=0.0,
                soft_max=2.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_anisotropy_max_stretch",
            prop=FloatProperty(
                name="Max Stretch",
                description="Maximum anisotropic elongation factor",
                default=2.4,
                min=1.0,
                soft_max=8.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_min_alpha",
            prop=FloatProperty(
                name="Thin Opacity",
                description="Minimum opacity used for thin SSF regions",
                default=0.3,
                min=0.0,
                max=1.0,
                subtype="FACTOR",
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_ssf_background_color",
            prop=FloatVectorProperty(
                name="Background",
                description="Background color seen through SSF",
                subtype="COLOR",
                size=3,
                default=(0.55, 0.65, 0.78),
                min=0.0,
                max=1.0,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LINES_LENGTHMODE",
            prop=EnumProperty(
                name="Length Mode",
                description="How line length is determined",
                items=_get_lines_length_mode_items,
            ),
            enum_map={
                "SPEED": "ID_NX_EMITTER_LINES_LENGTHMODE_SPEED",
                "RADIUS": "ID_NX_EMITTER_LINES_LENGTHMODE_RADIUS",
                "FIXED": "ID_NX_EMITTER_LINES_LENGTHMODE_FIXED",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LINES_FIXEDLENGTH",
            prop=FloatProperty(
                name="Fixed Length",
                description="Fixed length of particle direction lines",
                default=0.1,
                min=0.001,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: (
                getattr(props, "ID_NX_EMITTER_LINES_LENGTHMODE", "SPEED") == "FIXED"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LINES_CLAMP",
            prop=BoolProperty(
                name="Clamp Length",
                description=(
                    "Constrain Speed/Radius driven line length to a min/max range "
                    "so particles never shrink to a dot or stretch too far"
                ),
                default=False,
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LINES_MINLENGTH",
            prop=FloatProperty(
                name="Min Length",
                description="Shortest allowed line length (0 disables the lower bound)",
                default=0.05,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_LINES_MAXLENGTH",
            prop=FloatProperty(
                name="Max Length",
                description="Longest allowed line length (0 disables the upper bound)",
                default=1.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
            ),
            no_sync=True,
        ),
        PropertyDescriptor(
            name="emitter_particle_rotation_mode",
            prop=EnumProperty(
                name="Rotation",
                description="How particle rotation is generated",
                items=_get_particle_rotation_mode_items,
            ),
        ),
        PropertyDescriptor(
            name="emitter_particle_up_vector",
            prop=EnumProperty(
                name="Up Vector",
                description="Up-vector mode used for particle orientation",
                items=_get_particle_up_vector_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_COLOR_MODE",
            prop=EnumProperty(
                name="Color Mode",
                description="How particle colors are determined",
                items=_get_color_mode_items,
                update=_on_color_mode_update,
            ),
            enum_map={
                "SINGLE": "ID_NX_EMITTER_COLOR_MODE_SINGLE",
                "GRADIENT": "ID_NX_EMITTER_COLOR_MODE_GRADIENT",
                "SHADER": "ID_NX_EMITTER_COLOR_MODE_SHADER",
                "OBJECT": "ID_NX_EMITTER_COLOR_MODE_OBJECT",
                "NOISE": "ID_NX_EMITTER_COLOR_MODE_NOISE",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_GRADIENT_PARAMETER",
            prop=EnumProperty(
                name="Parameter",
                description="Which particle parameter drives the gradient color",
                items=_get_gradient_parameter_items,
            ),
            condition=lambda props: (
                getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE") == "GRADIENT"
            ),
            enum_map={
                "AGE": "ID_NX_EMITTER_GRADIENT_PARAMETER_AGE",
                "SPEED": "ID_NX_EMITTER_GRADIENT_PARAMETER_SPEED",
                "SPEED_WORLD": "ID_NX_EMITTER_GRADIENT_PARAMETER_SPEED_WORLD",
                "RADIUS": "ID_NX_EMITTER_GRADIENT_PARAMETER_RADIUS",
                "FLUID_DENSITY": "ID_NX_EMITTER_GRADIENT_PARAMETER_FLUID_DENSITY",
                "FLUID_DENSITY_VELOCITY": (
                    "ID_NX_EMITTER_GRADIENT_PARAMETER_FLUID_DENSITY_VELOCITY"
                ),
                "GRANULAR": "ID_NX_EMITTER_GRADIENT_PARAMETER_GRANULAR",
                "FLUID_SURFACE": "ID_NX_EMITTER_GRADIENT_PARAMETER_FLUID_SURFACE",
                "MASS": "ID_NX_EMITTER_GRADIENT_PARAMETER_MASS",
                "TEMPERATURE": "ID_NX_EMITTER_GRADIENT_PARAMETER_TEMPERATURE",
                "SMOKE": "ID_NX_EMITTER_GRADIENT_PARAMETER_SMOKE",
                "FIRE": "ID_NX_EMITTER_GRADIENT_PARAMETER_FIRE",
                "FUEL": "ID_NX_EMITTER_GRADIENT_PARAMETER_FUEL",
                "DISTANCE_TRAVELED": "ID_NX_EMITTER_GRADIENT_PARAMETER_DISTANCE_TRAVELED",
                "DIRECTION": "ID_NX_EMITTER_GRADIENT_PARAMETER_DIRECTION",
                "PP_DISTANCE": "ID_NX_EMITTER_GRADIENT_PARAMETER_PP_DISTANCE",
                "ROTATION": "ID_NX_EMITTER_GRADIENT_PARAMETER_ROTATION",
            },
        ),
        PropertyDescriptor(
            name="emitter_gradient_min",
            prop=FloatProperty(
                name="Min",
                description="Minimum value for gradient mapping range",
                default=0.0,
                soft_min=0.0,
                soft_max=100.0,
            ),
        ),
        PropertyDescriptor(
            name="emitter_gradient_max",
            prop=FloatProperty(
                name="Max",
                description="Maximum value for gradient mapping range",
                default=5.0,
                min=0.001,
                soft_max=100.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_GRADIENT_PARAMETER_AUTOSCALE",
            prop=BoolProperty(
                name="Autoscale",
                description="Automatically scale gradient range to particle data",
                default=True,
            ),
            condition=lambda props: (
                getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE") == "GRADIENT"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_TYPE",
            prop=EnumProperty(
                name="Noise Type",
                description="Type of noise to use for particle coloring",
                items=_NOISE_TYPE_ITEMS,
                update=_on_noise_param_update,
            ),
            condition=_is_noise_color_mode,
            enum_map={
                "SIMPLEX": "ID_NX_EMITTER_NOISE_TYPE_SIMPLEX",
                "FBM": "ID_NX_EMITTER_NOISE_TYPE_FBM",
                "TURBULENCE": "ID_NX_EMITTER_NOISE_TYPE_TURBULENCE",
                "WAVY_TURBULENCE": "ID_NX_EMITTER_NOISE_TYPE_WAVY_TURBULENCE",
                "VORONOISE": "ID_NX_EMITTER_NOISE_TYPE_VORONOISE",
                "CUBIC": "ID_NX_EMITTER_NOISE_TYPE_CUBIC",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_CHANNEL",
            prop=EnumProperty(
                name="Color Channel",
                description="How noise values are mapped to color",
                items=_NOISE_CHANNEL_ITEMS,
                update=_on_noise_param_update,
            ),
            condition=_is_noise_color_mode,
            enum_map={
                "GRADIENT": "ID_NX_EMITTER_NOISE_CHANNEL_GRADIENT",
                "NOISE": "ID_NX_EMITTER_NOISE_CHANNEL_DIRECT",
            },
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_SEED",
            prop=IntProperty(
                name="Seed",
                description="Seed for noise spatial offset",
                default=1,
                min=0,
                update=_on_noise_param_update,
            ),
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Noise spatial scale",
                default=100.0,
                min=0.0,
                soft_max=1000.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_PERSISTENCE",
            prop=FloatProperty(
                name="Persistence",
                description="Amplitude decay per octave",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_LACUNARITY",
            prop=FloatProperty(
                name="Lacunarity",
                description="Frequency multiplier per octave",
                default=1.0,
                min=0.0,
                soft_max=10.0,
                update=_on_noise_param_update,
            ),
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_FREQUENCY",
            prop=FloatProperty(
                name="Frequency",
                description="Base noise frequency",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_OCTAVES",
            prop=IntProperty(
                name="Octaves",
                description="Number of noise octaves",
                default=1,
                min=0,
                max=20,
                update=_on_noise_param_update,
            ),
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_LOW_CLIP",
            prop=FloatProperty(
                name="Low Clip",
                description="Low clip threshold",
                default=0.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_HIGH_CLIP",
            prop=FloatProperty(
                name="High Clip",
                description="High clip threshold",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_BRIGHTNESS",
            prop=FloatProperty(
                name="Brightness",
                description="Post-process brightness offset",
                default=0.0,
                min=-100.0,
                max=100.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_NOISE_CONTRAST",
            prop=FloatProperty(
                name="Contrast",
                description="Post-process contrast multiplier",
                default=100.0,
                min=0.0,
                soft_max=300.0,
                subtype="PERCENTAGE",
                update=_on_noise_param_update,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_noise_color_mode,
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_SUBFRAME_EMIT",
            prop=BoolProperty(
                name="Subframe Emit",
                description=(
                    "Emit particles randomly distributed across each frame time interval"
                ),
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EMITTER_GROUP_MODE",
            prop=EnumProperty(
                name="Mode",
                description="How particles are assigned to groups",
                items=_get_group_mode_items,
            ),
            enum_map={
                "RANDOM": "ID_NX_EMITTER_GROUP_MODE_RANDOM",
                "SEQUENTIAL": "ID_NX_EMITTER_GROUP_MODE_SEQUENTIAL",
                "FIRST_GROUP": "ID_NX_EMITTER_GROUP_MODE_FIRST_GROUP",
            },
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_objects",
            prop=_emitter_objects_props["emitter_objects"],
        ),
        PropertyDescriptor(
            name="emitter_objects_index",
            prop=_emitter_objects_props["emitter_objects_index"],
        ),
        PropertyDescriptor(
            name="emitter_objects_drop_target",
            prop=_emitter_objects_props.get("emitter_objects_drop_target"),
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_extended_data",
            prop=_emitter_ext_data_props["emitter_extended_data"],
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_extended_data_index",
            prop=_emitter_ext_data_props["emitter_extended_data_index"],
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_groups",
            prop=_emitter_groups_props["emitter_groups"],
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_groups_index",
            prop=_emitter_groups_props["emitter_groups_index"],
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_groups_drop_target",
            prop=_emitter_groups_props.get("emitter_groups_drop_target"),
            preset=False,
        ),
        PropertyDescriptor(
            name="emitter_modifier_objects",
            prop=_emitter_mod_objects_props["emitter_modifier_objects"],
        ),
        PropertyDescriptor(
            name="emitter_modifier_objects_index",
            prop=_emitter_mod_objects_props["emitter_modifier_objects_index"],
        ),
        PropertyDescriptor(
            name="emitter_modifier_objects_drop_target",
            prop=_emitter_mod_objects_props.get("emitter_modifier_objects_drop_target"),
            preset=False,
        ),
    ),
    nodetree_sync=combine_nodetree_sync(
        _EMITTER_OBJECTS,
        _EMITTER_GROUPS,
        _EMITTER_MODIFIER_OBJECTS,
    ),
)


NX_EMITTER_OBJECT_UI_CONFIG = {
    **_EMITTER_OBJECTS.ui_config("emitter_objects"),
    **_EMITTER_EXTENDED_DATA.ui_config("emitter_extended_data"),
    **_EMITTER_GROUPS.ui_config("emitter_groups"),
    **_EMITTER_MODIFIER_OBJECTS.ui_config("emitter_modifier_objects"),
}


def draw_emitter_object_item_settings(layout, item):

    if item.obj and item.obj.type == "MESH":
        layout.prop_search(
            item, "emitter_object_selection", item.obj, "vertex_groups", text="Vertex Group"
        )

    layout.prop(item, "emitter_object_emit_from")
    layout.prop(item, "emitter_object_threshold")
    layout.prop(item, "emitter_object_direction")

    # layout.prop(item, "emitter_object_stick")
    # layout.prop(item, "emitter_object_particle_per_element")


def draw_emitter_extended_data_item_settings(layout, item):

    layout.label(text="Not yet implemented...")


def get_emitter_ui_config():
    config = dict(NX_EMITTER_OBJECT_UI_CONFIG)
    config["emitter_objects"]["draw_item_settings"] = draw_emitter_object_item_settings
    return config


def get_emitter_modifier_ui_config():
    return dict(NX_EMITTER_OBJECT_UI_CONFIG)


def get_emitter_extended_data_ui_config():
    config = dict(NX_EMITTER_OBJECT_UI_CONFIG)
    config["emitter_extended_data"]["draw_item_settings"] = (
        draw_emitter_extended_data_item_settings
    )
    return config


register_collection_preset(
    "NX_EMITTER",
    CollectionPresetSpec(
        collection_attr="emitter_extended_data",
    ),
)

# `emitter_objects` / `emitter_groups` / `emitter_modifier_objects`: scene-link lists.
