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
)

from ..libs.cache_spec import CacheKind, CacheSpec
from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.nodetree_sync import NodeTreeSyncSpec, make_cached_link_resolver
from ..libs.theron_sync import Transform
from ..ui import NodeTreeDef, PerItemToggle, make_allowed_types_poll


def _camera_poll(self, obj):
    return obj.type == "CAMERA"


class NexusKillItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object", type=bpy.types.Object, poll=make_allowed_types_poll(["MESH"])
    )
    enabled: BoolProperty(name="Enabled", default=True)
    icon_flags: IntProperty(name="Icon Flags", default=1)


_KILL_OBJECTS = NodeTreeDef(
    "Kill Objects",
    item_type=NexusKillItem,
    allowed_types=["MESH"],
    per_item_toggles=[
        PerItemToggle(
            bit=0,
            icons=("nx_kill_in_volume", "nx_kill_out_volume"),
            tooltip_a="Kill inside volume (click for outside)",
            tooltip_b="Kill outside volume (click for inside)",
        ),
    ],
)


NX_KILL_UI_CONFIG = {
    **_KILL_OBJECTS.ui_config("kill_objects"),
}


def get_kill_ui_config():
    return NX_KILL_UI_CONFIG


_kill_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
_kill_active_meshes: set[str] = set()

_KILL_POLY_SPEC = CacheSpec(
    kind=CacheKind.POLY,
    collection_attr="kill_objects",
    cache_dict=_kill_poly_cache,
)

_kill_link_hooks = make_cached_link_resolver(
    poly_spec=_KILL_POLY_SPEC,
    active_names=_kill_active_meshes,
)


def _kill_post_insert(theron_mod, _get, node, _nc, item, _item_orig, _obj):
    theron_mod.set_node_icon_flags(node, item.icon_flags)


_KILL_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_KILL_OBJECTS_TREE",
    collection_attr="kill_objects",
    node_link_resolver=_kill_link_hooks.node_link_resolver,
    skip_if_no_link=True,
    per_item_post_syncer=_kill_post_insert,
    condition=lambda props: props.ID_NX_KILL_TYPE == "ID_NX_KILL_TYPE_OBJECTS",
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_KILL",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_KILL_TYPE",
            prop=EnumProperty(
                name="Volume",
                description="Kill volume type",
                items=[
                    (
                        "ID_NX_KILL_TYPE_BOX_IN",
                        "Inside Bounds",
                        "Kill particles inside the bounding volume",
                    ),
                    (
                        "ID_NX_KILL_TYPE_BOX_OUT",
                        "Outside Bounds",
                        "Kill particles outside the bounding volume",
                    ),
                    (
                        "ID_NX_KILL_TYPE_OBJECTS",
                        "Objects",
                        "Kill particles inside collision objects",
                    ),
                    (
                        "ID_NX_KILL_TYPE_FOV",
                        "Outside Camera FOV",
                        "Kill particles outside the camera field of view",
                    ),
                    (
                        "ID_NX_KILL_TYPE_CLAMP",
                        "Clamp to Max Particles",
                        "Limit total particle count",
                    ),
                ],
                default="ID_NX_KILL_TYPE_BOX_OUT",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_KILL_SHAPE",
            prop=EnumProperty(
                name="Shape",
                description="Kill volume shape",
                items=[
                    ("ID_NX_KILL_SHAPE_BOX", "Box", "Box-shaped kill volume"),
                    ("ID_NX_KILL_SHAPE_SPHERE", "Sphere", "Sphere-shaped kill volume"),
                ],
                default="ID_NX_KILL_SHAPE_BOX",
            ),
            condition=lambda props: (
                props.ID_NX_KILL_TYPE
                in (
                    "ID_NX_KILL_TYPE_BOX_IN",
                    "ID_NX_KILL_TYPE_BOX_OUT",
                )
            ),
        ),
        PropertyDescriptor(
            name="kill_size",
            prop=FloatVectorProperty(
                name="Size",
                description="Kill volume size",
                default=(10.0, 10.0, 10.0),
                min=0.001,
                size=3,
                subtype="XYZ",
                unit="LENGTH",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_KILL_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Kill volume radius",
                default=5.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: (
                props.ID_NX_KILL_TYPE in ("ID_NX_KILL_TYPE_BOX_IN", "ID_NX_KILL_TYPE_BOX_OUT")
                and props.ID_NX_KILL_SHAPE == "ID_NX_KILL_SHAPE_SPHERE"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_KILL_CLAMP",
            prop=IntProperty(
                name="Clamp To",
                description="Maximum number of particles",
                default=1000,
                min=0,
                soft_max=10000,
            ),
            condition=lambda props: props.ID_NX_KILL_TYPE == "ID_NX_KILL_TYPE_CLAMP",
        ),
        PropertyDescriptor(
            name="ID_NX_KILL_BORN",
            prop=BoolProperty(
                name="Only Born",
                description="Only kill particles at birth",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="kill_camera",
            prop=PointerProperty(
                name="Camera",
                description="Camera for FOV-based particle killing",
                type=bpy.types.Object,
                poll=_camera_poll,
            ),
            preset=False,
            reset=True,
            snapshot=False,
        ),
        PropertyDescriptor(
            name="ID_NX_KILL_FOV",
            prop=FloatProperty(
                name="Widen FOV",
                description="Widen the camera field of view for kill boundary",
                default=0.0,
                min=0.0,
                soft_max=3.14159,
                subtype="ANGLE",
            ),
            condition=lambda props: props.ID_NX_KILL_TYPE == "ID_NX_KILL_TYPE_FOV",
        ),
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _KILL_OBJECTS.properties("kill_objects").items()
        ),
    ),
    item_classes=(NexusKillItem,),
    nodetree_sync=(_KILL_OBJECTS_TREE_SPEC,),
)


# `kill_objects` is a scene-link list; not preset-captured.
