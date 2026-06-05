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

"""Volume rendering backends for nxExplosiaFX."""

from __future__ import annotations

_basic_renderer: VolumeBasicRenderer | None = None


def _get_basic_renderer() -> VolumeBasicRenderer:
    global _basic_renderer
    if _basic_renderer is None:
        from .basic import VolumeBasicRenderer

        _basic_renderer = VolumeBasicRenderer()
    return _basic_renderer


def _basic_draw(context, pipeline, scene, params) -> bool:
    return _get_basic_renderer().draw(context, pipeline, scene, params)


def register_volume_backends() -> None:
    """Register volume backends with the viewport registry."""
    from ..registry import ViewportBackend, register_volume_backend

    register_volume_backend(
        ViewportBackend(
            id="BASIC",
            label="Basic",
            description="GPU raymarcher volume renderer.",
            priority=5,
            is_available=lambda: True,
            draw=_basic_draw,
        )
    )


def shutdown_all() -> None:
    """Shut down volume renderers."""
    global _basic_renderer
    if _basic_renderer is not None:
        _basic_renderer.shutdown()
        _basic_renderer = None
