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
    IntProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import NodeTreeSyncSpec
from ..libs.theron_sync import TRANSFORM_FACTORS, Transform

CONSTRAINT_LAYER_DEFS = {
    "CON_BIRTH": {
        "name": "Connection Birth",
        "description": "Birth-based particle connections",
        "icon_name": "nx_constraints_birth",
        "blender_icon": "LINKED",
        "node_val": 8,
    },
    "CON_DISTANCE": {
        "name": "Connection Distance",
        "description": "Distance-based particle connections",
        "icon_name": "nx_constraints_distance",
        "blender_icon": "DRIVER_DISTANCE",
        "node_val": 9,
    },
    "CON_CUSTOM": {
        "name": "Connection Custom",
        "description": "Custom deformation connections",
        "icon_name": "nx_constraints_custom",
        "blender_icon": "PREFERENCES",
        "node_val": 10,
    },
    "COLLISIONS": {
        "name": "Collisions",
        "description": "Particle collision constraints",
        "icon_name": "nx_constraints_collisions",
        "blender_icon": "MOD_PHYSICS",
        "node_val": 2,
    },
    "FORCES": {
        "name": "Forces",
        "description": "Attraction and repulsion forces",
        "icon_name": "nx_constraints_forces",
        "blender_icon": "FORCE_FORCE",
        "node_val": 3,
    },
    "VISCOSITY": {
        "name": "Viscosity",
        "description": "Viscosity dampening constraints",
        "icon_name": "nx_constraints_viscosity",
        "blender_icon": "MOD_FLUIDSIM",
        "node_val": 4,
    },
    "FRICTION": {
        "name": "Friction",
        "description": "Friction constraints",
        "icon_name": "nx_constraints_friction",
        "blender_icon": "FORCE_DRAG",
        "node_val": 5,
    },
    "SURFACE_TENSION": {
        "name": "Surface Tension",
        "description": "Surface tension constraints",
        "icon_name": "nx_constraints_surfacet",
        "blender_icon": "META_BALL",
        "node_val": 6,
    },
}

_FALLOFF_TYPE_DEFS = [
    ("FLAT", "Flat", "No falloff"),
    ("LINEAR", "Linear", "Linear falloff"),
    ("QUADRATIC", "Quadratic", "Quadratic falloff"),
    ("CUBIC", "Cubic", "Cubic falloff"),
]

_BREAK_TYPE_DEFS = [
    ("NONE", "None", "No break"),
    ("REL_CON", "Relative Connected", "Break relative to connected distance"),
    ("REL_RAD", "Relative Radius", "Break relative to radius"),
    ("ABSOLUTE", "Absolute", "Break at absolute distance"),
]

_CONSTRAINT_LAYER_ITEMS = []
_FALLOFF_TYPE_ITEMS = []
_BREAK_TYPE_ITEMS = []


def build_constraints_enum_items():
    global _CONSTRAINT_LAYER_ITEMS, _FALLOFF_TYPE_ITEMS, _BREAK_TYPE_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _CONSTRAINT_LAYER_ITEMS = []
    for idx, (type_id, layer_def) in enumerate(CONSTRAINT_LAYER_DEFS.items()):
        icon_id = get_icon(layer_def.get("icon_name", ""))
        if icon_id and icon_id > 0:
            _CONSTRAINT_LAYER_ITEMS.append(
                (type_id, layer_def["name"], layer_def["description"], icon_id, idx)
            )
        else:
            _CONSTRAINT_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    layer_def.get("blender_icon", "NONE"),
                    idx,
                )
            )

    _FALLOFF_TYPE_ITEMS = []
    for idx, (type_id, name, desc) in enumerate(_FALLOFF_TYPE_DEFS):
        icon_name = f"nx_falloff_type_{type_id.lower()}"
        icon_id = get_icon(icon_name)
        if icon_id and icon_id > 0:
            _FALLOFF_TYPE_ITEMS.append((type_id, name, desc, icon_id, idx))
        else:
            _FALLOFF_TYPE_ITEMS.append((type_id, name, desc, "NONE", idx))

    _BREAK_TYPE_ITEMS = []
    for idx, (type_id, name, desc) in enumerate(_BREAK_TYPE_DEFS):
        _BREAK_TYPE_ITEMS.append((type_id, name, desc, "NONE", idx))

    register_nodetree(
        "constraints_layers",
        _CONSTRAINT_LAYER_ITEMS,
        "constraints_layers",
        "constraints_layers_index",
    )


def _get_constraint_layer_items(self, context):
    return _CONSTRAINT_LAYER_ITEMS


def _get_falloff_type_items(self, context):
    return _FALLOFF_TYPE_ITEMS


def _get_break_type_items(self, context):
    return _BREAK_TYPE_ITEMS


class NexusConstraintLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="")
    enabled: BoolProperty(name="Enabled", default=True)
    item_type: EnumProperty(
        name="Constraint Type",
        items=_get_constraint_layer_items,
        default=0,
    )

    con_birth_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_birth_born: BoolProperty(name="Only Born", default=False)
    con_birth_con_limit: IntProperty(name="Connection Limit", default=8, min=0, max=64)
    con_birth_radius: FloatProperty(
        name="Radius", default=0.4, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_birth_stiffness: FloatProperty(
        name="Stiffness", default=80.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_birth_min_dist: FloatProperty(
        name="Minimum Distance", default=0.0, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_birth_break: FloatProperty(
        name="Break", default=50.0, min=0.0, soft_max=200.0, subtype="PERCENTAGE"
    )
    con_birth_break_abs: FloatProperty(
        name="Break Above", default=0.6, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_birth_break_type: EnumProperty(name="Break Type", items=_get_break_type_items, default=1)

    con_dist_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_dist_con_limit: IntProperty(name="Connection Limit", default=8, min=0, max=64)
    con_dist_radius: FloatProperty(
        name="Radius", default=0.4, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_dist_stiffness: FloatProperty(
        name="Stiffness", default=80.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_dist_break: FloatProperty(
        name="Break", default=0.0, min=0.0, soft_max=200.0, subtype="PERCENTAGE"
    )

    con_custom_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_custom_con_limit: IntProperty(name="Connection Limit", default=16, min=0, max=64)
    con_custom_radius: FloatProperty(
        name="Radius", default=0.3, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_custom_com: FloatProperty(
        name="Compression", default=60.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_custom_com_break: FloatProperty(
        name="Break", default=0.05, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_custom_com_rate: FloatProperty(
        name="Rate", default=40.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_custom_com_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=3)
    con_custom_com_plastic: FloatProperty(
        name="Plastic", default=0.1, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_custom_exp: FloatProperty(
        name="Expansion", default=80.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_custom_exp_break: FloatProperty(
        name="Break", default=1.0, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_custom_exp_rate: FloatProperty(
        name="Rate", default=60.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_custom_exp_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=3)
    con_custom_exp_plastic: FloatProperty(
        name="Plastic", default=0.7, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )

    con_coll_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_coll_stiffness: FloatProperty(
        name="Stiffness", default=100.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )

    con_force_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_force_con_limit: IntProperty(name="Connection Limit", default=16, min=0, max=64)
    con_force_att: FloatProperty(
        name="Attraction", default=10.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_force_att_radius: FloatProperty(
        name="Radius", default=0.2, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_force_att_inner: FloatProperty(
        name="Inner", default=0.05, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_force_att_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=3)
    con_force_rep: FloatProperty(
        name="Repulsion", default=10.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_force_rep_radius: FloatProperty(
        name="Radius", default=0.1, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_force_rep_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=3)

    con_visc_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_visc_con_limit: IntProperty(name="Connection Limit", default=16, min=0, max=64)
    con_visc_radius: FloatProperty(
        name="Radius", default=0.4, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_visc_stiffness: FloatProperty(
        name="Stiffness", default=60.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )

    con_fric_force: FloatProperty(
        name="Friction", default=80.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_fric_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_fric_con_limit: IntProperty(name="Connection Limit", default=16, min=0, max=64)
    con_fric_radius: FloatProperty(
        name="Radius", default=0.3, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_fric_static: FloatProperty(
        name="Static", default=60.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_fric_kinetic: FloatProperty(
        name="Kinetic", default=40.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_fric_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=3)

    con_surft_weight: FloatProperty(
        name="Weight", default=100.0, min=0.0, soft_max=100.0, subtype="PERCENTAGE"
    )
    con_surft_con_limit: IntProperty(name="Connection Limit", default=16, min=0, max=64)
    con_surft_radius: FloatProperty(
        name="Radius", default=0.3, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_surft_inner: FloatProperty(
        name="Inner", default=0.05, min=0.0, soft_max=1.0, subtype="DISTANCE"
    )
    con_surft_tension: FloatProperty(
        name="Tension", default=40.0, min=0.0, max=100.0, subtype="PERCENTAGE"
    )
    con_surft_falloff: EnumProperty(name="Falloff", items=_get_falloff_type_items, default=1)


def _draw_birth_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_birth_weight")
    col.prop(item, "con_birth_born")
    col.prop(item, "con_birth_con_limit")
    col.prop(item, "con_birth_radius")
    col.prop(item, "con_birth_stiffness")
    col.prop(item, "con_birth_min_dist")

    col.separator(type="LINE")

    col.prop(item, "con_birth_break_type")

    sub = col.column()
    sub.active = item.con_birth_break_type in ("REL_CON", "REL_RAD")
    sub.prop(item, "con_birth_break")

    sub = col.column()
    sub.active = item.con_birth_break_type == "ABSOLUTE"
    sub.prop(item, "con_birth_break_abs")


def _draw_distance_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_dist_weight")
    col.prop(item, "con_dist_con_limit")
    col.prop(item, "con_dist_radius")
    col.prop(item, "con_dist_stiffness")
    col.prop(item, "con_dist_break")


def _draw_custom_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_custom_weight")
    col.prop(item, "con_custom_con_limit")
    col.prop(item, "con_custom_radius")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Compression")

    col.prop(item, "con_custom_com")
    col.prop(item, "con_custom_com_break")
    col.prop(item, "con_custom_com_rate")
    col.prop(item, "con_custom_com_falloff")
    col.prop(item, "con_custom_com_plastic")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Expansion")

    col.prop(item, "con_custom_exp")
    col.prop(item, "con_custom_exp_break")
    col.prop(item, "con_custom_exp_rate")
    col.prop(item, "con_custom_exp_falloff")
    col.prop(item, "con_custom_exp_plastic")


def _draw_collisions_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_coll_weight")
    col.prop(item, "con_coll_stiffness")


def _draw_forces_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_force_weight")
    col.prop(item, "con_force_con_limit")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Attraction")

    col.prop(item, "con_force_att")
    col.prop(item, "con_force_att_radius")
    col.prop(item, "con_force_att_inner")
    col.prop(item, "con_force_att_falloff")

    col.separator(type="LINE")

    header = col.row()
    header.use_property_split = False
    header.label(text="Repulsion")

    col.prop(item, "con_force_rep")
    col.prop(item, "con_force_rep_radius")
    col.prop(item, "con_force_rep_falloff")


def _draw_viscosity_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_visc_weight")
    col.prop(item, "con_visc_con_limit")
    col.prop(item, "con_visc_radius")
    col.prop(item, "con_visc_stiffness")


def _draw_friction_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_fric_force")
    col.prop(item, "con_fric_weight")
    col.prop(item, "con_fric_con_limit")
    col.prop(item, "con_fric_radius")
    col.prop(item, "con_fric_static")
    col.prop(item, "con_fric_kinetic")
    col.prop(item, "con_fric_falloff")


def _draw_surface_tension_settings(layout, item):
    col = layout.column()
    col.use_property_split = True

    col.prop(item, "con_surft_weight")
    col.prop(item, "con_surft_con_limit")
    col.prop(item, "con_surft_radius")
    col.prop(item, "con_surft_inner")
    col.prop(item, "con_surft_tension")
    col.prop(item, "con_surft_falloff")


_CONSTRAINT_DRAW_FUNCS = {
    "CON_BIRTH": _draw_birth_settings,
    "CON_DISTANCE": _draw_distance_settings,
    "CON_CUSTOM": _draw_custom_settings,
    "COLLISIONS": _draw_collisions_settings,
    "FORCES": _draw_forces_settings,
    "VISCOSITY": _draw_viscosity_settings,
    "FRICTION": _draw_friction_settings,
    "SURFACE_TENSION": _draw_surface_tension_settings,
}


def draw_constraint_layer_settings(layout, item):
    draw_func = _CONSTRAINT_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown constraint type", icon="ERROR")


def add_default_constraint_layer(obj):
    from ..utils import generate_unique_name

    props = obj.nexus_modifier
    item = props.constraints_layers.add()
    item.item_type = "CON_BIRTH"
    item.enabled = True

    base_name = CONSTRAINT_LAYER_DEFS["CON_BIRTH"]["name"]
    existing = [i.name for i in props.constraints_layers if i.name]
    item.name = generate_unique_name(base_name, existing)

    props.constraints_layers_index = 0


NX_CONSTRAINTS_UI_CONFIG = {}


def get_constraints_ui_config():
    config = dict(NX_CONSTRAINTS_UI_CONFIG)
    config["constraints_layers"] = {
        "type": "nodetree",
        "index_prop": "constraints_layers_index",
        "label": "Layers",
        "draw_item_settings": draw_constraint_layer_settings,
        "menu_id": "constraints_layers",
    }
    return config


_NODE_ID_OFFSET = 2000

CONSTRAINT_TYPE_NODE_VALS = {k: v["node_val"] for k, v in CONSTRAINT_LAYER_DEFS.items()}

BIRTH_BREAK_TYPE_IDS = {
    "NONE": "ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE_NONE",
    "REL_CON": "ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE_REL_CON",
    "REL_RAD": "ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE_REL_RAD",
    "ABSOLUTE": "ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE_ABS",
}

CUSTOM_FALLOFF_IDS = {
    "FLAT": "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_CUBIC",
}

FORCE_FALLOFF_IDS = {
    "FLAT": "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_FLAT",
    "LINEAR": "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_LINEAR",
    "QUADRATIC": "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_QUADRATIC",
    "CUBIC": "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_CUBIC",
}

FRICTION_FALLOFF_IDS = {
    "FLAT": "ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE_CUBIC",
}

SURFACET_FALLOFF_IDS = {
    "FLAT": "ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE_FLAT",
    "LINEAR": "ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE_LINEAR",
    "QUADRATIC": "ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE_QUADRATIC",
    "CUBIC": "ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE_CUBIC",
}


_pct = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]
_scale = TRANSFORM_FACTORS[Transform.UNIT_SCALE]


def _sync_birth(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_birth_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_WEIGHT"), weight)
    theron.set_bool(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_BORN"), item.con_birth_born)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_CON_LIMIT"), item.con_birth_con_limit)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_RADIUS"), item.con_birth_radius * _scale)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_BIRTH_STIFFNESS"),
        item.con_birth_stiffness * _pct,
    )
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_BIRTH_MIN_DIST"),
        item.con_birth_min_dist * _scale,
    )
    break_type_val = get(
        BIRTH_BREAK_TYPE_IDS.get(
            item.con_birth_break_type,
            "ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE_NONE",
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_TYPE"), break_type_val)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_BIRTH_BREAK"), item.con_birth_break * _pct)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_BIRTH_BREAK_ABS"),
        item.con_birth_break_abs * _scale,
    )


def _sync_distance(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_dist_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_DIST_WEIGHT"), weight)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_DIST_CON_LIMIT"), item.con_dist_con_limit)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_DIST_RADIUS"), item.con_dist_radius * _scale)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_DIST_STIFFNESS"), item.con_dist_stiffness * _pct
    )
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_DIST_BREAK"), item.con_dist_break * _pct)


def _sync_custom(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_custom_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_WEIGHT"), weight)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_CON_LIMIT"), item.con_custom_con_limit)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_RADIUS"), item.con_custom_radius * _scale
    )
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_COM"), item.con_custom_com * _pct)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_CUSTOM_COM_BREAK"),
        item.con_custom_com_break * _scale,
    )
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_COM_RATE"), item.con_custom_com_rate * _pct
    )
    com_falloff = get(
        CUSTOM_FALLOFF_IDS.get(
            item.con_custom_com_falloff,
            "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_CUBIC",
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_COM_FALLOFF"), com_falloff)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_CUSTOM_COM_PLASTIC"),
        item.con_custom_com_plastic * _scale,
    )
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_EXP"), item.con_custom_exp * _pct)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_CUSTOM_EXP_BREAK"),
        item.con_custom_exp_break * _scale,
    )
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_EXP_RATE"), item.con_custom_exp_rate * _pct
    )
    exp_falloff = get(
        CUSTOM_FALLOFF_IDS.get(
            item.con_custom_exp_falloff,
            "ID_XPGPU_CONSTRAINTS_CUSTOM_FALLOFF_TYPE_CUBIC",
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_CUSTOM_EXP_FALLOFF"), exp_falloff)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_CUSTOM_EXP_PLASTIC"),
        item.con_custom_exp_plastic * _scale,
    )


def _sync_collisions(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_coll_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_COLLISIONS_WEIGHT"), weight)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_COLLISIONS_STIFF"), item.con_coll_stiffness * _pct
    )


def _sync_forces(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_force_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_WEIGHT"), weight)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_CON_LIMIT"), item.con_force_con_limit)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_ATT"), item.con_force_att * _pct)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_FORCE_ATT_RADIUS"),
        item.con_force_att_radius * _scale,
    )
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_FORCE_ATT_INNER"),
        item.con_force_att_inner * _scale,
    )
    att_falloff = get(
        FORCE_FALLOFF_IDS.get(
            item.con_force_att_falloff, "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_CUBIC"
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_ATT_FALLOFF"), att_falloff)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_REP"), item.con_force_rep * _pct)
    theron.set_float(
        nc,
        get("ID_XPGPU_CONSTRAINTS_FORCE_REP_RADIUS"),
        item.con_force_rep_radius * _scale,
    )
    rep_falloff = get(
        FORCE_FALLOFF_IDS.get(
            item.con_force_rep_falloff, "ID_XPGPU_CONSTRAINTS_FORCE_FALLOFF_CUBIC"
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_FORCE_REP_FALLOFF"), rep_falloff)


def _sync_viscosity(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_visc_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_VISC_WEIGHT"), weight)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_VISC_CON_LIMIT"), item.con_visc_con_limit)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_VISC_RADIUS"), item.con_visc_radius * _scale)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_VISC_STIFFNESS"), item.con_visc_stiffness * _pct
    )


def _sync_friction(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_fric_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_WEIGHT"), weight)
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_FORCE"), item.con_fric_force * _pct)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_CON_LIMIT"), item.con_fric_con_limit)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_RADIUS"), item.con_fric_radius * _scale
    )
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_STATIC"), item.con_fric_static * _pct)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_KINETIC"), item.con_fric_kinetic * _pct
    )
    fric_falloff = get(
        FRICTION_FALLOFF_IDS.get(
            item.con_fric_falloff,
            "ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE_CUBIC",
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_FRICTION_FALLOFF_TYPE"), fric_falloff)


def _sync_surface_tension(theron, get, nc, item, _item_orig, _obj):
    weight = 0.0 if not item.enabled else item.con_surft_weight * _pct
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_WEIGHT"), weight)
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_CON_LIMIT"), item.con_surft_con_limit)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_RADIUS"), item.con_surft_radius * _scale
    )
    theron.set_float(nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_INNER"), item.con_surft_inner * _scale)
    theron.set_float(
        nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_TENSION"), item.con_surft_tension * _pct
    )
    surft_falloff = get(
        SURFACET_FALLOFF_IDS.get(
            item.con_surft_falloff,
            "ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE_LINEAR",
        )
    )
    theron.set_int32(nc, get("ID_XPGPU_CONSTRAINTS_SURFACET_FALLOFF_TYPE"), surft_falloff)


_CONSTRAINTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_XPGPU_CONSTRAINTS_TREE",
    collection_attr="constraints_layers",
    type_id_map=CONSTRAINT_TYPE_NODE_VALS,
    node_id_offset=_NODE_ID_OFFSET,
    enabled_disables_blend=True,
    per_type_syncers={
        "CON_BIRTH": _sync_birth,
        "CON_DISTANCE": _sync_distance,
        "CON_CUSTOM": _sync_custom,
        "COLLISIONS": _sync_collisions,
        "FORCES": _sync_forces,
        "VISCOSITY": _sync_viscosity,
        "FRICTION": _sync_friction,
        "SURFACE_TENSION": _sync_surface_tension,
    },
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_CONSTRAINTS",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_XPGPU_CONSTRAINTS_SUBSTEPS",
            prop=IntProperty(
                name="Iterations",
                description="Number of constraint solver iterations",
                default=1,
                min=1,
                max=100,
            ),
        ),
        PropertyDescriptor(
            name="ID_XPGPU_CONSTRAINTS_DAMP",
            prop=FloatProperty(
                name="Damping",
                description="Global constraint damping",
                default=0.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="constraints_layers",
            prop=CollectionProperty(
                name="Constraint Layers",
                type=NexusConstraintLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="constraints_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
            ),
        ),
    ),
    item_classes=(NexusConstraintLayerItem,),
    enum_builders=(build_constraints_enum_items,),
    enum_defaults={
        "con_birth_break_type": "REL_CON",
        "con_custom_com_falloff": "CUBIC",
        "con_custom_exp_falloff": "CUBIC",
        "con_force_att_falloff": "CUBIC",
        "con_force_rep_falloff": "CUBIC",
        "con_fric_falloff": "CUBIC",
        "con_surft_falloff": "LINEAR",
    },
    nodetree_sync=(_CONSTRAINTS_TREE_SPEC,),
)


register_collection_preset(
    "NX_CONSTRAINTS",
    CollectionPresetSpec(
        collection_attr="constraints_layers",
        menu_id="constraints_layers",
    ),
)
