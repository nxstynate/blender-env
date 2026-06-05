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
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

NX_WIND_UI_CONFIG = {
    "wind_turb_expanded": {"use_property_split": False},
}


def get_wind_ui_config():
    return NX_WIND_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_WIND",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_WIND_MODE",
            prop=EnumProperty(
                name="Mode",
                description="Wind simulation mode",
                items=[
                    ("ID_NX_WIND_MODE_STANDARD", "Standard", "Standard wind simulation"),
                    (
                        "ID_NX_WIND_MODE_VON_KARMAN",
                        "Von Kármán",
                        "Von Kármán turbulence model",
                    ),
                ],
                default="ID_NX_WIND_MODE_STANDARD",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_STR",
            prop=FloatProperty(
                name="Strength",
                description="Wind strength",
                default=1.5,
                soft_min=-5.0,
                soft_max=5.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_STR_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Variation in wind strength",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="wind_turb_expanded",
            prop=BoolProperty(
                name="Turbulence",
                description="Expand turbulence settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_TURB_STR",
            prop=FloatProperty(
                name="Strength",
                description="Turbulence strength",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_TURB_AXIS_STR",
            prop=FloatVectorProperty(
                name="Axis Strength",
                description="Turbulence strength per axis",
                default=(100.0, 100.0, 100.0),
                min=0.0,
                soft_max=100.0,
                size=3,
                subtype="XYZ",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_COORD_SPACE",
            prop=EnumProperty(
                name="Coordinate Space",
                description="Coordinate space for turbulence calculation",
                items=[
                    ("ID_NX_WIND_COORD_SPACE_LOCAL", "Local", "Use local coordinates"),
                    ("ID_NX_WIND_COORD_SPACE_WORLD", "World", "Use world coordinates"),
                ],
                default="ID_NX_WIND_COORD_SPACE_LOCAL",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_TURB_FREQ",
            prop=FloatProperty(
                name="Frequency",
                description="Turbulence frequency",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_TURB_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Turbulence scale",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WIND_FRICTION_VELOCITY",
            prop=FloatProperty(
                name="Friction Velocity",
                description="Friction velocity for turbulence",
                default=0.1,
                min=0.0,
                soft_max=1.0,
                step=1,
                precision=2,
            ),
        ),
    ),
)
