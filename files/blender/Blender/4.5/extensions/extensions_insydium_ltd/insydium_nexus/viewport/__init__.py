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

from typing import Optional

import bpy
import gpu

from . import hud
from .constraints import shutdown_all as _shutdown_all_constraints
from .generators import shutdown_all as _shutdown_all_generators
from .particles import clear_basic_shaders
from .particles import shutdown_all as _shutdown_all_particles
from .registry import (
    ConstraintDrawParams,
    GeneratorDrawParams,
    GeneratorLayerDraw,
    ParticleDrawParams,
    VolumeDrawParams,
    draw_constraints_with_backends,
    draw_generators_with_backends,
    draw_particles_with_backends,
    draw_trails_with_backends,
    draw_volume_with_backends,
)
from .trails import shutdown_all as _shutdown_all_trails
from .volume import shutdown_all as _shutdown_all_volumes


def clear_particle_cache(scene_key: Optional[int] = None) -> None:
    """Clear cached CPU-side particle buffers for one scene or all scenes."""
    from ..libs import theron

    if scene_key is None:
        theron.clear_all_position_buffers()
    else:
        theron.clear_position_buffer(scene_key)


def _draw_all_particles(context, depsgraph=None):
    from ..handlers import pipeline as pipeline_manager
    from ..libs import theron

    if not theron.is_initialized():
        return

    scene = context.scene
    pipeline = pipeline_manager.get_pipeline(scene)
    if pipeline is None:
        return

    count = theron.get_particle_count(pipeline)
    if count == 0:
        return

    particle_size = 1.0
    particle_color = (0.0, 0.2, 0.8, 1.0)
    display_shape = "POINTS"
    color_mode = "SINGLE"
    line_length_mode = 0  # 0=SPEED, 1=RADIUS, 2=FIXED
    line_fixed_length = 0.1
    line_min_length = 0.0
    line_max_length = 0.0
    rotation_mode = "UP_VECTOR"
    rotation_up_vector = "Z_POS"

    if depsgraph is None:
        depsgraph = context.evaluated_depsgraph_get()
    show_particles = False
    preferred_backend_id = None
    emitter_point_sizes: list[float] = []
    emitter_colors: list[tuple[float, float, float, float]] = []
    emitter_display_shapes: list[str] = []
    emitter_color_modes: list[str] = []
    emitter_line_length_modes: list[int] = []
    emitter_line_fixed_lengths: list[float] = []
    emitter_line_min_lengths: list[float] = []
    emitter_line_max_lengths: list[float] = []
    emitter_rotation_modes: list[int] = []
    emitter_rotation_up_vectors: list[tuple[float, float, float]] = []
    emitter_display_constraints: list[bool] = []
    emitter_constraint_palettes: list[
        tuple[
            tuple[float, float, float, float],
            tuple[float, float, float, float],
            tuple[float, float, float, float],
            tuple[float, float, float, float],
        ]
    ] = []
    # Order matches the sim's CONSTRAINT_TYPE_* enum so the shader can use
    # ParticleConstraint.type as a direct palette index:
    #   0 = BIRTH, 1 = DIST, 2 = CUSTOM, 3 = VISCOSITY.
    _CONSTRAINT_PALETTE_PROPS = (
        ("constraint_color_birth", (1.0, 0.95, 0.3, 1.0)),
        ("constraint_color_distance", (0.3, 0.85, 0.55, 1.0)),
        ("constraint_color_custom", (0.85, 0.4, 0.85, 1.0)),
        ("constraint_color_viscosity", (0.3, 0.55, 0.95, 1.0)),
    )

    # SSF tunables come from the first SSF-displaying emitter, if any.
    ssf_params: dict | None = None

    pipeline_data = scene.nexus_pipeline if hasattr(scene, "nexus_pipeline") else None
    if pipeline_data is not None and getattr(pipeline_data, "modifier_order", None):
        from ..pipeline_manager.utils import is_ancestor_disabled as _anc_disabled

        for item in pipeline_data.modifier_order:
            if getattr(item, "is_folder", False):
                continue
            obj = getattr(item, "modifier", None)
            if obj is None or obj.get("nexus_modifier_type") != "NX_EMITTER":
                continue
            try:
                eval_obj = obj.evaluated_get(depsgraph)
                props = eval_obj.nexus_modifier
            except Exception:
                continue
            if not getattr(props, "enabled", False):
                continue
            if _anc_disabled(pipeline_data, item):
                continue
            display = str(getattr(props, "ID_NX_EMITTER_DISPLAY_MODE", "POINTS"))
            color_mode_i = str(getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE"))
            line_mode_str = str(
                getattr(props, "ID_NX_EMITTER_LINES_LENGTHMODE", "SPEED")
            )
            emitter_point_sizes.append(
                float(getattr(props, "emitter_particle_size", 3.0))
            )
            emitter_colors.append(
                tuple(getattr(props, "emitter_particle_color", (0.0, 0.2, 0.8, 1.0)))
            )
            emitter_display_shapes.append(display)
            emitter_color_modes.append(color_mode_i)
            emitter_line_length_modes.append(
                {"SPEED": 0, "RADIUS": 1, "FIXED": 2}.get(line_mode_str, 0)
            )
            emitter_line_fixed_lengths.append(
                float(getattr(props, "ID_NX_EMITTER_LINES_FIXEDLENGTH", 0.1))
            )
            # Clamp only applies to Speed/Radius modes; 0 = bound disabled.
            clamp_active = (
                bool(getattr(props, "ID_NX_EMITTER_LINES_CLAMP", False))
                and line_mode_str != "FIXED"
            )
            emitter_line_min_lengths.append(
                float(getattr(props, "ID_NX_EMITTER_LINES_MINLENGTH", 0.0))
                if clamp_active
                else 0.0
            )
            emitter_line_max_lengths.append(
                float(getattr(props, "ID_NX_EMITTER_LINES_MAXLENGTH", 0.0))
                if clamp_active
                else 0.0
            )
            rot_mode_str = str(getattr(props, "emitter_particle_rotation_mode", "NONE"))
            emitter_rotation_modes.append(
                {"NONE": 0, "UP_VECTOR": 1, "TANGENTIAL": 2}.get(rot_mode_str, 0)
            )
            up_vec_str = str(getattr(props, "emitter_particle_up_vector", "Y_POS"))
            _up_map = {
                "X_POS": (1.0, 0.0, 0.0),
                "X_NEG": (-1.0, 0.0, 0.0),
                "Y_POS": (0.0, 1.0, 0.0),
                "Y_NEG": (0.0, -1.0, 0.0),
                "Z_POS": (0.0, 0.0, 1.0),
                "Z_NEG": (0.0, 0.0, -1.0),
            }
            emitter_rotation_up_vectors.append(_up_map.get(up_vec_str, (0.0, 1.0, 0.0)))

            emitter_display_constraints.append(
                bool(getattr(props, "display_constraints", False))
            )
            emitter_constraint_palettes.append(
                tuple(
                    tuple(float(c) for c in getattr(props, prop_name, default))
                    for prop_name, default in _CONSTRAINT_PALETTE_PROPS
                )
            )

            if display == "SSF" and ssf_params is None:
                ssf_params = {
                    "ssf_blur_iterations": int(
                        getattr(props, "emitter_ssf_blur_iterations", 3)
                    ),
                    "ssf_blur_radius": int(
                        getattr(props, "emitter_ssf_blur_radius", 8)
                    ),
                    "ssf_blur_depth_falloff": float(
                        getattr(props, "emitter_ssf_blur_depth_falloff", 50.0)
                    ),
                    "ssf_thickness_blur_iterations": int(
                        getattr(props, "emitter_ssf_thickness_blur_iterations", 2)
                    ),
                    "ssf_absorption": float(
                        getattr(props, "emitter_ssf_absorption", 2.0)
                    ),
                    "ssf_fresnel_power": float(
                        getattr(props, "emitter_ssf_fresnel_power", 5.0)
                    ),
                    "ssf_use_anisotropy": bool(
                        getattr(props, "emitter_ssf_use_anisotropy", False)
                    ),
                    "ssf_anisotropy_scale": float(
                        getattr(props, "emitter_ssf_anisotropy_scale", 0.2)
                    ),
                    "ssf_anisotropy_max_stretch": float(
                        getattr(props, "emitter_ssf_anisotropy_max_stretch", 3.0)
                    ),
                    "ssf_min_alpha": float(
                        getattr(props, "emitter_ssf_min_alpha", 0.3)
                    ),
                    "ssf_background_color": tuple(
                        getattr(
                            props,
                            "emitter_ssf_background_color",
                            (0.55, 0.65, 0.78),
                        )
                    ),
                }

    from ..pipeline_manager.utils import is_ancestor_disabled as _anc_disabled
    from ..utils import use_accelerated_viewport

    preferred_backend_id = None if use_accelerated_viewport() else "BASIC"

    for obj in scene.objects:
        if obj.get("nexus_modifier_type") != "NX_EMITTER":
            continue

        if obj.hide_viewport or obj.hide_get():
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        props = eval_obj.nexus_modifier

        if not bool(getattr(props, "emitter_show_particles", False)):
            continue

        if not props.enabled:
            continue

        if pipeline_data is not None:
            ancestor_disabled = False
            for item in pipeline_data.modifier_order:
                if not item.is_folder and item.modifier == obj:
                    ancestor_disabled = _anc_disabled(pipeline_data, item)
                    break
            if ancestor_disabled:
                continue

        show_particles = True
        particle_color = tuple(props.emitter_particle_color)
        display_shape = getattr(props, "ID_NX_EMITTER_DISPLAY_MODE", "POINTS")
        particle_size = (
            float(props.emitter_particle_size) if display_shape == "POINTS" else 3.0
        )
        color_mode = getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE")
        rotation_mode = getattr(props, "emitter_particle_rotation_mode", "NONE")
        rotation_up_vector = getattr(props, "emitter_particle_up_vector", "Y_POS")

        if display_shape == "NONE":
            return

        if display_shape in ("DIRECTION", "ARROW", "ARROW_FILLED"):
            mode_str = getattr(props, "ID_NX_EMITTER_LINES_LENGTHMODE", "SPEED")
            line_length_mode = {"SPEED": 0, "RADIUS": 1, "FIXED": 2}.get(mode_str, 0)
            line_fixed_length = float(
                getattr(props, "ID_NX_EMITTER_LINES_FIXEDLENGTH", 0.1)
            )
            # Clamp only applies to Speed/Radius modes; 0 = bound disabled.
            if (
                bool(getattr(props, "ID_NX_EMITTER_LINES_CLAMP", False))
                and mode_str != "FIXED"
            ):
                line_min_length = float(
                    getattr(props, "ID_NX_EMITTER_LINES_MINLENGTH", 0.0)
                )
                line_max_length = float(
                    getattr(props, "ID_NX_EMITTER_LINES_MAXLENGTH", 0.0)
                )
        break

    if not show_particles:
        return

    params = ParticleDrawParams(
        count=count,
        color=particle_color,
        size=particle_size,
        display_shape=display_shape,
        color_mode=color_mode,
        line_length_mode=line_length_mode,
        line_fixed_length=line_fixed_length,
        line_min_length=line_min_length,
        line_max_length=line_max_length,
        rotation_mode=rotation_mode,
        rotation_up_vector=rotation_up_vector,
        emitter_display_shapes=tuple(emitter_display_shapes),
        emitter_color_modes=tuple(emitter_color_modes),
        emitter_line_length_modes=tuple(emitter_line_length_modes),
        emitter_line_fixed_lengths=tuple(emitter_line_fixed_lengths),
        emitter_line_min_lengths=tuple(emitter_line_min_lengths),
        emitter_line_max_lengths=tuple(emitter_line_max_lengths),
        emitter_rotation_modes=tuple(emitter_rotation_modes),
        emitter_rotation_up_vectors=tuple(emitter_rotation_up_vectors),
        emitter_point_sizes=tuple(emitter_point_sizes),
        emitter_colors=tuple(emitter_colors),
        **(ssf_params or {}),
    )

    # Constraint overlay: stage per-emitter palette + global enable flag
    constraint_params = ConstraintDrawParams(
        overlay_enabled=any(emitter_display_constraints),
        emitter_display_constraints=tuple(emitter_display_constraints),
        emitter_constraint_palettes=tuple(emitter_constraint_palettes),
    )

    # Stage constraints before particles: the native constraint draw rides the
    # particle sentinel, so this keeps resize frames off a stale id-LUT (Metal flicker).
    draw_constraints_with_backends(
        context,
        pipeline,
        scene,
        constraint_params,
        preferred_backend_id,
    )

    # draw_particles_with_backends() handles binned-indirect backend fanout.
    draw_particles_with_backends(
        context,
        pipeline,
        scene,
        params,
        preferred_backend_id,
    )


def _draw_all_volumes(context, depsgraph=None):
    """Draw one volume sentinel per enabled nxExplosiaFX domain each frame."""
    from mathutils import Vector

    from ..handlers import pipeline as pipeline_manager
    from ..libs import theron

    scene = context.scene
    pipeline = pipeline_manager.get_pipeline(scene)

    if depsgraph is None:
        depsgraph = context.evaluated_depsgraph_get()

    from ..pipeline_manager.utils import is_modifier_effectively_disabled

    pipeline_data = scene.nexus_pipeline if hasattr(scene, "nexus_pipeline") else None

    for obj in context.view_layer.objects:
        if obj.get("nexus_modifier_type") != "NX_EXPLOSIAFX":
            continue

        if obj.hide_viewport or obj.hide_get():
            continue

        props = obj.nexus_modifier
        if not props.enabled:
            continue

        if pipeline_data is not None and is_modifier_effectively_disabled(
            pipeline_data, obj
        ):
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        eval_props = eval_obj.nexus_modifier

        # Allow selecting render styles between ray marcher and volume slicing
        render_style = getattr(
            eval_props, "explosiafx_display_volume_drawmode", "RAYMARCHER"
        )
        if render_style == "OFF":  # Skip this EFX is DrawMode = Off
            continue

        modifier_handle = pipeline_manager.get_modifier_handle(scene, obj)

        # Prefer to use Theron's actual grid spec when the backend is available. Theron may
        # regularize the user-set voxel size differently, so (nx, ny, nz) and dx
        # are the authoritative values for the world-space extent of the volume data.
        # Fall back to the UI-derived domain when Theron has no data yet.
        th_dx = None
        th_grid = None
        if theron.is_initialized() and modifier_handle is not None:
            th_dx = theron.get_efx_voxelsize(modifier_handle)
            th_grid = theron.get_efx_gridsize(modifier_handle)

        if th_dx is not None and th_grid is not None:
            domain_size = (th_grid[0] * th_dx, th_grid[1] * th_dx, th_grid[2] * th_dx)
        else:
            # No valid modifier handle yet — ask Theron's static domain regularizer
            # for what the engine would produce from the UI inputs.
            raw_domain_size = Vector(
                getattr(eval_props, "explosiafx_domain_size", (4.0, 4.0, 4.0))
            )
            voxel_size = getattr(eval_props, "ID_NX_EXPLOSIAFX_VOXELSIZE", 0.04)
            reg = theron.get_efx_regularizeddomain(
                float(raw_domain_size.x),
                float(raw_domain_size.y),
                float(raw_domain_size.z),
                float(voxel_size),
            )
            if reg is not None:
                domain_size = reg[0]
            else:
                domain_size = tuple(raw_domain_size)
        world_matrix = tuple(
            eval_obj.matrix_world[i][j] for i in range(4) for j in range(4)
        )

        # Smoke scattering
        smoke_tint_color = tuple(
            getattr(
                eval_props, "explosiafx_display_vrm_smoke_tint_color", (1.0, 1.0, 1.0)
            )
        )
        smoke_extinction_coef = float(
            getattr(eval_props, "explosiafx_display_vrm_smoke_extinction_coef", 80.0)
        )
        smoke_albedo = float(
            getattr(eval_props, "explosiafx_display_vrm_smoke_albedo", 0.8)
        )
        smoke_scatter_anisotropy = float(
            getattr(eval_props, "explosiafx_display_vrm_smoke_scatter_anisotropy", 0.4)
        )
        # Flame emission
        flame_emit_min_t = float(
            getattr(eval_props, "explosiafx_display_vrm_flame_emit_min_t", 1000.0)
        )
        flame_intensity = float(
            getattr(eval_props, "explosiafx_display_vrm_flame_intensity", 10.0)
        )
        # Ambient lighting
        light_dirn = tuple(
            getattr(eval_props, "explosiafx_display_vrm_light_dirn", (0.0, 0.9, 0.44))
        )
        light_intensity = float(
            getattr(eval_props, "explosiafx_display_vrm_light_intensity", 1.0)
        )
        light_color = tuple(
            getattr(eval_props, "explosiafx_display_vrm_light_color", (1.0, 1.0, 1.0))
        )
        # Hot gas emission
        hot_gas_emit_color = tuple(
            getattr(
                eval_props, "explosiafx_display_vrm_hot_gas_emit_color", (0.2, 0.4, 1.0)
            )
        )
        hot_gas_emit_strength = float(
            getattr(eval_props, "explosiafx_display_vrm_hot_gas_emit_strength", 5.0)
        )
        _hot_gas_emit_type_map = {"MANUAL": 0, "BB": 1}
        hot_gas_emit_type = _hot_gas_emit_type_map.get(
            getattr(eval_props, "explosiafx_display_vrm_hot_gas_emit_type", "BB"), 1
        )
        # Ray marching
        ray_max_steps = int(
            getattr(eval_props, "explosiafx_display_vrm_ray_max_steps", 150)
        )
        # Convert % to decimal for convention in shader code
        global_transparency = (
            float(
                getattr(eval_props, "explosiafx_display_vrm_global_transparency", 0.0)
            )
            / 100.0
        )
        slicer_count = int(getattr(eval_props, "explosiafx_display_slicer_count", 256))
        slicer_channel = str(
            getattr(eval_props, "explosiafx_display_slicer_channel", "SMOKE_TEMP")
        )
        slicer_transparency = float(
            getattr(
                eval_props, "explosiafx_display_slicer_transparency", 30.0
            )  # Percent
        )
        slicer_speed_min = float(
            getattr(eval_props, "explosiafx_display_slicer_speed_min", 0.0)
        )
        slicer_speed_max = float(
            getattr(eval_props, "explosiafx_display_slicer_speed_max", 2.0)
        )
        slicer_smoke_min_opacity_clip = float(
            getattr(eval_props, "explosiafx_display_slicer_smoke_min_opacity_clip", 0.0)
        )
        slicer_smoke_max_opacity_clip = float(
            getattr(
                eval_props, "explosiafx_display_slicer_smoke_max_opacity_clip", 100.0
            )
        )
        slicer_smoke_transparency = float(
            getattr(eval_props, "explosiafx_display_slicer_smoke_transparency", 30.0)
        )
        slicer_fuel_min_opacity_clip = float(
            getattr(eval_props, "explosiafx_display_slicer_fuel_min_opacity_clip", 0.0)
        )
        slicer_fuel_max_opacity_clip = float(
            getattr(
                eval_props, "explosiafx_display_slicer_fuel_max_opacity_clip", 100.0
            )
        )
        slicer_fuel_transparency = float(
            getattr(eval_props, "explosiafx_display_slicer_fuel_transparency", 80.0)
        )
        slicer_fuel_min = float(
            getattr(eval_props, "explosiafx_display_slicer_fuel_min", 0.0)
        )
        slicer_fuel_max = float(
            getattr(eval_props, "explosiafx_display_slicer_fuel_max", 0.25)
        )
        slicer_temp_color_mode = str(
            getattr(
                eval_props, "explosiafx_display_slicer_temp_color_mode", "BLACKBODY"
            )
        )
        slicer_temp_min_opacity_clip = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_min_opacity_clip", 0.0)
        )
        slicer_temp_max_opacity_clip = float(
            getattr(
                eval_props, "explosiafx_display_slicer_temp_max_opacity_clip", 100.0
            )
        )
        slicer_temp_transparency = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_transparency", 10.0)
        )
        slicer_temp_min = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_min", 300.0)
        )
        slicer_temp_max = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_max", 5000.0)
        )
        slicer_temp_bb_power = int(
            getattr(eval_props, "explosiafx_display_slicer_temp_bb_power", 4)
        )
        slicer_temp_bb_min = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_bb_min", 300.0)
        )
        slicer_temp_bb_max = float(
            getattr(eval_props, "explosiafx_display_slicer_temp_bb_max", 4300.0)
        )
        # Upscaled volume display
        display_upres = bool(
            getattr(eval_props, "explosiafx_display_volume_drawupres", True)
        )
        upres_factor = int(getattr(eval_props, "ID_NX_EXPLOSIAFX_UPRES", 1))
        # User override: keep preview alive even in Material/Rendered shading.
        show_in_rendered = bool(
            getattr(eval_props, "explosiafx_display_volume_show_in_rendered", False)
        )

        params = VolumeDrawParams(
            domain_size=domain_size,
            world_matrix=world_matrix,
            render_style=render_style,
            modifier_handle=modifier_handle,
            smoke_tint_color=smoke_tint_color,
            smoke_extinction_coef=smoke_extinction_coef,
            smoke_albedo=smoke_albedo,
            smoke_scatter_anisotropy=smoke_scatter_anisotropy,
            flame_emit_min_t=flame_emit_min_t,
            flame_intensity=flame_intensity,
            light_dirn=light_dirn,
            light_intensity=light_intensity,
            light_color=light_color,
            hot_gas_emit_color=hot_gas_emit_color,
            hot_gas_emit_strength=hot_gas_emit_strength,
            hot_gas_emit_type=hot_gas_emit_type,
            ray_max_steps=ray_max_steps,
            global_transparency=global_transparency,
            slicer_count=slicer_count,
            slicer_channel=slicer_channel,
            slicer_transparency=slicer_transparency,
            slicer_speed_min=slicer_speed_min,
            slicer_speed_max=slicer_speed_max,
            slicer_smoke_min_opacity_clip=slicer_smoke_min_opacity_clip,
            slicer_smoke_max_opacity_clip=slicer_smoke_max_opacity_clip,
            slicer_smoke_transparency=slicer_smoke_transparency,
            slicer_fuel_min_opacity_clip=slicer_fuel_min_opacity_clip,
            slicer_fuel_max_opacity_clip=slicer_fuel_max_opacity_clip,
            slicer_fuel_transparency=slicer_fuel_transparency,
            slicer_fuel_min=slicer_fuel_min,
            slicer_fuel_max=slicer_fuel_max,
            slicer_temp_color_mode=slicer_temp_color_mode,
            slicer_temp_min_opacity_clip=slicer_temp_min_opacity_clip,
            slicer_temp_max_opacity_clip=slicer_temp_max_opacity_clip,
            slicer_temp_transparency=slicer_temp_transparency,
            slicer_temp_min=slicer_temp_min,
            slicer_temp_max=slicer_temp_max,
            slicer_temp_bb_power=slicer_temp_bb_power,
            slicer_temp_bb_min=slicer_temp_bb_min,
            slicer_temp_bb_max=slicer_temp_bb_max,
            obj_name=obj.name,
            display_upres=display_upres,
            upres_factor=upres_factor,
            show_in_rendered=show_in_rendered,
        )
        draw_volume_with_backends(context, pipeline, scene, params)


def _draw_all_generators(context, depsgraph=None):
    """Draw a user-picked mesh at every active particle for each NX_GENERATOR."""
    from ..handlers import pipeline as pipeline_manager
    from ..libs import theron
    from ..pipeline_manager.utils import is_modifier_effectively_disabled
    from .generators import get_or_extract_mesh, invalidate_mesh_cache
    from .generators.cache import get_frozen_mesh

    if not theron.is_initialized():
        return
    scene = context.scene
    pipeline = pipeline_manager.get_pipeline(scene)
    if pipeline is None:
        return
    count = theron.get_particle_count(pipeline)
    if count == 0:
        return
    if depsgraph is None:
        depsgraph = context.evaluated_depsgraph_get()

    invalidate_mesh_cache(depsgraph)

    pipeline_data = scene.nexus_pipeline if hasattr(scene, "nexus_pipeline") else None

    scale_src_map = {"MESH": 0, "PARTICLE_RADIUS": 1, "PARTICLE_SCALE": 2, "CUSTOM": 3}
    color_src_map = {"MESH": 0, "PARTICLE": 1, "CUSTOM": 2}
    rot_src_map = {"MESH": 0, "PARTICLE": 1, "CUSTOM": 2}
    shading_mode_map = {"DEFAULT": 0, "FLAT": 1, "SMOOTH": 2}

    def _layer_variation(layer, scalar_attr, axis_attrs, per_axis_attr):
        if bool(getattr(layer, per_axis_attr, False)):
            return (
                float(getattr(layer, axis_attrs[0], 0.0)) / 100.0,
                float(getattr(layer, axis_attrs[1], 0.0)) / 100.0,
                float(getattr(layer, axis_attrs[2], 0.0)) / 100.0,
            )
        v = float(getattr(layer, scalar_attr, 0.0)) / 100.0
        return (v, v, v)

    for obj in context.view_layer.objects:
        if obj.get("nexus_modifier_type") != "NX_GENERATOR":
            continue
        if obj.hide_viewport or obj.hide_get():
            continue

        props = obj.nexus_modifier
        if not props.enabled:
            continue
        if pipeline_data is not None and is_modifier_effectively_disabled(
            pipeline_data, obj
        ):
            continue
        if getattr(props, "display_mode", "PREVIEW") == "GEOMETRY":
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        eval_props = eval_obj.nexus_modifier

        layers_out = []
        for layer in eval_props.generator_layers:
            mesh_obj = getattr(layer, "obj", None)
            if mesh_obj is None or mesh_obj.type != "MESH":
                continue

            cached = None
            frozen_frame_used = None
            if bool(getattr(layer, "freeze_animation", False)):
                frozen_frame_used = int(getattr(layer, "frozen_frame", 0))
                cached = get_frozen_mesh(mesh_obj, frozen_frame_used)
            if cached is None:
                cached = get_or_extract_mesh(mesh_obj, depsgraph)
                frozen_frame_used = None
            if cached is None:
                continue
            verts_f32, corner_normals_f32, smooth_normals_f32, tri_idx, vc, pc = cached

            revision_key = (
                mesh_obj.session_uid,
                mesh_obj.data.session_uid if mesh_obj.data else 0,
                vc,
                pc,
                frozen_frame_used,
            )

            _, rot_quat, scale_v = mesh_obj.matrix_world.decompose()
            rot_mat3 = rot_quat.to_matrix()
            mesh_rotation = tuple(
                float(rot_mat3[r][c]) for r in range(3) for c in range(3)
            )

            layers_out.append(
                GeneratorLayerDraw(
                    enabled=bool(layer.enabled),
                    spawn_chance=float(layer.spawn_chance),
                    mesh_vertices=verts_f32,
                    mesh_indices=tri_idx,
                    vertex_count=vc,
                    index_count=int(tri_idx.size),
                    mesh_revision_key=revision_key,
                    mesh_corner_normals=corner_normals_f32,
                    mesh_smooth_normals=smooth_normals_f32,
                    shading_mode_id=shading_mode_map.get(
                        str(getattr(layer, "shading_mode", "DEFAULT")), 0
                    ),
                    mesh_color=tuple(float(c) for c in mesh_obj.color),
                    mesh_scale=(
                        float(scale_v.x),
                        float(scale_v.y),
                        float(scale_v.z),
                    ),
                    mesh_rotation=mesh_rotation,
                    custom_color=tuple(float(c) for c in layer.custom_color),
                    custom_scale=(
                        tuple(float(c) for c in layer.custom_scale)
                        if layer.custom_scale_per_axis
                        else (float(layer.custom_scale_uniform),) * 3
                    ),
                    custom_rotation=(
                        tuple(float(c) for c in layer.custom_rotation)
                        if layer.custom_rotation_per_axis
                        else (float(layer.custom_rotation_uniform),) * 3
                    ),
                    scale_source_id=scale_src_map.get(
                        str(getattr(layer, "scale_source", "MESH")), 0
                    ),
                    color_source_id=color_src_map.get(
                        str(getattr(layer, "color_source", "MESH")), 0
                    ),
                    rotation_source_id=rot_src_map.get(
                        str(getattr(layer, "rotation_source", "MESH")), 0
                    ),
                    scale_variation=_layer_variation(
                        layer,
                        "scale_variation",
                        ("scale_variation_x", "scale_variation_y", "scale_variation_z"),
                        "scale_variation_per_axis",
                    ),
                    color_variation=_layer_variation(
                        layer,
                        "color_variation",
                        ("color_variation_r", "color_variation_g", "color_variation_b"),
                        "color_variation_per_axis",
                    ),
                    rotation_variation=_layer_variation(
                        layer,
                        "rotation_variation",
                        (
                            "rotation_variation_x",
                            "rotation_variation_y",
                            "rotation_variation_z",
                        ),
                        "rotation_variation_per_axis",
                    ),
                    scale_variation_per_axis=bool(
                        getattr(layer, "scale_variation_per_axis", False)
                    ),
                    color_variation_per_axis=bool(
                        getattr(layer, "color_variation_per_axis", False)
                    ),
                    rotation_variation_per_axis=bool(
                        getattr(layer, "rotation_variation_per_axis", False)
                    ),
                )
            )

        if not layers_out:
            continue
        from ..properties.nx_generator import compute_emitter_filter_mask

        params = GeneratorDrawParams(
            particle_count=int(count),
            layers=tuple(layers_out),
            emitter_filter_mask=int(compute_emitter_filter_mask(scene, obj)),
        )
        draw_generators_with_backends(context, pipeline, scene, params)


def _draw_all_trails(context, depsgraph=None):
    """Draw trail line overlays for all enabled NX_TRAIL modifiers."""
    from ..handlers import pipeline as pipeline_manager
    from ..utils import use_accelerated_viewport
    from .trails import collect_trail_draw_data, reset_trail_caches_for_pipeline

    scene = context.scene
    pipeline = pipeline_manager.get_pipeline(scene)
    if pipeline is None:
        return

    pipeline_manager.ensure_pipeline_timing_current(scene, depsgraph)

    params = collect_trail_draw_data(context, depsgraph)
    if params is None:
        reset_trail_caches_for_pipeline(pipeline)
        return

    preferred_backend_id = None if use_accelerated_viewport() else "BASIC"
    draw_trails_with_backends(context, pipeline, scene, params, preferred_backend_id)


def draw_nexus_modifiers():
    from ..libs import theron

    if theron.is_shutting_down():
        return

    if not theron.is_initialized():
        return

    context = bpy.context

    from ..modifiers import MODIFIER_REGISTRY

    prev_depth_test = gpu.state.depth_test_get()
    prev_depth_mask = gpu.state.depth_mask_get()

    try:
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)

        depsgraph = context.evaluated_depsgraph_get()

        from ..pipeline_manager.utils import is_modifier_effectively_disabled

        scene = context.scene
        pipeline_data = (
            scene.nexus_pipeline if hasattr(scene, "nexus_pipeline") else None
        )

        for obj in context.view_layer.objects:
            mod_type = obj.get("nexus_modifier_type")
            if not mod_type:
                continue

            mod_class = MODIFIER_REGISTRY.get(mod_type)
            if not mod_class:
                continue

            props = obj.nexus_modifier

            if not props.visible_in_editor:
                continue

            if obj.hide_viewport or obj.hide_get():
                continue

            if not props.enabled:
                continue

            if pipeline_data is not None and is_modifier_effectively_disabled(
                pipeline_data, obj
            ):
                continue

            eval_obj = obj.evaluated_get(depsgraph)
            mod_class.draw_viewport(obj, eval_obj.nexus_modifier, context)

        _draw_all_particles(context, depsgraph)
        _draw_all_volumes(context, depsgraph)
        _draw_all_generators(context, depsgraph)
        _draw_all_trails(context, depsgraph)

    finally:
        gpu.state.depth_test_set(prev_depth_test)
        gpu.state.depth_mask_set(prev_depth_mask)


_draw_handler = None
_hud_handler = None


def register():
    global _draw_handler, _hud_handler
    _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        draw_nexus_modifiers,
        (),
        "WINDOW",
        "POST_VIEW",
    )
    _hud_handler = bpy.types.SpaceView3D.draw_handler_add(
        hud.draw_hud,
        (),
        "WINDOW",
        "POST_PIXEL",
    )


def unregister():
    global _draw_handler, _hud_handler

    if _hud_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_hud_handler, "WINDOW")
        _hud_handler = None

    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, "WINDOW")
        _draw_handler = None

    clear_basic_shaders()
    _shutdown_all_particles()
    _shutdown_all_constraints()
    _shutdown_all_volumes()
    _shutdown_all_generators()
    _shutdown_all_trails()
