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

"""NeXus Rate System

Per-property rate mode (/f or /s) for emission count properties.

Usage in modifier UI::

    from ..libs.nexus_rate import draw_rate_prop
    draw_rate_prop(col, data, "ID_NX_EMITTER_SHOT_COUNT")

Usage in sync spec::

    SyncSpec("ID_NX_EMITTER_SHOT_COUNT", "ID_NX_EMITTER_SHOT_COUNT", SyncType.RATE),
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bpy

_MODE_KEY_PREFIX = "_nx_rate_"
_DEFAULT_RATE_MODE = "PER_SECOND"
_RATE_PROPERTY_REGISTRY: set[str] = set()


def register_rate_property(prop_name: str) -> None:
    _RATE_PROPERTY_REGISTRY.add(prop_name)


def get_rate_mode(data, prop_name: str) -> str:
    key = _MODE_KEY_PREFIX + prop_name
    mode = data.get(key)
    if mode in ("PER_FRAME", "PER_SECOND"):
        return mode
    return _DEFAULT_RATE_MODE


def set_rate_mode(data, prop_name: str, mode: str) -> None:
    key = _MODE_KEY_PREFIX + prop_name
    data[key] = mode


def _get_fps() -> float:
    from .nexus_time import get_fps

    return get_fps()


def to_per_second(value: int, fps: float | None = None, mode: str | None = None) -> int:
    if mode == "PER_FRAME":
        return max(1, round(value * (fps or _get_fps())))
    return value


def to_per_frame(value: int, fps: float | None = None, mode: str | None = None) -> int:
    if mode == "PER_SECOND":
        return max(1, round(value / (fps or _get_fps())))
    return value


def draw_rate_prop(
    layout,
    data,
    prop_name: str,
    *,
    text: str | None = None,
    enabled: bool = True,
) -> None:
    mode = get_rate_mode(data, prop_name)

    try:
        id_data = data.id_data
        obj_name = id_data.name if id_data else ""
        data_path = data.path_from_id() if id_data else ""
    except (AttributeError, TypeError):
        obj_name = ""
        data_path = ""

    row = layout.row(align=True)
    if not enabled:
        row.enabled = False

    kwargs = {}
    if text is not None:
        kwargs["text"] = text
    row.prop(data, prop_name, **kwargs)

    sub = row.row(align=True)
    sub.ui_units_x = 1.2
    op = sub.operator(
        "nexus.toggle_rate_mode",
        text="/f" if mode == "PER_FRAME" else "/s",
    )
    op.prop_name = prop_name
    op.object_name = obj_name
    op.data_path = data_path


def convert_object_rate_defaults(obj: bpy.types.Object) -> None:
    try:
        props = obj.nexus_modifier
    except AttributeError:
        return

    for prop_name in _RATE_PROPERTY_REGISTRY:
        if hasattr(props, prop_name):
            set_rate_mode(props, prop_name, "PER_FRAME")
