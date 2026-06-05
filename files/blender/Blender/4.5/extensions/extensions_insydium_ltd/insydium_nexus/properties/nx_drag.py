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

from bpy.props import BoolProperty, EnumProperty, FloatProperty

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

DENSITY_PRESETS = {
    "ID_NX_DRAG_DENSITY_VACUUM": 0.0,
    "ID_NX_DRAG_DENSITY_AIR": 1.205,
    "ID_NX_DRAG_DENSITY_CO2": 1.842,
    "ID_NX_DRAG_DENSITY_HELIUM": 0.1664,
    "ID_NX_DRAG_DENSITY_KRYPTON": 3.74,
    "ID_NX_DRAG_DENSITY_XENON": 5.86,
    "ID_NX_DRAG_DENSITY_WATER": 1000.0,
    "ID_NX_DRAG_DENSITY_GASOLINE": 737.0,
    "ID_NX_DRAG_DENSITY_ETHANOL": 789.0,
    "ID_NX_DRAG_DENSITY_GLYCERINE": 1259.0,
    "ID_NX_DRAG_DENSITY_BROMINE": 3120.0,
    "ID_NX_DRAG_DENSITY_TREACLE": 1600.0,
    "ID_NX_DRAG_DENSITY_MERCURY": 13590.0,
    "ID_NX_DRAG_DENSITY_PROPANE": 494.0,
    "ID_NX_DRAG_DENSITY_NAPHTHA": 665.0,
    "ID_NX_DRAG_DENSITY_SEAWATER": 1025.0,
    "ID_NX_DRAG_DENSITY_HEAVYWATER": 1105.0,
}

COEFF_PRESETS = {
    "ID_NX_DRAG_COEFF_MISSILE": 0.01,
    "ID_NX_DRAG_COEFF_FIGHTER": 0.016,
    "ID_NX_DRAG_COEFF_CAR": 0.29,
    "ID_NX_DRAG_COEFF_BIRD": 0.4,
    "ID_NX_DRAG_COEFF_SPHERE": 0.5,
    "ID_NX_DRAG_COEFF_CUBE": 0.8,
    "ID_NX_DRAG_COEFF_HUMAN": 1.15,
    "ID_NX_DRAG_COEFF_RECT": 2.1,
    "ID_NX_DRAG_COEFF_DOLPHIN": 0.0036,
    "ID_NX_DRAG_COEFF_BICYCLE": 0.9,
    "ID_NX_DRAG_COEFF_BICYCLE_RIDER": 1.1,
    "ID_NX_DRAG_COEFF_MCYCLE_RIDER": 1.8,
    "ID_NX_DRAG_COEFF_SHARDS": 1.5,
}


def _on_density_update(self, context):
    preset = self.ID_NX_DRAG_DENSITY
    if preset != "ID_NX_DRAG_DENSITY_CUSTOM" and preset in DENSITY_PRESETS:
        self.ID_NX_DRAG_DENSITY_VALUE = DENSITY_PRESETS[preset]


def _on_coeff_update(self, context):
    preset = self.ID_NX_DRAG_COEFF
    if preset != "ID_NX_DRAG_COEFF_CUSTOM" and preset in COEFF_PRESETS:
        self.ID_NX_DRAG_COEFF_VALUE = COEFF_PRESETS[preset]


NX_DRAG_UI_CONFIG = {}


def get_drag_ui_config():
    return NX_DRAG_UI_CONFIG


SPEC = ModifierPropertySpec(
    modifier_type="NX_DRAG",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_DRAG_DENSITY",
            prop=EnumProperty(
                name="Density",
                description="Density of the medium the particles travel through",
                items=[
                    ("ID_NX_DRAG_DENSITY_VACUUM", "Vacuum", ""),
                    ("", "", ""),
                    ("ID_NX_DRAG_DENSITY_AIR", "Air", ""),
                    ("ID_NX_DRAG_DENSITY_CO2", "Carbon Dioxide", ""),
                    ("ID_NX_DRAG_DENSITY_HELIUM", "Helium", ""),
                    ("ID_NX_DRAG_DENSITY_KRYPTON", "Krypton", ""),
                    ("ID_NX_DRAG_DENSITY_XENON", "Xenon", ""),
                    ("", "", ""),
                    ("ID_NX_DRAG_DENSITY_PROPANE", "Propane (Liquified)", ""),
                    ("ID_NX_DRAG_DENSITY_NAPHTHA", "Naphtha", ""),
                    ("ID_NX_DRAG_DENSITY_GASOLINE", "Gasoline (Petrol)", ""),
                    ("ID_NX_DRAG_DENSITY_ETHANOL", "Ethanol", ""),
                    ("ID_NX_DRAG_DENSITY_WATER", "Water", ""),
                    ("ID_NX_DRAG_DENSITY_GLYCERINE", "Glycerine", ""),
                    ("ID_NX_DRAG_DENSITY_SEAWATER", "Sea Water", ""),
                    ("ID_NX_DRAG_DENSITY_HEAVYWATER", "Heavy Water", ""),
                    ("ID_NX_DRAG_DENSITY_TREACLE", "Treacle", ""),
                    ("ID_NX_DRAG_DENSITY_BROMINE", "Bromine", ""),
                    ("ID_NX_DRAG_DENSITY_MERCURY", "Mercury", ""),
                    ("", "", ""),
                    ("ID_NX_DRAG_DENSITY_CUSTOM", "Custom", ""),
                ],
                default="ID_NX_DRAG_DENSITY_AIR",
                update=_on_density_update,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_DRAG_DENSITY_VALUE",
            prop=FloatProperty(
                name="Density Value",
                description="Custom density value in kg/m³",
                default=1.205,
                min=0.0,
                soft_max=2000.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_DRAG_COEFF",
            prop=EnumProperty(
                name="Drag Coefficient",
                description="Drag coefficient preset based on object shape",
                items=[
                    ("ID_NX_DRAG_COEFF_DOLPHIN", "Dolphin", ""),
                    ("ID_NX_DRAG_COEFF_MISSILE", "Missile", ""),
                    ("ID_NX_DRAG_COEFF_FIGHTER", "Fighter Aircraft", ""),
                    ("ID_NX_DRAG_COEFF_CAR", "Saloon Car", ""),
                    ("ID_NX_DRAG_COEFF_BIRD", "Bird", ""),
                    ("ID_NX_DRAG_COEFF_SPHERE", "Sphere", ""),
                    ("ID_NX_DRAG_COEFF_CUBE", "Cube", ""),
                    ("ID_NX_DRAG_COEFF_BICYCLE", "Bicycle", ""),
                    ("ID_NX_DRAG_COEFF_BICYCLE_RIDER", "Bicycle and Rider", ""),
                    ("ID_NX_DRAG_COEFF_HUMAN", "Human (Upright)", ""),
                    ("ID_NX_DRAG_COEFF_MCYCLE_RIDER", "Motorcycle and Rider", ""),
                    ("ID_NX_DRAG_COEFF_RECT", "Rectangular Box", ""),
                    ("", "", ""),
                    ("ID_NX_DRAG_COEFF_SHARDS", "xpShatter Fragments", ""),
                    ("ID_NX_DRAG_COEFF_CUSTOM", "Custom", ""),
                ],
                default="ID_NX_DRAG_COEFF_SPHERE",
                update=_on_coeff_update,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_DRAG_COEFF_VALUE",
            prop=FloatProperty(
                name="Drag Coeff. Value",
                description="Custom drag coefficient value",
                default=0.5,
                min=0.0,
                soft_max=3.0,
                step=1,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_DRAG_MULTI",
            prop=FloatProperty(
                name="Strength Multiplier",
                description="Overall strength multiplier for the drag effect",
                default=100.0,
                min=0.0,
                soft_max=1000.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_DRAG_USEUNITS",
            prop=BoolProperty(name="Use Scene Units", default=False),
            preset=False,
        ),
    ),
)
