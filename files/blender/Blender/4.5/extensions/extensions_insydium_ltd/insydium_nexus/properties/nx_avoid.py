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
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

from ..libs.cache_spec import CacheKind, CacheSpec
from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
)
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform
from ..ui import NodeTreeDef, make_allowed_types_poll

_AVOID_OPERATION_ITEMS = []


def build_avoid_enum_items():
    global _AVOID_OPERATION_ITEMS

    from ..icons import get_icon

    _AVOID_OPERATION_ITEMS = [
        (
            "CHANGE_DIR",
            "Change Direction",
            "Particle changes direction to avoid object",
            get_icon("nx_avoid_changedir"),
            0,
        ),
        (
            "FREEZE",
            "Freeze",
            "Particle freezes when approaching object",
            get_icon("nx_avoid_freeze"),
            1,
        ),
        (
            "DIE",
            "Die",
            "Particle dies when approaching object",
            get_icon("nx_avoid_die"),
            2,
        ),
    ]


def _get_avoid_operation_items(self, context):
    return _AVOID_OPERATION_ITEMS


class NexusAvoidItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
    )
    enabled: BoolProperty(name="Enabled", default=True)

    avoid_operation: EnumProperty(
        name="On Detection",
        description="What happens when a particle approaches this object",
        items=_get_avoid_operation_items,
    )

    avoid_detection_distance: FloatProperty(
        name="Detection Distance",
        description="Distance at which particles start avoiding the object",
        default=0.5,
        min=0.00001,
        soft_max=2.0,
        unit="LENGTH",
    )

    avoid_distance_variation: FloatProperty(
        name="Variation",
        description="Random variation in detection distance",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    avoid_scatter: FloatProperty(
        name="Scatter",
        description="Angular scatter when avoiding",
        default=0.0,
        min=0.0,
        max=math.pi,
        subtype="ANGLE",
    )

    avoid_object_shell: FloatProperty(
        name="Object Shell",
        description="Shell multiplier around the object",
        default=1.0,
        min=1.0,
        soft_max=5.0,
    )

    avoid_thickness: FloatProperty(
        name="Thickness",
        description="Thickness of the avoidance zone",
        default=0.05,
        min=0.00001,
        soft_max=1.0,
        unit="LENGTH",
    )


_AVOID_OBJECTS = NodeTreeDef("Objects", item_type=NexusAvoidItem, allowed_types=["MESH", "CURVE"])


NX_AVOID_UI_CONFIG = {
    **_AVOID_OBJECTS.ui_config("avoid_objects"),
}


def draw_avoid_item_settings(layout, item):
    layout.prop(item, "avoid_operation")
    layout.prop(item, "avoid_detection_distance", text="Detection Distance")
    layout.prop(item, "avoid_distance_variation", text="Variation")
    layout.prop(item, "avoid_scatter", text="Scatter")
    layout.prop(item, "avoid_object_shell", text="Object Shell")
    layout.prop(item, "avoid_thickness", text="Thickness")


def get_avoid_ui_config():
    config = dict(NX_AVOID_UI_CONFIG)
    config["avoid_objects"]["draw_item_settings"] = draw_avoid_item_settings
    return config


_AVOID_OPERATION_MAP = {
    "CHANGE_DIR": "ID_NX_AVOID_OPERATION_CHANGEDIR",
    "FREEZE": "ID_NX_AVOID_OPERATION_FREEZE",
    "DIE": "ID_NX_AVOID_OPERATION_DIE",
}

_avoid_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
_avoid_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}

_AVOID_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="avoid_objects",
    cache_dict=_avoid_poly_cache,
)

_AVOID_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="avoid_objects",
    cache_dict=_avoid_line_cache,
)

_avoid_link_hooks = make_cached_link_resolver(
    poly_spec=_AVOID_POLY_SPEC,
    line_spec=_AVOID_LINE_SPEC,
)


_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]

_AVOID_PARAM_SPECS = (
    SyncSpec.param(
        "enum",
        "avoid_operation",
        "ID_NX_AVOID_OPERATION",
        enum_map=_AVOID_OPERATION_MAP,
    ),
    SyncSpec.param(
        "float", "avoid_detection_distance", "ID_NX_AVOID_GEOMETRY_DISTANCE", scale=_unit
    ),
    SyncSpec.param(
        "float",
        "avoid_distance_variation",
        "ID_NX_AVOID_GEOMETRY_DISTANCE_VAR_PERCENT",
        scale=_pct,
    ),
    SyncSpec.param("float", "avoid_object_shell", "ID_NX_AVOID_GEOMETRY_SHELL"),
    SyncSpec.param("float", "avoid_thickness", "ID_NX_AVOID_THICKNESS", scale=_unit),
    SyncSpec.param("float", "avoid_scatter", "ID_NX_AVOID_GEOMETRY_DNVARIATION"),
)

NexusAvoidItem._sync_specs = _AVOID_PARAM_SPECS


_AVOID_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_AVOID_OBJECTS_TREE",
    collection_attr="avoid_objects",
    pre_syncer=_avoid_link_hooks.pre_syncer,
    post_syncer=_avoid_link_hooks.post_syncer,
    node_link_resolver=_avoid_link_hooks.node_link_resolver,
    skip_if_no_link=True,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_AVOID",
    descriptors=(
        ENABLED_DESCRIPTOR,
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _AVOID_OBJECTS.properties("avoid_objects").items()
        ),
    ),
    item_classes=(NexusAvoidItem,),
    enum_builders=(build_avoid_enum_items,),
    enum_defaults={},
    nodetree_sync=(_AVOID_TREE_SPEC,),
)


# `avoid_objects` is a scene-link list; not preset-captured.
