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

"""Trail rendering backends for NX_TRAIL."""

from __future__ import annotations

from ..bridges import get_metal_bridge, get_opengl_bridge, get_vulkan_bridge
from .bridge import TrailsNativeStager
from .metal import TrailsMetalStager
from .opengl import TrailsOpenGLRenderer
from .vulkan import TrailsVulkanStager


class _TrailsBasicStager:
    def stage(self, context, pipeline, params) -> bool:  # noqa: ARG002
        return False

    def shutdown(self) -> None:
        return None


_vulkan_bridge = get_vulkan_bridge()
_metal_bridge = get_metal_bridge()
_opengl_bridge = get_opengl_bridge()

_vulkan_stager = TrailsVulkanStager(_vulkan_bridge)
_metal_stager = TrailsMetalStager(_metal_bridge)
_opengl_stager = TrailsOpenGLRenderer(_opengl_bridge)
_basic_stager = _TrailsBasicStager()
_STAGERS = (
    _vulkan_stager,
    _metal_stager,
    _opengl_stager,
    _basic_stager,
)


def _wrap(stager):
    def draw(context, pipeline, scene, params):  # noqa: ARG001
        return bool(stager.stage(context, pipeline, params))

    return draw


def collect_trail_draw_data(context, depsgraph=None):
    from .collect import collect_trail_draw_data as _collect

    return _collect(context, depsgraph)


def register_trail_backends() -> None:
    from ..registry import ViewportBackend, register_trail_backend

    register_trail_backend(
        ViewportBackend(
            id="VULKAN",
            label="Vulkan",
            description="Native Vulkan trail renderer (GPU buffer pass-through).",
            priority=25,
            is_available=_vulkan_bridge.is_available,
            draw=_wrap(_vulkan_stager),
        )
    )
    register_trail_backend(
        ViewportBackend(
            id="METAL",
            label="Metal",
            description="Native Metal trail renderer (GPU buffer pass-through).",
            priority=20,
            is_available=_metal_bridge.is_available,
            draw=_wrap(_metal_stager),
        )
    )
    register_trail_backend(
        ViewportBackend(
            id="OPENGL",
            label="OpenGL",
            description="Zero-copy Vulkan→OpenGL trail draw via external memory.",
            priority=10,
            is_available=_opengl_bridge.is_available,
            draw=_wrap(_opengl_stager),
        )
    )
    register_trail_backend(
        ViewportBackend(
            id="BASIC",
            label="Basic",
            description="NX_TRAIL Lines is not implemented for Basic.",
            priority=0,
            is_available=lambda: True,
            draw=_wrap(_basic_stager),
        )
    )


def reset_trail_caches_for_pipeline(pipeline: int) -> None:
    """Release any retained trail buffers for the given pipeline across all backends."""
    for stager in _STAGERS:
        reset = getattr(stager, "reset", None)
        if reset is not None:
            reset(pipeline)


def shutdown_all() -> None:
    for stager in _STAGERS:
        stager.shutdown()
