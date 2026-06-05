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

"""Icon System with Auto-Discovery - this might want a rethink, but it works.
    It will require icon duplication for regularly used icons which is a big caveat
Naming Convention: nx_{modifier}_{category}_{item}
Examples:
    - nx_wind.png (modifier icon)
    - nx_cover_objmode_sequence.png (cover modifier, object mode, sequence option)
    - nx_fluids_solver_pbd.png (fluids modifier, solver category, pbd option)
"""

import os

import bpy
import bpy.utils.previews

_preview_collections = {}
_icon_paths = {}


def get_icons_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "images")


def _discover_icons(base_dir: str) -> dict:
    icons = {}

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not d.startswith("_")]

        for filename in files:
            if filename.lower().endswith(".png"):
                key = filename[:-4]
                full_path = os.path.join(root, filename)
                icons[key] = full_path

                normalized = key.lower().replace("-", "_")
                if normalized != key:
                    icons[normalized] = full_path

    return icons


def get_icon(name: str) -> int:
    pcoll = _preview_collections.get("nexus_icons")
    if not pcoll:
        return 0

    if name in pcoll:
        return pcoll[name].icon_id

    normalized = name.lower().replace("-", "_")
    if normalized in pcoll:
        return pcoll[normalized].icon_id

    return 0


def get_icon_path(name: str) -> str:
    """Return the filesystem path for a discovered icon, or empty string."""
    if name in _icon_paths:
        return _icon_paths[name]
    normalized = name.lower().replace("-", "_")
    if normalized in _icon_paths:
        return _icon_paths[normalized]
    return ""


def icon_exists(name: str) -> bool:
    pcoll = _preview_collections.get("nexus_icons")
    if not pcoll:
        return False

    if name in pcoll:
        return True

    normalized = name.lower().replace("-", "_")
    return normalized in pcoll


def register():
    global _icon_paths
    pcoll = bpy.utils.previews.new()
    icons_dir = get_icons_dir()

    discovered = _discover_icons(icons_dir)
    _icon_paths = dict(discovered)
    loaded_paths = set()

    for icon_key, icon_path in discovered.items():
        if icon_path in loaded_paths:
            continue

        try:
            if icon_key not in pcoll:
                pcoll.load(icon_key, icon_path, "IMAGE")
                loaded_paths.add(icon_path)
        except Exception:
            pass

    _preview_collections["nexus_icons"] = pcoll


def unregister():
    from ..utils.tinted_icon import unregister_all as unregister_tinted_caches

    unregister_tinted_caches()

    for pcoll in _preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    _preview_collections.clear()
    _icon_paths.clear()
