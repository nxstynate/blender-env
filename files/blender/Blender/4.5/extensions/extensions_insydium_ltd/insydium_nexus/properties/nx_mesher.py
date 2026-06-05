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
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import NodeTreeSyncSpec
from ..libs.theron_sync import Transform
from ..ui import make_allowed_types_poll
from ..ui.nodetree import auto_rename

_poll_mesher_emitter = make_allowed_types_poll(["NX_EMITTER"])
_poll_mesher_efx = make_allowed_types_poll(["NX_EXPLOSIAFX"])


def _poll_mesher_layer_obj(self, obj):
    if self.item_type == "ID_NX_MESHER_LAYER_TYPE_EMITTER":
        return _poll_mesher_emitter(self, obj)
    if self.item_type == "ID_NX_MESHER_LAYER_TYPE_EFX":
        return _poll_mesher_efx(self, obj)
    return False


def _clear_invalid_obj(self, _context):
    if self.obj is not None and not _poll_mesher_layer_obj(self, self.obj):
        self.obj = None


_MESHER_TAB_ITEMS = [
    ("GENERAL", "General", "General mesher settings", 0),
    ("EXPORT_TAGS", "Export Tags", "Export tags settings", 1),
    ("DOMAIN", "Domain", "Domain settings", 2),
]

_MESHER_SURFACE_SIZE_MODE_ITEMS = []
_MESHER_SURFACE_TYPE_ITEMS = []
_MESHER_POLYGON_MODE_ITEMS = []
_MESHER_SMOOTHING_MODE_ITEMS = []


def build_mesher_enum_items():
    global _MESHER_SURFACE_SIZE_MODE_ITEMS, _MESHER_SURFACE_TYPE_ITEMS
    global _MESHER_POLYGON_MODE_ITEMS, _MESHER_SMOOTHING_MODE_ITEMS

    from ..icons import get_icon

    _MESHER_SURFACE_SIZE_MODE_ITEMS = [
        (
            "ID_NX_MESHER_SURFACE_SIZE_MODE_FIXED",
            "Custom",
            "Use custom radius value",
            get_icon("nx_mesher_size_custom"),
            0,
        ),
        (
            "ID_NX_MESHER_SURFACE_SIZE_MODE_SOURCE",
            "Source",
            "Use source particle radius with scale",
            get_icon("nx_mesher_size_source"),
            1,
        ),
    ]

    _MESHER_SURFACE_TYPE_ITEMS = [
        (
            "ID_NX_MESHER_SURFACE_TYPE_ZHU_BRIDSON",
            "Zhu-Bridson",
            "Zhu-Bridson surface reconstruction",
            get_icon("nx_mesher_surface_zhubridson"),
            0,
        ),
        (
            "ID_NX_MESHER_SURFACE_TYPE_SPHERES",
            "Spheres",
            "Sphere-based surface reconstruction",
            get_icon("nx_mesher_surface_spheres"),
            1,
        ),
        (
            "ID_NX_MESHER_SURFACE_TYPE_ANISOTROPIC",
            "Anisotropic (Basic)",
            "Anisotropic surface reconstruction",
            get_icon("nx_mesher_surface_anisotropic"),
            2,
        ),
    ]

    _MESHER_POLYGON_MODE_ITEMS = [
        (
            "ID_NX_MESHER_POLY_TYPE_TRIS",
            "Tris",
            "Triangle polygons",
            get_icon("nx_mesher_polygon_tris"),
            0,
        ),
        (
            "ID_NX_MESHER_POLY_TYPE_QUADS",
            "Quads",
            "Quadrilateral polygons",
            get_icon("nx_mesher_polygon_quads"),
            1,
        ),
    ]

    _MESHER_SMOOTHING_MODE_ITEMS = [
        (
            "ID_NX_MESHER_SMOOTHING_MODE_GAUSS",
            "Gaussian",
            "Gaussian smoothing",
            get_icon("nx_mesher_smoothing_gaussian"),
            0,
        ),
        (
            "ID_NX_MESHER_SMOOTHING_MODE_LAPLACE",
            "Laplacian",
            "Laplacian smoothing",
            get_icon("nx_mesher_smoothing_laplacian"),
            1,
        ),
        (
            "ID_NX_MESHER_SMOOTHING_MODE_MEAN_CURVATURE",
            "Mean Curvature",
            "Mean curvature flow smoothing",
            get_icon("nx_mesher_smoothing_meancurvature"),
            2,
        ),
    ]


def _update_viewport(self, context):
    if context and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


MESHER_LAYER_DEFS = {
    "ID_NX_MESHER_LAYER_TYPE_EMITTER": {
        "name": "Emitter",
        "description": "Particle emitter source",
        "blender_icon": "PARTICLES",
    },
    "ID_NX_MESHER_LAYER_TYPE_SMOOTHING": {
        "name": "Smoothing",
        "description": "Mesh smoothing layer",
        "icon_name": "nx_mesher_layer_smoothing",
        "blender_icon": "MOD_SMOOTH",
    },
    "ID_NX_MESHER_LAYER_TYPE_EFX": {
        "name": "ExplosiaFX",
        "description": "ExplosiaFX volume source",
        "blender_icon": "MOD_FLUID",
    },
}

_MESHER_LAYER_ITEMS = []


def build_mesher_layer_enum_items():
    global _MESHER_LAYER_ITEMS
    from ..icons import get_icon
    from ..ui import register_nodetree

    _MESHER_LAYER_ITEMS = []

    for idx, (type_id, layer_def) in enumerate(MESHER_LAYER_DEFS.items()):
        icon_name = layer_def.get("icon_name")
        icon_id = 0
        if icon_name:
            icon_id = get_icon(icon_name)

        if icon_id and icon_id > 0:
            _MESHER_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    icon_id,
                    idx,
                )
            )
        else:
            blender_icon = layer_def.get("blender_icon", "NONE")
            _MESHER_LAYER_ITEMS.append(
                (
                    type_id,
                    layer_def["name"],
                    layer_def["description"],
                    blender_icon,
                    idx,
                )
            )

    register_nodetree(
        "mesher_layers",
        _MESHER_LAYER_ITEMS,
        "mesher_layers",
        "mesher_layers_index",
        on_add=_on_mesher_layer_add,
    )


def _on_mesher_layer_add(_context, obj, item):
    if obj is None:
        item.is_renamed = False
        return
    layers = obj.nexus_modifier.mesher_layers
    base = MESHER_LAYER_DEFS.get(item.item_type, {}).get("name", "Layer")
    auto_rename.initialize_added(item, layers, base)


def _get_mesher_layer_items(self, context):
    return _MESHER_LAYER_ITEMS


def _get_mesher_smoothing_mode_items(self, context):
    return _MESHER_SMOOTHING_MODE_ITEMS


def _get_mesher_tab_items(self, context):
    return _MESHER_TAB_ITEMS


def _get_mesher_surface_size_mode_items(self, context):
    return _MESHER_SURFACE_SIZE_MODE_ITEMS


def _get_mesher_surface_type_items(self, context):
    return _MESHER_SURFACE_TYPE_ITEMS


def _get_mesher_polygon_mode_items(self, context):
    return _MESHER_POLYGON_MODE_ITEMS


_on_item_type_change = auto_rename.on_trigger(
    base_name_fn=auto_rename.base_name_from_defs(MESHER_LAYER_DEFS, "Layer"),
    collection_attr="mesher_layers",
    pre=_clear_invalid_obj,
)


class NexusMesherLayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        description="Layer name",
        default="",
        update=auto_rename.on_name_update(),
    )

    is_renamed: BoolProperty(
        name="",
        default=False,
        options={"HIDDEN"},
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this layer",
        default=True,
    )

    item_type: EnumProperty(
        name="Type",
        description="Layer type",
        items=_get_mesher_layer_items,
        default=0,
        update=_on_item_type_change,
    )

    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        description="Target emitter object",
        poll=_poll_mesher_layer_obj,
    )

    icon_flags: IntProperty(name="Icon flag bits", default=0)

    emitter_smoothing: IntProperty(
        name="Smoothing",
        description="Smoothing iterations for emitter contribution",
        default=0,
        min=0,
        max=100,
    )

    smoothing_mode: EnumProperty(
        name="Mode",
        description="Smoothing algorithm",
        items=_get_mesher_smoothing_mode_items,
        default=0,
    )

    smoothing_strength: FloatProperty(
        name="Strength",
        description="Smoothing strength",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
    )

    smoothing_range: FloatProperty(
        name="Influence Range",
        description="Range for Gaussian smoothing",
        default=0.05,
        min=0.0,
        soft_max=1.0,
        unit="LENGTH",
    )

    smoothing_iterations: IntProperty(
        name="Iterations",
        description="Number of smoothing passes",
        default=1,
        min=1,
        soft_max=20,
    )

    efx_use_smoke: BoolProperty(
        name="Smoke",
        description="Use smoke density for meshing",
        default=True,
    )

    efx_smoke_threshold: FloatProperty(
        name="Iso-value",
        description="Smoke density threshold for surface generation",
        default=100.0,
        min=0.0,
        soft_max=100.0,
    )

    efx_use_temperature: BoolProperty(
        name="Temperature",
        description="Use temperature for meshing",
        default=False,
    )

    efx_temperature_threshold: FloatProperty(
        name="Iso-value",
        description="Temperature threshold for surface generation",
        default=50.0,
        min=0.0,
        soft_max=100.0,
    )


NX_MESHER_UI_CONFIG = {}


def get_mesher_ui_config():
    return NX_MESHER_UI_CONFIG


def _draw_emitter_layer_settings(layout, item):
    ui_config = get_mesher_ui_config()

    col = layout.column()
    col.use_property_split = ui_config.get("item_type", {}).get("use_property_split", True)
    col.prop(item, "item_type")
    col.separator(type="LINE")

    col.prop(item, "obj", text="Target")
    col.prop(item, "emitter_smoothing")


def _draw_smoothing_layer_settings(layout, item):
    ui_config = get_mesher_ui_config()

    col = layout.column()
    col.use_property_split = ui_config.get("item_type", {}).get("use_property_split", True)
    col.prop(item, "item_type")
    col.separator(type="LINE")

    col.prop(item, "smoothing_mode")
    col.prop(item, "smoothing_strength")

    row = col.row()
    row.enabled = item.smoothing_mode == "ID_NX_MESHER_SMOOTHING_MODE_GAUSS"
    row.prop(item, "smoothing_range")

    col.prop(item, "smoothing_iterations")


def _draw_efx_layer_settings(layout, item):
    ui_config = get_mesher_ui_config()

    col = layout.column()
    col.use_property_split = ui_config.get("item_type", {}).get("use_property_split", True)
    col.prop(item, "item_type")
    col.separator(type="LINE")

    col.prop(item, "obj", text="Target")

    col.separator(type="LINE")

    col.prop(item, "efx_use_smoke")
    row = col.row()
    row.enabled = item.efx_use_smoke
    row.prop(item, "efx_smoke_threshold")

    col.prop(item, "efx_use_temperature")
    row = col.row()
    row.enabled = item.efx_use_temperature
    row.prop(item, "efx_temperature_threshold")


LAYER_DRAW_FUNCS = {
    "ID_NX_MESHER_LAYER_TYPE_EMITTER": _draw_emitter_layer_settings,
    "ID_NX_MESHER_LAYER_TYPE_SMOOTHING": _draw_smoothing_layer_settings,
    "ID_NX_MESHER_LAYER_TYPE_EFX": _draw_efx_layer_settings,
}


def draw_mesher_layer_settings(layout, item):
    draw_func = LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


def _resolve_mesher_link(theron_mod, item, _obj, scene, _depsgraph):
    if (
        item.item_type
        not in (
            "ID_NX_MESHER_LAYER_TYPE_EMITTER",
            "ID_NX_MESHER_LAYER_TYPE_EFX",
        )
        or item.obj is None
    ):
        return None
    from ..handlers.pipeline import get_nexus_obj_handle

    return get_nexus_obj_handle(scene, item.obj)


def _sync_mesher_layer_type(theron, get, nc, item, item_orig, _obj):
    del item
    theron.set_int32(nc, get("ID_NX_MESHER_LAYER_TYPE"), get(item_orig.item_type))


def _sync_emitter(theron, get, nc, item, _item_orig, _obj):
    theron.set_int32(nc, get("ID_NX_MESHER_EXPORT_BLEND_EMITTER"), item.emitter_smoothing)


def _sync_smoothing(theron, get, nc, item, _item_orig, _obj):
    theron.set_int32(nc, get("ID_NX_MESHER_SMOOTHING_MODE"), get(item.smoothing_mode))
    theron.set_float(nc, get("ID_NX_MESHER_SMOOTHING_STRENGTH"), item.smoothing_strength * 0.01)
    theron.set_float(nc, get("ID_NX_MESHER_SMOOTHING_RANGE"), item.smoothing_range)
    theron.set_int32(nc, get("ID_NX_MESHER_SMOOTHING_ITERATIONS"), item.smoothing_iterations)


def _sync_efx(theron, get, nc, item, _item_orig, _obj):
    theron.set_bool(nc, get("ID_NX_MESHER_EFX_SMOKE"), item.efx_use_smoke)
    theron.set_float(nc, get("ID_NX_MESHER_EFX_SMOKE_THRESHOLD"), item.efx_smoke_threshold)
    theron.set_bool(nc, get("ID_NX_MESHER_EFX_TEMP"), item.efx_use_temperature)
    theron.set_float(nc, get("ID_NX_MESHER_EFX_TEMP_THRESHOLD"), item.efx_temperature_threshold)


def _mesher_post_insert(theron_mod, _get, node, _nc, item, _item_orig, _obj):
    theron_mod.set_node_icon_flags(node, item.icon_flags)


_MESHER_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_MESHER_LAYERS",
    collection_attr="mesher_layers",
    sequential_node_id=True,
    skip_if_no_link=False,
    node_link_resolver=_resolve_mesher_link,
    pre_dispatch_syncer=_sync_mesher_layer_type,
    per_type_syncers={
        "ID_NX_MESHER_LAYER_TYPE_EMITTER": _sync_emitter,
        "ID_NX_MESHER_LAYER_TYPE_SMOOTHING": _sync_smoothing,
        "ID_NX_MESHER_LAYER_TYPE_EFX": _sync_efx,
    },
    per_item_post_syncer=_mesher_post_insert,
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_MESHER",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="mesher_tab",
            prop=EnumProperty(
                name="Section",
                description="Mesher settings section",
                items=_get_mesher_tab_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_GRID_SIZE",
            prop=FloatProperty(
                name="Polygon Size",
                description="Size of generated polygons",
                default=0.05,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_SURFACE_SIZE_MODE",
            prop=EnumProperty(
                name="Surface Size",
                description="How to determine particle surface size",
                items=_get_mesher_surface_size_mode_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_SURFACE_SIZE",
            prop=FloatProperty(
                name="Radius",
                description="Custom particle radius for meshing",
                default=0.05,
                min=0.0,
                soft_max=1.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: (
                props.ID_NX_MESHER_SURFACE_SIZE_MODE == "ID_NX_MESHER_SURFACE_SIZE_MODE_FIXED"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_SURFACE_SIZE_MULT",
            prop=FloatProperty(
                name="Scale",
                description="Scale factor for source particle radius",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: (
                props.ID_NX_MESHER_SURFACE_SIZE_MODE == "ID_NX_MESHER_SURFACE_SIZE_MODE_SOURCE"
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_SURFACE_TYPE",
            prop=EnumProperty(
                name="Surface Type",
                description="Surface reconstruction algorithm",
                items=_get_mesher_surface_type_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_ANISOTROPY_USE_SPEED",
            prop=BoolProperty(
                name="Speed Anisotropy",
                description="Use particle speed for anisotropic stretching",
                default=False,
            ),
            condition=lambda props: props.ID_NX_MESHER_SURFACE_TYPE == "ANISOTROPIC",
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_KERNEL_ECCENTRICITY",
            prop=FloatProperty(
                name="Eccentricity",
                description="Eccentricity of anisotropic particles",
                default=30.0,
                min=0.0,
                max=100.0,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: (
                props.ID_NX_MESHER_SURFACE_TYPE == "ANISOTROPIC"
                and not props.ID_NX_MESHER_ANISOTROPY_USE_SPEED
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_ANISOTROPY_MAX_SPEED",
            prop=FloatProperty(
                name="Max Speed",
                description="Maximum speed for anisotropic stretching",
                default=2.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: (
                props.ID_NX_MESHER_SURFACE_TYPE == "ANISOTROPIC"
                and props.ID_NX_MESHER_ANISOTROPY_USE_SPEED
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_POLY_TYPE",
            prop=EnumProperty(
                name="Polygon Mode",
                description="Type of polygons to generate",
                items=_get_mesher_polygon_mode_items,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_COLOUR",
            prop=BoolProperty(
                name="Transfer Color",
                description="Transfer particle color to mesh vertices",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_BLEND_COLOUR",
            prop=IntProperty(
                name="Smoothing",
                description="Color smoothing iterations",
                default=0,
                min=0,
                max=100,
            ),
            condition=lambda props: props.ID_NX_MESHER_EXPORT_COLOUR,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_VELOCITY",
            prop=BoolProperty(
                name="Transfer Velocity",
                description="Transfer particle velocity to mesh vertices",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_MAX_VELOCITY_X",
            prop=FloatProperty(
                name="Max Velocity X",
                description="Maximum velocity in X axis for normalization",
                default=2.0,
                min=0.0,
                max=10.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_MESHER_EXPORT_VELOCITY,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_MAX_VELOCITY_Y",
            prop=FloatProperty(
                name="Max Velocity Y",
                description="Maximum velocity in Y axis for normalization",
                default=2.0,
                min=0.0,
                max=10.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_MESHER_EXPORT_VELOCITY,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_MAX_VELOCITY_Z",
            prop=FloatProperty(
                name="Max Velocity Z",
                description="Maximum velocity in Z axis for normalization",
                default=2.0,
                min=0.0,
                max=10.0,
                unit="VELOCITY",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_MESHER_EXPORT_VELOCITY,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_EXPORT_BLEND_VELOCITY",
            prop=IntProperty(
                name="Smoothing",
                description="Velocity smoothing iterations",
                default=0,
                min=0,
                max=100,
            ),
            condition=lambda props: props.ID_NX_MESHER_EXPORT_VELOCITY,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_DOMAIN",
            prop=FloatVectorProperty(
                name="Domain Size",
                description="Size of the meshing domain",
                default=(4.0, 4.0, 4.0),
                min=0.0,
                unit="LENGTH",
                size=3,
                subtype="XYZ",
            ),
            transform=Transform.UNIT_SCALE,
        ),
        PropertyDescriptor(
            name="ID_NX_MESHER_ADAPTIVE_DOMAIN",
            prop=BoolProperty(
                name="Adaptive Domain",
                description="Automatically adapt domain to particle bounds",
                default=True,
                update=_update_viewport,
            ),
        ),
        PropertyDescriptor(
            name="mesher_adaptive_color",
            prop=FloatVectorProperty(
                name="Adaptive Color",
                description="Color for adaptive domain visualization",
                default=(1.0, 0.29, 0.39, 1.0),
                subtype="COLOR",
                size=4,
                min=0.0,
                max=1.0,
                update=_update_viewport,
            ),
        ),
        PropertyDescriptor(
            name="mesher_draw_domain",
            prop=BoolProperty(
                name="Draw Domain",
                description="Draw the meshing domain in the viewport",
                default=False,
                update=_update_viewport,
            ),
        ),
        PropertyDescriptor(
            name="mesher_layers",
            prop=CollectionProperty(
                name="Layers",
                type=NexusMesherLayerItem,
            ),
        ),
        PropertyDescriptor(
            name="mesher_layers_index",
            prop=IntProperty(
                name="Active Layer Index",
                default=0,
                min=0,
            ),
        ),
    ),
    item_classes=(NexusMesherLayerItem,),
    enum_builders=(build_mesher_enum_items, build_mesher_layer_enum_items),
    enum_defaults={
        "mesher_tab": "GENERAL",
        "ID_NX_MESHER_SURFACE_SIZE_MODE": "ID_NX_MESHER_SURFACE_SIZE_MODE_FIXED",
        "ID_NX_MESHER_SURFACE_TYPE": "ID_NX_MESHER_SURFACE_TYPE_SPHERES",
        "ID_NX_MESHER_POLY_TYPE": "ID_NX_MESHER_POLY_TYPE_TRIS",
    },
    nodetree_sync=(_MESHER_TREE_SPEC,),
)


# `mesher_layers` is a scene-link list (emitter pointer per row); not preset-captured.
