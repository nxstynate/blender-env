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

"""Blender GPU module bridge (CPU-read fallback).

This is the always-available fallback.  It does not own any GPU resources
itself — each basic-mode particle renderer creates Blender ``GPUShader``
and ``GPUBatch`` objects directly.
"""

from __future__ import annotations

from .base import BridgeBase


class BlenderGPUBridge(BridgeBase):
    """Thin wrapper so the basic backend fits the bridge hierarchy."""

    def is_available(self) -> bool:
        return True

    def load(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass
