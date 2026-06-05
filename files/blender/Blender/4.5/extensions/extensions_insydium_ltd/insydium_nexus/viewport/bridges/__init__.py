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

"""Platform / API bridge backends for Nexus viewport rendering."""

from __future__ import annotations

from .metal import MetalBridge
from .opengl import OpenGLBridge
from .vulkan import VulkanBridge

# Make bridges into shared singletons: one nexus_init() per backend per process.
# All registered renderers (e.g., particle and volume renderers) import these instances to
# avoid multiple-init.
_vulkan_bridge: VulkanBridge | None = None
_metal_bridge: MetalBridge | None = None
_opengl_bridge: OpenGLBridge | None = None


def get_vulkan_bridge() -> VulkanBridge:
    global _vulkan_bridge
    if _vulkan_bridge is None:
        _vulkan_bridge = VulkanBridge()
    return _vulkan_bridge


def get_metal_bridge() -> MetalBridge:
    global _metal_bridge
    if _metal_bridge is None:
        _metal_bridge = MetalBridge()
    return _metal_bridge


def get_opengl_bridge() -> OpenGLBridge:
    global _opengl_bridge
    if _opengl_bridge is None:
        _opengl_bridge = OpenGLBridge()
    return _opengl_bridge
