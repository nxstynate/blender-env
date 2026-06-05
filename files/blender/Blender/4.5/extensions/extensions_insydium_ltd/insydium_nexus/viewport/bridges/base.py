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

"""Abstract base for all bridge backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BridgeBase(ABC):
    """A bridge encapsulates one GPU interop mechanism.

    Concrete subclasses: NativeBridge (Vulkan/Metal DLL), OpenGLBridge,
    BlenderGPUBridge (CPU fallback).
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Lightweight check shown in the Blender UI dropdown."""

    @abstractmethod
    def load(self) -> bool:
        """Perform heavy initialisation (DLL load, extension resolve, …).

        Returns True when the bridge is ready for draw calls.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release all resources. Safe to call multiple times."""
