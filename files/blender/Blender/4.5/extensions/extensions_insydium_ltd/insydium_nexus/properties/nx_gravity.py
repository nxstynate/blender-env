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
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform


def _on_effect_towards_update(self, context):
    obj = self.id_data
    if obj.get("nexus_modifier_type") != "NX_GRAVITY":
        return

    from ..modifiers.nx_gravity import NXGravityModifier

    NXGravityModifier._update_effect_towards(obj, self.gravity_effect_towards)


NX_GRAVITY_UI_CONFIG = {}


def get_gravity_ui_config():
    return NX_GRAVITY_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_GRAVITY",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_GRAVITY_STRENGTH",
            prop=FloatProperty(
                name="Strength",
                description="Gravitational acceleration strength",
                default=9.81,
                soft_min=0.0,
                soft_max=20.0,
                unit="ACCELERATION",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_GRAVITY_STRENGTH_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Variation in gravity strength",
                default=0.0,
                min=0.0,
                soft_max=10.0,
                unit="ACCELERATION",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_GRAVITY_SEED",
            prop=IntProperty(
                name="Seed",
                description="Random seed for variation",
                default=12345,
                min=0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_GRAVITY_VARIATION_MODE",
            prop=EnumProperty(
                name="Variation Mode",
                description="How variation is applied",
                items=[
                    (
                        "ID_NX_GRAVITY_VARIATION_MODE_PER_FRAME",
                        "Per Frame",
                        "Variation changes each frame",
                    ),
                    (
                        "ID_NX_GRAVITY_VARIATION_MODE_PER_PARTICLE",
                        "Per Particle",
                        "Variation is constant per particle",
                    ),
                ],
                default="ID_NX_GRAVITY_VARIATION_MODE_PER_PARTICLE",
            ),
        ),
        PropertyDescriptor(
            name="gravity_effect_towards",
            prop=PointerProperty(
                name="Effect Towards",
                description="Object to direct gravity towards",
                type=bpy.types.Object,
                update=_on_effect_towards_update,
            ),
        ),
    ),
)
