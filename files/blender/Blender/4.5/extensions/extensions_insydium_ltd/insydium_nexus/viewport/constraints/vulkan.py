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

"""Vulkan constraint overlay stager.

Wraps :class:`ConstraintsNativeStager` against the shared Vulkan bridge.
The actual draw is recorded by ``vk_constraints_record_draw`` on the C++
side at the tail of ``vk_indirect_record_all_modes``; this Python module
only stages enable + palette state each frame.
"""

from __future__ import annotations

from .bridge import ConstraintsNativeStager


def make_vulkan_stager():
    from ..bridges import get_vulkan_bridge

    return ConstraintsNativeStager(get_vulkan_bridge())
