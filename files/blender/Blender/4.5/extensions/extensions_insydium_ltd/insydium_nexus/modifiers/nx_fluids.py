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

from typing import Tuple

import bpy
import gpu
from mathutils import Vector

from ..libs.nexus_time import draw_time_prop
from ..properties.nx_fluids import SPEC, get_fluids_ui_config
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_ORANGE,
    XP_COLOR_MODS_RED,
    draw_lines,
    draw_thick_lines,
)
from ..utils.gradient import GradientSpec, NexusGradient
from .base import MenuCategory, NexusModifier, UIFlags

XP_COLOR_GRID = (0.5, 0.7, 0.9, 0.4)

FLUIDS_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR_GRADIENT",
        label="Density Color",
        default_stops=[
            (0.0, (0.0, 1.0, 0.0, 1.0)),
            (0.069, (0.0, 0.0, 1.0, 1.0)),
            (0.4483, (0.0, 0.0, 1.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
        theron_ids=("ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR_GRADIENT",),
    ),
    GradientSpec(
        slot_name="fluids_speed_color",
        label="Speed Color",
        default_stops=[
            (0.0, (0.0, 0.0, 1.0, 1.0)),
            (0.25, (0.0, 1.0, 1.0, 1.0)),
            (0.5, (0.0, 1.0, 0.0, 1.0)),
            (0.75, (1.0, 1.0, 0.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="fluids_speed_alpha",
        label="Speed Alpha",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
]


class NXFluidsModifier(NexusModifier):
    object_type = "NX_FLUIDS"
    object_name = "nxFluids"
    object_label = "Fluid Modifier"
    object_description = "Fluid simulation using PBD, SPH, FLIP, or APIC solvers"
    icon_name = "nx_fluids"
    category = "Simulation"
    menu_category = MenuCategory.SIMULATION
    gizmo_max_handles = 3

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_theron_type(cls, obj):
        solver = obj.nexus_modifier.ID_XPFLUIDGPU_SOLVER_CHOICE
        if solver == "PBD":
            return "TR_MODIFIER_TYPE_PBD_FLUIDS"
        elif solver == "SPH":
            return "TR_MODIFIER_TYPE_SPH_FLUIDS"
        else:
            return "TR_MODIFIER_TYPE_FLIP_FLUIDS"

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        if props.ID_XPFLUIDGPU_SOLVER_CHOICE not in ("FLIP", "APIC"):
            return []

        return [
            HandleConfig(
                Vector((1, 0, 0)),
                "fluids_flip_domain_size",
                prop_component=0,
                position_factor=0.5,
                min_value=0.1,
            ),
            HandleConfig(
                Vector((0, 1, 0)),
                "fluids_flip_domain_size",
                prop_component=1,
                position_factor=0.5,
                min_value=0.1,
            ),
            HandleConfig(
                Vector((0, 0, 1)),
                "fluids_flip_domain_size",
                prop_component=2,
                position_factor=0.5,
                min_value=0.1,
            ),
        ]

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_tabs(cls, props):
        tabs = []
        if props.ID_XPFLUIDGPU_SOLVER_CHOICE in ("FLIP", "APIC"):
            tabs.append(("DISPLAY", "Display"))
        return tabs

    @classmethod
    def draw_tab(cls, section_id, layout, props):
        col = layout.column()
        col.use_property_split = True

        if section_id == "DISPLAY":
            cls.draw_display_section(layout, props)

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_XPFLUIDGPU_SOLVER_CHOICE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_XPFLUIDGPU_SOLVER_CHOICE")

        solver = data.ID_XPFLUIDGPU_SOLVER_CHOICE

        if solver == "PBD":
            cls._draw_pbd_ui(layout, data)
        elif solver == "SPH":
            cls._draw_sph_ui(layout, data)
        elif solver in ("FLIP", "APIC"):
            cls._draw_flip_ui(layout, data, solver)

    @classmethod
    def _draw_pbd_ui(cls, layout, data):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_XPFLUIDGPU_PBF_KERNEL_RADIUS", {}).get(
            "use_property_split", True
        )

        col.label(text="Solver")
        col.prop(data, "ID_XPFLUIDGPU_PBF_KERNEL_RADIUS")
        col.prop(data, "ID_XPFLUIDGPU_PBF_SUBSTEPS")
        draw_time_prop(col, data, "ID_XPFLUIDGPU_EASEIN")
        col.separator(type="LINE")

        col.prop(data, "ID_XPFLUIDGPU_PBF_DENSITY_MIN")
        col.prop(data, "ID_XPFLUIDGPU_PBF_DENSITY_ITERATIONS")
        col.prop(data, "ID_XPFLUIDGPU_PBF_DENSITY_COMPRESSION")
        col.separator(type="LINE")

        col.prop(data, "ID_XPFLUIDGPU_PBF_CHECKDENSITY")
        row = col.row()
        row.enabled = data.ID_XPFLUIDGPU_PBF_CHECKDENSITY
        row.prop(data, "ID_XPFLUIDGPU_PBF_CHECKDENSITY_MAX")
        row = col.row()
        row.enabled = data.ID_XPFLUIDGPU_PBF_CHECKDENSITY
        row.prop(data, "ID_XPFLUIDGPU_PBF_CHECKDENSITY_ITERS")
        col.separator(type="LINE")

        col.label(text="Liquid")
        col.prop(data, "ID_XPFLUIDGPU_PBF_VISCOCITY")
        col.prop(data, "ID_XPFLUIDGPU_PBF_VORTICITY")
        col.prop(data, "ID_XPFLUIDGPU_PBF_TENSION")
        col.prop(data, "ID_XPFLUIDGPU_PBF_REPULSION")
        col.prop(data, "ID_XPFLUIDGPU_PBF_EXTPRESSURE")

    @classmethod
    def _draw_sph_ui(cls, layout, data):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_XPFLUIDGPU_SPH_TYPE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_XPFLUIDGPU_SPH_TYPE")
        col.separator(type="LINE")

        col.label(text="Solver")
        col.prop(data, "ID_XPFLUIDGPU_SPH_RADIUS")

        substeps_row = col.row()
        split = substeps_row.split(factor=0.385)

        # Left side: expand icon + label
        label_row = split.row(align=True)
        label_row.alignment = "RIGHT"
        icon = "TRIA_DOWN" if data.fluids_sph_substeps_expanded else "TRIA_RIGHT"
        label_row.prop(
            data,
            "fluids_sph_substeps_expanded",
            icon=icon,
            icon_only=True,
            emboss=False,
        )
        label_row.label(text="Substeps")

        split.prop(data, "ID_XPFLUIDGPU_SPH_SUBSTEPS", text="")

        if data.fluids_sph_substeps_expanded:
            col.prop(data, "ID_XPFLUIDGPU_SPH_SUBSTEPS_ADAPTIVE")
            row = col.row()
            row.enabled = data.ID_XPFLUIDGPU_SPH_SUBSTEPS_ADAPTIVE
            row.prop(data, "ID_XPFLUIDGPU_SPH_SUBSTEPS_MIN")
            row = col.row()
            row.enabled = data.ID_XPFLUIDGPU_SPH_SUBSTEPS_ADAPTIVE
            row.prop(data, "ID_XPFLUIDGPU_SPH_SUBSTEPS_CFL")

        col.prop(data, "ID_XPFLUIDGPU_SPH_DAMPING")
        draw_time_prop(col, data, "ID_XPFLUIDGPU_SPH_EASEIN")
        col.separator(type="LINE")

        col.prop(data, "ID_XPFLUIDGPU_SPH_MIN_DENSITY_STEPS")
        col.prop(data, "ID_XPFLUIDGPU_SPH_MAX_DENSITY_STEPS")
        col.prop(data, "ID_XPFLUIDGPU_SPH_MAX_MATERIAL_COMPRESSION")
        col.prop(data, "ID_XPFLUIDGPU_SPH_USE_VELOCITY")
        col.separator(type="LINE")

        col.prop(data, "ID_XPFLUIDGPU_SPH_CHECKDENSITY")
        row = col.row()
        row.enabled = data.ID_XPFLUIDGPU_SPH_CHECKDENSITY
        row.prop(data, "ID_XPFLUIDGPU_SPH_CHECKDENSITY_MAX")
        row = col.row()
        row.enabled = data.ID_XPFLUIDGPU_SPH_CHECKDENSITY
        row.prop(data, "ID_XPFLUIDGPU_SPH_CHECKDENSITY_ITERS")
        col.separator(type="LINE")

        col.label(text="Liquid")
        col.prop(data, "ID_XPFLUIDGPU_SPH_VISCOSITY_FLOAT")
        col.prop(data, "ID_XPFLUIDGPU_SPH_VISCOSITY")
        col.prop(data, "ID_XPFLUIDGPU_SPH_VORT_S")
        col.prop(data, "ID_XPFLUIDGPU_SPH_VORT_L")
        col.prop(data, "ID_XPFLUIDGPU_SPH_SURFACE_TENSION")
        col.prop(data, "ID_XPFLUIDGPU_SPH_INTERNAL_PRESSURE")
        col.prop(data, "ID_XPFLUIDGPU_SPH_EXTERNAL_PRESSURE")
        col.separator(type="LINE")

        col.label(text="Granular")
        col.prop(data, "ID_XPFLUIDGPU_SPH_FRICTION")
        col.prop(data, "ID_XPFLUIDGPU_SPH_FRICTION_ITERATIONS")
        col.prop(data, "ID_XPFLUIDGPU_SPH_STABILITY")
        col.prop(data, "ID_XPFLUIDGPU_SPH_COHESION")

    @classmethod
    def should_show_display_section(cls, props) -> bool:
        return props.ID_XPFLUIDGPU_SOLVER_CHOICE in ("FLIP", "APIC")

    @classmethod
    def draw_display_section(cls, layout, data):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("fluids_flip_draw_grid", {}).get(
            "use_property_split", True
        )
        col.prop(data, "fluids_flip_draw_grid")
        col.prop(data, "fluids_flip_draw_liquid_voxels")
        col.prop(data, "fluids_flip_draw_solid_voxels")
        col.prop(data, "fluids_flip_draw_wall_types")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR")

        draw_density_color_enabled = data.ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR
        obj = bpy.context.object
        if obj:
            NexusGradient(obj, "ID_NX_FLIPFLUIDS_DISPLAY_DENSITY_COLOR_GRADIENT").draw_ui(
                col, "Density Color", enabled=draw_density_color_enabled
            )

        col.separator(type="LINE")

        col.prop(data, "fluids_flip_draw_velocity")
        velocity_enabled = data.fluids_flip_draw_velocity

        if obj:
            NexusGradient(obj, "fluids_speed_color").draw_ui(
                col, "Speed Color", enabled=velocity_enabled
            )
            NexusGradient(obj, "fluids_speed_alpha").draw_ui(
                col, "Speed Alpha", enabled=velocity_enabled
            )

        row = col.row()
        row.enabled = velocity_enabled
        row.prop(data, "fluids_flip_speed_auto_range")

        speed_range_enabled = velocity_enabled and not data.fluids_flip_speed_auto_range

        row = col.row()
        row.enabled = speed_range_enabled
        row.prop(data, "fluids_flip_speed_min")

        row = col.row()
        row.enabled = speed_range_enabled
        row.prop(data, "fluids_flip_speed_max")

        row = col.row()
        row.enabled = velocity_enabled
        row.prop(data, "fluids_flip_speed_trail_length")

    @classmethod
    def get_gradient_specs(cls):
        return FLUIDS_GRADIENT_SPECS

    @classmethod
    def post_sync(cls, obj, container, handle, props, scene, depsgraph=None, original_props=None):
        """Sync FLIP/APIC domain size."""
        if props.ID_XPFLUIDGPU_SOLVER_CHOICE not in ("FLIP", "APIC"):
            return
        from ..libs import theron
        from ..libs.theron_ids import get as get_id

        domain = props.fluids_flip_domain_size
        theron.set_vector(
            container,
            get_id("ID_NX_FLIPFLUIDS_DOMAINSIZE"),
            float(domain[0]),
            float(domain[1]),
            float(domain[2]),
        )

    @classmethod
    def _draw_flip_ui(cls, layout, data, solver):
        row = layout.row(align=True)
        row.prop(data, "fluids_flip_tab", expand=True)

        if data.fluids_flip_tab == "DOMAIN":
            cls._draw_flip_domain_tab(layout, data, solver)
        else:
            cls._draw_flip_solver_tab(layout, data)

    @classmethod
    def _draw_flip_domain_tab(cls, layout, data, solver):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_FLIPFLUIDS_VOXELSIZE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_FLIPFLUIDS_VOXELSIZE")
        col.prop(data, "fluids_flip_domain_size")
        col.prop(data, "ID_NX_FLIPFLUIDS_TIMESCALE")
        col.separator(type="LINE")

        if solver == "FLIP":
            col.prop(data, "ID_NX_FLIPFLUIDS_FLIP_PIC_MIX")
            col.separator(type="LINE")

        col.prop(data, "ID_NX_FLIPFLUIDS_VISCOSITY")
        col.prop(data, "ID_NX_FLIPFLUIDS_VORTICITY")
        col.prop(data, "ID_NX_FLIPFLUIDS_SURFACETENSION")
        col.separator(type="LINE")

        col.prop(data, "ID_NX_FLIPFLUIDS_ADDWEAKREPULSION")
        row = col.row()
        row.enabled = data.ID_NX_FLIPFLUIDS_ADDWEAKREPULSION
        row.prop(data, "ID_NX_FLIPFLUIDS_WEAKREPULSIONSTRENGTH")

        col.separator(type="LINE")
        col.label(text="Domain Boundary Walls")

        flow = col.grid_flow(columns=2, row_major=True, align=True)
        flow.use_property_split = ui_config.get("ID_NX_FLIPFLUIDS_WALLS_XPLUS", {}).get(
            "use_property_split", True
        )
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_XPLUS")
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_XMINUS")
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_YPLUS")
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_YMINUS")
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_ZPLUS")
        flow.prop(data, "ID_NX_FLIPFLUIDS_WALLS_ZMINUS")

    @classmethod
    def _draw_flip_solver_tab(cls, layout, data):
        ui_config = get_fluids_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_FLIPFLUIDS_PRESSUREACCURACY", {}).get(
            "use_property_split", True
        )

        col.label(text="Pressure Solver")
        col.prop(data, "ID_NX_FLIPFLUIDS_PRESSUREACCURACY")
        col.prop(data, "ID_NX_FLIPFLUIDS_PRESSUREITERS")
        col.separator(type="LINE")

        col.label(text="Viscosity Solver")
        row = col.row()
        row.enabled = data.ID_NX_FLIPFLUIDS_VISCOSITY > 0
        row.prop(data, "ID_NX_FLIPFLUIDS_VISCACC")
        row = col.row()
        row.enabled = data.ID_NX_FLIPFLUIDS_VISCOSITY > 0
        row.prop(data, "ID_NX_FLIPFLUIDS_VISCITERS")
        col.separator(type="LINE")

        col.label(text="Advection")
        col.prop(data, "ID_NX_FLIPFLUIDS_CFLNUMBER")
        col.prop(data, "ID_NX_FLIPFLUIDS_MINSUBSTEPS")
        col.prop(data, "ID_NX_FLIPFLUIDS_MAXSUBSTEPS")

    @classmethod
    def _draw_base_grid(
        cls,
        shader,
        mx,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []
        z = -half.z

        for i in range(1, nx):
            x = -half.x + i * voxel_size
            lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        for j in range(1, ny):
            y = -half.y + j * voxel_size
            lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def _find_back_face(cls, context, obj) -> str:
        view_matrix = context.region_data.view_matrix
        view_forward = Vector((view_matrix[2][0], view_matrix[2][1], view_matrix[2][2]))

        obj_rot = obj.matrix_world.to_3x3().normalized()
        face_normals = {
            "x_pos": obj_rot @ Vector((1, 0, 0)),
            "x_neg": obj_rot @ Vector((-1, 0, 0)),
            "y_pos": obj_rot @ Vector((0, 1, 0)),
            "y_neg": obj_rot @ Vector((0, -1, 0)),
            "z_pos": obj_rot @ Vector((0, 0, 1)),
            "z_neg": obj_rot @ Vector((0, 0, -1)),
        }

        best_face = "z_neg"
        best_dot = 2.0
        for face_id, normal in face_normals.items():
            dot = normal.dot(view_forward)
            if dot < best_dot:
                best_dot = dot
                best_face = face_id

        return best_face

    @classmethod
    def _draw_face_grid(
        cls,
        shader,
        mx,
        face_id: str,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []

        if face_id == "x_pos":
            x = half.x
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        elif face_id == "x_neg":
            x = -half.x
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        elif face_id == "y_pos":
            y = half.y
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "y_neg":
            y = -half.y
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "z_pos":
            z = half.z
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "z_neg":
            z = -half.z
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def _draw_voxel_grid(
        cls,
        shader,
        mx,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []

        for i in range(1, nx):
            x = -half.x + i * voxel_size
            for j in range(ny + 1):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(nz + 1):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        for j in range(1, ny):
            y = -half.y + j * voxel_size
            for i in range(nx + 1):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(nz + 1):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        for k in range(1, nz):
            z = -half.z + k * voxel_size
            for i in range(nx + 1):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))
            for j in range(ny + 1):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        solver = getattr(props, "ID_XPFLUIDGPU_SOLVER_CHOICE", "PBD")

        if solver not in ("FLIP", "APIC"):
            return

        from ..libs import theron

        voxel_size = getattr(props, "ID_NX_FLIPFLUIDS_VOXELSIZE", 0.1)
        domain_size_raw = Vector(getattr(props, "fluids_flip_domain_size", (2.0, 2.0, 2.0)))
        draw_wall_types = getattr(props, "fluids_flip_draw_wall_types", False)

        # Theron is the single source of truth for the regularized domain extent
        # and voxel counts. If the back end isn't reachable yet, fall back to the
        # raw domain + floor(L/dx) voxel count so the box and grid overlays still draw.
        reg = theron.get_flipfluids_regularizeddomain(
            float(domain_size_raw.x),
            float(domain_size_raw.y),
            float(domain_size_raw.z),
            float(voxel_size),
        )
        if reg is not None:
            domain_size = Vector(reg[0])
            num_voxels = reg[1]
        elif voxel_size > 0:
            domain_size = domain_size_raw.copy()
            num_voxels = (
                max(1, int(domain_size_raw.x / voxel_size)),
                max(1, int(domain_size_raw.y / voxel_size)),
                max(1, int(domain_size_raw.z / voxel_size)),
            )
        else:
            domain_size = domain_size_raw.copy()
            num_voxels = (1, 1, 1)

        half = domain_size / 2.0

        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        corners = [
            Vector((-half.x, -half.y, -half.z)),  # 0: back-left-bottom
            Vector((half.x, -half.y, -half.z)),  # 1: back-right-bottom
            Vector((half.x, half.y, -half.z)),  # 2: front-right-bottom
            Vector((-half.x, half.y, -half.z)),  # 3: front-left-bottom
            Vector((-half.x, -half.y, half.z)),  # 4: back-left-top
            Vector((half.x, -half.y, half.z)),  # 5: back-right-top
            Vector((half.x, half.y, half.z)),  # 6: front-right-top
            Vector((-half.x, half.y, half.z)),  # 7: front-left-top
        ]
        world_corners = [mx @ c for c in corners]

        box_edges = [
            (world_corners[0], world_corners[1]),
            (world_corners[1], world_corners[2]),
            (world_corners[2], world_corners[3]),
            (world_corners[3], world_corners[0]),
            (world_corners[4], world_corners[5]),
            (world_corners[5], world_corners[6]),
            (world_corners[6], world_corners[7]),
            (world_corners[7], world_corners[4]),
            (world_corners[0], world_corners[4]),
            (world_corners[1], world_corners[5]),
            (world_corners[2], world_corners[6]),
            (world_corners[3], world_corners[7]),
        ]

        # Write depth so the volume slicer's LESS_EQUAL test fails on line pixels.
        prev_depth_test = gpu.state.depth_test_get()
        prev_depth_mask = gpu.state.depth_mask_get()
        try:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(True)
            shader.uniform_float("color", XP_COLOR_MODS_BLUE)
            draw_lines(shader, box_edges)
        finally:
            gpu.state.depth_test_set(prev_depth_test)
            gpu.state.depth_mask_set(prev_depth_mask)

        # Add corner decorators
        corner_len = min(0.25, min(half.x, half.y, half.z) * 0.5)

        corner_lines = []
        corner_dirs = [
            [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],  # 0
            [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],  # 1
            [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],  # 2
            [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],  # 3
            [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],  # 4
            [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],  # 5
            [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],  # 6
            [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],  # 7
        ]

        for i, corner in enumerate(corners):
            world_corner = mx @ corner
            for direction in corner_dirs[i]:
                end_local = corner + direction * corner_len
                end_world = mx @ end_local
                corner_lines.append((world_corner, end_world))

        draw_thick_lines(context, corner_lines, XP_COLOR_MODS_RED, 4.0)

        draw_grid = getattr(props, "fluids_flip_draw_grid", "NONE")
        if draw_grid != "NONE":
            if draw_grid == "BASE":
                cls._draw_base_grid(shader, mx, half, num_voxels, voxel_size)
            elif draw_grid == "BACK":
                back_face = cls._find_back_face(context, obj)
                cls._draw_face_grid(shader, mx, back_face, half, num_voxels, voxel_size)
            elif draw_grid == "BASEANDBACK":
                cls._draw_base_grid(shader, mx, half, num_voxels, voxel_size)
                back_face = cls._find_back_face(context, obj)
                if back_face != "z_neg":
                    cls._draw_face_grid(shader, mx, back_face, half, num_voxels, voxel_size)
            elif draw_grid == "VOXELS":
                cls._draw_voxel_grid(shader, mx, half, num_voxels, voxel_size)

        if draw_wall_types:
            cls._draw_wall_indicators(shader, mx, half, props)

        draw_solidvoxels = getattr(props, "fluids_flip_draw_solid_voxels", False)
        if context.scene.frame_current <= 1:
            draw_solidvoxels = False
        if draw_solidvoxels:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    result = theron.get_flipfluids_solidsdf_voxelcenter(modifier_handle)
                    if result is not None:
                        # dx is Theron's actual voxel size. The UI voxel_size can
                        # differ if the engine adjusted it, so use dx for any
                        # spatial positioning of returned data.
                        flat_data, resolution, dx = result
                        nx, ny, nz = resolution

                        # Do not attempt to draw the solid voxels if the simulation data is stale
                        # i.e., voxel grid spec change since theron last ran a step
                        if num_voxels[0] == nx and num_voxels[1] == ny and num_voxels[2] == nz:
                            # Collect voxel center coordinates that are inside colliders
                            # Use Numpy to efficiently collect the list of coordinates
                            # Theron storage order is ix + nx*(iz + nz*iy), i.e. axes
                            # (y, z, x) slowest-to-fastest — reshape as a view, no copy.
                            flat = np.asarray(flat_data, dtype=np.float32).reshape(ny, nz, nx)
                            iy_idx, iz_idx, ix_idx = np.where(flat < 0.0)

                            local_x = (-half.x + (ix_idx + 0.5) * dx).astype(np.float32)
                            local_y = (-half.y + (iy_idx + 0.5) * dx).astype(np.float32)
                            local_z = (-half.z + (iz_idx + 0.5) * dx).astype(np.float32)

                            R = np.array(mx.to_3x3(), dtype=np.float32)
                            t = np.array(mx.translation, dtype=np.float32)
                            local_pts = np.stack([local_x, local_y, local_z], axis=1)
                            # batch_for_shader accepts numpy arrays directly
                            solid_points = local_pts @ R.T + t

                            # Batched drawing
                            if len(solid_points):
                                gpu.state.point_size_set(6.0)
                                batch = batch_for_shader(shader, "POINTS", {"pos": solid_points})
                                shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0))
                                gpu.state.depth_test_set("LESS_EQUAL")
                                batch.draw(shader)
                                gpu.state.depth_test_set("NONE")
                except Exception as exc:
                    print(f"[FLIPFluids] solid sdf field fetch failed: {exc}")

        draw_liquiddomain = getattr(props, "fluids_flip_draw_liquid_voxels", False)
        if context.scene.frame_current <= 1:
            draw_liquiddomain = False
        if draw_liquiddomain:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    result = theron.get_flipfluids_liquidphi(modifier_handle)
                    if result is not None:
                        # dx is Theron's actual voxel size; use it (not the UI value)
                        # for any spatial positioning of returned data.
                        flat_data, resolution, dx = result
                        nx, ny, nz = resolution

                        # Do not attempt to draw the liquid domain
                        # if the simulation data is stale i.e., voxel grid spec
                        # change since theron last ran a step
                        if num_voxels[0] == nx and num_voxels[1] == ny and num_voxels[2] == nz:
                            # Theron storage order is ix + nx*(iz + nz*iy), i.e. axes
                            # (y, z, x) slowest-to-fastest — reshape as a view, no copy.
                            flat = np.asarray(flat_data, dtype=np.float32).reshape(ny, nz, nx)
                            a = flat <= 0.0  # boolean active mask, shape (ny, nz, nx)

                            vs = np.float32(dx)
                            hx = np.float32(half.x)
                            hy = np.float32(half.y)
                            hz = np.float32(half.z)

                            # Per-face draw masks: active voxel whose neighbor in that
                            # direction is inactive (or is at the grid boundary).
                            # np.pad fills with 0 (inactive) at boundaries.
                            # Axis layout: 0=y, 1=z, 2=x.
                            xm = a & ~np.pad(a, ((0, 0), (0, 0), (1, 0)))[:, :, :nx]
                            xp = a & ~np.pad(a, ((0, 0), (0, 0), (0, 1)))[:, :, 1:]
                            ym = a & ~np.pad(a, ((1, 0), (0, 0), (0, 0)))[:ny, :, :]
                            yp = a & ~np.pad(a, ((0, 1), (0, 0), (0, 0)))[1:, :, :]
                            zm = a & ~np.pad(a, ((0, 0), (1, 0), (0, 0)))[:, :nz, :]
                            zp = a & ~np.pad(a, ((0, 0), (0, 1), (0, 0)))[:, 1:, :]

                            # 4 corners per face as (xi, yi, zi) selectors into [lo, hi] arrays.
                            # Edges drawn are AB, BC, CD, DA (one square outline per face).
                            face_defs = [
                                (xm, ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1))),
                                (xp, ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
                                (ym, ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
                                (yp, ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1))),
                                (zm, ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))),
                                (zp, ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
                            ]

                            segments = []
                            for mask, corners in face_defs:
                                iy_idx, iz_idx, ix_idx = np.where(mask)
                                if len(ix_idx) == 0:
                                    continue
                                x_lo = -hx + ix_idx.astype(np.float32) * vs
                                y_lo = -hy + iy_idx.astype(np.float32) * vs
                                z_lo = -hz + iz_idx.astype(np.float32) * vs
                                # xs/ys/zs: shape (2, n) — index 0 = lo, 1 = hi
                                xs = np.stack([x_lo, x_lo + vs])
                                ys = np.stack([y_lo, y_lo + vs])
                                zs = np.stack([z_lo, z_lo + vs])
                                c = corners
                                A = np.stack([xs[c[0][0]], ys[c[0][1]], zs[c[0][2]]], axis=1)
                                B = np.stack([xs[c[1][0]], ys[c[1][1]], zs[c[1][2]]], axis=1)
                                C = np.stack([xs[c[2][0]], ys[c[2][1]], zs[c[2][2]]], axis=1)
                                D = np.stack([xs[c[3][0]], ys[c[3][1]], zs[c[3][2]]], axis=1)
                                # np.stack produces (n, 8, 3); reshape to (8n, 3) for LINES
                                segments.append(
                                    np.stack([A, B, B, C, C, D, D, A], axis=1).reshape(-1, 3)
                                )

                            if segments:
                                R = np.array(mx.to_3x3(), dtype=np.float32)
                                t = np.array(mx.translation, dtype=np.float32)
                                all_verts = np.concatenate(segments, axis=0)
                                world_verts = all_verts @ R.T + t
                                batch = batch_for_shader(shader, "LINES", {"pos": world_verts})
                                shader.uniform_float("color", (0.0, 0.71, 1.0, 0.2))
                                gpu.state.depth_test_set("LESS_EQUAL")
                                batch.draw(shader)
                                gpu.state.depth_test_set("NONE")
                except Exception as exc:
                    print(f"[FLIPFluids] liquid phi field fetch failed: {exc}")

        draw_liquidvel = getattr(props, "fluids_flip_draw_velocity", False)
        if context.scene.frame_current <= 1:
            draw_liquidvel = False
        if draw_liquidvel:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    vel_result = theron.get_flipfluids_liquidvelocity(modifier_handle)
                    phi_result = theron.get_flipfluids_liquidphi(modifier_handle)
                    if vel_result is not None and phi_result is not None:
                        # vel_dx is Theron's actual voxel size for the velocity grid.
                        # Use this (not the UI value) for spatial positioning. The phi
                        # dx is unused here since phi is sampled in the same grid space.
                        flat_u_data, flat_v_data, flat_w_data, vel_resolution, vel_dx = vel_result
                        phi_flat_data, phi_resolution, _phi_dx = phi_result
                        nx, ny, nz = vel_resolution

                        if (
                            num_voxels[0] == nx
                            and num_voxels[1] == ny
                            and num_voxels[2] == nz
                            and phi_resolution == vel_resolution
                        ):
                            # Theron storage order is ix + nx*(iz + nz*iy), i.e. axes
                            # (y, z, x) slowest-to-fastest — reshape as a view, no copy.
                            flat_u = np.asarray(flat_u_data, dtype=np.float32).reshape(
                                ny, nz, (nx + 1)
                            )
                            flat_v = np.asarray(flat_v_data, dtype=np.float32).reshape(
                                (ny + 1), nz, nx
                            )
                            flat_w = np.asarray(flat_w_data, dtype=np.float32).reshape(
                                ny, (nz + 1), nx
                            )
                            flat_phi = np.asarray(phi_flat_data, dtype=np.float32).reshape(
                                ny, nz, nx
                            )
                            cls._draw_velocity_trails(
                                obj,
                                props,
                                mx,
                                half,
                                vel_dx,
                                nx,
                                ny,
                                nz,
                                flat_u,
                                flat_v,
                                flat_w,
                                flat_phi,
                            )
                except Exception as exc:
                    print(f"[FLIPFluids] liquid velocity field fetch failed: {exc}")

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)

    @staticmethod
    def _trilinear(arr, gy, gz, gx, max_iy, max_iz, max_ix):
        """Trilinear sample a (Ny, Nz, Nx) array at fractional indices (gy, gz, gx).

        Out-of-range fractional indices are clamped to the array bounds.
        """
        import numpy as np

        gy_c = np.clip(gy, 0.0, float(max_iy))
        gz_c = np.clip(gz, 0.0, float(max_iz))
        gx_c = np.clip(gx, 0.0, float(max_ix))
        iy0 = np.floor(gy_c).astype(np.int32)
        iz0 = np.floor(gz_c).astype(np.int32)
        ix0 = np.floor(gx_c).astype(np.int32)
        iy1 = np.minimum(iy0 + 1, max_iy)
        iz1 = np.minimum(iz0 + 1, max_iz)
        ix1 = np.minimum(ix0 + 1, max_ix)
        fy = (gy_c - iy0).astype(np.float32)
        fz = (gz_c - iz0).astype(np.float32)
        fx = (gx_c - ix0).astype(np.float32)

        c000 = arr[iy0, iz0, ix0]
        c001 = arr[iy0, iz0, ix1]
        c010 = arr[iy0, iz1, ix0]
        c011 = arr[iy0, iz1, ix1]
        c100 = arr[iy1, iz0, ix0]
        c101 = arr[iy1, iz0, ix1]
        c110 = arr[iy1, iz1, ix0]
        c111 = arr[iy1, iz1, ix1]

        c00 = c000 * (1.0 - fx) + c001 * fx
        c01 = c010 * (1.0 - fx) + c011 * fx
        c10 = c100 * (1.0 - fx) + c101 * fx
        c11 = c110 * (1.0 - fx) + c111 * fx

        c0 = c00 * (1.0 - fz) + c01 * fz
        c1 = c10 * (1.0 - fz) + c11 * fz

        return c0 * (1.0 - fy) + c1 * fy

    @classmethod
    def _draw_velocity_trails(
        cls,
        obj,
        props,
        mx,
        half: Vector,
        voxel_size: float,
        nx: int,
        ny: int,
        nz: int,
        flat_u,
        flat_v,
        flat_w,
        flat_phi,
    ) -> None:
        import numpy as np
        from gpu_extras.batch import batch_for_shader

        vs = float(voxel_size)
        if vs <= 0.0:
            return

        # Trail length and segment count
        trail_length = float(getattr(props, "fluids_flip_speed_trail_length", 0.2))
        seg_length = vs * 0.3
        if seg_length <= 0.0 or trail_length <= 0.0:
            return
        num_segs = max(2, min(8, int(trail_length / seg_length)))
        seg_length = trail_length / float(num_segs)

        # Speed range: min/max of |component| over each MAC field
        # independently (not vector magnitude).
        if getattr(props, "fluids_flip_speed_auto_range", True):
            max_speed = float(
                max(
                    np.abs(flat_u).max(),
                    np.abs(flat_v).max(),
                    np.abs(flat_w).max(),
                )
            )
            min_speed = float(
                min(
                    np.abs(flat_u).min(),
                    np.abs(flat_v).min(),
                    np.abs(flat_w).min(),
                )
            )
        else:
            min_speed = float(getattr(props, "fluids_flip_speed_min", 0.0))
            max_speed = float(getattr(props, "fluids_flip_speed_max", 1.0))

        speed_range = max_speed - min_speed
        inv_speed_range = 1.0 / speed_range if speed_range > 0.0 else 0.0

        # Pre-cache gradient lookups.
        color_lut = NexusGradient(obj, "fluids_speed_color").lut
        alpha_lut = NexusGradient(obj, "fluids_speed_alpha").lut
        if color_lut is None or alpha_lut is None:
            return

        seg_colors = np.zeros((num_segs, 3), dtype=np.float32)
        for s in range(num_segs):
            cidx = max(0, min(255, int((s / float(num_segs)) * 255.0)))
            seg_colors[s] = color_lut[cidx][:3]

        # Alpha is taken from the red channel of the alpha gradient.
        alpha_lut_r = np.array([alpha_lut[i][0] for i in range(256)], dtype=np.float32)

        # Seed cells: liquid cells + immediate neighbors.
        seed_mask = flat_phi <= np.float32(vs)
        iy_seed, iz_seed, ix_seed = np.where(seed_mask)
        if ix_seed.size == 0:
            return

        # Collocated voxel-center velocity from MAC face averages.
        u_c = 0.5 * (flat_u[iy_seed, iz_seed, ix_seed] + flat_u[iy_seed, iz_seed, ix_seed + 1])
        v_c = 0.5 * (flat_v[iy_seed, iz_seed, ix_seed] + flat_v[iy_seed + 1, iz_seed, ix_seed])
        w_c = 0.5 * (flat_w[iy_seed, iz_seed, ix_seed] + flat_w[iy_seed, iz_seed + 1, ix_seed])

        speed = np.sqrt(u_c * u_c + v_c * v_c + w_c * w_c)
        keep = speed > 1e-12
        if not np.any(keep):
            return

        ix_seed = ix_seed[keep]
        iy_seed = iy_seed[keep]
        iz_seed = iz_seed[keep]
        u_c = u_c[keep]
        v_c = v_c[keep]
        w_c = w_c[keep]
        speed = speed[keep]

        # Per-seed alpha based on the seed-cell relative speed.
        rel = np.clip((speed - min_speed) * inv_speed_range, 0.0, 1.0)
        a_idx = np.clip((rel * 255.0).astype(np.int32), 0, 255)
        seed_alpha = alpha_lut_r[a_idx]

        # Initial start positions in object-centered coords (voxel centers).
        hx = np.float32(half.x)
        hy = np.float32(half.y)
        hz = np.float32(half.z)
        vsf = np.float32(vs)

        pos = np.empty((ix_seed.size, 3), dtype=np.float32)
        pos[:, 0] = -hx + (ix_seed.astype(np.float32) + 0.5) * vsf
        pos[:, 1] = -hy + (iy_seed.astype(np.float32) + 0.5) * vsf
        pos[:, 2] = -hz + (iz_seed.astype(np.float32) + 0.5) * vsf

        vel = np.stack([u_c, v_c, w_c], axis=1).astype(np.float32)

        half_arr = np.array([hx, hy, hz], dtype=np.float32)
        active = np.ones(ix_seed.size, dtype=bool)

        seg_starts: list = []
        seg_ends: list = []
        seg_cols: list = []

        for seg in range(num_segs):
            if not np.any(active):
                break

            s_now = np.linalg.norm(vel, axis=1)
            nonzero = s_now > 1e-12
            active = active & nonzero
            if not np.any(active):
                break

            safe_s = np.where(nonzero, s_now, 1.0).astype(np.float32)
            d = vel / safe_s[:, None]

            end = pos + d * np.float32(seg_length)

            # Clip trails whose end leaves the box; mark them to terminate.
            outside = active & np.any(np.abs(end) > half_arr, axis=1)
            if np.any(outside):
                cp = pos[outside]
                cd = d[outside]
                t_min = np.full(cp.shape[0], np.inf, dtype=np.float32)
                for axis in range(3):
                    d_axis = cd[:, axis]
                    p_axis = cp[:, axis]
                    target = np.where(d_axis > 0, half_arr[axis], -half_arr[axis])
                    with np.errstate(divide="ignore", invalid="ignore"):
                        t = (target - p_axis) / d_axis
                    t = np.where(np.isfinite(t) & (t > 0), t, np.inf)
                    t_min = np.minimum(t_min, t)
                t_clip = np.minimum(t_min, np.float32(seg_length))
                end[outside] = cp + cd * t_clip[:, None]

            # Phi at end — kill any trail that has wandered too far from the liquid.
            sp = end + half_arr  # corner-origin coords for sampling
            phi_end = cls._trilinear(
                flat_phi,
                sp[:, 1] / vsf - 0.5,
                sp[:, 2] / vsf - 0.5,
                sp[:, 0] / vsf - 0.5,
                ny - 1,
                nz - 1,
                nx - 1,
            )
            phi_far = phi_end > (2.0 * vs)

            draw_mask = active & ~phi_far
            if np.any(draw_mask):
                seg_starts.append(pos[draw_mask].copy())
                seg_ends.append(end[draw_mask].copy())
                cols = np.empty((int(draw_mask.sum()), 4), dtype=np.float32)
                cols[:, :3] = seg_colors[seg]
                cols[:, 3] = seed_alpha[draw_mask]
                seg_cols.append(cols)

            # Continue only trails that drew this segment AND were not clipped.
            active = draw_mask & ~outside

            pos = end

            if seg < num_segs - 1 and np.any(active):
                # Trilinear sample of the MAC velocity at the new position.
                sp = pos + half_arr
                new_u = cls._trilinear(
                    flat_u,
                    sp[:, 1] / vsf - 0.5,
                    sp[:, 2] / vsf - 0.5,
                    sp[:, 0] / vsf,
                    ny - 1,
                    nz - 1,
                    nx,
                )
                new_v = cls._trilinear(
                    flat_v,
                    sp[:, 1] / vsf,
                    sp[:, 2] / vsf - 0.5,
                    sp[:, 0] / vsf - 0.5,
                    ny,
                    nz - 1,
                    nx - 1,
                )
                new_w = cls._trilinear(
                    flat_w,
                    sp[:, 1] / vsf - 0.5,
                    sp[:, 2] / vsf,
                    sp[:, 0] / vsf - 0.5,
                    ny - 1,
                    nz,
                    nx - 1,
                )
                vel = np.stack([new_u, new_v, new_w], axis=1).astype(np.float32)

        if not seg_starts:
            return

        starts = np.concatenate(seg_starts, axis=0)
        ends = np.concatenate(seg_ends, axis=0)
        cols = np.concatenate(seg_cols, axis=0)

        n = starts.shape[0]
        verts_local = np.empty((2 * n, 3), dtype=np.float32)
        verts_local[0::2] = starts
        verts_local[1::2] = ends
        vert_cols = np.empty((2 * n, 4), dtype=np.float32)
        vert_cols[0::2] = cols
        vert_cols[1::2] = cols

        R = np.array(mx.to_3x3(), dtype=np.float32)
        t = np.array(mx.translation, dtype=np.float32)
        world_verts = verts_local @ R.T + t

        color_shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        batch = batch_for_shader(color_shader, "LINES", {"pos": world_verts, "color": vert_cols})
        gpu.state.depth_test_set("LESS_EQUAL")
        batch.draw(color_shader)
        gpu.state.depth_test_set("NONE")

    @classmethod
    def _draw_wall_indicators(cls, shader, mx, half, props):
        wall_states = {
            "x_plus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_XPLUS", "CLOSED"),
            "x_minus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_XMINUS", "CLOSED"),
            "y_plus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_YPLUS", "CLOSED"),
            "y_minus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_YMINUS", "CLOSED"),
            "z_plus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_ZPLUS", "CLOSED"),
            "z_minus": getattr(props, "ID_NX_FLIPFLUIDS_WALLS_ZMINUS", "CLOSED"),
        }

        state_colors = {
            "OPEN": XP_COLOR_MODS_BLUE,
            "CLOSED": XP_COLOR_MODS_ORANGE,
            "KILL": XP_COLOR_MODS_RED,
        }

        inset = 0.05

        face_corners = {
            "x_plus": [
                Vector((half.x, -half.y + inset, -half.z + inset)),
                Vector((half.x, half.y - inset, -half.z + inset)),
                Vector((half.x, half.y - inset, half.z - inset)),
                Vector((half.x, -half.y + inset, half.z - inset)),
            ],
            "x_minus": [
                Vector((-half.x, -half.y + inset, -half.z + inset)),
                Vector((-half.x, half.y - inset, -half.z + inset)),
                Vector((-half.x, half.y - inset, half.z - inset)),
                Vector((-half.x, -half.y + inset, half.z - inset)),
            ],
            "y_plus": [
                Vector((-half.x + inset, half.y, -half.z + inset)),
                Vector((half.x - inset, half.y, -half.z + inset)),
                Vector((half.x - inset, half.y, half.z - inset)),
                Vector((-half.x + inset, half.y, half.z - inset)),
            ],
            "y_minus": [
                Vector((-half.x + inset, -half.y, -half.z + inset)),
                Vector((half.x - inset, -half.y, -half.z + inset)),
                Vector((half.x - inset, -half.y, half.z - inset)),
                Vector((-half.x + inset, -half.y, half.z - inset)),
            ],
            "z_plus": [
                Vector((-half.x + inset, -half.y + inset, half.z)),
                Vector((half.x - inset, -half.y + inset, half.z)),
                Vector((half.x - inset, half.y - inset, half.z)),
                Vector((-half.x + inset, half.y - inset, half.z)),
            ],
            "z_minus": [
                Vector((-half.x + inset, -half.y + inset, -half.z)),
                Vector((half.x - inset, -half.y + inset, -half.z)),
                Vector((half.x - inset, half.y - inset, -half.z)),
                Vector((-half.x + inset, half.y - inset, -half.z)),
            ],
        }

        lines_by_state = {"OPEN": [], "CLOSED": [], "KILL": []}

        for wall_name, state in wall_states.items():
            corners = face_corners[wall_name]
            world_corners = [mx @ c for c in corners]
            lines_by_state[state].extend(
                [
                    (world_corners[0], world_corners[1]),
                    (world_corners[1], world_corners[2]),
                    (world_corners[2], world_corners[3]),
                    (world_corners[3], world_corners[0]),
                ]
            )

        for state, lines in lines_by_state.items():
            if lines:
                shader.uniform_float("color", state_colors[state])
                draw_lines(shader, lines)
