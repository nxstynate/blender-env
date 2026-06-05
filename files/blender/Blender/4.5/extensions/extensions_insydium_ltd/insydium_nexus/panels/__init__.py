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

"""Panels package: registers NeXus Properties-editor panels.

Module layout:
    _helpers.py        — pure object-classification utilities
    mapping.py         — Mapping tab (UIList, menus, draw_mapping_section)
    modifier_main.py   — NEXUS_PT_modifier_main (the tabbed modifier panel)
    reactor.py         — NEXUS_PT_reactor_properties
    infectio_seed.py   — NEXUS_PT_infectio_seed_properties
"""

from . import infectio_seed, mapping, modifier_main, reactor

_MODULES = (mapping, modifier_main, reactor, infectio_seed)


def register():
    from bpy.utils import register_class

    for module in _MODULES:
        for cls in module.classes:
            try:
                register_class(cls)
            except ValueError:
                pass


def unregister():
    from bpy.utils import unregister_class

    for module in reversed(_MODULES):
        for cls in reversed(module.classes):
            try:
                unregister_class(cls)
            except RuntimeError:
                pass
