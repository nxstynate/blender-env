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

"""Metal trail backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .bridge import TrailNativeFrame, TrailsNativeStager

if TYPE_CHECKING:
    from ..bridges.native import NativeBridge
    from ..registry import TrailDrawParams


class TrailsMetalStager(TrailsNativeStager):
    def __init__(self, bridge: "NativeBridge") -> None:
        super().__init__(bridge, "METAL", supports_lines=True)

    def draw_staged(
        self,
        context,
        pipeline: int,
        params: "TrailDrawParams",
        frame: TrailNativeFrame,
    ) -> bool:
        flags = tuple(bool(flag) for flag in params.source_enabled_flags)
        return self.stage_pass(params, frame, flags)
