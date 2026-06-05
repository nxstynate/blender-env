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

"""Generator rendering backends for NX_GENERATOR.

Registration mirrors viewport/volume/__init__.py.
"""

from __future__ import annotations

from ..bridges import get_metal_bridge, get_opengl_bridge, get_vulkan_bridge
from .cache import (
    clear as clear_mesh_cache,
)
from .cache import (
    get_or_extract_mesh,
)
from .cache import (
    invalidate_from_depsgraph as invalidate_mesh_cache,
)

__all__ = [
    "clear_mesh_cache",
    "get_or_extract_mesh",
    "invalidate_mesh_cache",
    "register_generator_backends",
    "shutdown_all",
]

_opengl_bridge = get_opengl_bridge()
_vulkan_bridge = get_vulkan_bridge()
_metal_bridge = get_metal_bridge()

_opengl_renderer = None
_vulkan_renderer = None
_metal_renderer = None


def _get_opengl_renderer():
    global _opengl_renderer
    if _opengl_renderer is None:
        from .opengl import GeneratorOpenGLRenderer

        _opengl_renderer = GeneratorOpenGLRenderer(_opengl_bridge)
    return _opengl_renderer


def _get_vulkan_renderer():
    global _vulkan_renderer
    if _vulkan_renderer is None:
        from .native import GeneratorNativeRenderer

        _vulkan_renderer = GeneratorNativeRenderer(_vulkan_bridge)
    return _vulkan_renderer


def _get_metal_renderer():
    global _metal_renderer
    if _metal_renderer is None:
        from .native import GeneratorNativeRenderer

        _metal_renderer = GeneratorNativeRenderer(_metal_bridge)
    return _metal_renderer


def _opengl_draw(context, pipeline, scene, params) -> bool:
    return _get_opengl_renderer().draw(context, pipeline, scene, params)


def _vulkan_draw(context, pipeline, scene, params) -> bool:
    return _get_vulkan_renderer().draw(context, pipeline, scene, params)


def _metal_draw(context, pipeline, scene, params) -> bool:
    return _get_metal_renderer().draw(context, pipeline, scene, params)


def _vulkan_available() -> bool:
    """Available only when Blender's GPU backend is Vulkan AND the native lib
    exposes the generator C API (``nexus_stage_generator_frame``)."""
    if not _vulkan_bridge.is_available():
        return False
    if not _vulkan_bridge.load():
        return False
    return _vulkan_bridge.generator_hook_ready()


def _metal_available() -> bool:
    """Available only when Blender's GPU backend is Metal AND the native lib
    exposes the generator C API (``nexus_stage_generator_frame``)."""
    if not _metal_bridge.is_available():
        return False
    if not _metal_bridge.load():
        return False
    return _metal_bridge.generator_hook_ready()


def register_generator_backends() -> None:
    """Register the Vulkan, Metal, and OpenGL generator backends."""
    from ..registry import ViewportBackend, register_generator_backend

    register_generator_backend(
        ViewportBackend(
            id="VULKAN",
            label="Vulkan",
            description="Native Vulkan mesh-instancing via classifier compute + indirect draws.",
            priority=25,
            is_available=_vulkan_available,
            draw=_vulkan_draw,
        )
    )
    register_generator_backend(
        ViewportBackend(
            id="METAL",
            label="Metal",
            description="Native Metal mesh-instancing via classifier compute + indirect draws.",
            priority=20,
            is_available=_metal_available,
            draw=_metal_draw,
        )
    )
    register_generator_backend(
        ViewportBackend(
            id="OPENGL",
            label="OpenGL",
            description="Zero-copy OpenGL mesh instancing on particle positions.",
            priority=10,
            is_available=_opengl_bridge.is_available,
            draw=_opengl_draw,
        )
    )


def shutdown_all() -> None:
    """Shut down generator renderers (bridges are shared — not shut down here)."""
    global _opengl_renderer, _vulkan_renderer, _metal_renderer
    if _opengl_renderer is not None:
        _opengl_renderer.shutdown()
        _opengl_renderer = None
    if _vulkan_renderer is not None:
        _vulkan_renderer.shutdown()
        _vulkan_renderer = None
    if _metal_renderer is not None:
        _metal_renderer.shutdown()
        _metal_renderer = None
    clear_mesh_cache()
