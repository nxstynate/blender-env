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

"""OpenGL zero-copy circle filled renderer (indirect binned quad path)."""

from __future__ import annotations

from ..circle.opengl import CircleOpenGLRenderer


class CircleFilledOpenGLRenderer(CircleOpenGLRenderer):
    """Same quad renderer as outline; driven by `is_circle = 2`."""

    def draw(self, context, pipeline, scene, params) -> bool:
        return self._draw_impl(context, pipeline, params, is_circle_mode=2)
