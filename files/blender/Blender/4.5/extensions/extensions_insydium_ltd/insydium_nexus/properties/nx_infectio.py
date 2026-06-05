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

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nexus_time import nexus_time_property
from ..libs.theron_sync import SyncType, Transform
from ..ui import make_allowed_types_poll, register_nodetree
from ..utils import XP_COLOR_MODS_BLUE

# ---------------------------------------------------------------------------
# Seed object management
# ---------------------------------------------------------------------------


def _create_seed_object(context, infectio_obj):
    base_name = f"{infectio_obj.name}.Seed"

    seed = bpy.data.objects.new(base_name, None)
    seed.empty_display_size = 0
    seed.empty_display_type = "PLAIN_AXES"

    for collection in infectio_obj.users_collection:
        collection.objects.link(seed)
        break
    else:
        context.collection.objects.link(seed)

    seed.parent = infectio_obj
    seed.matrix_parent_inverse = infectio_obj.matrix_world.inverted()

    seed.location = (0, 0, 0)

    seed["nexus_object_type"] = "NX_INFECTIO_SEED"

    return seed


def _remove_seed_object(context, seed_obj):
    if seed_obj is None:
        return

    for collection in seed_obj.users_collection:
        collection.objects.unlink(seed_obj)

    bpy.data.objects.remove(seed_obj, do_unlink=True)


def _on_seed_add(context, infectio_obj, item):
    seed = _create_seed_object(context, infectio_obj)
    item.seed_object = seed
    item.name = seed.name


def _on_seed_remove(context, infectio_obj, item):
    if item.seed_object:
        _remove_seed_object(context, item.seed_object)
        item.seed_object = None


# ---------------------------------------------------------------------------
# Seed enum items (single-type list)
# ---------------------------------------------------------------------------

SEED_DEFS = {
    "SEED": {
        "name": "Seed Object",
        "description": "An infection seed point with radius and threshold",
        "blender_icon": "MESH_UVSPHERE",
    },
}

_SEED_ITEMS = []


def build_infectio_seed_enum_items():
    global _SEED_ITEMS
    from ..icons import get_icon

    _SEED_ITEMS = []

    for idx, (type_id, seed_def) in enumerate(SEED_DEFS.items()):
        icon_name = seed_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _SEED_ITEMS.append(
                (
                    type_id,
                    seed_def["name"],
                    seed_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = seed_def.get("blender_icon", "NONE")
            _SEED_ITEMS.append(
                (
                    type_id,
                    seed_def["name"],
                    seed_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "infectio_seeds",
        _SEED_ITEMS,
        "infectio_seeds",
        "infectio_seeds_index",
        on_add=_on_seed_add,
        on_remove=_on_seed_remove,
        child_pointer_prop="seed_object",
    )


def _get_seed_items(self, context):
    return _SEED_ITEMS


# ---------------------------------------------------------------------------
# Seed PropertyGroup
# ---------------------------------------------------------------------------


class NexusInfectioSeedItem(bpy.types.PropertyGroup):
    name: StringProperty(
        name="Name",
        description="Seed name",
        default="",
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this seed",
        default=True,
    )

    item_type: EnumProperty(
        name="Seed Type",
        description="Type of seed",
        items=_get_seed_items,
        default=0,
    )

    seed_object: PointerProperty(
        name="Seed Object",
        type=bpy.types.Object,
        description="The Empty object representing this seed's position",
    )

    seed_radius: FloatProperty(
        name="Radius",
        description="Infection seed radius",
        default=0.1,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
    )

    seed_threshold: FloatProperty(
        name="Threshold",
        description="Incubation threshold to trigger infection",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )

    seed_color: FloatVectorProperty(
        name="Color",
        description="Viewport display color for this seed",
        default=XP_COLOR_MODS_BLUE,
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
    )


def draw_seed_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.separator(type="LINE")
    col.prop(item, "seed_radius")
    col.prop(item, "seed_threshold")
    col.prop(item, "seed_color")


# ---------------------------------------------------------------------------
# Main properties -- order follows onxinfectio.h res layout
# ---------------------------------------------------------------------------


SPEC = ModifierPropertySpec(
    modifier_type="NX_INFECTIO",
    item_classes=(NexusInfectioSeedItem,),
    enum_builders=(build_infectio_seed_enum_items,),
    enum_defaults={
        "ID_NX_INFECTIO_COLOR_MODE": "ID_NX_INFECTIO_COLOR_MODE_FIXED",
        "ID_NX_INFECTIO_INCUBATION_MODE": "ID_NX_INFECTIO_INCUBATION_MODE_COLOR",
        "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE": (
            "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_BOTH"
        ),
    },
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="infectio_seeds",
            prop=CollectionProperty(
                name="Seeds",
                type=NexusInfectioSeedItem,
            ),
        ),
        PropertyDescriptor(
            name="infectio_seeds_index",
            prop=IntProperty(
                name="Active Seed Index",
                default=0,
                min=0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_COLOR_MODE",
            prop=EnumProperty(
                name="Color Mode",
                description="How infected particles are colored",
                items=[
                    (
                        "ID_NX_INFECTIO_COLOR_MODE_FIXED",
                        "Fixed Value",
                        "Use fixed colors for incubating and infected states",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_MODE_GRADIENT",
                        "Gradient",
                        "Use a gradient based on incubation level",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_MODE_USE_GROUPS",
                        "Use Groups",
                        "Use particle group colors",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_MODE_NO_CHANGE",
                        "No Color Change",
                        "Do not change particle color",
                    ),
                ],
                default="ID_NX_INFECTIO_COLOR_MODE_FIXED",
            ),
        ),
        PropertyDescriptor(
            name="infectio_color_incubating",
            prop=FloatVectorProperty(
                name="Incubating",
                description="Color for incubating particles",
                default=(0.0, 0.0, 250.0 / 255.0),
                size=3,
                min=0.0,
                max=1.0,
                subtype="COLOR",
            ),
        ),
        PropertyDescriptor(
            name="infectio_color_infected",
            prop=FloatVectorProperty(
                name="Infected",
                description="Color for infected particles",
                default=(238.0 / 255.0, 161.0 / 255.0, 103.0 / 255.0),
                size=3,
                min=0.0,
                max=1.0,
                subtype="COLOR",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_COLOR_GROUPS_INCUBATING",
            prop=PointerProperty(
                name="Incubating Group",
                description="Group to use for incubating particles",
                type=bpy.types.Object,
                poll=make_allowed_types_poll(["NX_GROUP"]),
            ),
            sync_type=SyncType.LINK,
            when=lambda props, _obj, _scene, _depsgraph: (
                props.ID_NX_INFECTIO_COLOR_MODE == "ID_NX_INFECTIO_COLOR_MODE_USE_GROUPS"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_COLOR_GROUPS_INFECTED",
            prop=PointerProperty(
                name="Infected Group",
                description="Group to use for infected particles",
                type=bpy.types.Object,
                poll=make_allowed_types_poll(["NX_GROUP"]),
            ),
            sync_type=SyncType.LINK,
            when=lambda props, _obj, _scene, _depsgraph: (
                props.ID_NX_INFECTIO_COLOR_MODE == "ID_NX_INFECTIO_COLOR_MODE_USE_GROUPS"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE",
            prop=EnumProperty(
                name="Group Color Change",
                description="When to apply group color changes",
                items=[
                    (
                        "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_BOTH",
                        "Both Stages",
                        "Change color on both transitions",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_UNINF_TO_INCUB",
                        "Uninfected to Incubated Stage",
                        "Change on infection",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_INCUB_TO_INF",
                        "Incubated to Infected Stage",
                        "Change on full infection",
                    ),
                    (
                        "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_NO_CHANGE",
                        "No Color Changes",
                        "Do not change color",
                    ),
                ],
                default="ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE_BOTH",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_SEARCH_RAD",
            prop=FloatProperty(
                name="Search Radius",
                description="Radius to search for particles to infect",
                default=0.1,
                min=0.0,
                soft_max=0.2,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_MAX_INFECTED",
            prop=IntProperty(
                name="Max Infected",
                description="Maximum number of particles that can be infected per step",
                default=3,
                min=0,
                max=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INFECTED_LIFESPAN",
            prop=nexus_time_property(
                "ID_NX_INFECTIO_INFECTED_LIFESPAN",
                name="Infected Lifespan",
                description="How long a particle remains infected (0 = infinite)",
                default=300.0,
                min=0.0,
                soft_max=1000.0,
            ),
            sync_type=SyncType.TIME,
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_SEARCH_ONCE",
            prop=BoolProperty(
                name="Search for Nearest Once",
                description="Only search for new infections once per particle",
                default=True,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_CONSTRAIN_SEARCH",
            prop=BoolProperty(
                name="Constrain Search",
                description="Constrain the infection search area",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="infectio_limit",
            prop=FloatVectorProperty(
                name="Limit",
                description="Constrain search area per axis",
                default=(1.0, 1.0, 1.0),
                size=3,
                min=0.0,
                max=1.0,
                subtype="XYZ",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_MODE",
            prop=EnumProperty(
                name="Incubation Mode",
                description="Method used to determine incubation progress",
                items=[
                    (
                        "ID_NX_INFECTIO_INCUBATION_MODE_RATE",
                        "Set From Incubation Rate",
                        "Incubation based on a rate over time",
                    ),
                    (
                        "ID_NX_INFECTIO_INCUBATION_MODE_COLOR",
                        "Use Particle Color",
                        "Incubation based on particle color channel value",
                    ),
                    (
                        "ID_NX_INFECTIO_INCUBATION_MODE_RADIUS",
                        "Particle Radius",
                        "Incubation based on particle radius",
                    ),
                    (
                        "ID_NX_INFECTIO_INCUBATION_MODE_MASS",
                        "Particle Mass",
                        "Incubation based on particle mass",
                    ),
                ],
                default="ID_NX_INFECTIO_INCUBATION_MODE_COLOR",
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_MIN",
            prop=FloatProperty(
                name="Min Value",
                description="Minimum incubation value",
                default=0.0,
                min=0.0,
                soft_max=10.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_MAX",
            prop=FloatProperty(
                name="Max Value",
                description="Maximum incubation value",
                default=10.0,
                min=0.0,
                soft_max=10.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_RATE",
            prop=FloatProperty(
                name="Incubation Rate",
                description="Rate of incubation progression",
                default=50.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_VAR",
            prop=FloatProperty(
                name="Variation",
                description="Random variation in incubation",
                default=25.0,
                min=0.0,
                soft_max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_MULTI",
            prop=FloatProperty(
                name="Incubation Multiplier",
                description="Multiplier applied to incubation per additional infecting neighbor",
                default=1.0,
                min=0.0,
                soft_max=5.0,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_INCUBATION_INVERT",
            prop=BoolProperty(
                name="Invert",
                description="Invert incubation logic",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_IMMUNITY_USE",
            prop=BoolProperty(
                name="Use Immunity",
                description="Enable particle immunity to infection",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_INFECTIO_IMMUNITY_LEVEL",
            prop=FloatProperty(
                name="Immunity Level",
                description="Base immunity level for particles",
                default=0.0,
                min=0.0,
                soft_max=5.0,
            ),
        ),
    ),
)


# Seed position lives on `seed_object.matrix_world`, which preset apply can't
# restore. Drop every row; registration stays so apply/INSYDIUM Default still
# fire `on_remove` to clean up stale seed helpers.
def _infectio_seed_drop(_item_or_data) -> bool:
    return False


register_collection_preset(
    "NX_INFECTIO",
    CollectionPresetSpec(
        collection_attr="infectio_seeds",
        menu_id="infectio_seeds",
        item_capture_condition=_infectio_seed_drop,
        item_apply_condition=_infectio_seed_drop,
    ),
)
