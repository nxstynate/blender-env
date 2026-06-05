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

"""Object-classification helpers shared across NeXus panel modules.

Keep this module thin: pure object-introspection utilities only. Anything that
draws into a layout belongs in the panel module that owns the section.
"""

from ..modifiers import MODIFIER_REGISTRY
from ..modifiers.base import NexusModifier


def is_nexus_modifier(obj):
    if obj is None:
        return False
    return "nexus_modifier_type" in obj


def is_nexus_reactor(obj):
    if obj is None:
        return False
    return obj.get("nexus_object_type") == "NX_FLOCK_REACTOR"


def get_reactor_parent_and_item(obj):
    if not is_nexus_reactor(obj):
        return None, None

    flock_obj = obj.parent
    if flock_obj is None:
        return None, None

    if flock_obj.get("nexus_modifier_type") != "NX_FLOCK":
        return None, None

    props = flock_obj.nexus_modifier
    for item in props.flock_reactions:
        if item.reactor_object == obj:
            return flock_obj, item

    return flock_obj, None


def is_nexus_infectio_seed(obj):
    if obj is None:
        return False
    return obj.get("nexus_object_type") == "NX_INFECTIO_SEED"


def get_infectio_seed_parent_and_item(obj):
    if not is_nexus_infectio_seed(obj):
        return None, None

    infectio_obj = obj.parent
    if infectio_obj is None:
        return None, None

    if infectio_obj.get("nexus_modifier_type") != "NX_INFECTIO":
        return None, None

    props = infectio_obj.nexus_modifier
    for item in props.infectio_seeds:
        if item.seed_object == obj:
            return infectio_obj, item

    return infectio_obj, None


def get_modifier_class(obj):
    if not is_nexus_modifier(obj):
        return None
    mod_type = obj.get("nexus_modifier_type")
    return MODIFIER_REGISTRY.get(mod_type)


def get_available_sections(mod_class, props):
    sections = [("OBJECT_PROPERTIES", "Object Properties")]

    sections.extend(mod_class.get_tabs(props))

    if issubclass(mod_class, NexusModifier):
        sections.append(("GROUPS_AFFECTED", "Groups Affected"))
        sections.append(("MAPPING", "Mapping"))
        sections.append(("FALLOFF", "Falloff"))

    return sections
