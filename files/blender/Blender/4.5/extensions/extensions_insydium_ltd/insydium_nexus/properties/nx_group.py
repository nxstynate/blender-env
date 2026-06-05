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

from bpy.props import (
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform
from ..utils import XP_COLOR_MODS_GREEN

_GROUP_DISPLAY_MODE_DEFS = [
    (
        "ID_NX_EMITTER_DISPLAY_MODE_DOT",
        "Points",
        "Display particles as dots",
        "nx_emitter_display_dot",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_BOX",
        "Square",
        "Display particles as squares",
        "nx_emitter_display_square",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_LINE",
        "Line",
        "Display particles as lines",
        "nx_emitter_display_line",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_BOX3D",
        "Box 3D",
        "Display particles as 3D boxes",
        "nx_emitter_display_box",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_BOX3D_FILLED",
        "Box 3D Filled",
        "Solid 3D boxes",
        "nx_emitter_display_box_filled",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE",
        "Circle",
        "Display particles as circles",
        "nx_emitter_display_circle",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_CIRCLE_FILLED",
        "Circle Filled",
        "Filled circles",
        "nx_emitter_display_circle_filled",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID",
        "Pyramid",
        "Display particles as pyramids",
        "nx_emitter_display_pyramid",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_PYRAMID_FILLED",
        "Pyramid Filled",
        "Solid pyramids",
        "nx_emitter_display_pyramid_filled",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_ARROW",
        "Arrow",
        "Display particles as arrows",
        "nx_emitter_display_arrow",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_ARROW_FILLED",
        "Arrow Filled",
        "Solid arrows",
        "nx_emitter_display_arrow_filled",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_SPHERE",
        "Sphere",
        "Display particles as solid 3D spheres",
        "nx_emitter_display_sphere",
    ),
    (
        "ID_NX_EMITTER_DISPLAY_MODE_AXIS",
        "Axis",
        "Display particle local axes (X=red, Y=green, Z=blue)",
        "nx_emitter_display_line",
    ),
    ("ID_NX_EMITTER_DISPLAY_MODE_NONE", "None", "Hide particle display", None),
]
_GROUP_DISPLAY_MODE_ITEMS = []

_GROUP_COLOR_MODE_ITEMS = [
    ("ID_NX_EMITTER_COLOR_MODE_SINGLE", "Single Color", "Use a single color for all particles"),
    (
        "ID_NX_EMITTER_COLOR_MODE_GRADIENT",
        "Gradient",
        "Use a gradient to color particles",
    ),
    ("ID_NX_EMITTER_COLOR_MODE_SHADER", "Shader", "Use shader to color particles"),
    ("ID_NX_EMITTER_COLOR_MODE_OBJECT", "Object Color", "Use object colors for particles"),
    ("ID_NX_EMITTER_COLOR_MODE_NOISE", "Noise", "Use noise to color particles at birth"),
]


def build_group_enum_items():
    global _GROUP_DISPLAY_MODE_ITEMS
    from ..icons import get_icon

    _GROUP_DISPLAY_MODE_ITEMS = []
    for idx, (value, label, desc, icon_name) in enumerate(_GROUP_DISPLAY_MODE_DEFS):
        icon = get_icon(icon_name) if icon_name is not None else 0
        _GROUP_DISPLAY_MODE_ITEMS.append((value, label, desc, icon, idx))


def _get_group_display_mode_items(self, context):
    return _GROUP_DISPLAY_MODE_ITEMS


SPEC = ModifierPropertySpec(
    modifier_type="NX_GROUP",
    enum_builders=(build_group_enum_items,),
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_GROUP_ID",
            prop=IntProperty(
                name="Group ID",
                description="Numeric identifier for this particle group",
                default=1,
                min=1,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_DISPLAY_MODE",
            prop=EnumProperty(
                name="Display Mode",
                description="How this group is displayed in the viewport",
                items=_get_group_display_mode_items,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_COLOR_MODE",
            prop=EnumProperty(
                name="Color Mode",
                description="How the particle colors are determined",
                items=_GROUP_COLOR_MODE_ITEMS,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_COLOR",
            prop=FloatVectorProperty(
                name="Color",
                description="Display color for this group",
                default=XP_COLOR_MODS_GREEN,
                subtype="COLOR",
                size=4,
                min=0.0,
                max=1.0,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_SPEED",
            prop=FloatProperty(
                name="Speed",
                description="Initial particle speed",
                default=1.5,
                min=0.0,
                soft_max=100.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_SPEED_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in initial speed",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Physical radius of each particle",
                default=0.03,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_RADIUS_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in particle radius",
                default=0.0,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_MASS",
            prop=FloatProperty(
                name="Mass",
                description="Mass of each particle",
                default=1.0,
                min=0.0,
                soft_max=100.0,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="ID_NX_GROUP_MASS_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in particle mass",
                default=0.0,
                min=0.0,
                soft_max=100.0,
            ),
            preset=False,
        ),
    ),
)
