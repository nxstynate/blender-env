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

import re

from .mesh import extract_line_data, extract_mesh_data, extract_mesh_loop_data
from .viewport import draw_circle, draw_lines, draw_thick_circle, draw_thick_lines

__all__ = [
    "draw_circle",
    "draw_lines",
    "draw_thick_circle",
    "draw_thick_lines",
    "extract_line_data",
    "extract_mesh_data",
    "extract_mesh_loop_data",
]

XP_COLOR_MODS = (1.0, 0.62, 0.36, 1.0)
XP_COLOR_MODS_BLUE = (0.45, 0.75, 0.94, 1.0)
XP_COLOR_MODS_RED = (1.0, 0.29, 0.39, 1.0)
XP_COLOR_MODS_ORANGE = (1.0, 0.5, 0.1, 1.0)
XP_COLOR_MODS_GREEN = (0.0, 1.0, 0.5, 1.0)


def _srgb_channel_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def srgb_to_linear(color):
    """Convert an sRGB display-space colour to linear scene-space."""
    if len(color) == 4:
        r, g, b, a = color
        return (
            _srgb_channel_to_linear(r),
            _srgb_channel_to_linear(g),
            _srgb_channel_to_linear(b),
            a,
        )
    r, g, b = color
    return (
        _srgb_channel_to_linear(r),
        _srgb_channel_to_linear(g),
        _srgb_channel_to_linear(b),
    )


def generate_unique_name(base_name: str, existing_names) -> str:
    names_set = set(existing_names)

    pattern = r"^(.+?)\.(\d{3})$"
    match = re.match(pattern, base_name)
    base = match.group(1) if match else base_name

    if base not in names_set:
        return base

    num = 1
    while True:
        candidate = f"{base}.{num:03d}"
        if candidate not in names_set:
            return candidate
        num += 1


def get_blender_addon():
    """Return the add-on object."""

    import bpy

    addon_name = __package__.rsplit(".", 1)[0]
    return bpy.context.preferences.addons[addon_name]


def use_accelerated_viewport() -> bool:
    """Read the Accelerated Viewport pref; defaults to True if prefs aren't available."""
    try:
        return bool(get_blender_addon().preferences.accelerated_viewport)
    except Exception:
        return True
