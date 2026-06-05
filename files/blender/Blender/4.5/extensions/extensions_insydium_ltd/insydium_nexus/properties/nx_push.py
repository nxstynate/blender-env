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

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.theron_sync import SyncType, Transform

NX_PUSH_UI_CONFIG = {}


def get_push_ui_config():
    return NX_PUSH_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_PUSH",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_PUSH_DISTANCE_MODE",
            prop=EnumProperty(
                name="Distance Mode",
                description="How to determine push distance",
                items=[
                    ("ID_NX_PUSH_DISTANCE_MODE_ABSOLUTE", "Absolute", "Use fixed distance"),
                    ("ID_NX_PUSH_DISTANCE_MODE_RADIUS", "Particle Radius", "Use particle radius"),
                ],
                default=0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_PUSH_DISTANCE",
            prop=FloatProperty(
                name="Distance",
                description="Distance to push particles apart",
                default=0.1,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_PUSH_STRENGTH",
            prop=FloatProperty(
                name="Strength",
                description="Strength of the push effect",
                default=50.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_PUSH_ITERS",
            prop=IntProperty(
                name="Iterations",
                description="Number of push iterations per frame",
                default=5,
                min=2,
                soft_max=20,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_PUSH_EASEIN",
            prop=nexus_time_property(
                "ID_NX_PUSH_EASEIN",
                name="Ease In",
                description="Time before push effect reaches full strength",
                default=0.0,
                min=0.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_PUSH_SAMEGROUP",
            prop=BoolProperty(
                name="Only Same Group",
                description="Only push particles within the same group",
                default=False,
            ),
        ),
    ),
)
