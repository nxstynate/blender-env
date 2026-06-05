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
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

_WAVE_NOISE_TYPE_ITEMS = [
    ("ID_NX_WAVES_NOISE_TYPE_SIMPLEX", "Simplex", "Simplex noise", 0),
    ("ID_NX_WAVES_NOISE_TYPE_FBM", "FBM", "Fractal Brownian Motion", 1),
    ("ID_NX_WAVES_NOISE_TYPE_TURBULENCE", "Turbulence", "Turbulence noise", 2),
    ("ID_NX_WAVES_NOISE_TYPE_WAVY_TURBULENCE", "Wavy Turbulence", "Wavy turbulence noise", 3),
    ("ID_NX_WAVES_NOISE_TYPE_VORO", "Voronoise", "Voronoi-based noise", 4),
    ("ID_NX_WAVES_NOISE_TYPE_CUBIC", "Cubic", "Cubic noise", 5),
]

_WAVE_DRAW_TYPE_ITEMS = [
    ("NONE", "None", "No visualization", 0),
    ("LINE", "Lines", "Draw displacement lines", 1),
    ("ARROW", "Arrows", "Draw displacement arrows", 2),
    ("SURFACE", "Surface", "Draw filled surface", 3),
    ("GRID", "Grid", "Draw wireframe grid", 4),
    ("PLANE", "Plane", "Draw flat colored plane", 5),
]


def _get_wave_noise_type_items(self, context):
    return _WAVE_NOISE_TYPE_ITEMS


def _get_wave_draw_type_items(self, context):
    return _WAVE_DRAW_TYPE_ITEMS


def build_wave_enum_items():
    pass


NX_WAVE_UI_CONFIG = {}


def get_wave_ui_config():
    return NX_WAVE_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_WAVE",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_WAVES_SPEED",
            prop=FloatProperty(
                name="Speed",
                description="Wave animation speed",
                default=1.0,
                soft_min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_STRENGTH",
            prop=FloatProperty(
                name="Strength",
                description="Displacement multiplier",
                default=0.1,
                soft_min=0.0,
                soft_max=1.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="wave_size_x",
            prop=FloatProperty(
                name="Size X",
                description="Bounding box size along X axis",
                default=2.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
        PropertyDescriptor(
            name="wave_size_y",
            prop=FloatProperty(
                name="Size Y",
                description="Bounding box size along Y axis",
                default=2.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
        PropertyDescriptor(
            name="wave_size_z",
            prop=FloatProperty(
                name="Size Z",
                description="Bounding box size along Z axis",
                default=2.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_TIME_SCALE",
            prop=FloatProperty(
                name="Time Scale",
                description="Time multiplier for wave animation",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="wave_scale_x",
            prop=FloatProperty(
                name="Scale X",
                description="Noise scale along X axis",
                default=10.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="wave_scale_y",
            prop=FloatProperty(
                name="Scale Y",
                description="Noise scale along Y axis",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="wave_scale_z",
            prop=FloatProperty(
                name="Scale Z",
                description="Noise scale along Z axis",
                default=0.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_NOISE_TYPE",
            prop=EnumProperty(
                name="Noise Type",
                description=("Type of noise to use for wave generation"),
                items=_get_wave_noise_type_items,
                default=2,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_LOW_CLIP",
            prop=FloatProperty(
                name="Low Clip",
                description="Minimum noise value threshold",
                default=0.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_HIGH_CLIP",
            prop=FloatProperty(
                name="High Clip",
                description="Maximum noise value threshold",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_BRIGHTNESS",
            prop=FloatProperty(
                name="Brightness",
                description="Brightness adjustment for noise",
                default=0.0,
                min=-100.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_WAVES_CONTRAST",
            prop=FloatProperty(
                name="Contrast",
                description="Contrast adjustment for noise",
                default=100.0,
                min=-100.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="wave_draw_type",
            prop=EnumProperty(
                name="Draw Type",
                description=("Visualization mode for the wave effect"),
                items=_get_wave_draw_type_items,
                default=3,
            ),
        ),
        PropertyDescriptor(
            name="wave_slices",
            prop=IntProperty(
                name="Slices",
                description="Number of visualization slices",
                default=1,
                min=1,
                soft_max=10,
            ),
        ),
        PropertyDescriptor(
            name="wave_grid_spacing_x",
            prop=FloatProperty(
                name="Grid Spacing X",
                description="Grid spacing along X axis",
                default=0.16,
                min=0.001,
                soft_max=1.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
        PropertyDescriptor(
            name="wave_grid_spacing_y",
            prop=FloatProperty(
                name="Grid Spacing Y",
                description=("Grid spacing along Y axis (forward direction)"),
                default=0.16,
                min=0.001,
                soft_max=1.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
        ),
    ),
    enum_builders=(build_wave_enum_items,),
    enum_defaults={
        "ID_NX_WAVES_NOISE_TYPE": "ID_NX_WAVES_NOISE_TYPE_TURBULENCE",
        "wave_draw_type": "SURFACE",
    },
)
