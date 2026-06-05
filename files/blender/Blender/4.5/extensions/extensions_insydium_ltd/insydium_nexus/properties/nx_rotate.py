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

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

NX_ROTATE_UI_CONFIG = {}


def get_rotate_ui_config():
    return NX_ROTATE_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_ROTATE",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_ROTATE_TYPE",
            prop=EnumProperty(
                name="Type",
                description="How rotation affects particles",
                items=[
                    ("ID_NX_ROTATE_TYPE_FORCE", "Force", "Apply rotational force"),
                    ("ID_NX_ROTATE_TYPE_VEL", "Velocity", "Directly set rotational velocity"),
                ],
                default="ID_NX_ROTATE_TYPE_FORCE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_VALUE",
            prop=FloatProperty(
                name="Rotate Speed",
                description="Speed of rotation",
                default=math.pi,
                subtype="ANGLE",
                step=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_SPEEDMULT",
            prop=FloatProperty(
                name="Speed Multiplier",
                description="Multiplier applied to rotation speed",
                default=1.0,
                soft_min=-5.0,
                soft_max=5.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_ATTRACT",
            prop=FloatProperty(
                name="Attraction",
                description="How strongly particles are attracted to the rotation axis",
                default=10.0,
                subtype="PERCENTAGE",
                min=-100.0,
                max=100.0,
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="rotate_accel_expanded",
            prop=BoolProperty(
                name="Angular Acceleration",
                description="Expand angular acceleration and clamping settings",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_ACCEL",
            prop=FloatProperty(
                name="Angular Accel",
                description="Angular acceleration applied to rotation",
                default=0.0,
                subtype="ANGLE",
                step=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_SPEEDCLAMP",
            prop=EnumProperty(
                name="Clamp",
                description="Clamp rotation speed to min/max values",
                items=[
                    ("ROTATE_SPEEDCLAMP_NONE", "Neither", "No clamping"),
                    ("ROTATE_SPEEDCLAMP_BOTH", "Both", "Clamp to both min and max"),
                    ("ROTATE_SPEEDCLAMP_MIN", "Min", "Clamp to minimum only"),
                    ("ROTATE_SPEEDCLAMP_MAX", "Max", "Clamp to maximum only"),
                ],
                default="ROTATE_SPEEDCLAMP_NONE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_SPEEDCLAMP_MIN",
            prop=FloatProperty(
                name="Min Rotation Speed",
                description="Minimum rotation speed when clamping is enabled",
                default=0.0,
                subtype="ANGLE",
                step=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_SPEEDCLAMP_MAX",
            prop=FloatProperty(
                name="Max Rotation Speed",
                description="Maximum rotation speed when clamping is enabled",
                default=math.pi,
                subtype="ANGLE",
                step=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_ROTATE_FORCELIMIT",
            prop=FloatProperty(
                name="Escape Velocity",
                description="Velocity at which particles escape the rotation field",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
    ),
)
