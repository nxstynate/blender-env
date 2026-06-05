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
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.theron_sync import SyncType, Transform


def _clamp_variation_to_speed(self, context):
    if self.ID_NX_EXPLODE_SPEED_VAR > self.ID_NX_EXPLODE_SPEED:
        self.ID_NX_EXPLODE_SPEED_VAR = self.ID_NX_EXPLODE_SPEED


NX_EXPLODE_UI_CONFIG = {}


def get_explode_ui_config():
    return NX_EXPLODE_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_EXPLODE",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="explode_display_expanded",
            prop=BoolProperty(
                name="Viewport Display",
                default=False,
            ),
            preset=False,
        ),
        PropertyDescriptor(
            name="explode_icon_size",
            prop=FloatProperty(
                name="Icon Size",
                description="Size of the viewport gizmo",
                default=1.0,
                min=0.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_TIMING",
            prop=EnumProperty(
                name="Timing",
                description="When the explode effect triggers",
                items=[
                    ("EXPLODE_TIMING_NONE", "Always On", "Effect is always active"),
                    (
                        "EXPLODE_TIMING_SCENE",
                        "Trigger at Scene Time",
                        "Trigger at a specific scene time",
                    ),
                    (
                        "EXPLODE_TIMING_AGE",
                        "Trigger at Particle Age",
                        "Trigger at a specific particle age",
                    ),
                ],
                default="EXPLODE_TIMING_NONE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_TIMING_MODE",
            prop=EnumProperty(
                name="Timing Mode",
                description="How to compare against the trigger time",
                items=[
                    (
                        "EXPLODE_TIMING_MODE_EQUAL",
                        "Equals",
                        "Trigger when time equals the specified value",
                    ),
                    (
                        "EXPLODE_TIMING_MODE_OVER",
                        "Equals or Greater Than",
                        "Trigger when time equals or exceeds the specified value",
                    ),
                    (
                        "EXPLODE_TIMING_MODE_UNDER",
                        "Equals or Less Than",
                        "Trigger when time equals or is less than the specified value",
                    ),
                ],
                default="EXPLODE_TIMING_MODE_EQUAL",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_TIME",
            prop=nexus_time_property(
                "ID_NX_EXPLODE_TIME",
                name="Time",
                description="Time value for triggering the effect",
                default=1.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_SOURCE",
            prop=EnumProperty(
                name="Explode Away From",
                description="The point particles explode away from",
                items=[
                    (
                        "EXPLODE_SOURCE_PCENTER",
                        "Particle Mass Center",
                        "Explode away from the particle's mass center",
                    ),
                    (
                        "EXPLODE_SOURCE_THIS",
                        "This Modifier",
                        "Explode away from this modifier's position",
                    ),
                ],
                default="EXPLODE_SOURCE_PCENTER",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_SPEED",
            prop=FloatProperty(
                name="Speed",
                description="Speed of the explosion",
                default=5.0,
                min=0.0,
                soft_max=20.0,
                unit="VELOCITY",
                subtype="NONE",
                update=_clamp_variation_to_speed,
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_SPEED_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in explosion speed",
                default=0.0,
                min=0.0,
                soft_max=20.0,
                unit="VELOCITY",
                subtype="NONE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_SEED",
            prop=IntProperty(
                name="Seed",
                description="Random seed for variation",
                default=12345,
                min=0,
                soft_max=10000,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_UNSTICK",
            prop=BoolProperty(
                name="Unstick if Necessary",
                description="Unstick particles that are stuck to surfaces",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_EXPLODE_MAP_START",
            prop=BoolProperty(
                name="Set Speed at Start Only",
                description="Only set the explosion speed at the start of the effect",
                default=True,
            ),
        ),
    ),
)
