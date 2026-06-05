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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CurveSpec:
    slot_name: str
    label: str
    default_points: list[tuple[float, float]]
    theron_ids: tuple[str | int, ...] = ()
    slot_suffix_attr: str | None = None
    sync_condition: Callable[[Any, Any], bool] | None = None


@dataclass(frozen=True)
class GradientSpec:
    slot_name: str
    label: str
    default_stops: list[tuple[float, tuple[float, float, float, float]]]
    theron_ids: tuple[str | int, ...] = ()
    slot_suffix_attr: str | None = None
    sync_condition: Callable[[Any, Any], bool] | None = None
    default_interpolation: str = "LINEAR"
    default_color_mode: str = "RGB"
    default_hue_interpolation: str = "NEAR"


CurveSpecs = (
    tuple[CurveSpec, ...]
    | list[CurveSpec]
    | Callable[[Any], tuple[CurveSpec, ...] | list[CurveSpec]]
    | None
)

GradientSpecs = (
    tuple[GradientSpec, ...]
    | list[GradientSpec]
    | Callable[[Any], tuple[GradientSpec, ...] | list[GradientSpec]]
    | None
)
