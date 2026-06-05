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

"""Viewport backend registry and routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple


@dataclass(frozen=True)
class TrailDrawParams:
    """Per-frame parameters for the trail line-overlay pass."""

    pipeline: int = 0
    source_count: int = 0
    slots_per_particle: int = 0
    history_capacity: int = 0
    max_points_per_segment: int = 0
    source_colors: Tuple[Tuple[float, float, float, float], ...] = ()
    source_color_modes: Tuple[str, ...] = ()
    source_thickness_modes: Tuple[str, ...] = ()
    source_thickness_values: Tuple[float, ...] = ()
    source_no_data_flags: Tuple[bool, ...] = ()
    source_trail_color_modes: Tuple[str, ...] = ()
    source_thickness_variations: Tuple[float, ...] = ()
    source_spline_max_values: Tuple[float, ...] = ()
    source_enabled_flags: Tuple[bool, ...] = ()
    source_algorithms: Tuple[str, ...] = ()
    source_segment_lengths: Tuple[int, ...] = ()
    source_gap_lengths: Tuple[int, ...] = ()
    source_multiple_modes: Tuple[int, ...] = ()
    source_sequences: Tuple[int, ...] = ()
    source_sequence_lengths: Tuple[int, ...] = ()
    source_min_distances: Tuple[float, ...] = ()
    source_max_distances: Tuple[float, ...] = ()
    source_max_numbers: Tuple[int, ...] = ()


@dataclass(frozen=True)
class ConstraintDrawParams:
    """Per-frame parameters for the constraint overlay pass."""

    # True when at least one emitter has display_constraints toggled on.
    # When False, registered backends should skip the pass entirely.
    overlay_enabled: bool = False
    # Per-emitter display_constraints flag (length == emitter count).
    emitter_display_constraints: Tuple[bool, ...] = ()
    # Per-emitter palette: each entry is 4 RGBA tuples ordered to match the
    # sim's CONSTRAINT_TYPE_* enum (0=Birth, 1=Distance, 2=Custom,
    # 3=Viscosity). Indexed in the shader by ParticleConstraint.type.
    emitter_constraint_palettes: Tuple[Tuple[Tuple[float, float, float, float], ...], ...] = ()


@dataclass(frozen=True)
class VolumeDrawParams:
    """Per-object draw parameters for ExplosiaFX volume rendering."""

    # Regularised (whole # voxels) domain extent in local space.
    domain_size: Tuple[float, float, float]
    # Flat row-major 16-float world transform of the domain object.
    world_matrix: Tuple[float, ...]
    # Volume render algorithm selected on this object.
    render_style: str = "RAYMARCHER"
    # Theron modifier handle for this specific NX_EXPLOSIAFX instance.
    # Used by renderers to fetch field data (density, temperature, ...).
    # None when Theron is not running or the handle is not yet created.
    modifier_handle: int | None = None
    # Smoke scattering
    smoke_tint_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    smoke_extinction_coef: float = 80.0
    smoke_albedo: float = 0.8
    smoke_scatter_anisotropy: float = 0.4
    # Flame emission
    flame_emit_min_t: float = 1000.0
    flame_intensity: float = 10.0
    # Ambient lighting
    light_dirn: Tuple[float, float, float] = (0.0, 0.9, 0.44)
    light_intensity: float = 1.0
    light_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    # Hot gas emission
    hot_gas_emit_color: Tuple[float, float, float] = (0.2, 0.4, 1.0)
    hot_gas_emit_strength: float = 5.0
    hot_gas_emit_type: int = 1
    # Ray marching
    ray_max_steps: int = 150
    global_transparency: float = 0.0
    # Volume slicer - global controls
    slicer_count: int = 256
    slicer_channel: str = "SMOKE_TEMP"
    slicer_transparency: float = 30.0  # Percent
    # Volume slicer - speed controls
    slicer_speed_min: float = 0.0
    slicer_speed_max: float = 2.0
    # Volume slicer - smoke controls
    slicer_smoke_min_opacity_clip: float = 0.0
    slicer_smoke_max_opacity_clip: float = 100.0
    slicer_smoke_transparency: float = 30.0
    # Volume slicer - fuel controls
    slicer_fuel_min_opacity_clip: float = 0.0
    slicer_fuel_max_opacity_clip: float = 100.0
    slicer_fuel_transparency: float = 80.0
    slicer_fuel_min: float = 0.0
    slicer_fuel_max: float = 0.25
    # Volume slicer - temperature controls
    slicer_temp_color_mode: str = "BLACKBODY"
    slicer_temp_min_opacity_clip: float = 0.0
    slicer_temp_max_opacity_clip: float = 100.0
    slicer_temp_transparency: float = 10.0
    slicer_temp_min: float = 300.0
    slicer_temp_max: float = 5000.0
    slicer_temp_bb_power: int = 4
    slicer_temp_bb_min: float = 300.0
    slicer_temp_bb_max: float = 4300.0
    # Owning Blender object name. The slicer renderer uses it to look up the
    # NexusGradient nodes for transfer function tabulation
    obj_name: str = ""
    # Upscaled volume display
    display_upres: bool = True
    upres_factor: int = 1
    # Keep the VRM preview alive when the viewport is in Material/Rendered shading.
    # Default False — those shading modes draw the volume via the Volume object's
    # material, so suppressing the raymarcher avoids two drawing modes competing.
    show_in_rendered: bool = False


@dataclass(frozen=True)
class GeneratorLayerDraw:
    """One layer of an NX_GENERATOR for the renderer to draw."""

    enabled: bool
    spawn_chance: float
    # numpy float32 (V, 3) — local-space vertices.
    mesh_vertices: object
    # numpy uint32 (I,) — flattened triangle indices.
    mesh_indices: object
    vertex_count: int
    index_count: int
    # Identity tuple; renderer reuses the static VBO/IBO when unchanged.
    mesh_revision_key: tuple
    mesh_corner_normals: object = None
    mesh_smooth_normals: object = None
    mesh_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    mesh_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    mesh_rotation: Tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    custom_color: Tuple[float, float, float, float] = (0.45, 0.75, 0.94, 1.0)
    custom_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    custom_rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale_source_id: int = 0
    color_source_id: int = 0
    rotation_source_id: int = 0
    # 0 = DEFAULT (corner normals), 1 = FLAT (derivative), 2 = SMOOTH (vertex normals).
    shading_mode_id: int = 0
    scale_variation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    color_variation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_variation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale_variation_per_axis: bool = False
    color_variation_per_axis: bool = False
    rotation_variation_per_axis: bool = False


@dataclass(frozen=True)
class GeneratorDrawParams:
    """Per-frame draw parameters for one NX_GENERATOR object."""

    particle_count: int
    layers: Tuple[GeneratorLayerDraw, ...] = ()
    # Bit i set = include emitter i. 0 = no draw.
    emitter_filter_mask: int = 0


@dataclass(frozen=True)
class ParticleDrawParams:
    """Shared particle draw parameters passed to every backend."""

    count: int
    color: Tuple[float, float, float, float]
    size: float
    display_shape: str
    color_mode: str = "SINGLE"
    line_length_mode: int = 0  # 0=SPEED, 1=RADIUS, 2=FIXED
    line_fixed_length: float = 0.1
    # Speed/Radius length clamp; 0 disables that bound (FIXED mode is never clamped).
    line_min_length: float = 0.0
    line_max_length: float = 0.0
    rotation_mode: str = "NONE"
    rotation_up_vector: str = "Z_POS"
    emitter_display_shapes: Tuple[str, ...] = ()
    emitter_color_modes: Tuple[str, ...] = ()
    emitter_line_length_modes: Tuple[int, ...] = ()
    emitter_line_fixed_lengths: Tuple[float, ...] = ()
    emitter_line_min_lengths: Tuple[float, ...] = ()
    emitter_line_max_lengths: Tuple[float, ...] = ()
    emitter_rotation_modes: Tuple[int, ...] = ()  # 0=NONE, 1=UP_VECTOR, 2=TANGENTIAL
    emitter_rotation_up_vectors: Tuple[Tuple[float, float, float], ...] = ()
    emitter_point_sizes: Tuple[float, ...] = ()
    emitter_colors: Tuple[Tuple[float, float, float, float], ...] = ()
    # Screen-space fluid (SSF) tunables; sourced from the first SSF emitter.
    ssf_blur_iterations: int = 3
    ssf_blur_radius: int = 8
    ssf_blur_depth_falloff: float = 50.0
    ssf_thickness_blur_iterations: int = 2
    ssf_absorption: float = 2.0
    ssf_fresnel_power: float = 5.0
    ssf_use_anisotropy: bool = False
    ssf_anisotropy_scale: float = 0.2
    ssf_anisotropy_max_stretch: float = 3.0
    ssf_min_alpha: float = 0.3
    ssf_background_color: Tuple[float, float, float] = (0.55, 0.65, 0.78)
    indirect_binned_indices: object | None = None
    indirect_start: int = 0
    indirect_end: int = 0
    cpu_ready: bool | None = None
    cpu_positions: object | None = None
    cpu_colors: object | None = None
    cpu_velocities: object | None = None
    cpu_radii: object | None = None
    cpu_rotations: object | None = None
    cpu_emitter_indices: object | None = None
    cpu_count: int | None = None


DrawFn = Callable[
    [
        object,  # context
        object,  # pipeline
        object,  # scene (bpy.types.Scene)
        ParticleDrawParams,
    ],
    bool,
]

AvailabilityFn = Callable[[], bool]


def get_blender_gpu_backend() -> str:
    """Best-effort detection of Blender's active GPU backend."""
    try:
        import gpu

        platform = getattr(gpu, "platform", None)
        backend_get = getattr(platform, "backend_type_get", None)
        if backend_get is not None:
            backend = backend_get()
            if backend:
                return str(backend).upper()
    except Exception:
        pass

    try:
        import bpy
    except Exception:
        return ""
    try:
        backend = getattr(bpy.context.preferences.system, "gpu_backend", None)
    except Exception:
        return ""
    return str(backend).upper() if backend else ""


@dataclass(frozen=True)
class ViewportBackend:
    """A single viewport draw backend (Vulkan, OpenGL, Basic, …)."""

    id: str
    label: str
    description: str
    priority: int = 0
    is_available: AvailabilityFn = lambda: True
    draw: DrawFn | None = None


_BACKENDS: dict[str, ViewportBackend] = {}
_DEFAULT_LOADED = False

# Set when an available non-BASIC backend fails to draw; locks routing to BASIC
# for the session so the viewport can't flicker between accel and fallback.
_LOCK_TO_BASIC: bool = False


def is_locked_to_basic() -> bool:
    """True once an accelerated backend failed this session; UI greys the dropdown."""
    return _LOCK_TO_BASIC


def register_backend(backend: ViewportBackend) -> None:
    """Register or replace a backend by id."""
    _BACKENDS[backend.id] = backend


def _ensure_default_backends_loaded() -> None:
    global _DEFAULT_LOADED
    if _DEFAULT_LOADED:
        return
    _DEFAULT_LOADED = True

    from .particles import register_all_backends

    register_all_backends()


def iter_backends():
    _ensure_default_backends_loaded()
    return _BACKENDS.values()


def get_backend(backend_id: str) -> ViewportBackend | None:
    _ensure_default_backends_loaded()
    return _BACKENDS.get(backend_id)


def draw_particles_with_backends(
    context,
    pipeline,
    scene,
    params: ParticleDrawParams,
    preferred_backend_id: str | None,
) -> None:
    """Route drawing through registered backends with clean fallback."""
    global _LOCK_TO_BASIC
    _ensure_default_backends_loaded()

    if not params.display_shape or params.display_shape == "NONE":
        return

    if params.count <= 0:
        return

    tried: set[str] = set()
    ordered: list[ViewportBackend] = []

    if preferred_backend_id:
        pref = get_backend(preferred_backend_id)
        if pref is not None:
            ordered.append(pref)
            tried.add(pref.id)

    for b in sorted(iter_backends(), key=lambda b: b.priority, reverse=True):
        if b.id not in tried:
            ordered.append(b)
            tried.add(b.id)

    for b in ordered:
        if _LOCK_TO_BASIC and b.id != "BASIC":
            continue
        if b.draw is None:
            continue
        try:
            if not b.is_available():
                continue
        except Exception:
            continue
        try:
            if b.draw(context, pipeline, scene, params):
                return
            # Backend declined this frame -- lock to Basic to stop the flicker.
            if b.id != "BASIC":
                _LOCK_TO_BASIC = True
        except Exception:
            if b.id != "BASIC":
                _LOCK_TO_BASIC = True
            continue

    # Ultimate fallback: try basic draw directly
    try:
        from .particles import basic_draw

        basic_draw(context, pipeline, scene, params)
    except Exception:
        return


# ---------------------------------------------------------------------------
# Volume backend registry (ExplosiaFX volume rendering)
# ---------------------------------------------------------------------------

_VOLUME_BACKENDS: dict[str, ViewportBackend] = {}
_VOLUME_DEFAULT_LOADED = False


def register_volume_backend(backend: ViewportBackend) -> None:
    """Register or replace a volume backend by id."""
    _VOLUME_BACKENDS[backend.id] = backend


def _ensure_default_volume_backends_loaded() -> None:
    global _VOLUME_DEFAULT_LOADED
    if _VOLUME_DEFAULT_LOADED:
        return
    _VOLUME_DEFAULT_LOADED = True

    from .volume import register_volume_backends

    register_volume_backends()


# ---------------------------------------------------------------------------
# Constraint overlay registry
# ---------------------------------------------------------------------------

_CONSTRAINTS_BACKENDS: dict[str, ViewportBackend] = {}
_CONSTRAINTS_DEFAULT_LOADED = False


def register_constraint_backend(backend: ViewportBackend) -> None:
    """Register or replace a constraint backend by id."""
    _CONSTRAINTS_BACKENDS[backend.id] = backend


def _ensure_default_constraint_backends_loaded() -> None:
    global _CONSTRAINTS_DEFAULT_LOADED
    if _CONSTRAINTS_DEFAULT_LOADED:
        return
    _CONSTRAINTS_DEFAULT_LOADED = True

    from .constraints import register_constraint_backends

    register_constraint_backends()


def draw_constraints_with_backends(
    context,
    pipeline,
    scene,
    params: ConstraintDrawParams,
    preferred_backend_id: str | None = None,
) -> None:
    """Route constraint overlay through registered backends"""
    _ensure_default_constraint_backends_loaded()

    tried: set[str] = set()
    ordered: list[ViewportBackend] = []

    if preferred_backend_id:
        pref = _CONSTRAINTS_BACKENDS.get(preferred_backend_id)
        if pref is not None:
            ordered.append(pref)
            tried.add(pref.id)

    for b in sorted(_CONSTRAINTS_BACKENDS.values(), key=lambda b: b.priority, reverse=True):
        if b.id not in tried:
            ordered.append(b)
            tried.add(b.id)

    for b in ordered:
        # Stay on Basic once the particle pass has fallen back, so passes agree.
        if _LOCK_TO_BASIC and b.id != "BASIC":
            continue
        if b.draw is None:
            continue
        try:
            if not b.is_available():
                continue
        except Exception:
            continue
        try:
            if b.draw(context, pipeline, scene, params):
                return
        except Exception:
            continue


def draw_volume_with_backends(
    context,
    pipeline,
    scene,
    params: VolumeDrawParams,
) -> None:
    """Route a single ExplosiaFX domain through registered volume backends.

    Called once per enabled NX_EXPLOSIAFX object each frame. Attempts to use backends
    in priority order and stops on the first success.
    """
    _ensure_default_volume_backends_loaded()

    for b in sorted(_VOLUME_BACKENDS.values(), key=lambda b: b.priority, reverse=True):
        if b.draw is None:
            continue
        try:
            if not b.is_available():
                continue
        except Exception:
            continue
        try:
            if b.draw(context, pipeline, scene, params):
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Generator backend registry (NX_GENERATOR mesh-instancing)
# ---------------------------------------------------------------------------

_GENERATOR_BACKENDS: dict[str, ViewportBackend] = {}
_GENERATOR_DEFAULT_LOADED = False


def register_generator_backend(backend: ViewportBackend) -> None:
    """Register or replace a generator backend by id."""
    _GENERATOR_BACKENDS[backend.id] = backend


def _ensure_default_generator_backends_loaded() -> None:
    global _GENERATOR_DEFAULT_LOADED
    if _GENERATOR_DEFAULT_LOADED:
        return
    _GENERATOR_DEFAULT_LOADED = True

    from .generators import register_generator_backends

    register_generator_backends()


def draw_generators_with_backends(
    context,
    pipeline,
    scene,
    params: GeneratorDrawParams,
) -> None:
    """Route a single NX_GENERATOR object through registered generator backends.

    Called once per enabled NX_GENERATOR object each frame. Attempts backends in
    priority order and stops on the first success.
    """
    _ensure_default_generator_backends_loaded()

    for b in sorted(_GENERATOR_BACKENDS.values(), key=lambda b: b.priority, reverse=True):
        if b.draw is None:
            continue
        try:
            if not b.is_available():
                continue
        except Exception:
            continue
        try:
            if b.draw(context, pipeline, scene, params):
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Trail backend registry (NX_TRAIL line overlay)
# ---------------------------------------------------------------------------

_TRAIL_BACKENDS: dict[str, ViewportBackend] = {}
_TRAIL_DEFAULT_LOADED = False


def register_trail_backend(backend: ViewportBackend) -> None:
    """Register or replace a trail backend by id."""
    _TRAIL_BACKENDS[backend.id] = backend


def _ensure_default_trail_backends_loaded() -> None:
    global _TRAIL_DEFAULT_LOADED
    if _TRAIL_DEFAULT_LOADED:
        return
    _TRAIL_DEFAULT_LOADED = True

    from .trails import register_trail_backends

    register_trail_backends()


def draw_trails_with_backends(
    context,
    pipeline,
    scene,
    params: TrailDrawParams,
    preferred_backend_id: str | None = None,
) -> None:
    """Route trail drawing through the selected backend, or priority fallback."""
    _ensure_default_trail_backends_loaded()

    preferred = (preferred_backend_id or "").upper()
    ordered: list[ViewportBackend] = []
    tried: set[str] = set()
    if preferred:
        backend = _TRAIL_BACKENDS.get(preferred)
        if backend is not None:
            ordered.append(backend)
            tried.add(backend.id)

    for b in sorted(_TRAIL_BACKENDS.values(), key=lambda b: b.priority, reverse=True):
        if b.id not in tried:
            ordered.append(b)
            tried.add(b.id)

    for b in ordered:
        if b.draw is None:
            continue
        try:
            if not b.is_available():
                continue
        except Exception:
            continue
        try:
            if b.draw(context, pipeline, scene, params):
                return
        except Exception:
            continue
