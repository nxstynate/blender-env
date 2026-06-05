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

from collections import deque
from datetime import datetime
from time import perf_counter

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

hud_bounds = None

_SPARKLINE_SAMPLES = 120
_sparkline_history: dict = {}
_last_sampled_tick: int = -1


def _get_history(key: str) -> deque:
    """Get or create a rolling history buffer for the given key."""
    if key not in _sparkline_history:
        _sparkline_history[key] = deque(maxlen=_SPARKLINE_SAMPLES)
    return _sparkline_history[key]


# (setting_name, label_fmt, value_getter, font_scale, sparkline_key, spark_max)
# sparkline_key: if set, the numeric value is pushed to a history buffer
# and a sparkline can be drawn behind the row. None = no sparkline support.
# spark_max: fixed ceiling for the sparkline (e.g. 100 for %).
#            None = auto-scale to peak sample.
HUD_ITEMS = [
    (
        "hud_show_particle_count",
        "Particle Count: {:,}",
        lambda p: _get_particle_count(p),
        1.0,
        "particle_count",
        None,
    ),
    ("hud_show_vram_usage", None, lambda p: _get_vram_usage(), 1.0, "vram_pct", 100.0),
    ("hud_show_frame_time", None, lambda p: _get_frame_time(), 1.0, "frame_time", None),
    ("hud_show_release_info", None, lambda p: _get_release_info(), 0.75, None, None),
    ("hud_show_device_name", None, lambda p: _get_device_name(), 0.75, None, None),
]

# Reference string used to get a stable line height for a given font size.
_HEIGHT_REF = "Ag0,|"

# Sparkline samplers: return a numeric value for the given pipeline.
# Called only when a new frame has been executed.
_SPARKLINE_SAMPLERS = {
    "particle_count": lambda p: _sample_particle_count(p),
    "vram_pct": lambda _: _sample_vram_pct(),
    "frame_time": lambda _: _sample_frame_time(),
}


def _get_particle_count(pipeline):
    if pipeline is None:
        return None
    from ..libs import theron

    return theron.get_particle_count(pipeline)


def _sample_particle_count(pipeline):
    if pipeline is None:
        return None
    from ..libs import theron

    return theron.get_particle_count(pipeline)


def _sample_vram_pct():
    from ..libs import theron

    allocated = theron.get_allocated_vram()
    available = theron.get_available_vram()
    pool = allocated + available
    if pool == 0:
        return None
    return (allocated / pool) * 100.0


def _sample_frame_time():
    from ..handlers import pipeline as pipeline_manager

    return pipeline_manager.get_last_frame_time_ms()


def _format_bytes(b):
    if b >= 1000**3:
        return f"{b / (1000**3):.1f} GB"
    return f"{b / (1000**2):.0f} MB"


def _get_vram_usage():
    """Return a pre-formatted VRAM usage string."""
    from ..libs import theron

    allocated = theron.get_allocated_vram()
    available = theron.get_available_vram()
    pool = allocated + available
    if pool == 0:
        return None
    pct = (allocated / pool) * 100.0
    return f"VRAM: {_format_bytes(allocated)} / {_format_bytes(pool)} ({pct:.0f}%)"


def _get_frame_time():
    """Return a pre-formatted NeXus FPS string."""
    from ..handlers import pipeline as pipeline_manager

    ms = pipeline_manager.get_last_frame_time_ms()
    if ms <= 0.0:
        return None
    fps = 1000.0 / ms
    return f"FPS: {fps:.1f}"


def _get_release_info():
    """Return a pre-formatted release info string."""
    from .. import version
    from ..libs import theron

    ver = version.get_blender_version_str()
    build_ts = theron.get_build_date()
    if build_ts:
        date = datetime.fromtimestamp(build_ts).strftime("%Y-%m-%d %H:%M")
        return f"NeXus v{ver} | Build: {date}"
    return f"NeXus v{ver}"


def _get_device_name():
    """Returns the current device name."""
    from ..libs import theron

    return theron.get_current_device_name()


def _draw_sparkline(samples, x0, y0, x1, y1, color, max_value=None):
    """Draw a filled sparkline area chart within the given bounds.

    Args:
        max_value: If set, use this as the ceiling (e.g. 100 for percentage).
                   If None, auto-scale to the peak sample value.
    """
    import numpy as np

    n = len(samples)
    if n < 2:
        return

    peak = max_value if max_value is not None else max(samples)
    if peak <= 0.0:
        return

    width = x1 - x0
    height = y1 - y0

    # X positions for each sample point.
    t = np.arange(n, dtype=np.float32) / (n - 1)
    sx = x0 + t * width

    # Y positions (data points clamped to peak).
    s = np.array(samples, dtype=np.float32)
    sy = y0 + np.minimum(s / peak, 1.0) * height

    # Build 6 vertices per segment: two triangles forming a quad.
    #   tri1: (sx[i], y0), (sx[i], sy[i]), (sx[i+1], sy[i+1])
    #   tri2: (sx[i], y0), (sx[i+1], sy[i+1]), (sx[i+1], y0)
    m = n - 1
    verts = np.empty((m * 6, 2), dtype=np.float32)
    verts[0::6, 0] = sx[:-1]
    verts[0::6, 1] = y0
    verts[1::6, 0] = sx[:-1]
    verts[1::6, 1] = sy[:-1]
    verts[2::6, 0] = sx[1:]
    verts[2::6, 1] = sy[1:]
    verts[3::6, 0] = sx[:-1]
    verts[3::6, 1] = y0
    verts[4::6, 0] = sx[1:]
    verts[4::6, 1] = sy[1:]
    verts[5::6, 0] = sx[1:]
    verts[5::6, 1] = y0

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRIS", {"pos": verts.tolist()})
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_hud():
    """POST_PIXEL entry. The finally block closes the playback frame timer so
    the measurement spans sim → end of HUD draw even on early returns."""
    from ..handlers import pipeline as pipeline_manager

    try:
        _draw_hud_body()
    finally:
        frame_start = pipeline_manager.consume_playback_frame_start()
        if frame_start is not None:
            active_ms = (perf_counter() - frame_start) * 1000.0
            wall_clock_ms = pipeline_manager.get_last_wall_clock_ms()
            target_ms = _scene_target_frame_ms()
            pipeline_manager.set_last_frame_time_ms(
                _resolve_playback_frame_ms(active_ms, wall_clock_ms, target_ms)
            )


def _scene_target_frame_ms() -> float:
    try:
        scene = bpy.context.scene
        fps = float(scene.render.fps)
        fps_base = float(scene.render.fps_base)
    except (AttributeError, RuntimeError):
        return 0.0
    if fps <= 0.0 or fps_base <= 0.0:
        return 0.0
    return (fps_base / fps) * 1000.0


def _resolve_playback_frame_ms(active_ms: float, wall_clock_ms: float, target_ms: float) -> float:
    """Use wall-clock only when saturated (work exceeds target, no sleep);
    otherwise fall back to uncapped active work. The 4× upper bound rejects
    spikes from pause/resume or scene changes."""
    saturated = target_ms > 0.0 and target_ms * 1.02 < wall_clock_ms <= target_ms * 4.0
    return wall_clock_ms if saturated else active_ms


def _draw_hud_body():
    global hud_bounds

    hud_bounds = None

    from ..handlers import pipeline as pipeline_manager
    from ..libs import theron

    if not theron.is_initialized():
        return

    scene = bpy.context.scene
    if not hasattr(scene, "nexus_pipeline"):
        return

    pipeline_settings = scene.nexus_pipeline
    hud = pipeline_settings.hud

    if not hud.hud_enabled:
        return

    global _last_sampled_tick

    pipeline = pipeline_manager.get_pipeline(scene)

    # Only push sparkline samples when the pipeline has actually executed a new frame.
    tick = pipeline_manager.get_execution_tick()
    is_new_frame = tick != _last_sampled_tick
    if is_new_frame:
        _last_sampled_tick = tick
        for key, sampler in _SPARKLINE_SAMPLERS.items():
            val = sampler(pipeline)
            if val is not None:
                _get_history(key).append(val)

    lines = []
    base_font_size = hud.hud_font_size
    for setting_name, label_fmt, value_getter, font_scale, spark_key, spark_max in HUD_ITEMS:
        if getattr(hud, setting_name, False):
            value = value_getter(pipeline)
            if value is None:
                continue
            text = str(value) if label_fmt is None else label_fmt.format(value)
            lines.append((text, int(base_font_size * font_scale), spark_key, spark_max))

    if not lines:
        return

    font_id = 0
    padding_x = 10
    padding_y = 8
    line_spacing = 4

    line_heights = []
    max_width = 0.0
    for text, size, _, _ in lines:
        blf.size(font_id, size)
        w, _ = blf.dimensions(font_id, text)
        _, ref_h = blf.dimensions(font_id, _HEIGHT_REF)
        line_heights.append(ref_h)
        if w > max_width:
            max_width = w

    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)

    region = bpy.context.region
    if region is None or region.width < 1 or region.height < 1:
        return

    x = int(hud.hud_pos_x * region.width)
    y = int(hud.hud_pos_y * region.height)

    bg_w = max_width + 2 * padding_x
    bg_h = total_text_height + 2 * padding_y

    if x - padding_x + bg_w > region.width:
        x = region.width - int(bg_w) + padding_x
    if y - padding_y + bg_h > region.height:
        y = region.height - int(bg_h) + padding_y
    if x - padding_x < 0:
        x = padding_x
    if y - padding_y < 0:
        y = padding_y

    bg_x0 = x - padding_x
    bg_y0 = y - padding_y
    bg_x1 = x + max_width + padding_x
    bg_y1 = y + total_text_height + padding_y

    gpu.state.blend_set("ALPHA")

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    vertices = [(bg_x0, bg_y0), (bg_x1, bg_y0), (bg_x1, bg_y1), (bg_x0, bg_y1)]
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})
    shader.uniform_float("color", (*hud.hud_bg_color, hud.hud_opacity))
    batch.draw(shader)

    hud_bounds = (bg_x0, bg_y0, bg_x1, bg_y1)

    line_y_tops = []
    cur_y = y + total_text_height - line_heights[0]
    for i in range(len(lines)):
        line_y_tops.append(cur_y)
        if i < len(lines) - 1:
            cur_y -= line_heights[i] + line_spacing

    spark_color = (*hud.hud_text_color, 0.12)
    for i, (_, _, spark_key, spark_max) in enumerate(lines):
        if spark_key is None:
            continue
        spark_prop = f"hud_spark_{spark_key}"
        if not getattr(hud, spark_prop, False):
            continue
        history = _sparkline_history.get(spark_key)
        if history and len(history) >= 2:
            row_y0 = line_y_tops[i] - line_heights[i] * 0.15
            row_y1 = line_y_tops[i] + line_heights[i] * 1.0
            _draw_sparkline(
                history,
                bg_x0,
                row_y0,
                bg_x1,
                row_y1,
                spark_color,
                spark_max,
            )

    for i, (text, size, _, _) in enumerate(lines):
        blf.size(font_id, size)
        blf.position(font_id, x, line_y_tops[i], 0)
        blf.color(font_id, *hud.hud_text_color, 1.0)
        blf.draw(font_id, text)

    gpu.state.blend_set("NONE")
