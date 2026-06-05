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

"""Abstract base class for all Nexus viewport renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NexusRenderer(ABC):
    """Base class for all renderers in the Nexus viewport system.

    Subclasses include ParticleRenderer (and future VolumeRenderer, etc.).
    Each concrete renderer is associated with one bridge backend and one
    display mode.
    """

    @abstractmethod
    def draw(self, context, pipeline, scene, params) -> bool:
        """Render into the current viewport.

        Returns True if drawing succeeded, False to signal the registry
        should try the next fallback backend.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release any GPU resources owned by this renderer."""
