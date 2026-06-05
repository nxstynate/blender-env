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

from bpy.props import EnumProperty, FloatProperty, IntProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform
from ..ui import NodeTreeDef

_ATTRACT_OBJECTS = NodeTreeDef("Attractors")
_attract_tree_props = _ATTRACT_OBJECTS.properties("attract_objects")

NX_ATTRACT_UI_CONFIG = {
    **_ATTRACT_OBJECTS.ui_config("attract_objects"),
}


def get_attract_ui_config():
    return NX_ATTRACT_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_ATTRACT",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_ATTRACT_TYPE",
            prop=EnumProperty(
                name="Type",
                description="How attraction affects particles",
                items=[
                    (
                        "ID_NX_ATTRACT_TYPE_VELOCITY",
                        "Velocity",
                        "Affect particle velocity directly",
                    ),
                    ("ID_NX_ATTRACT_TYPE_FORCE", "Force", "Apply force to particles"),
                ],
                default="ID_NX_ATTRACT_TYPE_VELOCITY",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ATTRACT_FORCE",
            prop=FloatProperty(
                name="Force",
                description="Attraction force strength",
                default=30.0,
                soft_min=-300.0,
                soft_max=300.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ATTRACT_GRAVITY",
            prop=FloatProperty(
                name="Acceleration",
                description="Acceleration towards attractor",
                default=3.0,
                soft_min=-30.0,
                soft_max=30.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_ATTRACT_SPEEDLIMIT",
            prop=FloatProperty(
                name="Speed Limit",
                description="Maximum speed of attracted particles",
                default=2.5,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_ATTRACT_OBJMODE",
            prop=EnumProperty(
                name="Object Select",
                description=(
                    "How to select the target when multiple objects are in the attract list"
                ),
                items=[
                    (
                        "ID_NX_ATTRACT_OBJMODE_NEAREST",
                        "Nearest",
                        "Attract to the nearest object",
                    ),
                    (
                        "ID_NX_ATTRACT_OBJMODE_FURTHEST",
                        "Furthest",
                        "Attract to the furthest object",
                    ),
                    (
                        "ID_NX_ATTRACT_OBJMODE_AVERAGE",
                        "Average",
                        "Attract to the average position of all objects",
                    ),
                    (
                        "ID_NX_ATTRACT_OBJMODE_INDEX",
                        "Index",
                        "Attract to a specific object by index",
                    ),
                    (
                        "ID_NX_ATTRACT_OBJMODE_RANDOM",
                        "Random",
                        "Attract to a random object",
                    ),
                ],
                default="ID_NX_ATTRACT_OBJMODE_NEAREST",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ATTRACT_OBJINDEX",
            prop=IntProperty(
                name="Index",
                description="Index of the target object when mode is Index",
                default=0,
                min=0,
                soft_max=1000,
            ),
        ),
        PropertyDescriptor(
            name="attract_objects",
            prop=_attract_tree_props["attract_objects"],
        ),
        PropertyDescriptor(
            name="attract_objects_index",
            prop=_attract_tree_props["attract_objects_index"],
        ),
        PropertyDescriptor(
            name="attract_objects_drop_target",
            prop=_attract_tree_props.get("attract_objects_drop_target"),
            preset=False,
        ),
    ),
)


# Pure scene-link list; not portable preset data.
