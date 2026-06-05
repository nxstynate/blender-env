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

"""Reusable tinted icon preview cache.

Create an instance at module scope and call ``get_icon_id(key, color)``
at draw time. The preview collection is lazily created on first use and
cleaned up automatically via ``unregister_all()`` at addon unregister.
"""

import bpy
import bpy.utils.previews

_ICON_SIZE = 32
_NOT_LOADED = object()

_instances: list["TintedIconCache"] = []


def unregister_all():
    """Release preview collections for every TintedIconCache instance."""
    for cache in _instances:
        cache._release()


class TintedIconCache:
    """Generates and caches colour-tinted copies of a single source icon."""

    def __init__(self, source_icon_name: str):
        self._source_icon_name = source_icon_name
        self.pcoll = None
        self._source_pixels = _NOT_LOADED
        self._cache_keys: dict[str, tuple[int, int, int]] = {}
        _instances.append(self)

    # -- lifecycle -----------------------------------------------------------

    def _ensure_pcoll(self):
        if self.pcoll is None:
            self.pcoll = bpy.utils.previews.new()

    def _release(self):
        if self.pcoll is not None:
            bpy.utils.previews.remove(self.pcoll)
            self.pcoll = None
        self._source_pixels = _NOT_LOADED
        self._cache_keys = {}

    # -- internal ------------------------------------------------------------

    def _ensure_source_pixels(self):
        if self._source_pixels is not _NOT_LOADED:
            return

        self._source_pixels = None

        from ..icons import get_icon_path

        png_path = get_icon_path(self._source_icon_name)
        if not png_path:
            return

        try:
            tmp_img = bpy.data.images.load(png_path, check_existing=False)
        except (RuntimeError, AttributeError):
            return

        try:
            if tmp_img.size[0] != _ICON_SIZE or tmp_img.size[1] != _ICON_SIZE:
                tmp_img.scale(_ICON_SIZE, _ICON_SIZE)
            self._source_pixels = list(tmp_img.pixels[:])
        finally:
            bpy.data.images.remove(tmp_img)

    # -- public API ----------------------------------------------------------

    def get_icon_id(self, cache_key: str, color: tuple) -> int:
        """Return a preview icon_id tinted to *color* (RGB floats 0-1).

        Results are cached per *cache_key*; the preview is only regenerated
        when the quantised colour changes.
        """
        self._ensure_pcoll()
        self._ensure_source_pixels()

        if self.pcoll is None or self._source_pixels is None:
            return 0

        r8 = int(round(color[0] * 255))
        g8 = int(round(color[1] * 255))
        b8 = int(round(color[2] * 255))
        quant_key = (r8, g8, b8)

        cached = self._cache_keys.get(cache_key)
        if cached == quant_key and cache_key in self.pcoll:
            return self.pcoll[cache_key].icon_id

        if cache_key in self.pcoll:
            del self.pcoll[cache_key]

        preview = self.pcoll.new(cache_key)
        preview.image_size = (_ICON_SIZE, _ICON_SIZE)
        preview.icon_size = (_ICON_SIZE, _ICON_SIZE)

        pixel_count = _ICON_SIZE * _ICON_SIZE * 4
        tinted = [0.0] * pixel_count
        rf = r8 / 255.0
        gf = g8 / 255.0
        bf = b8 / 255.0

        for i in range(0, pixel_count, 4):
            a = self._source_pixels[i + 3]
            if a < 0.2:
                continue
            lum = self._source_pixels[i]
            tinted[i] = rf * lum
            tinted[i + 1] = gf * lum
            tinted[i + 2] = bf * lum
            tinted[i + 3] = a

        preview.image_pixels_float[:] = tinted
        preview.icon_pixels_float[:] = tinted
        self._cache_keys[cache_key] = quant_key

        return preview.icon_id

    def remove_icon(self, cache_key: str):
        """Remove a cached tinted icon entry."""
        self._cache_keys.pop(cache_key, None)
        if self.pcoll is not None and cache_key in self.pcoll:
            del self.pcoll[cache_key]
