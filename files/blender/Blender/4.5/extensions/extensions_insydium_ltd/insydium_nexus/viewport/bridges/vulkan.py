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

"""Unified Vulkan bridge for Windows + Linux.

Subclass of NativeBridge — only provides platform-specific DLL search
paths and the Linux log-callback hook.
"""

from __future__ import annotations

import ctypes
import os
import sys

from .native import NativeBridge


class VulkanBridge(NativeBridge):
    """Python-side bridge for the Vulkan funchook backend (Win32 + Linux)."""

    _log_callback_ref = None  # prevent GC of C callback

    def _platform_ok(self) -> bool:
        return sys.platform in ("win32", "linux")

    def _gpu_backend_ok(self) -> bool:
        backend = self._get_blender_gpu_backend()
        return "VULKAN" in backend if backend else False

    def load(self) -> bool:
        ok = super().load()
        if not ok and self._loaded and not self._available:
            self._loaded = False
        return ok

    def _get_dll_candidates(self) -> list[str]:
        addon_dir = self._get_addon_dir()
        libs_dir = os.path.join(addon_dir, "libs")

        if sys.platform == "win32":
            names = ("nexus_viewport.dll",)
        else:
            names = ("libnexus_viewport.so",)

        return [os.path.join(libs_dir, name) for name in names]

    def shutdown(self) -> None:
        super().shutdown()
        VulkanBridge._log_callback_ref = None

    # Windows + Linux: forward native log output to the Blender console
    def _on_loaded(self, lib: ctypes.CDLL) -> None:
        if not hasattr(lib, "nexus_set_log_callback"):
            return
        try:
            LOG_CB = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

            def _fwd(msg: bytes) -> None:
                try:
                    if msg:
                        print(msg.decode("utf-8", errors="replace"), end="", flush=True)
                except Exception:
                    pass

            VulkanBridge._log_callback_ref = LOG_CB(_fwd)
            lib.nexus_set_log_callback.restype = None
            lib.nexus_set_log_callback.argtypes = [LOG_CB]
            lib.nexus_set_log_callback(VulkanBridge._log_callback_ref)
        except Exception:
            pass
