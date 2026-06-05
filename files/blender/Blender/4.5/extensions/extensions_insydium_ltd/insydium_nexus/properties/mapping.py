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

"""Data model for a single entry in a modifier's generic Mapping tab.

Each entry is a "layer" keyed by a particle-data source. Semantically it reads
    <modifier parameter>  ←  driven by  ←  <particle property>
e.g. "Gravity Strength  ←  Age". `dest_param` stores the modifier param being modulated;
`source_param` stores the particle property feeding it.

Source-range semantics vary by the picked particle property:
- Time-valued particle data (Age, Life, Doc Time, Mod Time) -> NeXus time properties with
  frames/seconds toggle.
- Everything else -> plain FloatProperty, default range 0..1.
A helper (`is_time_source`) picks the right storage path at UI + sync time.
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)

from ..libs.modifier_preset_spec import (
    CollectionPresetSpec,
    register_universal_collection_preset,
)
from ..libs.nexus_time import nexus_time_property
from ..libs.resource_spec import CurveSpec

_CLAMP_ITEMS = [
    ("CLAMP", "Clamp", "Clamp mapped values at the range boundaries"),
    ("CYCLE", "Cycle", "Wrap mapped values through the range"),
    ("CONTINUE", "Continue", "Pass values outside the range through unmodified"),
]

CLAMP_VALUES = {
    "CLAMP": 1,
    "CYCLE": 2,
    "CONTINUE": 4,
}


#   11 -> PARTICLE_PROPERTY.TIME
#   21 -> PARTICLE_PROPERTY.LIFE
#   25 -> PARTICLE_PROPERTY.MOD_TIME
#   66 -> DATAMAPPARAMETER.PARAMETER_DOC_TIME
TIME_SOURCES = frozenset({11, 21, 25, 66})


def is_time_source(source_id: int) -> bool:
    return int(source_id) in TIME_SOURCES


MAPPING_CURVE_SPEC = CurveSpec(
    slot_name="mapping_curve",
    label="Mapping",
    default_points=[(0.0, 0.0), (1.0, 1.0)],
    theron_ids=("ID_XP_MOD_DATAMAPPING_MAPPING",),
    slot_suffix_attr="curve_id",
)


class NexusMappingEntry(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)

    dest_param: IntProperty(
        name="Parameter",
        description="Modifier parameter being modulated by this layer",
        default=0,
    )
    source_param: IntProperty(
        name="Particle Data",
        description="Particle property driving this layer",
        default=0,
    )
    layer_id: IntProperty(
        name="Layer",
        description=(
            "Tree index of the modifier's layer this mapping targets (0 = first layer). "
            "Ignored for non-layered modifiers."
        ),
        default=0,
    )

    # Time-valued range (Age, Life, Doc Time, Mod Time). NeXus time system, frames/seconds toggle.
    range_min_time: nexus_time_property(
        "range_min_time",
        name="Range Min",
        description="Lower bound of the time-valued source range",
        default=0.0,
        collection_path="mappings",
    )
    range_max_time: nexus_time_property(
        "range_max_time",
        name="Range Max",
        description="Upper bound of the time-valued source range",
        default=2.0,
        collection_path="mappings",
    )

    range_min: FloatProperty(name="Range Min", default=0.0)
    range_max: FloatProperty(name="Range Max", default=1.0)

    weight: FloatProperty(
        name="Weight",
        description="Blend strength for the mapped value",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    clamp: EnumProperty(name="Clamp", items=_CLAMP_ITEMS, default=0)

    curve_id: StringProperty(
        name="Curve ID",
        description="Per-entry suffix for the mapping curve's Blender storage slot",
    )


classes = [NexusMappingEntry]


def _add_mapping_for_preset(obj, props_or_parent, item_data):
    from ..utils.curve import create_item_curves, generate_curve_id

    collection = getattr(props_or_parent, "mappings", None)
    if collection is None:
        return None
    item = collection.add()
    item.curve_id = generate_curve_id()
    create_item_curves(obj, item.curve_id, [MAPPING_CURVE_SPEC])
    return item


register_universal_collection_preset(
    CollectionPresetSpec(
        collection_attr="mappings",
        add_callback=_add_mapping_for_preset,
        curve_specs=[MAPPING_CURVE_SPEC],
        suffix_attr="curve_id",
    ),
)
