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
    PointerProperty,
)

from ..libs.modifier_spec import (
    ENABLED_DESCRIPTOR,
    ModifierPropertySpec,
    PropertyDescriptor,
)
from ..libs.theron_sync import SyncSpec
from ..ui import NodeTreeDef, make_allowed_types_poll
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_ORANGE

_COLLIDER_TAB_ITEMS = [
    ("GENERAL", "General", "General collider settings", 0),
    ("ACTION", "Action", "Action settings", 1),
    ("EXTENDED", "Extended", "Extended settings", 2),
]


def _get_collider_tab_items(self, context):
    return _COLLIDER_TAB_ITEMS


class NexusColliderItem(bpy.types.PropertyGroup):
    obj: PointerProperty(
        name="Object", type=bpy.types.Object, poll=make_allowed_types_poll(["MESH"])
    )
    enabled: BoolProperty(name="Enabled", default=True)

    collider_tab: EnumProperty(
        name="Section",
        description="Collider settings section",
        items=_get_collider_tab_items,
    )
    ID_NX_COLLIDER_NORMALS: EnumProperty(
        name="Normals",
        description="Which side of the mesh surface to collide with",
        items=[
            (
                "ID_NX_COLLIDER_NORMALS_OUTSIDE",
                "Outside",
                "Collide with the outside of the mesh",
            ),
            (
                "ID_NX_COLLIDER_NORMALS_INSIDE",
                "Inside",
                "Collide with the inside of the mesh",
            ),
            ("ID_NX_COLLIDER_NORMALS_ANY", "Any", "Collide with both sides of the mesh"),
        ],
        default="ID_NX_COLLIDER_NORMALS_OUTSIDE",
    )
    collider_draw_bounds: BoolProperty(
        name="Draw Bounds",
        description="Draw collision bounds in the viewport",
        default=False,
    )
    collider_bound_color_1: FloatVectorProperty(
        name="Bound Color 1",
        description="Primary bound visualization color",
        default=XP_COLOR_MODS_BLUE,
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
    )
    collider_bound_color_2: FloatVectorProperty(
        name="Bound Color 2",
        description="Secondary bound visualization color",
        default=XP_COLOR_MODS_ORANGE,
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
    )
    ID_NX_COLLIDER_BOUNCE: FloatProperty(
        name="Bounce",
        description="Amount of energy retained after collision",
        default=40.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    ID_NX_COLLIDER_FRICTION: FloatProperty(
        name="Friction",
        description="Surface friction applied on collision",
        default=1.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    ID_NX_COLLIDER_SCATTER: FloatProperty(
        name="Scatter",
        description="Random scattering of particle direction after collision",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )
    ID_NX_COLLIDER_EXPAND: FloatProperty(
        name="Expand",
        description="Expand the collision surface outward",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )


_COLLIDER_OBJECTS = NodeTreeDef("Colliders", item_type=NexusColliderItem, allowed_types=["MESH"])


NX_COLLIDER_UI_CONFIG = {
    **_COLLIDER_OBJECTS.ui_config("collider_objects"),
}


def draw_collider_item_settings(layout, item):
    if item.obj is None:
        return

    col = layout.column()
    col.use_property_split = True
    col.prop(item, "ID_NX_COLLIDER_NORMALS")

    layout.separator(factor=0.5)

    row = layout.row(align=True)
    row.use_property_split = False
    row.prop(item, "collider_tab", expand=True)

    tab = item.collider_tab
    if tab == "GENERAL":
        _draw_general_tab(layout, item)
    elif tab == "ACTION":
        _draw_action_tab(layout)
    elif tab == "EXTENDED":
        _draw_extended_tab(layout)


def _draw_general_tab(layout, item):
    col = layout.column()
    col.use_property_split = True

    disabled = col.column()
    disabled.enabled = False
    disabled.prop(item, "collider_draw_bounds")
    disabled.prop(item, "collider_bound_color_1")
    disabled.prop(item, "collider_bound_color_2")

    col.separator(type="LINE")

    col.prop(item, "ID_NX_COLLIDER_BOUNCE")
    col.prop(item, "ID_NX_COLLIDER_FRICTION")
    col.prop(item, "ID_NX_COLLIDER_SCATTER")

    disabled = col.column()
    disabled.enabled = False
    disabled.prop(item, "ID_NX_COLLIDER_EXPAND")


def _draw_action_tab(layout):
    col = layout.column()
    col.label(text="Action settings coming soon.", icon="INFO")


def _draw_extended_tab(layout):
    col = layout.column()
    col.label(text="Extended settings coming soon.", icon="INFO")


def get_collider_ui_config():
    config = dict(NX_COLLIDER_UI_CONFIG)
    config["collider_objects"]["draw_item_settings"] = draw_collider_item_settings
    return config


_COLLIDER_ITEM_SYNC_SPECS = (
    SyncSpec.param("enum", "ID_NX_COLLIDER_NORMALS", "ID_NX_COLLIDER_NORMALS"),
    SyncSpec.param("float", "ID_NX_COLLIDER_BOUNCE", "ID_NX_COLLIDER_BOUNCE", scale=0.01),
    SyncSpec.param("float", "ID_NX_COLLIDER_FRICTION", "ID_NX_COLLIDER_FRICTION", scale=0.01),
    SyncSpec.param("float", "ID_NX_COLLIDER_SCATTER", "ID_NX_COLLIDER_SCATTER", scale=0.01),
    SyncSpec.param("float", "ID_NX_COLLIDER_EXPAND", "ID_NX_COLLIDER_EXPAND", scale=0.01),
)

NexusColliderItem._sync_specs = _COLLIDER_ITEM_SYNC_SPECS


SPEC = ModifierPropertySpec(
    modifier_type="NX_COLLIDER",
    descriptors=(
        ENABLED_DESCRIPTOR,
        *(
            PropertyDescriptor(name=n, prop=p, preset=False, reset=True, snapshot=True)
            for n, p in _COLLIDER_OBJECTS.properties("collider_objects").items()
        ),
    ),
    item_classes=(NexusColliderItem,),
    enum_defaults={},
)


# `collider_objects` is a scene-link list; not preset-captured.
