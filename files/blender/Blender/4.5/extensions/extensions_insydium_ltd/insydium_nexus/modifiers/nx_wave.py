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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from ..libs import theron
from ..properties.nx_wave import SPEC, get_wave_ui_config
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_RED,
    draw_lines,
    draw_thick_lines,
)
from ..utils.gradient import GradientSpec, NexusGradient
from .base import MenuCategory, NexusModifier, UIFlags

WAVE_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="wave_gradient",
        label="Color",
        default_stops=[
            (0.0, (0.078, 0.0, 1.0, 1.0)),
            (0.333, (0.0, 0.549, 1.0, 1.0)),
            (0.666, (0.549, 0.862, 1.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
]

NOISE_TYPE_MAP = {
    "ID_NX_WAVES_NOISE_TYPE_SIMPLEX": theron.TrNoiseType.TR_NOISE_TYPE_SIMPLEX,
    "ID_NX_WAVES_NOISE_TYPE_FBM": theron.TrNoiseType.TR_NOISE_TYPE_FBM,
    "ID_NX_WAVES_NOISE_TYPE_TURBULENCE": theron.TrNoiseType.TR_NOISE_TYPE_TURBULENCE,
    "ID_NX_WAVES_NOISE_TYPE_WAVY_TURBULENCE": theron.TrNoiseType.TR_NOISE_TYPE_WAVY_TURBULENCE,
    "ID_NX_WAVES_NOISE_TYPE_VORO": theron.TrNoiseType.TR_NOISE_TYPE_VORONOISE,
    "ID_NX_WAVES_NOISE_TYPE_CUBIC": theron.TrNoiseType.TR_NOISE_TYPE_CUBIC,
}


@dataclass
class WaveCacheData:
    grid_slices: Optional[List] = None
    noise_positions: Optional[List[Tuple[float, float, float]]] = None
    noise_values: Optional[List[float]] = None
    displaced_slices: Optional[List] = None
    batches: Dict[str, Any] = field(default_factory=dict)

    prev_size: Optional[Tuple[float, float, float]] = None
    prev_spacing_x: Optional[float] = None
    prev_spacing_y: Optional[float] = None
    prev_slices: Optional[int] = None
    prev_scale: Optional[Tuple[float, float, float]] = None
    prev_matrix: Optional[Tuple] = None
    prev_noise_type: Optional[str] = None
    prev_time: Optional[float] = None
    prev_strength: Optional[float] = None
    prev_low_clip: Optional[float] = None
    prev_high_clip: Optional[float] = None
    prev_brightness: Optional[float] = None
    prev_contrast: Optional[float] = None
    prev_draw_type: Optional[str] = None
    prev_gradient_hash: Optional[int] = None


_wave_cache: Dict[str, WaveCacheData] = {}


def _get_wave_cache(key: str) -> WaveCacheData:
    if key not in _wave_cache:
        _wave_cache[key] = WaveCacheData()
    return _wave_cache[key]


def _wave_cache_key(obj: bpy.types.Object) -> str:
    from ..pipeline_manager.identity import get_object_uid

    return get_object_uid(obj) or obj.name


def _matrix_to_tuple(mx: Matrix) -> Tuple:
    return tuple(tuple(row) for row in mx)


def _check_wave_dirty(
    cache: WaveCacheData,
    size: Tuple[float, float, float],
    spacing_x: float,
    spacing_y: float,
    num_slices: int,
    scale: Tuple[float, float, float],
    matrix_tuple: Tuple,
    noise_type: str,
    wave_time: float,
    strength: float,
    low_clip: float,
    high_clip: float,
    brightness: float,
    contrast: float,
    draw_type: str,
) -> Tuple[bool, bool, bool, bool, bool]:
    grid_dirty = (
        cache.grid_slices is None
        or cache.prev_size != size
        or cache.prev_spacing_x != spacing_x
        or cache.prev_spacing_y != spacing_y
        or cache.prev_slices != num_slices
    )

    noise_pos_dirty = (
        grid_dirty
        or cache.noise_positions is None
        or cache.prev_scale != scale
        or cache.prev_matrix != matrix_tuple
        or cache.prev_time != wave_time
    )

    noise_val_dirty = (
        noise_pos_dirty or cache.noise_values is None or cache.prev_noise_type != noise_type
    )

    disp_dirty = (
        noise_val_dirty
        or cache.displaced_slices is None
        or cache.prev_strength != strength
        or cache.prev_low_clip != low_clip
        or cache.prev_high_clip != high_clip
        or cache.prev_brightness != brightness
        or cache.prev_contrast != contrast
        or cache.prev_draw_type != draw_type
    )

    batch_dirty = disp_dirty or draw_type not in cache.batches

    return grid_dirty, noise_pos_dirty, noise_val_dirty, disp_dirty, batch_dirty


def _update_cache_state(
    cache: WaveCacheData,
    size: Tuple[float, float, float],
    spacing_x: float,
    spacing_y: float,
    num_slices: int,
    scale: Tuple[float, float, float],
    matrix_tuple: Tuple,
    noise_type: str,
    wave_time: float,
    strength: float,
    low_clip: float,
    high_clip: float,
    brightness: float,
    contrast: float,
    draw_type: str,
) -> None:
    cache.prev_size = size
    cache.prev_spacing_x = spacing_x
    cache.prev_spacing_y = spacing_y
    cache.prev_slices = num_slices
    cache.prev_scale = scale
    cache.prev_matrix = matrix_tuple
    cache.prev_noise_type = noise_type
    cache.prev_time = wave_time
    cache.prev_strength = strength
    cache.prev_low_clip = low_clip
    cache.prev_high_clip = high_clip
    cache.prev_brightness = brightness
    cache.prev_contrast = contrast
    cache.prev_draw_type = draw_type


def clear_wave_cache(key: Optional[str] = None):
    if key is None:
        _wave_cache.clear()
    elif key in _wave_cache:
        del _wave_cache[key]


class NXWaveModifier(NexusModifier):
    object_type = "NX_WAVE"
    object_name = "nxWave"
    object_label = "Wave Modifier"
    object_description = "Apply wave motion using noise patterns"
    icon_name = "nx_wave"
    category = "Forces"
    menu_category = MenuCategory.SIMULATION

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    gizmo_max_handles = 3

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        clear_wave_cache(mod_uid)

    @classmethod
    def on_state_clear(cls, *, free_resources=True):
        clear_wave_cache()

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        return [
            HandleConfig(Vector((1, 0, 0)), "wave_size_x"),
            HandleConfig(Vector((0, 1, 0)), "wave_size_y"),
            HandleConfig(Vector((0, 0, 1)), "wave_size_z"),
        ]

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def post_sync(cls, obj, container, handle, props, scene, depsgraph=None, original_props=None):
        from ..libs import theron
        from ..libs.theron_ids import get as get_id

        sx = float(props.wave_size_x)
        sy = float(props.wave_size_y)
        sz = float(props.wave_size_z)
        theron.set_vector(container, get_id("ID_NX_WAVES_SIZE"), sx, sy, sz)

        scx = float(props.wave_scale_x) * 0.01
        scy = float(props.wave_scale_y) * 0.01
        scz = float(props.wave_scale_z) * 0.01
        theron.set_vector(container, get_id("ID_NX_WAVES_SCALE"), scx, scy, scz)

    @classmethod
    def get_gradient_specs(cls):
        return WAVE_GRADIENT_SPECS

    @classmethod
    def get_tabs(cls, props):
        tabs = []
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
        ui_config = get_wave_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get(
            "ID_NX_WAVES_SPEED",
            {},
        ).get("use_property_split", True)
        col.prop(data, "ID_NX_WAVES_SPEED")
        col.prop(data, "ID_NX_WAVES_STRENGTH")

        size_row = col.row(align=True)
        size_split = size_row.split(factor=0.385)
        size_split.use_property_split = False
        label_col = size_split.column()
        label_col.alignment = "RIGHT"
        label_col.label(text="Size")
        content_col = size_split.column()
        content_row = content_col.row(align=True)
        content_row.prop(data, "wave_size_x", text="X")
        content_row.prop(data, "wave_size_y", text="Y")
        content_row.prop(data, "wave_size_z", text="Z")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_WAVES_TIME_SCALE")

        scale_row = col.row(align=True)
        scale_split = scale_row.split(factor=0.385)
        scale_split.use_property_split = False
        label_col = scale_split.column()
        label_col.alignment = "RIGHT"
        label_col.label(text="Scale")
        content_col = scale_split.column()
        content_row = content_col.row(align=True)
        content_row.prop(data, "wave_scale_x", text="X")
        content_row.prop(data, "wave_scale_y", text="Y")
        content_row.prop(data, "wave_scale_z", text="Z")

        col.prop(data, "ID_NX_WAVES_NOISE_TYPE")
        col.prop(data, "ID_NX_WAVES_LOW_CLIP")
        col.prop(data, "ID_NX_WAVES_HIGH_CLIP")
        col.prop(data, "ID_NX_WAVES_BRIGHTNESS")
        col.prop(data, "ID_NX_WAVES_CONTRAST")

    @classmethod
    def draw_display_section(cls, layout, data):
        obj = bpy.context.object

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "wave_draw_type")
        col.prop(data, "wave_slices")
        col.prop(data, "wave_grid_spacing_x")
        col.prop(data, "wave_grid_spacing_y")

        if data.wave_draw_type in ("SURFACE", "GRID", "PLANE", "LINE", "ARROW"):
            col.separator()

            if obj:
                NexusGradient(obj, "wave_gradient").draw_ui(col, "Color")

    @classmethod
    def _build_noise_positions(
        cls,
        slices: List[List[List[Vector]]],
        mx: Matrix,
        scale: Vector,
        wave_time: float,
    ) -> List[Tuple[float, float, float]]:

        scale *= 0.01  # convert from percentage

        positions = []
        for grid in slices:
            for row in grid:
                for pos in row:
                    world_pos = mx @ pos
                    scaled_pos = (
                        world_pos.x * scale.x,
                        (world_pos.y - wave_time) * scale.y,
                        world_pos.z * scale.z,
                    )
                    positions.append(scaled_pos)
        return positions

    @classmethod
    def _process_noise_value(
        cls,
        raw_noise: float,
        low_clip: float,
        high_clip: float,
        brightness: float,
        contrast: float,
    ) -> Tuple[float, float]:
        value = (raw_noise - 0.5) * contrast + 0.5 + brightness
        value = (value + 1.0) * 0.5
        color_value = max(low_clip, min(high_clip, value))
        displacement_value = 2.0 * (color_value - 0.5)
        return displacement_value, color_value

    @classmethod
    def _generate_grid_positions(
        cls, size: Vector, spacing_x: float, spacing_y: float, num_slices: int
    ) -> List[List[Vector]]:
        half_x = size.x
        half_y = size.y
        half_z = size.z

        spacing_x = max(0.01, spacing_x)
        spacing_y = max(0.01, spacing_y)

        total_range_x = 2.0 * half_x
        total_range_y = 2.0 * half_y

        num_x = max(1, int(total_range_x / spacing_x))
        if num_x > 100:
            num_x = 100
            spacing_x = total_range_x / num_x

        num_y = max(1, int(total_range_y / spacing_y))
        if num_y > 100:
            num_y = 100
            spacing_y = total_range_y / num_y

        slices = []
        slice_positions = (
            [0.0]
            if num_slices <= 1
            else [-half_z + (i / (num_slices - 1)) * (2.0 * half_z) for i in range(num_slices)]
        )

        for z_pos in slice_positions:
            grid = []
            for iy in range(num_y):
                row = []
                y = -half_y + (iy * spacing_y) + (spacing_y / 2.0)
                for ix in range(num_x):
                    x = -half_x + (ix * spacing_x) + (spacing_x / 2.0)
                    row.append(Vector((x, y, z_pos)))
                grid.append(row)
            slices.append(grid)

        return slices

    @classmethod
    def _build_displaced_slices(
        cls,
        slices: List,
        noise_values: List[float],
        mx: Matrix,
        strength: float,
        low_clip: float,
        high_clip: float,
        brightness: float,
        contrast: float,
        draw_type: str,
    ) -> List:
        displaced_slices = []
        value_index = 0

        for grid in slices:
            displaced_grid = []
            for row in grid:
                displaced_row = []
                for pos in row:
                    noise_val = (
                        noise_values[value_index] if value_index < len(noise_values) else 0.0
                    )
                    value_index += 1

                    disp_val, color_val = cls._process_noise_value(
                        noise_val, low_clip, high_clip, brightness, contrast
                    )

                    if draw_type == "PLANE":
                        displaced = mx @ pos
                    else:
                        displacement = disp_val * strength
                        local_displaced = Vector((pos.x, pos.y, pos.z + displacement))
                        displaced = mx @ local_displaced

                    displaced_row.append((displaced, color_val))
                displaced_grid.append(displaced_row)
            displaced_slices.append(displaced_grid)

        return displaced_slices

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        draw_type = getattr(props, "wave_draw_type", "NONE")

        if draw_type == "NONE":
            return

        size = Vector(
            (
                getattr(props, "wave_size_x", 2.0),
                getattr(props, "wave_size_y", 2.0),
                getattr(props, "wave_size_z", 2.0),
            )
        )
        strength = getattr(props, "ID_NX_WAVES_STRENGTH", 1.0)
        speed = getattr(props, "ID_NX_WAVES_SPEED", 1.0)
        time_scale = getattr(props, "ID_NX_WAVES_TIME_SCALE", 1.0)

        scale = Vector(
            (
                getattr(props, "wave_scale_x", 10.0),
                getattr(props, "wave_scale_y", 100.0),
                getattr(props, "wave_scale_z", 0.0),
            )
        )

        noise_type = getattr(props, "ID_NX_WAVES_NOISE_TYPE", "ID_NX_WAVES_NOISE_TYPE_SIMPLEX")
        low_clip = getattr(props, "ID_NX_WAVES_LOW_CLIP", 0.0)
        high_clip = getattr(props, "ID_NX_WAVES_HIGH_CLIP", 1.0)
        brightness = getattr(props, "ID_NX_WAVES_BRIGHTNESS", 0.0)
        contrast = getattr(props, "ID_NX_WAVES_CONTRAST", 1.0)
        num_slices = getattr(props, "wave_slices", 1)
        spacing_x = getattr(props, "wave_grid_spacing_x", 0.1)
        spacing_y = getattr(props, "wave_grid_spacing_y", 0.1)

        fps = context.scene.render.fps / context.scene.render.fps_base
        current_time_seconds = context.scene.frame_current / fps
        wave_time = current_time_seconds * time_scale * 0.01 * speed

        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        cls._draw_bounding_box(shader, mx, size)

        shader.uniform_float("color", XP_COLOR_MODS_RED)
        cls._draw_direction_arrow(shader, mx, size)

        cls._draw_corner_accents(context, mx, size, XP_COLOR_MODS_RED)

        if draw_type in ("LINE", "ARROW", "GRID", "SURFACE", "PLANE"):
            size_tuple = (size.x, size.y, size.z)
            scale_tuple = (scale.x, scale.y, scale.z)
            matrix_tuple = _matrix_to_tuple(mx)

            cache = _get_wave_cache(_wave_cache_key(obj))

            grid_dirty, noise_pos_dirty, noise_val_dirty, disp_dirty, batch_dirty = (
                _check_wave_dirty(
                    cache,
                    size_tuple,
                    spacing_x,
                    spacing_y,
                    num_slices,
                    scale_tuple,
                    matrix_tuple,
                    noise_type,
                    wave_time,
                    strength,
                    low_clip,
                    high_clip,
                    brightness,
                    contrast,
                    draw_type,
                )
            )

            if grid_dirty:
                cache.grid_slices = cls._generate_grid_positions(
                    size, spacing_x, spacing_y, num_slices
                )
                cache.batches.clear()

            if noise_pos_dirty:
                cache.noise_positions = cls._build_noise_positions(
                    cache.grid_slices, mx, scale, wave_time
                )
                cache.batches.clear()

            if noise_val_dirty:
                theron_noise_type = NOISE_TYPE_MAP.get(
                    noise_type, theron.TrNoiseType.TR_NOISE_TYPE_SIMPLEX
                )
                if theron.is_initialized() and cache.noise_positions:
                    prefs = theron.create_prefs(
                        octaves=4,
                        scale=1.0,
                        persistence=0.5,
                        lacunarity=2.0,
                        frequency=1.0,
                        amplitude=1.0,
                        absolute=False,
                    )
                    cache.noise_values = theron.eval_1d(
                        cache.noise_positions, theron_noise_type, prefs, 0.0
                    )
                else:
                    cache.noise_values = (
                        [0.0] * len(cache.noise_positions) if cache.noise_positions else []
                    )
                cache.batches.clear()

            if disp_dirty:
                cache.displaced_slices = cls._build_displaced_slices(
                    cache.grid_slices,
                    cache.noise_values,
                    mx,
                    strength * 100.0 * (1.0 / fps),
                    low_clip * 0.01,
                    high_clip * 0.01,
                    brightness * 0.01,
                    contrast * 0.01,
                    draw_type,
                )
                cache.batches.clear()

            gradient = NexusGradient(obj, "wave_gradient")
            gradient_lut = gradient.lut
            current_grad_hash = gradient.hash
            if current_grad_hash != cache.prev_gradient_hash:
                cache.batches.clear()
                cache.prev_gradient_hash = current_grad_hash
                batch_dirty = True

            if batch_dirty or draw_type not in cache.batches:
                if draw_type == "LINE":
                    cache.batches[draw_type] = cls._build_lines_batch(
                        mx, cache.grid_slices, cache.displaced_slices, gradient_lut
                    )
                elif draw_type == "ARROW":
                    cache.batches[draw_type] = cls._build_arrows_batch(
                        mx, cache.grid_slices, cache.displaced_slices, gradient_lut
                    )
                elif draw_type == "GRID":
                    cache.batches[draw_type] = cls._build_grid_batch(
                        cache.displaced_slices, gradient_lut
                    )
                elif draw_type in ("SURFACE", "PLANE"):
                    cache.batches[draw_type] = cls._build_surface_batch(
                        cache.displaced_slices, gradient_lut
                    )

            _update_cache_state(
                cache,
                size_tuple,
                spacing_x,
                spacing_y,
                num_slices,
                scale_tuple,
                matrix_tuple,
                noise_type,
                wave_time,
                strength,
                low_clip,
                high_clip,
                brightness,
                contrast,
                draw_type,
            )

            cached_batch = cache.batches.get(draw_type)
            if cached_batch:
                if draw_type in ("SURFACE", "PLANE"):
                    cls._draw_surface_batch(cached_batch)
                else:
                    cls._draw_colored_batch(cached_batch)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)

    @classmethod
    def _draw_bounding_box(cls, shader, mx: Matrix, size: Vector) -> None:
        hx, hy, hz = size.x, size.y, size.z

        corners = [
            Vector((-hx, -hy, -hz)),
            Vector((hx, -hy, -hz)),
            Vector((hx, -hy, hz)),
            Vector((-hx, -hy, hz)),
            Vector((-hx, hy, -hz)),
            Vector((hx, hy, -hz)),
            Vector((hx, hy, hz)),
            Vector((-hx, hy, hz)),
        ]
        corners = [mx @ c for c in corners]

        edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]

        lines = [(corners[e[0]], corners[e[1]]) for e in edges]
        draw_lines(shader, lines)

    @classmethod
    def _draw_direction_arrow(cls, shader, mx: Matrix, size: Vector) -> None:
        hy = size.y
        arrow_length = size.y * 0.3
        barb_size = arrow_length * 0.2

        base = mx @ Vector((0.0, hy, 0.0))
        tip = mx @ Vector((0.0, hy + arrow_length, 0.0))

        arrow_lines = [
            (base, tip),
            (tip, mx @ Vector((-barb_size, hy + arrow_length - barb_size, 0.0))),
            (tip, mx @ Vector((barb_size, hy + arrow_length - barb_size, 0.0))),
            (tip, mx @ Vector((0.0, hy + arrow_length - barb_size, barb_size))),
            (tip, mx @ Vector((0.0, hy + arrow_length - barb_size, -barb_size))),
        ]
        draw_lines(shader, arrow_lines)

    @classmethod
    def _draw_corner_accents(cls, context, mx: Matrix, size: Vector, color: Tuple) -> None:
        hx, hy, hz = size.x, size.y, size.z
        accent_length = min(hx, hy, hz) * 0.2

        corners = [
            (
                Vector((-hx, -hy, -hz)),
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, -hy, -hz)),
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, -hy, hz)),
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, -hy, hz)),
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, hy, -hz)),
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, hy, -hz)),
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, hy, hz)),
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, hy, hz)),
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
            ),
        ]

        accent_lines = []
        for corner, directions in corners:
            corner_world = mx @ corner
            for d in directions:
                end_local = corner + d * accent_length
                end_world = mx @ end_local
                accent_lines.append((corner_world, end_world))

        draw_thick_lines(context, accent_lines, color, line_width=3.0)

    @classmethod
    def _value_to_color(cls, value: float, lut) -> Tuple[float, float, float, float]:
        if lut is None:
            return (1.0, 1.0, 1.0, 0.7)
        r, g, b, a = lut[max(0, min(255, int(value * 255.0)))]
        return (r, g, b, 0.7)

    @classmethod
    def _build_lines_batch(
        cls, mx: Matrix, original_slices: List, displaced_slices: List, lut
    ) -> Any:
        vertices = []
        colors = []

        for orig_grid, disp_grid in zip(original_slices, displaced_slices):
            for row_orig, row_disp in zip(orig_grid, disp_grid):
                for orig_pos, (disp_pos, value) in zip(row_orig, row_disp):
                    orig_world = mx @ orig_pos
                    color = cls._value_to_color(value, lut)
                    vertices.extend([orig_world, disp_pos])
                    colors.extend([color, color])

        if not vertices:
            return None

        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        return batch_for_shader(shader, "LINES", {"pos": vertices, "color": colors})

    @classmethod
    def _build_arrows_batch(
        cls, mx: Matrix, original_slices: List, displaced_slices: List, lut
    ) -> Any:
        vertices = []
        colors = []
        barb_size = 0.02

        for orig_grid, disp_grid in zip(original_slices, displaced_slices):
            for row_orig, row_disp in zip(orig_grid, disp_grid):
                for orig_pos, (disp_pos, value) in zip(row_orig, row_disp):
                    orig_world = mx @ orig_pos
                    color = cls._value_to_color(value, lut)

                    vertices.extend([orig_world, disp_pos])
                    colors.extend([color, color])

                    direction = disp_pos - orig_world
                    if direction.length > 0.001:
                        direction.normalize()
                        perp = Vector((-direction.z, 0, direction.x))
                        if perp.length < 0.001:
                            perp = Vector((1, 0, 0))
                        perp.normalize()

                        barb1 = disp_pos - direction * barb_size + perp * barb_size * 0.5
                        barb2 = disp_pos - direction * barb_size - perp * barb_size * 0.5
                        vertices.extend([disp_pos, barb1])
                        colors.extend([color, color])
                        vertices.extend([disp_pos, barb2])
                        colors.extend([color, color])

        if not vertices:
            return None

        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        return batch_for_shader(shader, "LINES", {"pos": vertices, "color": colors})

    @classmethod
    def _build_grid_batch(cls, displaced_slices: List, lut) -> Any:
        vertices = []
        colors = []

        for disp_grid in displaced_slices:
            for iz, row in enumerate(disp_grid):
                for ix, (pos, value) in enumerate(row):
                    if ix < len(row) - 1:
                        next_pos, next_value = row[ix + 1]
                        vertices.extend([pos, next_pos])
                        colors.extend(
                            [
                                cls._value_to_color(value, lut),
                                cls._value_to_color(next_value, lut),
                            ]
                        )
                    if iz < len(disp_grid) - 1:
                        below_pos, below_value = disp_grid[iz + 1][ix]
                        vertices.extend([pos, below_pos])
                        colors.extend(
                            [
                                cls._value_to_color(value, lut),
                                cls._value_to_color(below_value, lut),
                            ]
                        )

        if not vertices:
            return None

        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        return batch_for_shader(shader, "LINES", {"pos": vertices, "color": colors})

    @classmethod
    def _build_surface_batch(cls, displaced_slices: List, lut) -> Any:
        vertices = []
        colors = []

        for disp_grid in displaced_slices:
            num_rows = len(disp_grid)
            if num_rows < 2:
                continue

            for iz in range(num_rows - 1):
                row = disp_grid[iz]
                next_row = disp_grid[iz + 1]
                num_cols = len(row)
                if num_cols < 2:
                    continue

                for ix in range(num_cols - 1):
                    p00, v00 = row[ix]
                    p10, v10 = row[ix + 1]
                    p01, v01 = next_row[ix]
                    p11, v11 = next_row[ix + 1]

                    vertices.extend([p00, p10, p11])
                    colors.extend(
                        [
                            cls._value_to_color(v00, lut),
                            cls._value_to_color(v10, lut),
                            cls._value_to_color(v11, lut),
                        ]
                    )

                    vertices.extend([p00, p11, p01])
                    colors.extend(
                        [
                            cls._value_to_color(v00, lut),
                            cls._value_to_color(v11, lut),
                            cls._value_to_color(v01, lut),
                        ]
                    )

        if not vertices:
            return None

        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        return batch_for_shader(shader, "TRIS", {"pos": vertices, "color": colors})

    @classmethod
    def _draw_colored_batch(cls, batch) -> None:
        if batch is None:
            return
        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        batch.draw(shader)

    @classmethod
    def _draw_surface_batch(cls, batch) -> None:
        if batch is None:
            return
        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        gpu.state.depth_test_set("LESS_EQUAL")
        batch.draw(shader)
        gpu.state.depth_test_set("NONE")
