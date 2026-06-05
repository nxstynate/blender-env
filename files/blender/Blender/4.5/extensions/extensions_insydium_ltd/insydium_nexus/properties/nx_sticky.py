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
from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty

from ..libs.cache_spec import CacheKind, CacheSpec
from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_cleanup
from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nexus_time import draw_time_prop, nexus_time_property
from ..libs.nodetree_sync import (
    NodeTreeSyncSpec,
    make_cached_link_resolver,
)
from ..libs.theron_sync import TRANSFORM_FACTORS, SyncSpec, Transform
from ..ui import NodeTreeDef, make_allowed_types_poll
from ..utils.curve import CurveSpec, NexusCurve, create_item_curves, generate_curve_id

STICKY_FALLOFF_CURVE_SPECS = [
    CurveSpec(
        "sticky_falloff",
        "Sticky Falloff",
        [(0.0, 1.0), (0.3, 1.0), (0.9, 0.04), (1.0, 0.0)],
        theron_ids=("ID_NX_STICKY_TIME_FALLOFF",),
        slot_suffix_attr="curve_id",
    ),
]


def _on_sticky_item_obj_update(self, context):
    if self.obj is None:
        return
    if not self.curve_id:
        self.curve_id = generate_curve_id()
        obj = self.id_data
        create_item_curves(obj, self, STICKY_FALLOFF_CURVE_SPECS)


class NexusStickyItem(bpy.types.PropertyGroup):
    curve_id: StringProperty(name="", default="", options={"HIDDEN"})

    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=make_allowed_types_poll(["MESH", "CURVE"]),
        update=_on_sticky_item_obj_update,
    )
    enabled: BoolProperty(name="Enabled", default=True)

    sticky_inherit: BoolProperty(
        name="Inherit Parent",
        description="Inherit settings from the first object in the list",
        default=False,
    )

    sticky_inherit_speed: BoolProperty(
        name="Inherit Speed",
        description="Inherit speed from the target object",
        default=True,
    )

    sticky_rotate_object: BoolProperty(
        name="Rotate With Object",
        description="Particles rotate with the target object",
        default=False,
    )

    sticky_prob: FloatProperty(
        name="Probability",
        description="Probability that a particle will stick",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    sticky_distance: FloatProperty(
        name="Range",
        description="Maximum distance at which particles can stick",
        default=0.1,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    sticky_tolerance: FloatProperty(
        name="Tolerance",
        description="Distance tolerance for sticking",
        default=0.1,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    sticky_outside: BoolProperty(
        name="Outside Only",
        description="Only stick to the outside of the surface",
        default=True,
    )

    sticky_at: BoolProperty(
        name="Custom Offset",
        description="Enable custom offset distance from the surface",
        default=False,
    )

    sticky_offset: FloatProperty(
        name="Distance",
        description="Offset distance from the surface",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    sticky_time: nexus_time_property(
        "sticky_time",
        name="Sticky Time",
        description="How long particles remain stuck (0 = infinite)",
        default=60.0,
        min=0.0,
        soft_max=1000.0,
        collection_path="sticky_objects",
    )


_STICKY_OBJECTS = NodeTreeDef(
    "Objects",
    item_type=NexusStickyItem,
    allowed_types=["MESH", "CURVE"],
)


NX_STICKY_UI_CONFIG = {
    **_STICKY_OBJECTS.ui_config("sticky_objects"),
}


def draw_sticky_item_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.separator(type="LINE")
    col.prop(item, "sticky_inherit")

    if item.sticky_inherit:
        return

    col.separator(type="LINE")
    col.prop(item, "sticky_inherit_speed")
    col.prop(item, "sticky_prob")
    col.prop(item, "sticky_distance")
    col.prop(item, "sticky_tolerance")

    col.separator(type="LINE")
    col.prop(item, "sticky_rotate_object")

    col.separator(type="LINE")
    col.prop(item, "sticky_outside")
    col.prop(item, "sticky_at")

    row = col.row()
    row.prop(item, "sticky_offset")
    row.enabled = item.sticky_at

    col.separator(type="LINE")
    draw_time_prop(col, item, "sticky_time")

    NexusCurve(item.id_data, f"sticky_falloff_{item.curve_id}").draw_ui(col, "Sticky Falloff")


def get_sticky_ui_config():
    config = dict(NX_STICKY_UI_CONFIG)
    config["sticky_objects"]["draw_item_settings"] = draw_sticky_item_settings
    return config


_sticky_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
_sticky_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
_sticky_active_objects: set[str] = set()

_STICKY_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="sticky_objects",
    cache_dict=_sticky_poly_cache,
)

_STICKY_LINE_SPEC = CacheSpec(
    kind=CacheKind.LINE,
    collection_attr="sticky_objects",
    cache_dict=_sticky_line_cache,
)

_sticky_link_hooks = make_cached_link_resolver(
    poly_spec=_STICKY_POLY_SPEC,
    line_spec=_STICKY_LINE_SPEC,
    active_names=_sticky_active_objects,
)


_unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]
_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

_STICKY_PARAM_SPECS = (
    SyncSpec.param("bool", "sticky_inherit", "ID_NX_STICKY_INHERIT"),
    SyncSpec.param("bool", "sticky_inherit_speed", "ID_NX_STICKY_INHERIT_SPEED"),
    SyncSpec.param("bool", "sticky_rotate_object", "ID_NX_STICKY_ROTATE_OBJECT"),
    SyncSpec.param("float", "sticky_prob", "ID_NX_STICKY_PROB", scale=_pct),
    SyncSpec.param("float", "sticky_distance", "ID_NX_STICKY_DISTANCE", scale=_unit),
    SyncSpec.param("float", "sticky_tolerance", "ID_NX_STICKY_TOLERANCE", scale=_unit),
    SyncSpec.param("bool", "sticky_outside", "ID_NX_STICKY_OUTSIDE"),
    SyncSpec.param("bool", "sticky_at", "ID_NX_STICKY_AT"),
    SyncSpec.param("float", "sticky_offset", "ID_NX_STICKY_OFFSET", scale=_unit),
    SyncSpec.param("time", "sticky_time", "ID_NX_STICKY_TIME"),
)

NexusStickyItem._sync_specs = _STICKY_PARAM_SPECS


_STICKY_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_STICKY_OBJECTS_TREE",
    collection_attr="sticky_objects",
    pre_syncer=_sticky_link_hooks.pre_syncer,
    post_syncer=_sticky_link_hooks.post_syncer,
    node_link_resolver=_sticky_link_hooks.node_link_resolver,
    skip_if_no_link=True,
    curve_specs=STICKY_FALLOFF_CURVE_SPECS,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_STICKY",
    descriptors=(
        ENABLED_DESCRIPTOR,
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _STICKY_OBJECTS.properties("sticky_objects").items()
        ),
    ),
    item_classes=(NexusStickyItem,),
    nodetree_sync=(_STICKY_TREE_SPEC,),
)


# Scene-link list; not preset-captured. Cleanup-only so per-item falloff
# curves are released on reset.
register_collection_cleanup(
    "NX_STICKY",
    CollectionPresetSpec(
        collection_attr="sticky_objects",
        curve_specs=STICKY_FALLOFF_CURVE_SPECS,
        suffix_attr="curve_id",
    ),
)
