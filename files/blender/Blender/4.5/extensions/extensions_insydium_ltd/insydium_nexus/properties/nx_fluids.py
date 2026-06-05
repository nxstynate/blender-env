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
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.theron_sync import SyncType, Transform

_FLUIDS_SOLVER_ITEMS = []
_FLUIDS_SPH_TYPE_ITEMS = []
_FLUIDS_FLIP_TAB_ITEMS = [
    ("DOMAIN", "Domain", "Domain settings", 0),
    ("SOLVER", "Solver Accuracy", "Solver settings", 1),
]

_FLUIDS_WALL_TYPE_ITEMS = []

_FLUIDS_FLIP_GRID_ITEMS = [
    ("NONE", "None", "Don't draw grid", 0),
    ("VOXELS", "Voxels", "Draw all voxels", 1),
    ("BACK", "Back only", "Draw back faces only", 2),
    ("BASE", "Base only", "Draw base plane only", 3),
    ("BASEANDBACK", "Base and Back", "Draw base plane and back faces", 4),
]


def build_fluids_enum_items():
    global _FLUIDS_SOLVER_ITEMS, _FLUIDS_SPH_TYPE_ITEMS, _FLUIDS_WALL_TYPE_ITEMS

    from ..icons import get_icon

    _FLUIDS_SOLVER_ITEMS = [
        (
            "PBD",
            "PBD",
            "Position Based Dynamics solver",
            get_icon("nx_fluids_solver_pbd"),
            0,
        ),
        (
            "SPH",
            "SPH",
            "Smoothed Particle Hydrodynamics solver",
            get_icon("nx_fluids_solver_sph"),
            1,
        ),
        (
            "FLIP",
            "FLIP",
            "Fluid Implicit Particle solver",
            get_icon("nx_fluids_solver_flip"),
            2,
        ),
        (
            "APIC",
            "APIC",
            "Affine Particle-In-Cell solver",
            get_icon("nx_fluids_solver_apic"),
            3,
        ),
    ]

    _FLUIDS_SPH_TYPE_ITEMS = [
        (
            "LIQUID",
            "Liquid",
            "SPH liquid simulation",
            get_icon("nx_fluids_type_liquid"),
            0,
        ),
        (
            "GRANULAR",
            "Granular",
            "SPH granular material simulation",
            get_icon("nx_fluids_type_granular"),
            1,
        ),
    ]

    _FLUIDS_WALL_TYPE_ITEMS = [
        (
            "OPEN",
            "Open",
            "Particles can pass through this boundary",
            get_icon("nx_fluids_wall_open"),
            0,
        ),
        (
            "CLOSED",
            "Closed",
            "Particles collide with this boundary",
            get_icon("nx_fluids_wall_closed"),
            1,
        ),
        (
            "KILL",
            "Kill",
            "Particles are killed at this boundary",
            get_icon("nx_fluids_wall_kill"),
            2,
        ),
    ]


def _get_fluids_solver_items(self, context):
    return _FLUIDS_SOLVER_ITEMS


def _get_fluids_sph_type_items(self, context):
    return _FLUIDS_SPH_TYPE_ITEMS


def _get_fluids_flip_tab_items(self, context):
    return _FLUIDS_FLIP_TAB_ITEMS


def _get_fluids_wall_type_items(self, context):
    return _FLUIDS_WALL_TYPE_ITEMS


def _get_fluids_flip_grid_items(self, context):
    return _FLUIDS_FLIP_GRID_ITEMS


NX_FLUIDS_UI_CONFIG = {
    "fluids_pbd_solver_expanded": {"use_property_split": False},
    "fluids_pbd_liquid_expanded": {"use_property_split": False},
    "fluids_sph_solver_expanded": {"use_property_split": False},
    "fluids_sph_liquid_expanded": {"use_property_split": False},
    "fluids_sph_granular_expanded": {"use_property_split": False},
    "fluids_sph_substeps_expanded": {"use_property_split": False},
}


def get_fluids_ui_config():
    return NX_FLUIDS_UI_CONFIG


# ---------------------------------------------------------------------------
# Condition helpers
# ---------------------------------------------------------------------------


def _is_pbd(p):
    return p.ID_XPFLUIDGPU_SOLVER_CHOICE == "PBD"


def _is_sph(p):
    return p.ID_XPFLUIDGPU_SOLVER_CHOICE == "SPH"


def _is_flip_apic(p):
    return p.ID_XPFLUIDGPU_SOLVER_CHOICE in ("FLIP", "APIC")


def _is_flip_only(p):
    return p.ID_XPFLUIDGPU_SOLVER_CHOICE == "FLIP"


_WALL_ENUM_MAP = {
    "OPEN": "ID_NX_FLIPFLUIDS_BOUNDARYWALLTYPE_OPEN",
    "CLOSED": "ID_NX_FLIPFLUIDS_BOUNDARYWALLTYPE_CLOSED",
    "KILL": "ID_NX_FLIPFLUIDS_BOUNDARYWALLTYPE_KILL",
}

# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

SPEC = ModifierPropertySpec(
    modifier_type="NX_FLUIDS",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SOLVER_CHOICE",
            prop=EnumProperty(
                name="Solver",
                description="Fluid simulation solver type",
                items=_get_fluids_solver_items,
            ),
            enum_map={
                "PBD": "ID_XPFLUIDGPU_SOLVER_CHOICE_PBD",
                "SPH": "ID_XPFLUIDGPU_SOLVER_CHOICE_SPH",
                "FLIP": "ID_XPFLUIDGPU_SOLVER_CHOICE_FLIP",
                "APIC": "ID_XPFLUIDGPU_SOLVER_CHOICE_APIC",
            },
        ),
        # -- PBD Solver --
        PropertyDescriptor(
            name="fluids_pbd_solver_expanded",
            prop=BoolProperty(
                name="Solver",
                description="Expand solver settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_KERNEL_RADIUS",
            prop=FloatProperty(
                name="Smoothing Radius",
                description="Radius of influence for particle interactions",
                default=100.0,
                min=0.0,
                max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_SUBSTEPS",
            prop=IntProperty(
                name="Substeps",
                description="Number of simulation substeps per frame",
                default=6,
                min=1,
                max=30,
            ),
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_EASEIN",
            prop=nexus_time_property(
                "ID_XPFLUIDGPU_EASEIN",
                name="Ease In",
                description="Time to ease in the simulation",
                default=0.0,
                min=0.0,
            ),
            sync_type=SyncType.TIME,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_DENSITY_MIN",
            prop=IntProperty(
                name="Min Density",
                description="Minimum density solver iterations",
                default=1,
                min=1,
                max=30,
            ),
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_DENSITY_ITERATIONS",
            prop=IntProperty(
                name="Max Density",
                description="Maximum density solver iterations",
                default=10,
                min=1,
                max=30,
            ),
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_DENSITY_COMPRESSION",
            prop=FloatProperty(
                name="Density Compression",
                description="Amount of density compression allowed",
                default=20.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_CHECKDENSITY",
            prop=BoolProperty(
                name="Check Density",
                description="Enable density checking",
                default=False,
            ),
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_CHECKDENSITY_MAX",
            prop=FloatProperty(
                name="Max Density",
                description="Maximum allowed density for checking",
                default=110.0,
                min=0.0,
                max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_CHECKDENSITY_ITERS",
            prop=IntProperty(
                name="Iterations",
                description="Number of iterations for density checking",
                default=3,
                min=1,
                max=40,
            ),
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="fluids_pbd_liquid_expanded",
            prop=BoolProperty(
                name="Liquid",
                description="Expand liquid settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_VISCOCITY",
            prop=FloatProperty(
                name="Viscosity",
                description="Fluid viscosity",
                default=5.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_VORTICITY",
            prop=FloatProperty(
                name="Vorticity",
                description="Vorticity confinement strength",
                default=1.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_TENSION",
            prop=FloatProperty(
                name="Attraction",
                description="Particle attraction strength",
                default=10.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_REPULSION",
            prop=FloatProperty(
                name="Repulsion",
                description="Particle repulsion strength",
                default=20.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_PBF_EXTPRESSURE",
            prop=FloatProperty(
                name="Ext Pressure",
                description="External pressure applied to particles",
                default=10.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_pbd,
        ),
        # -- SPH Solver --
        PropertyDescriptor(
            name="fluids_sph_solver_expanded",
            prop=BoolProperty(
                name="Solver",
                description="Expand solver settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_TYPE",
            prop=EnumProperty(
                name="Fluid Type",
                description="SPH simulation type",
                items=_get_fluids_sph_type_items,
            ),
            condition=_is_sph,
            enum_map={
                "LIQUID": "ID_XPFLUIDGPU_SPH_TYPE_LIQUID",
                "GRANULAR": "ID_XPFLUIDGPU_SPH_TYPE_GRANULAR",
            },
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_RADIUS",
            prop=FloatProperty(
                name="Smoothing Radius",
                description="Particle influence radius",
                default=100.0,
                min=0.01,
                max=150.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_SUBSTEPS",
            prop=IntProperty(
                name="Substeps",
                description="Number of simulation substeps per frame",
                default=6,
                min=1,
                max=30,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="fluids_sph_substeps_expanded",
            prop=BoolProperty(
                name="Adaptive Substeps",
                description="Expand adaptive substeps settings",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_SUBSTEPS_ADAPTIVE",
            prop=BoolProperty(
                name="Adaptive",
                description=("Use adaptive substeps based on particle velocity"),
                default=True,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_SUBSTEPS_MIN",
            prop=IntProperty(
                name="Min",
                description=("Minimum number of substeps when adaptive"),
                default=1,
                min=1,
                max=30,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_SUBSTEPS_CFL",
            prop=FloatProperty(
                name="CFL",
                description="CFL condition for adaptive substeps",
                default=0.4,
                min=0.0,
                max=1.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_DAMPING",
            prop=FloatProperty(
                name="Damping",
                description=("Velocity damping factor for SPH particles"),
                default=10.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_EASEIN",
            prop=nexus_time_property(
                "ID_XPFLUIDGPU_SPH_EASEIN",
                name="Ease In",
                description="Time to ease in the simulation",
                default=0.0,
                min=0.0,
            ),
            sync_type=SyncType.TIME,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_MIN_DENSITY_STEPS",
            prop=IntProperty(
                name="Min Density",
                description="Minimum density solver iterations",
                default=3,
                min=1,
                max=30,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_MAX_DENSITY_STEPS",
            prop=IntProperty(
                name="Max Density",
                description="Maximum density solver iterations",
                default=7,
                min=1,
                max=30,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_MAX_MATERIAL_COMPRESSION",
            prop=FloatProperty(
                name="Max Compression",
                description="Maximum density compression allowed",
                default=1.0,
                min=0.0,
                max=10.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_USE_VELOCITY",
            prop=BoolProperty(
                name="Velocity Correction",
                description=("Apply velocity correction for stability"),
                default=False,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_CHECKDENSITY",
            prop=BoolProperty(
                name="Check Density",
                description="Enable density checking",
                default=False,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_CHECKDENSITY_MAX",
            prop=FloatProperty(
                name="Max Density",
                description="Maximum allowed density for checking",
                default=110.0,
                min=0.0,
                max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_CHECKDENSITY_ITERS",
            prop=IntProperty(
                name="Iterations",
                description=("Number of iterations for density checking"),
                default=3,
                min=1,
                max=40,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="fluids_sph_liquid_expanded",
            prop=BoolProperty(
                name="Liquid",
                description="Expand liquid settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_VISCOSITY_FLOAT",
            prop=FloatProperty(
                name="Viscosity",
                description="Fluid viscosity",
                default=30.0,
                min=0.0,
                soft_max=100.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_VISCOSITY",
            prop=IntProperty(
                name="Viscosity Iter",
                description=("Number of viscosity solver iterations"),
                default=1,
                min=1,
                max=20,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_VORT_S",
            prop=FloatProperty(
                name="Vorticity (Small)",
                description=("Vorticity confinement for small-scale features"),
                default=5.0,
                min=0.0,
                soft_max=100.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_VORT_L",
            prop=FloatProperty(
                name="Vorticity (Large)",
                description=("Vorticity confinement for large-scale features"),
                default=10.0,
                min=0.0,
                soft_max=100.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_SURFACE_TENSION",
            prop=FloatProperty(
                name="Surface Tension",
                description="Surface tension strength",
                default=3.0,
                min=0.0,
                soft_max=500.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_INTERNAL_PRESSURE",
            prop=FloatProperty(
                name="Internal Pressure",
                description="Internal pressure strength",
                default=100.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_EXTERNAL_PRESSURE",
            prop=FloatProperty(
                name="External Pressure",
                description="External pressure strength",
                default=30.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="fluids_sph_granular_expanded",
            prop=BoolProperty(
                name="Granular",
                description="Expand granular settings",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_FRICTION",
            prop=FloatProperty(
                name="Friction",
                description="Particle friction",
                default=3.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_FRICTION_ITERATIONS",
            prop=IntProperty(
                name="Friction Iterations",
                description=("Number of friction solver iterations"),
                default=20,
                min=1,
                soft_max=50,
                max=9999,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_STABILITY",
            prop=FloatProperty(
                name="Stability",
                description="Simulation stability factor",
                default=30.0,
                min=0.01,
                soft_max=100.0,
            ),
            condition=_is_sph,
        ),
        PropertyDescriptor(
            name="ID_XPFLUIDGPU_SPH_COHESION",
            prop=FloatProperty(
                name="Cohesion",
                description="Particle cohesion strength",
                default=10.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_sph,
        ),
        # -- FLIP/APIC --
        PropertyDescriptor(
            name="fluids_flip_tab",
            prop=EnumProperty(
                name="Section",
                description="FLIP/APIC settings section",
                items=_get_fluids_flip_tab_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_VOXELSIZE",
            prop=FloatProperty(
                name="Voxel Size",
                description=("Size of each voxel in the simulation grid"),
                default=0.1,
                min=0.001,
                unit="LENGTH",
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="fluids_flip_domain_size",
            prop=FloatVectorProperty(
                name="Domain Size",
                description="Size of the simulation domain",
                default=(4.0, 4.0, 4.0),
                min=0.1,
                soft_max=100.0,
                unit="LENGTH",
                size=3,
                step=10,
                precision=3,
                subtype="XYZ",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_TIMESCALE",
            prop=FloatProperty(
                name="Retiming",
                description="Simulation timescale",
                default=100.0,
                min=0.0,
                max=500.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_FLIP_PIC_MIX",
            prop=FloatProperty(
                name="FLIP Fraction",
                description=("Mix between PIC (stable) and FLIP (splashy) methods"),
                default=95.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_only,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_VISCOSITY",
            prop=FloatProperty(
                name="Viscosity",
                description="Fluid viscosity",
                default=0.0,
                min=0.0,
                soft_max=1000.0,
                precision=0,
                step=100,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_VORTICITY",
            prop=FloatProperty(
                name="Vorticity",
                description="Vorticity confinement strength",
                default=0.0,
                min=0.0,
                soft_max=1.0,
                precision=1,
                step=10,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_SURFACETENSION",
            prop=FloatProperty(
                name="Surface Tension",
                description="Surface tension strength",
                default=0.0,
                min=0.0,
                soft_max=100.0,
                precision=0,
                step=100,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_ADDWEAKREPULSION",
            prop=BoolProperty(
                name="Weak Particle Repulsion",
                description="Enable weak particle repulsion",
                default=False,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WEAKREPULSIONSTRENGTH",
            prop=FloatProperty(
                name="Strength",
                description=("Strength of weak particle repulsion"),
                default=0.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_XMINUS",
            prop=EnumProperty(
                name="-X",
                description="Boundary type for -X wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_XPLUS",
            prop=EnumProperty(
                name="+X",
                description="Boundary type for +X wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_YMINUS",
            prop=EnumProperty(
                name="-Y",
                description="Boundary type for -Y wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_YPLUS",
            prop=EnumProperty(
                name="+Y",
                description="Boundary type for +Y wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_ZMINUS",
            prop=EnumProperty(
                name="-Z",
                description="Boundary type for -Z wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_WALLS_ZPLUS",
            prop=EnumProperty(
                name="+Z",
                description="Boundary type for +Z wall",
                items=_get_fluids_wall_type_items,
                default=1,
            ),
            condition=_is_flip_apic,
            enum_map=_WALL_ENUM_MAP,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_PRESSUREACCURACY",
            prop=FloatProperty(
                name="Accuracy",
                description=("Accuracy threshold for pressure solver"),
                default=50.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_PRESSUREITERS",
            prop=IntProperty(
                name="Iterations",
                description="Maximum pressure solver iterations",
                default=30,
                min=1,
                max=500,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_VISCACC",
            prop=FloatProperty(
                name="Accuracy",
                description=("Accuracy threshold for viscosity solver"),
                default=30.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_VISCITERS",
            prop=IntProperty(
                name="Iterations",
                description=("Maximum viscosity solver iterations"),
                default=40,
                min=1,
                max=500,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_CFLNUMBER",
            prop=FloatProperty(
                name="CFL",
                description="CFL condition for stability",
                default=0.7,
                min=0.1,
                max=2.0,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_MINSUBSTEPS",
            prop=IntProperty(
                name="Min Substeps",
                description=("Minimum number of substeps per frame"),
                default=1,
                min=1,
                max=20,
            ),
            condition=_is_flip_apic,
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_MAXSUBSTEPS",
            prop=IntProperty(
                name="Max Substeps",
                description=("Maximum number of substeps per frame"),
                default=3,
                min=1,
                max=50,
            ),
            condition=_is_flip_apic,
        ),
        # -- Display --
        PropertyDescriptor(
            name="fluids_flip_draw_grid",
            prop=EnumProperty(
                name="Draw Grid",
                description=("How to visualize the simulation grid"),
                items=_get_fluids_flip_grid_items,
                default=0,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_draw_liquid_voxels",
            prop=BoolProperty(
                name="Draw Liquid Voxels",
                description="Visualize voxels containing liquid",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_draw_solid_voxels",
            prop=BoolProperty(
                name="Draw Solid Voxels",
                description="Visualize voxels marked as solid",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_draw_wall_types",
            prop=BoolProperty(
                name="Draw Wall Types",
                description="Color-code walls by their type",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR",
            prop=BoolProperty(
                name="Draw FLIP/APIC Density (Color)",
                description="Color particles by the local fluid density",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_draw_velocity",
            prop=BoolProperty(
                name="Draw Velocity Vectors",
                description="Visualize liquid velocity field",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_speed_auto_range",
            prop=BoolProperty(
                name="Auto Range",
                description=("Automatically determine speed color range"),
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_speed_min",
            prop=FloatProperty(
                name="Speed Min",
                description="Minimum speed for color mapping",
                default=0.0,
                min=0.0,
                soft_max=10.0,
                unit="VELOCITY",
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_speed_max",
            prop=FloatProperty(
                name="Speed Max",
                description="Maximum speed for color mapping",
                default=10.0,
                min=0.0,
                soft_max=2000.0,
                unit="VELOCITY",
            ),
        ),
        PropertyDescriptor(
            name="fluids_flip_speed_trail_length",
            prop=FloatProperty(
                name="Trail Length",
                description=("Length of velocity trails for visualization"),
                default=0.2,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
        ),
    ),
    enum_builders=(build_fluids_enum_items,),
    enum_defaults={
        "ID_XPFLUIDGPU_SOLVER_CHOICE": "PBD",
        "ID_XPFLUIDGPU_SPH_TYPE": "LIQUID",
        "fluids_flip_tab": "DOMAIN",
        "ID_NX_FLIPFLUIDS_WALLS_XMINUS": "CLOSED",
        "ID_NX_FLIPFLUIDS_WALLS_XPLUS": "CLOSED",
        "ID_NX_FLIPFLUIDS_WALLS_YMINUS": "CLOSED",
        "ID_NX_FLIPFLUIDS_WALLS_YPLUS": "CLOSED",
        "ID_NX_FLIPFLUIDS_WALLS_ZMINUS": "CLOSED",
        "ID_NX_FLIPFLUIDS_WALLS_ZPLUS": "CLOSED",
        "fluids_flip_draw_grid": "NONE",
    },
)
