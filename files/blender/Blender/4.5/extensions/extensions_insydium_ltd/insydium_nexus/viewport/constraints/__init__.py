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

"""Constraint overlay registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import ConstraintDrawParams

from .basic import ConstraintsBasicRenderer
from .metal import make_metal_stager
from .opengl import make_opengl_stager
from .vulkan import make_vulkan_stager


def _wrap(stager):
    """Adapt a stager's ``stage(context, pipeline, params) -> bool`` signature
    to the registry's ``draw(context, pipeline, scene, params) -> bool`` shape."""

    def draw(context, pipeline, scene, params):  # noqa: ARG001
        return bool(stager.stage(context, pipeline, params))

    return draw


_vulkan_stager = make_vulkan_stager()
_metal_stager = make_metal_stager()
_opengl_stager = make_opengl_stager()
_basic_stager = ConstraintsBasicRenderer()


def shutdown_all() -> None:
    """Tear down every constraint stager."""
    for stager in (_vulkan_stager, _metal_stager, _opengl_stager, _basic_stager):
        if hasattr(stager, "shutdown"):
            try:
                stager.shutdown()
            except Exception:
                pass


def register_constraint_backends() -> None:
    """Register Vulkan, Metal, OpenGL, and Basic constraint overlay backends."""
    from ..registry import ViewportBackend, register_constraint_backend

    register_constraint_backend(
        ViewportBackend(
            id="VULKAN",
            label="Vulkan",
            description="Vulkan constraint overlay (LINE_LIST, own descriptor set).",
            priority=25,
            is_available=_vulkan_stager._bridge.is_available,
            draw=_wrap(_vulkan_stager),
        )
    )
    register_constraint_backend(
        ViewportBackend(
            id="METAL",
            label="Metal",
            description="Metal constraint overlay (LINE_LIST, hand-authored MSL).",
            priority=20,
            is_available=_metal_stager._bridge.is_available,
            draw=_wrap(_metal_stager),
        )
    )
    register_constraint_backend(
        ViewportBackend(
            id="OPENGL",
            label="OpenGL",
            description="OpenGL constraint overlay (forwards to native bridge).",
            priority=10,
            is_available=_opengl_stager._bridge.is_available,
            draw=_wrap(_opengl_stager),
        )
    )
    register_constraint_backend(
        ViewportBackend(
            id="BASIC",
            label="Basic",
            description="No-op stager (CPU fallback awaiting host-readable constraints).",
            priority=0,
            is_available=lambda: True,
            draw=_wrap(_basic_stager),
        )
    )
