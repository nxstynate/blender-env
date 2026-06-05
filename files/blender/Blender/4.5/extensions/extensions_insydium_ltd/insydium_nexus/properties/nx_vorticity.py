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

from bpy.props import FloatProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

NX_VORTICITY_UI_CONFIG = {}


def get_vorticity_ui_config():
    return NX_VORTICITY_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_VORTICITY",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_VORTICITY_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Radius of the vorticity effect",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                max=1000.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_VORTICITY_CON",
            prop=FloatProperty(
                name="Strength",
                description="Strength of the vorticity effect",
                default=1.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_VORTICITY_FORCE_LIMIT",
            prop=FloatProperty(
                name="Force Limit",
                description="Maximum force applied by the vorticity effect",
                default=1000.0,
                min=0.0,
                max=1000.0,
            ),
        ),
    ),
)
