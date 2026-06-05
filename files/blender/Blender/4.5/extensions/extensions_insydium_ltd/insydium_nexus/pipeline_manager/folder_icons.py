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

"""Per folder tinted icon previews using bpy.utils.previews.
Icons are cached by folder_id and only regenerated when the color changes.
"""

from ..utils.tinted_icon import TintedIconCache

_cache = TintedIconCache("nx_folder")


def get_folder_icon_id(folder_id: str, color: tuple) -> int:
    """Return an icon_id for a folder tinted to the given RGB color."""
    return _cache.get_icon_id(folder_id, color)


def remove_folder_icon(folder_id: str):
    """Remove a folder's cached icon when the folder is deleted."""
    _cache.remove_icon(folder_id)
