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

from bpy.props import EnumProperty, FloatProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.nodetree_sync import BlendSpec
from ..libs.theron_sync import SyncType, Transform

NX_BLEND_UI_CONFIG = {}

NX_BLEND_BLEND_SPEC = BlendSpec(
    mode_id_name="ID_NX_BLEND_TYPE",
    strength_id_name="ID_NX_BLEND_STRENGTH",
    id_map={
        "NORMAL": "ID_NX_BLEND_TYPE_NORMAL",
        "ADDITION": "ID_NX_BLEND_TYPE_ADDITION",
        "SUBTRACT": "ID_NX_BLEND_TYPE_SUBTRACT",
        "MULTIPLY": "ID_NX_BLEND_TYPE_MULTIPLY",
        "DIFFERENCE": "ID_NX_BLEND_TYPE_DIFFERENCE",
        "SCREEN": "ID_NX_BLEND_TYPE_SCREEN",
        "OVERLAY": "ID_NX_BLEND_TYPE_OVERLAY",
    },
    mode_attr="blend_type",
    strength_attr="blend_strength",
    labels={
        "NORMAL": ("Normal", "Normal blending"),
        "ADDITION": ("Addition", "Additive blending"),
        "SUBTRACT": ("Subtract", "Subtractive blending"),
        "MULTIPLY": ("Multiply", "Multiplicative blending"),
        "DIFFERENCE": ("Difference", "Difference blending"),
        "SCREEN": ("Screen", "Screen blending"),
        "OVERLAY": ("Overlay", "Overlay blending"),
    },
)


def get_blend_ui_config():
    return NX_BLEND_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_BLEND",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="blend_type",
            prop=EnumProperty(
                name="Blend",
                description="Blending mode for particle parameters",
                items=NX_BLEND_BLEND_SPEC.enum_items(),
                default="NORMAL",
            ),
        ),
        PropertyDescriptor(
            name="blend_strength",
            prop=FloatProperty(
                name="Strength",
                description="Overall blend strength",
                default=10.0,
                min=0.0,
                max=1000.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_DISTANCE",
            prop=FloatProperty(
                name="Distance",
                description="Maximum distance for particle blending",
                default=0.1,
                min=0.0,
                soft_max=2.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_MAXBLEND",
            prop=nexus_time_property(
                "ID_NX_BLEND_MAXBLEND",
                name="Max Blend",
                description=("Maximum particle age for blending to apply"),
                default=300.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_PARAMS_RADIUS",
            prop=FloatProperty(
                name="Radius",
                description="Blend amount for particle radius",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_PARAMS_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Blend amount for particle scale",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_PARAMS_MASS",
            prop=FloatProperty(
                name="Mass",
                description="Blend amount for particle mass",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_PARAMS_ROTATION",
            prop=FloatProperty(
                name="Rotation",
                description="Blend amount for particle rotation",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_BLEND_PARAMS_COLOR",
            prop=FloatProperty(
                name="Color",
                description="Blend amount for particle color",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
    ),
    blend_spec=NX_BLEND_BLEND_SPEC,
)
