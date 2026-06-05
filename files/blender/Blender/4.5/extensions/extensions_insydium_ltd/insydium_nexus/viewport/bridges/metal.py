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

"""macOS Metal bridge.

Subclass of NativeBridge — only provides platform-specific dylib search
paths.  The underlying C++ uses Objective-C++ method swizzling + MSL
shaders, but the Python ctypes API is identical to Vulkan.
"""

from __future__ import annotations

import os
import sys

from .native import NativeBridge


class MetalBridge(NativeBridge):
    """Python-side bridge for the Metal swizzle backend (macOS)."""

    def _platform_ok(self) -> bool:
        return sys.platform == "darwin"

    def _gpu_backend_ok(self) -> bool:
        backend = self._get_blender_gpu_backend()
        return "METAL" in backend if backend else False

    def _get_dll_candidates(self) -> list[str]:
        addon_dir = self._get_addon_dir()
        libs_dir = os.path.join(addon_dir, "libs")
        names = ("libnexus_viewport.dylib",)
        return [os.path.join(libs_dir, name) for name in names]
