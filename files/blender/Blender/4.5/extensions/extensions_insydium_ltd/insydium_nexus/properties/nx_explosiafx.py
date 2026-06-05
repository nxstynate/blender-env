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
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..libs.modifier_preset_spec import CollectionPresetSpec, register_collection_preset
from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.nodetree_sync import NodeTreeSyncSpec
from ..libs.theron_sync import Transform
from ..ui import NodeTreeDef, combine_nodetree_sync
from ..ui.nodetree import auto_rename
from ..utils.curve import CurveSpec, NexusCurve, create_item_curves, generate_curve_id

_EXPLOSIAFX_OBJECT_TAB_ITEMS = [
    ("SIMULATION", "Simulation", "Simulation domain settings", 0),
    ("SOURCES", "Sources", "Emission sources", 1),
    ("COLLIDERS", "Colliders", "EFX colliders", 2),
    ("SOLVER", "Solver", "Solver settings", 3),
]

_EXPLOSIAFX_SOURCEMESH_EMIT_ITEMS = []

_EXPLOSIAFX_SOURCEMESH_VELOCITY_ITEMS = []

_EXPLOSIAFX_SOURCEMESH_COLOR_ITEMS = []

_EXPLOSIAFX_SOURCESPLINE_COLOR_ITEMS = []

_EXPLOSIAFX_SOURCEXP_COLOR_ITEMS = []

_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS = [
    ("SET", "Set", "Set the value of the voxel to the target value, overwriting other sources", 0),
    ("BLEND", "Blend", "Blend voxel values between overlapping sources", 1),
    ("ADDRATE", "Add / sec", "Add the specified value per second to voxel grid", 2),
    ("SUBRATE", "Sub. / sec", "Subtract the specified value per second to voxel grid", 3),
]

_EXPLOSIAFX_SOURCEMESH_CHANNEL_EMIT_WEIGHTBY_ITEMS = []

_EXPLOSIAFX_SOURCEMESH_TEXTURE_COORDS_ITEMS = [
    ("UV", "UV", "Sample at the vertex's UV coordinate"),
    ("OBJECT", "Object", "Sample at the vertex's local position"),
    (
        "GENERATED",
        "Generated",
        "Sample at the vertex position normalised to the mesh bounding box (0..1)",
    ),
]

# Possible methods of down-sampling the RGBA values into a scalar vertex weight
_EXPLOSIAFX_SOURCEMESH_COLOR_CHANNEL_ITEMS = [
    ("R", "R", "Use the red channel as the per-vertex weight"),
    ("G", "G", "Use the green channel as the per-vertex weight"),
    ("B", "B", "Use the blue channel as the per-vertex weight"),
    ("A", "A", "Use the alpha channel as the per-vertex weight"),
    (
        "LUMINANCE",
        "Luminance",
        "Use Rec.709 luminance (0.2126R + 0.7152G + 0.0722B) as per-vertex weight",
    ),
]

_EXPLOSIAFX_TURBULENCE_TYPE_ITEMS = []
_EXPLOSIAFX_FORCE_LAYER_ITEMS = []

_EXPLOSIAFX_FORCE_LAYER_LABELS = {
    "TURBULENCE": "Turbulence",
    "VORTICITY": "Vorticity",
    "WIND": "Wind",
}

_EXPLOSIAFX_TURBULENCE_TYPE_LABELS = {
    "SIMPLEX": "Simplex",
    "TURBULENCE": "Turbulence",
    "WAVYTURBULENCE": "Wavy Turbulence",
    "VORONOISE": "Voronoise",
    "FBM": "FBM",
    "CUBIC": "Cubic",
}

_EXPLOSIAFX_FORCE_DATAMAP_ITEMS = []

_EXPLOSIAFX_DYNAMICS_TAB_ITEMS = [
    ("FORCES", "Forces", "Apply forces / acceleration to fluid", 0),
    ("MODIFIERS", "Modifiers", "Apply NeXus modifiers to flow", 1),
    ("PARTICLEADVECT", "Particle Advect", "Advect particles with fluid", 2),
]

_EXPLOSIAFX_ADVECTION_METHOD_ITEMS = [
    ("FAST", "Fast", "Fast advection method", 0),
    ("ACCURATE", "Accurate", "Accurate advection method", 1),
]

_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP = {
    "FAST": "ID_NX_EXPLOSIAFX_ADVECTIONTYPE_LINEAR_RK3",
    "ACCURATE": "ID_NX_EXPLOSIAFX_ADVECTIONTYPE_PSEUDOCIP_RK3",
}

_EXPLOSIAFX_DYNAMICS_TAB_ITEMS = [
    ("FORCES", "Forces", "Apply forces to fluid", 0),
    ("MODIFIERS", "Modifiers", "Integration with other NeXus modifiers", 1),
    ("PADVECT", "Particle Advect", "Advect NeXus particles with ExplosiaFX simulation", 2),
]

_EXPLOSIAFX_PADVECT_MODE_ITEMS = [
    ("POSITION", "Position", "Particle positions trace flow without velocity update", 0),
    ("DIRECTION", "Direction", "Particle direction is inherited from flow, but not speed", 1),
    ("VELOCITY", "Velocity", "Particle takes velocity from local nxExplosiaFX flow velocity", 2),
]

_EXPLOSIAFX_PADVECT_PROPXFERTYPE_ITEMS = [
    ("SET", "Set", "Set a particle's property value directly from the nxExplosiaFX channel", 0),
    (
        "ADD",
        "Add",
        "Add the nxExplosiaFX channel value to a particle's existing property value",
        1,
    ),
]

_EXPLOSIAFX_DISPLAY_TAB_ITEMS = [
    ("VOLUME", "Volume", "Viewport volume rendering", 0),
    ("HUD", "Viewport HUD", "HUD simulation diagnostics", 1),
]

_EXPLOSIAFX_DISPLAY_VOLUME_DRAWMODE_ITEMS = [
    ("OFF", "Off", "Disable volumetric rendering", 0),
    ("SLICES", "Volume Slicing", "Render volumes with blended camera-facing slices", 1),
    (
        "RAYMARCHER",
        "Volumetric Ray Marching",
        "Render smoke and fire with a physical ray marcher",
        2,
    ),
]

_EXPLOSIAFX_DISPLAY_SLICER_TEMP_COLOR_MODE_ITEMS = [
    ("BLACKBODY", "Blackbody", "Color from a blackbody emission curve", 0),
    ("MANUAL", "Manual", "Color from the user-defined Temperature Color gradient", 1),
]

_EXPLOSIAFX_DISPLAY_SLICER_CHANNEL_ITEMS = [
    ("SMOKE_TEMP", "Smoke + Temperature", "Smoke density modulated by temperature emission", 0),
    ("SMOKE_FUEL", "Smoke + Fuel", "Smoke density modulated by fuel concentration", 1),
    ("TEMP", "Temperature", "Temperature field", 2),
    ("SMOKE", "Smoke", "Smoke density field", 3),
    ("FUEL", "Fuel", "Fuel concentration field", 4),
    ("COLOR", "Color", "Color field", 5),
    ("SPEED", "Speed", "Velocity magnitude (speed) field", 6),
]

_EXPLOSIAFX_DISPLAY_VRM_GASEMIT_ITEMS = [
    ("MANUAL", "Manual", "Select emission color manually", 0),
    ("BB", "Black Body", "Black body emission spectrum", 1),
]

_EXPLOSIAFX_DISPLAY_DRAW_VOXELGRID_ITEMS = [
    ("NONE", "None", "Don't draw grid", 0),
    ("VOXELS", "Voxels", "Draw all voxels", 1),
    ("BACK", "Back only", "Draw back faces only", 2),
    ("BASE", "Base only", "Draw base plane only", 3),
    ("BASEANDBACK", "Base and Back", "Draw base plane and back faces", 4),
]

EXPLOSIAFX_FORCE_DATAMAP_CURVE_SPECS = [
    CurveSpec(
        "explosiafx_force_mapping",
        "Map",
        [(0.0, 0.0), (0.4, 0.2), (0.5, 0.5), (0.6, 0.8), (1.0, 1.0)],
        theron_ids=("ID_NX_EXPLOSIAFX_FORCES_MAPPING_MAPSPLINE",),
        slot_suffix_attr="curve_id",
    ),
]


def _lookup_enum_label(enum_items, item_id, fallback):
    for entry in enum_items:
        if entry and entry[0] == item_id:
            return entry[1]
    return fallback


def _get_force_layer_base_name(item):
    if item.item_type == "TURBULENCE":
        fallback = _EXPLOSIAFX_TURBULENCE_TYPE_LABELS.get(item.turbulence_type, "Turbulence")
        return _lookup_enum_label(
            _EXPLOSIAFX_TURBULENCE_TYPE_ITEMS, item.turbulence_type, fallback
        )

    fallback = _EXPLOSIAFX_FORCE_LAYER_LABELS.get(item.item_type, "Force")
    return _lookup_enum_label(_EXPLOSIAFX_FORCE_LAYER_ITEMS, item.item_type, fallback)


def _ensure_force_layer_curves(item):
    if item.name is None or item.curve_id:
        return False

    item.curve_id = generate_curve_id()
    obj = getattr(item, "id_data", None)
    if obj is not None:
        create_item_curves(obj, item.curve_id, EXPLOSIAFX_FORCE_DATAMAP_CURVE_SPECS)
    return True


def _on_efx_force_layer_nodetree_add(context, obj, item):
    del context
    _ensure_force_layer_curves(item)

    if obj is None:
        item.is_renamed = False
        return

    layers = obj.nexus_modifier.explosiafx_force_layers
    auto_rename.initialize_added(item, layers, _get_force_layer_base_name(item))


def build_explosiafx_enum_items():
    global _EXPLOSIAFX_FORCE_DATAMAP_ITEMS
    global _EXPLOSIAFX_SOURCEMESH_EMIT_ITEMS
    global _EXPLOSIAFX_SOURCEMESH_VELOCITY_ITEMS
    global _EXPLOSIAFX_SOURCEMESH_COLOR_ITEMS
    global _EXPLOSIAFX_SOURCEMESH_CHANNEL_EMIT_WEIGHTBY_ITEMS
    global _EXPLOSIAFX_SOURCESPLINE_COLOR_ITEMS
    global _EXPLOSIAFX_SOURCEXP_COLOR_ITEMS
    global _EXPLOSIAFX_FORCE_LAYER_ITEMS
    global _EXPLOSIAFX_TURBULENCE_TYPE_ITEMS

    from ..icons import get_icon
    from ..ui import register_nodetree

    _EXPLOSIAFX_SOURCEMESH_EMIT_ITEMS = [
        (
            "VOLUME",
            "Volume",
            "Emit from full mesh volume",
            get_icon("nx_explosiafx_sources_emitfromvolume"),
            0,
        ),
        (
            "SURFACE",
            "Surface",
            "Emit from mesh surface",
            get_icon("nx_explosiafx_sources_emitfromsurface"),
            1,
        ),
    ]

    _EXPLOSIAFX_SOURCEMESH_VELOCITY_ITEMS = [
        (
            "OBJMOTION",
            "Object Motion",
            "Transfer velocity of object to voxel grid",
            get_icon("nx_explosiafx_sources_objmotion"),
            0,
        ),
        (
            "MESHPERP",
            "Mesh Normals",
            "Transfer velocity in direction of mesh normals to grid",
            get_icon("nx_explosiafx_sources_meshnormal"),
            1,
        ),
        (
            "CUSTOM",
            "Custom",
            "Transfer custom velocity from source mesh to voxel grid",
            get_icon("nx_explosiafx_sources_velocitycustom"),
            2,
        ),
    ]

    _EXPLOSIAFX_SOURCEMESH_COLOR_ITEMS = [
        (
            "OBJECT",
            "Object",
            "Use the object's viewport display color",
            get_icon("nx_explosiafx_sources_colorfromobject"),
            0,
        ),
        (
            "ATTRIBUTE",
            "Color Attribute",
            "Use a mesh color attribute",
            "GROUP_VCOL",
            1,
        ),
        (
            "CUSTOM",
            "Custom",
            "Use a custom color",
            get_icon("nx_explosiafx_sources_colorfrom_uservalue"),
            2,
        ),
    ]

    _EXPLOSIAFX_SOURCESPLINE_COLOR_ITEMS = [
        (
            "OBJECT",
            "Object",
            "Use the object's viewport display color",
            get_icon("nx_explosiafx_sources_colorfromobject"),
            0,
        ),
        (
            "CUSTOM",
            "Custom",
            "Use a custom color",
            get_icon("nx_explosiafx_sources_colorfrom_uservalue"),
            1,
        ),
    ]

    _EXPLOSIAFX_SOURCEXP_COLOR_ITEMS = [
        (
            "PARTICLES",
            "Particles",
            "Use the particles' colors",
            get_icon("nx_explosiafx_sources_colorfromobject"),
            0,
        ),
        (
            "CUSTOM",
            "Custom",
            "Use a custom color",
            get_icon("nx_explosiafx_sources_colorfrom_uservalue"),
            1,
        ),
    ]

    _EXPLOSIAFX_FORCE_DATAMAP_ITEMS = [
        ("NONE", "None", "No data mapping", get_icon("nx_explosiafx_dynamics_mapping_none"), 0),
        (
            "SMOKE",
            "Smoke",
            "Map force strength to local smoke concentration",
            get_icon("nx_explosiafx_dynamics_mapping_smoke"),
            1,
        ),
        (
            "TEMPERATURE",
            "Temperature",
            "Map force strength to local temperature",
            get_icon("nx_explosiafx_dynamics_mapping_temperature"),
            2,
        ),
        (
            "FUEL",
            "Fuel",
            "Map force strength to local fuel concentration",
            get_icon("nx_explosiafx_dynamics_mapping_fuel"),
            3,
        ),
        (
            "COLORR",
            "Color (R)",
            "Map force strength to local color red channel",
            get_icon("nx_explosiafx_dynamics_mapping_colorred"),
            4,
        ),
        (
            "COLORG",
            "Color (G)",
            "Map force strength to local color green channel",
            get_icon("nx_explosiafx_dynamics_mapping_colorgreen"),
            5,
        ),
        (
            "COLORB",
            "Color (B)",
            "Map force strength to local color blue channel",
            get_icon("nx_explosiafx_dynamics_mapping_colorblue"),
            6,
        ),
        (
            "VELX",
            "Velocity (x)",
            "Map force strength to local fluid velocity along the domain's x direction",
            get_icon("nx_explosiafx_dynamics_mapping_velx"),
            7,
        ),
        (
            "VELY",
            "Velocity (y)",
            "Map force strength to local fluid velocity along the domain's y direction",
            get_icon("nx_explosiafx_dynamics_mapping_vely"),
            8,
        ),
        (
            "VELZ",
            "Velocity (z)",
            "Map force strength to local fluid velocity along the domain's z direction",
            get_icon("nx_explosiafx_dynamics_mapping_velz"),
            9,
        ),
        (
            "SPEED",
            "Speed",
            "Map force strength to local fluid speed",
            get_icon("nx_explosiafx_dynamics_mapping_speed"),
            10,
        ),
        (
            "POSX",
            "Position (x)",
            "Map force strength to the scaled position along the domain's local x axis",
            get_icon("nx_explosiafx_dynamics_mapping_posx"),
            11,
        ),
        (
            "POSY",
            "Position (y)",
            "Map force strength to the scaled position along the domain's local y axis",
            get_icon("nx_explosiafx_dynamics_mapping_posy"),
            12,
        ),
        (
            "POSZ",
            "Position (z)",
            "Map force strength to the scaled position along the domain's local z axis",
            get_icon("nx_explosiafx_dynamics_mapping_posz"),
            13,
        ),
        (
            "PRESSURE",
            "Pressure",
            "Map force strength to the local fluid pressure",
            get_icon("nx_explosiafx_dynamics_mapping_pressure"),
            14,
        ),
        (
            "DOCTIME",
            "Document Time",
            "Map force strength to the current document time",
            get_icon("nx_explosiafx_dynamics_mapping_doctime"),
            15,
        ),
    ]

    _EXPLOSIAFX_SOURCEMESH_CHANNEL_EMIT_WEIGHTBY_ITEMS = [
        (
            "VERTEX_GROUP",
            "Vertex Group",
            "Emission is weighted by a vertex group's per-vertex weights",
            "GROUP_VERTEX",
            0,
        ),
        (
            "ATTRIBUTE",
            "Attribute",
            "Emission is weighted by a point-domain float attribute "
            "(e.g. sculpt mask, vertex crease, or a Geometry Nodes output)",
            "MESH_DATA",
            4,
        ),
        (
            "COLOR_ATTRIBUTE",
            "Color Attribute",
            "Emission is weighted by a channel of a point-domain color attribute",
            "GROUP_VCOL",
            5,
        ),
        (
            "TEXTURE",
            "Texture",
            "Emission is weighted by a specified texture",
            get_icon("nx_explosiafx_sources_weightbytexture"),
            1,
        ),
        (
            "NOISE",
            "Noise",
            "Emission is weighted by INSYDIUM GPU noise",
            get_icon("nx_explosiafx_sources_weightbynoise"),
            2,
        ),
        (
            "NONE",
            "None (Uniform)",
            "Uniform emission in the region occupied by the source",
            get_icon("nx_explosiafx_sources_weightbynone"),
            3,
        ),
    ]

    _EXPLOSIAFX_TURBULENCE_TYPE_ITEMS = [
        ("SIMPLEX", "Simplex", "Turbulence with simplex noise", get_icon("nx_noise_simplex"), 0),
        ("TURBULENCE", "Turbulence", "Turbulence noise", get_icon("nx_noise_turbulence"), 1),
        (
            "WAVYTURBULENCE",
            "Wavy Turbulence",
            "Wavy turbulence noise",
            get_icon("nx_noise_wavy_turbulence"),
            2,
        ),
        (
            "VORONOISE",
            "Voronoise",
            "Turbulence with voronoise noise",
            get_icon("nx_noise_voronoise"),
            3,
        ),
        ("FBM", "FBM", "Turbulence with FBM noise", get_icon("nx_noise_fbm"), 4),
        ("CUBIC", "Cubic", "Turbulence with cubic noise", get_icon("nx_noise_cubic"), 5),
    ]

    _EXPLOSIAFX_FORCE_LAYER_ITEMS = [
        (
            "TURBULENCE",
            "Turbulence",
            "Add turbuluence to fluid flow",
            get_icon("nx_noise_simplex"),
            0,
        ),
        (
            "VORTICITY",
            "Vorticity",
            "Amplify vorticity in fluid flow",
            get_icon("nx_explosiafx_dynamics_vorticity"),
            1,
        ),
        (
            "WIND",
            "Wind",
            "Add wind force to fluid flow",
            get_icon("nx_explosiafx_dynamics_wind"),
            2,
        ),
    ]

    register_nodetree(
        "explosiafx_force_layers",
        _EXPLOSIAFX_FORCE_LAYER_ITEMS,
        "explosiafx_force_layers",
        "explosiafx_force_layers_index",
        on_add=_on_efx_force_layer_nodetree_add,
    )


def _get_explosiafx_object_tab_items(self, context):
    return _EXPLOSIAFX_OBJECT_TAB_ITEMS


def _get_explosiafx_sourcemesh_emit_items(self, context):
    return _EXPLOSIAFX_SOURCEMESH_EMIT_ITEMS


def _get_explosiafx_sourcemesh_velocity_items(self, context):
    return _EXPLOSIAFX_SOURCEMESH_VELOCITY_ITEMS


def _get_explosiafx_sourcemesh_color_items(self, context):
    return _EXPLOSIAFX_SOURCEMESH_COLOR_ITEMS


def _get_explosiafx_sourcemesh_emit_weightby_items(self, context):
    return _EXPLOSIAFX_SOURCEMESH_CHANNEL_EMIT_WEIGHTBY_ITEMS


def _get_explosiafx_sourcespline_color_items(self, context):
    return _EXPLOSIAFX_SOURCESPLINE_COLOR_ITEMS


def _get_explosiafx_sourcexp_color_items(self, context):
    return _EXPLOSIAFX_SOURCEXP_COLOR_ITEMS


def _get_explosiafx_advection_method_items(self, context):
    return _EXPLOSIAFX_ADVECTION_METHOD_ITEMS


def _get_explosiafx_dynamics_tab_items(self, context):
    return _EXPLOSIAFX_DYNAMICS_TAB_ITEMS


def _get_explosiafx_padvect_mode_items(self, context):
    return _EXPLOSIAFX_PADVECT_MODE_ITEMS


def _get_explosiafx_padvect_propxfertype_items(self, context):
    return _EXPLOSIAFX_PADVECT_PROPXFERTYPE_ITEMS


def _get_explosiafx_display_tab_items(self, context):
    return _EXPLOSIAFX_DISPLAY_TAB_ITEMS


def _get_explosiafx_display_volume_drawmode_items(self, context):
    return _EXPLOSIAFX_DISPLAY_VOLUME_DRAWMODE_ITEMS


def _get_explosiafx_display_slicer_channel_items(self, context):
    return _EXPLOSIAFX_DISPLAY_SLICER_CHANNEL_ITEMS


def _get_explosiafx_display_slicer_temp_color_mode_items(self, context):
    return _EXPLOSIAFX_DISPLAY_SLICER_TEMP_COLOR_MODE_ITEMS


def _get_explosiafx_display_draw_voxelgrid_items(self, context):
    return _EXPLOSIAFX_DISPLAY_DRAW_VOXELGRID_ITEMS


def _get_explosiafx_force_layer_items(self, context):
    return _EXPLOSIAFX_FORCE_LAYER_ITEMS


def _get_explosiafx_turbulence_type_items(self, context):
    return _EXPLOSIAFX_TURBULENCE_TYPE_ITEMS


def _get_explosiafx_force_datamap_items(self, context):
    return _EXPLOSIAFX_FORCE_DATAMAP_ITEMS


# Item sheet for source nodetree item properties
class NexusEFXSourceItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)

    explosiafx_sourcemesh_emit_from: EnumProperty(
        name="Emit From",
        description="Emit from surface or volume of mesh",
        items=_get_explosiafx_sourcemesh_emit_items,
        default=1,
    )

    explosiafx_sourcemesh_surface_emitwidth: FloatProperty(
        name="Surface Width",
        description="Width (in voxel size counts) of surface emission region",
        default=0.5,
        min=0.0,
        step=10.0,
        precision=1,
    )

    explosiafx_sourcemesh_surface_taperwidth: FloatProperty(
        name="Taper Width",
        description=(
            "Width (in voxel size counts) of additional smoothing region outside surface emission"
        ),
        default=1.0,
        min=0.0,
        step=10.0,
        precision=1,
    )

    explosiafx_sourcemesh_smoke_expanded: BoolProperty(
        name="Smoke",
        description="Expand smoke emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcemesh_smoke: FloatProperty(
        name="Smoke",
        description="Smoke emission value",
        default=0.0,
        min=0.0,
        soft_max=5.0,
    )

    explosiafx_sourcemesh_smoke_framelimit_enabled: BoolProperty(
        name="Smoke frame limit",
        description="Limit smoke emission to a range of frames",
        default=False,
    )

    explosiafx_sourcemesh_smoke_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcemesh_smoke_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcemesh_smoke_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcemesh_smoke_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_smoke_noisewt_strength: FloatProperty(
        name="Strength",
        description="Strength (saturation range) of the noise weighting",
        default=40.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_smoke_noisewt_lenscl: FloatProperty(
        name="Length Scale",
        description="Length scale of noise (primary harmonic / octave)",
        default=0.4,
        min=0.0,
        soft_max=10.0,
        precision=2,
        step=1,
        unit="LENGTH",
    )

    explosiafx_sourcemesh_smoke_noisewt_freq: FloatProperty(
        name="Frequency",
        description="Temporal frequency of noise variations",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_smoke_noisewt_octaves: IntProperty(
        name="Octaves",
        description="Number of octaves of spatial variations",
        default=2,
        min=1,
        soft_max=20,
    )

    explosiafx_sourcemesh_smoke_noisewt_persistence: FloatProperty(
        name="Persistence",
        description="Ratio of amplitude of each octave to the previous",
        default=80,
        min=0,
        soft_max=100.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_smoke_weight: EnumProperty(
        name="Weight by",
        description="Apply any weighting when transferring source to voxel grid",
        items=_get_explosiafx_sourcemesh_emit_weightby_items,
        default=3,
    )

    explosiafx_sourcemesh_smoke_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group whose per-vertex weights drive smoke emission",
        default="",
    )

    explosiafx_sourcemesh_smoke_attribute: StringProperty(
        name="Attribute",
        description="Vertex float attribute whose per-vertex values drive smoke emission",
        default="",
    )

    explosiafx_sourcemesh_smoke_color_attribute: StringProperty(
        name="Color Attribute",
        description="Color attribute that weights smoke emission",
        default="",
    )

    explosiafx_sourcemesh_smoke_color_channel: EnumProperty(
        name="Weight From",
        description="Which channel of the color attribute provides the per-vertex weight",
        items=_EXPLOSIAFX_SOURCEMESH_COLOR_CHANNEL_ITEMS,
        default="LUMINANCE",
    )

    explosiafx_sourcemesh_smoke_image: PointerProperty(
        name="Image",
        type=bpy.types.Image,
        description="Image sampled per-vertex to drive smoke emission",
    )

    explosiafx_sourcemesh_smoke_texture_coords: EnumProperty(
        name="Coordinates",
        description="How texture coordinates are derived per vertex",
        items=_EXPLOSIAFX_SOURCEMESH_TEXTURE_COORDS_ITEMS,
        default="UV",
    )

    explosiafx_sourcemesh_smoke_uv_map: StringProperty(
        name="UV Map",
        description="UV map to sample (when Coordinates = UV)",
        default="",
    )

    explosiafx_sourcemesh_temperature_expanded: BoolProperty(
        name="Temperature",
        description="Expand temperature emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcemesh_temperature: FloatProperty(
        name="Temperature",
        description="Temperature emission value",
        default=1000,
        min=0.0,
        soft_max=10000,
        precision=0,
        step=1000.0,
        unit="TEMPERATURE",
    )

    explosiafx_sourcemesh_temperature_framelimit_enabled: BoolProperty(
        name="Temperature frame limit",
        description="Limit temperature emission to a range of frames",
        default=False,
    )

    explosiafx_sourcemesh_temperature_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcemesh_temperature_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcemesh_temperature_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcemesh_temperature_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_temperature_noisewt_strength: FloatProperty(
        name="Strength",
        description="Strength (saturation range) of the noise weighting",
        default=40.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_temperature_noisewt_lenscl: FloatProperty(
        name="Length Scale",
        description="Length scale of noise (primary harmonic / octave)",
        default=0.4,
        min=0.0,
        soft_max=10.0,
        precision=2,
        step=1,
        unit="LENGTH",
    )

    explosiafx_sourcemesh_temperature_noisewt_freq: FloatProperty(
        name="Frequency",
        description="Temporal frequency of noise variations",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_temperature_noisewt_octaves: IntProperty(
        name="Octaves",
        description="Number of octaves of spatial variations",
        default=2,
        min=1,
        soft_max=20,
    )

    explosiafx_sourcemesh_temperature_noisewt_persistence: FloatProperty(
        name="Persistence",
        description="Ratio of amplitude of each octave to the previous",
        default=80,
        min=0,
        soft_max=100.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_temperature_weight: EnumProperty(
        name="Weight by",
        description="Apply any weighting when transferring source to voxel grid",
        items=_get_explosiafx_sourcemesh_emit_weightby_items,
        default=3,
    )

    explosiafx_sourcemesh_temperature_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group whose per-vertex weights drive temperature emission",
        default="",
    )

    explosiafx_sourcemesh_temperature_attribute: StringProperty(
        name="Attribute",
        description="Vertex float attribute whose per-vertex values drive temperature emission",
        default="",
    )

    explosiafx_sourcemesh_temperature_color_attribute: StringProperty(
        name="Color Attribute",
        description="Color attribute that weights temperature emission",
        default="",
    )

    explosiafx_sourcemesh_temperature_color_channel: EnumProperty(
        name="Weight From",
        description="Which channel of the color attribute provides the per-vertex weight",
        items=_EXPLOSIAFX_SOURCEMESH_COLOR_CHANNEL_ITEMS,
        default="LUMINANCE",
    )

    explosiafx_sourcemesh_temperature_image: PointerProperty(
        name="Image",
        type=bpy.types.Image,
        description="Image sampled per-vertex to drive temperature emission",
    )

    explosiafx_sourcemesh_temperature_texture_coords: EnumProperty(
        name="Coordinates",
        description="How texture coordinates are derived per vertex",
        items=_EXPLOSIAFX_SOURCEMESH_TEXTURE_COORDS_ITEMS,
        default="UV",
    )

    explosiafx_sourcemesh_temperature_uv_map: StringProperty(
        name="UV Map",
        description="UV map to sample (when Coordinates = UV)",
        default="",
    )

    explosiafx_sourcemesh_fuel_expanded: BoolProperty(
        name="Fuel",
        description="Expand fuel emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcemesh_fuel: FloatProperty(
        name="Fuel",
        description="Fuel emission value",
        default=0.2,
        min=0.0,
        soft_max=1,
    )

    explosiafx_sourcemesh_fuel_framelimit_enabled: BoolProperty(
        name="Fuel frame limit",
        description="Limit fuel emission to a range of frames",
        default=False,
    )

    explosiafx_sourcemesh_fuel_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcemesh_fuel_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcemesh_fuel_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcemesh_fuel_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_fuel_noisewt_strength: FloatProperty(
        name="Strength",
        description="Strength (saturation range) of the noise weighting",
        default=40.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_fuel_noisewt_lenscl: FloatProperty(
        name="Length Scale",
        description="Length scale of noise (primary harmonic / octave)",
        default=0.4,
        min=0.0,
        soft_max=10.0,
        precision=2,
        step=1,
        unit="LENGTH",
    )

    explosiafx_sourcemesh_fuel_noisewt_freq: FloatProperty(
        name="Frequency",
        description="Temporal frequency of noise variations",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_fuel_noisewt_octaves: IntProperty(
        name="Octaves",
        description="Number of octaves of spatial variations",
        default=2,
        min=1,
        soft_max=20,
    )

    explosiafx_sourcemesh_fuel_noisewt_persistence: FloatProperty(
        name="Persistence",
        description="Ratio of amplitude of each octave to the previous",
        default=80,
        min=0,
        soft_max=100.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_fuel_weight: EnumProperty(
        name="Weight by",
        description="Apply any weighting when transferring source to voxel grid",
        items=_get_explosiafx_sourcemesh_emit_weightby_items,
        default=3,
    )

    explosiafx_sourcemesh_fuel_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group whose per-vertex weights drive fuel emission",
        default="",
    )

    explosiafx_sourcemesh_fuel_attribute: StringProperty(
        name="Attribute",
        description="Vertex float attribute whose per-vertex values drive fuel emission",
        default="",
    )

    explosiafx_sourcemesh_fuel_color_attribute: StringProperty(
        name="Color Attribute",
        description="Color attribute that weights fuel emission",
        default="",
    )

    explosiafx_sourcemesh_fuel_color_channel: EnumProperty(
        name="Weight From",
        description="Which channel of the color attribute provides the per-vertex weight",
        items=_EXPLOSIAFX_SOURCEMESH_COLOR_CHANNEL_ITEMS,
        default="LUMINANCE",
    )

    explosiafx_sourcemesh_fuel_image: PointerProperty(
        name="Image",
        type=bpy.types.Image,
        description="Image sampled per-vertex to drive fuel emission",
    )

    explosiafx_sourcemesh_fuel_texture_coords: EnumProperty(
        name="Coordinates",
        description="How texture coordinates are derived per vertex",
        items=_EXPLOSIAFX_SOURCEMESH_TEXTURE_COORDS_ITEMS,
        default="UV",
    )

    explosiafx_sourcemesh_fuel_uv_map: StringProperty(
        name="UV Map",
        description="UV map to sample (when Coordinates = UV)",
        default="",
    )

    explosiafx_sourcemesh_pressure_expanded: BoolProperty(
        name="Pressure",
        description="Expand pressure emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcemesh_pressure: FloatProperty(
        name="Pressure",
        description="Pressure from source",
        default=10.0,
        soft_min=-1000.0,
        soft_max=1000.0,
    )

    explosiafx_sourcemesh_pressure_framelimit_enabled: BoolProperty(
        name="Pressure frame limit",
        description="Limit pressure emission to a range of frames",
        default=False,
    )

    explosiafx_sourcemesh_pressure_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcemesh_pressure_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcemesh_pressure_noisewt_strength: FloatProperty(
        name="Strength",
        description="Strength (saturation range) of the noise weighting",
        default=40.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_pressure_noisewt_lenscl: FloatProperty(
        name="Length Scale",
        description="Length scale of noise (primary harmonic / octave)",
        default=0.4,
        min=0.0,
        soft_max=10.0,
        precision=2,
        step=1,
        unit="LENGTH",
    )

    explosiafx_sourcemesh_pressure_noisewt_freq: FloatProperty(
        name="Frequency",
        description="Temporal frequency of noise variations",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_pressure_noisewt_octaves: IntProperty(
        name="Octaves",
        description="Number of octaves of spatial variations",
        default=2,
        min=1,
        soft_max=20,
    )

    explosiafx_sourcemesh_pressure_noisewt_persistence: FloatProperty(
        name="Persistence",
        description="Ratio of amplitude of each octave to the previous",
        default=80,
        min=0,
        soft_max=100.0,
        precision=0,
        step=100,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_pressure_weight: EnumProperty(
        name="Weight by",
        description="Apply any weighting when transferring source to voxel grid",
        items=_get_explosiafx_sourcemesh_emit_weightby_items,
        default=3,
    )

    explosiafx_sourcemesh_pressure_vertex_group: StringProperty(
        name="Vertex Group",
        description="Vertex group whose per-vertex weights drive pressure emission",
        default="",
    )

    explosiafx_sourcemesh_pressure_attribute: StringProperty(
        name="Attribute",
        description="Vertex float attribute whose per-vertex values drive pressure emission",
        default="",
    )

    explosiafx_sourcemesh_pressure_color_attribute: StringProperty(
        name="Color Attribute",
        description="Color attribute that weights pressure emission",
        default="",
    )

    explosiafx_sourcemesh_pressure_color_channel: EnumProperty(
        name="Weight From",
        description="Which channel of the color attribute provides the per-vertex weight",
        items=_EXPLOSIAFX_SOURCEMESH_COLOR_CHANNEL_ITEMS,
        default="LUMINANCE",
    )

    explosiafx_sourcemesh_pressure_image: PointerProperty(
        name="Image",
        type=bpy.types.Image,
        description="Image sampled per-vertex to drive pressure emission",
    )

    explosiafx_sourcemesh_pressure_texture_coords: EnumProperty(
        name="Coordinates",
        description="How texture coordinates are derived per vertex",
        items=_EXPLOSIAFX_SOURCEMESH_TEXTURE_COORDS_ITEMS,
        default="UV",
    )

    explosiafx_sourcemesh_pressure_uv_map: StringProperty(
        name="UV Map",
        description="UV map to sample (when Coordinates = UV)",
        default="",
    )

    explosiafx_sourcemesh_velocity_from: EnumProperty(
        name="Velocity From",
        description="Method of velocity transfer from source to voxel grid",
        items=_get_explosiafx_sourcemesh_velocity_items,
        default=0,
    )

    explosiafx_sourcemesh_velocity_objpercent: FloatProperty(
        name="",
        description="Percentage of object velocity to transfer to fluid",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_velocity_perpsize: FloatProperty(
        name="",
        description="Velocity magnitude to emit perpendicular to surface",
        default=0.0,
        precision=3,
        step=1,
        unit="VELOCITY",
    )

    explosiafx_sourcemesh_velocity_custom: FloatVectorProperty(
        name="",
        description="Custom vector fluid velocity emitted from source object",
        default=(0.0, 0.0, 0.0),
        precision=3,
        step=1,
        unit="VELOCITY",
        size=3,
        subtype="XYZ",
    )

    explosiafx_sourcemesh_color_from: EnumProperty(
        name="Color From",
        description="Source of color transferred from source mesh to voxel grid",
        items=_get_explosiafx_sourcemesh_color_items,
        default=0,
    )

    explosiafx_sourcemesh_color_objpercent: FloatProperty(
        name="",
        description="Percentage of color to transfer to fluid",
        default=0.0,
        min=0.0,
        max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcemesh_color_attribute: StringProperty(
        name="Color Attribute",
        description="Mesh color attribute to sample per vertex",
        default="",
    )

    explosiafx_sourcemesh_color_custom: FloatVectorProperty(
        name="",
        description="Custom color transferred from source mesh to voxel grid",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=3,
        subtype="COLOR",
    )

    # --

    explosiafx_sourcespline_custom_radius: BoolProperty(
        name="Custom Radius",
        description="Set the emission radius manually",
        default=False,
    )

    explosiafx_sourcespline_radius: FloatProperty(
        name="Emit Radius",
        description="Size of the emission region around the spline path",
        default=0.1,
        min=0.0,
        soft_max=1.0,
        step=1,
    )

    explosiafx_sourcespline_smoke_expanded: BoolProperty(
        name="Smoke",
        description="Expand smoke emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcespline_smoke: FloatProperty(
        name="Smoke",
        description="Smoke emission value",
        default=0.0,
        min=0.0,
        soft_max=5.0,
    )

    explosiafx_sourcespline_smoke_framelimit_enabled: BoolProperty(
        name="Smoke frame limit",
        description="Limit smoke emission to a range of frames",
        default=False,
    )

    explosiafx_sourcespline_smoke_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcespline_smoke_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcespline_smoke_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcespline_smoke_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcespline_temperature_expanded: BoolProperty(
        name="Temperature",
        description="Expand temperature emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcespline_temperature: FloatProperty(
        name="Temperature",
        description="Temperature emission value",
        default=1000,
        min=0.0,
        soft_max=10000,
        precision=0,
        step=1000.0,
        unit="TEMPERATURE",
    )

    explosiafx_sourcespline_temperature_framelimit_enabled: BoolProperty(
        name="Temperature frame limit",
        description="Limit temperature emission to a range of frames",
        default=False,
    )

    explosiafx_sourcespline_temperature_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcespline_temperature_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcespline_temperature_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcespline_temperature_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcespline_fuel_expanded: BoolProperty(
        name="Fuel",
        description="Expand fuel emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcespline_fuel: FloatProperty(
        name="Fuel",
        description="Fuel emission value",
        default=0.2,
        min=0.0,
        soft_max=1,
    )

    explosiafx_sourcespline_fuel_framelimit_enabled: BoolProperty(
        name="Fuel frame limit",
        description="Limit fuel emission to a range of frames",
        default=False,
    )

    explosiafx_sourcespline_fuel_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcespline_fuel_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcespline_fuel_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcespline_fuel_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcespline_pressure_expanded: BoolProperty(
        name="Pressure",
        description="Expand pressure emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcespline_pressure: FloatProperty(
        name="Pressure",
        description="Pressure from source",
        default=10.0,
        soft_min=-1000.0,
        soft_max=1000.0,
    )

    explosiafx_sourcespline_pressure_framelimit_enabled: BoolProperty(
        name="Pressure frame limit",
        description="Limit pressure emission to a range of frames",
        default=False,
    )

    explosiafx_sourcespline_pressure_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcespline_pressure_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcespline_velocity_objpercent: FloatProperty(
        name="Velocity",
        description="Percentage of object velocity to transfer to fluid",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcespline_color_from: EnumProperty(
        name="Color From",
        description="Source of color transferred from source spline to voxel grid",
        items=_get_explosiafx_sourcespline_color_items,
        default=0,
    )

    explosiafx_sourcespline_color_objpercent: FloatProperty(
        name="",
        description="Percentage of color to transfer to fluid",
        default=0.0,
        min=0.0,
        max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcespline_color_custom: FloatVectorProperty(
        name="",
        description="Custom color transferred from source spline to voxel grid",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=3,
        subtype="COLOR",
    )

    # --

    explosiafx_sourcexp_smoke_expanded: BoolProperty(
        name="Smoke",
        description="Expand smoke emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcexp_smoke: FloatProperty(
        name="Smoke",
        description="Smoke emission value",
        default=0.0,
        min=0.0,
        soft_max=5.0,
    )

    explosiafx_sourcexp_smoke_framelimit_enabled: BoolProperty(
        name="Smoke frame limit",
        description="Limit smoke emission to a range of frames",
        default=False,
    )

    explosiafx_sourcexp_smoke_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcexp_smoke_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcexp_smoke_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcexp_smoke_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcexp_temperature_expanded: BoolProperty(
        name="Temperature",
        description="Expand temperature emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcexp_temperature: FloatProperty(
        name="Temperature",
        description="Temperature emission value",
        default=1000,
        min=0.0,
        soft_max=10000,
        precision=0,
        step=1000.0,
        unit="TEMPERATURE",
    )

    explosiafx_sourcexp_temperature_framelimit_enabled: BoolProperty(
        name="Temperature frame limit",
        description="Limit temperature emission to a range of frames",
        default=False,
    )

    explosiafx_sourcexp_temperature_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcexp_temperature_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcexp_temperature_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcexp_temperature_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcexp_fuel_expanded: BoolProperty(
        name="Fuel",
        description="Expand fuel emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcexp_fuel: FloatProperty(
        name="Fuel",
        description="Fuel emission value",
        default=0.2,
        min=0.0,
        soft_max=1,
    )

    explosiafx_sourcexp_fuel_framelimit_enabled: BoolProperty(
        name="Fuel frame limit",
        description="Limit fuel emission to a range of frames",
        default=False,
    )

    explosiafx_sourcexp_fuel_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcexp_fuel_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcexp_fuel_mode: EnumProperty(
        name="Mode",
        description="How to transfer source values to voxel grid",
        items=_EXPLOSIAFX_SOURCE_CHANNEL_EMIT_MODE_ITEMS,
        default="SET",
    )

    explosiafx_sourcexp_fuel_mixpc: FloatProperty(
        name="Mix",
        description="Mixing ratio between new value and existing value on voxel grid",
        default=100.0,
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcexp_pressure_expanded: BoolProperty(
        name="Pressure",
        description="Expand pressure emission settings",
        default=False,
        options={"HIDDEN"},
    )

    explosiafx_sourcexp_pressure: FloatProperty(
        name="Pressure",
        description="Pressure from source",
        default=10.0,
        soft_min=-1000.0,
        soft_max=1000.0,
    )

    explosiafx_sourcexp_pressure_framelimit_enabled: BoolProperty(
        name="Pressure frame limit",
        description="Limit pressure emission to a range of frames",
        default=False,
    )

    explosiafx_sourcexp_pressure_framelimit_min: IntProperty(
        name="Start",
        description="First frame for emission",
        default=0,
        min=0,
    )

    explosiafx_sourcexp_pressure_framelimit_max: IntProperty(
        name="End",
        description="Last frame for emission",
        default=30,
        min=0,
    )

    explosiafx_sourcexp_velocity_objpercent: FloatProperty(
        name="Velocity",
        description="Percentage of object velocity to transfer to fluid",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcexp_color_from: EnumProperty(
        name="Color From",
        description="Source of color transferred from particles to voxel grid",
        items=_get_explosiafx_sourcexp_color_items,
        default=0,
    )

    explosiafx_sourcexp_color_objpercent: FloatProperty(
        name="",
        description="Percentage of color to transfer to fluid",
        default=0.0,
        min=0.0,
        max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_sourcexp_color_custom: FloatVectorProperty(
        name="",
        description="Custom color transferred from particles to voxel grid",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=3,
        subtype="COLOR",
    )


def _sync_explosiafx_source_tree(
    _spec,
    container,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
):
    del _spec
    if obj is None:
        return
    from ..modifiers.nx_explosiafx import _sync_sourceobjects_tree

    original_props = collection_source if collection_source is not None else props
    _sync_sourceobjects_tree(obj, container, original_props, props, scene, depsgraph)


_EXPLOSIAFX_SOURCE_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EXPLOSIAFX_SOURCE_OBJECTSTREE",
    collection_attr="explosiafx_source_objects",
    tree_syncer=_sync_explosiafx_source_tree,
)

_EXPLOSIAFX_SOURCE_OBJECTS = NodeTreeDef(
    "Sources",
    item_type=NexusEFXSourceItem,
    allowed_types=["MESH", "CURVE", "NX_EMITTER"],
    nodetree_sync=_EXPLOSIAFX_SOURCE_OBJECTS_TREE_SPEC,
)


# Item sheet for collider nodetree item properties
class NexusEFXColliderItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)

    explosiafx_collider_insidenormals: BoolProperty(
        name="Inside Normals",
        description="Reverse the direction of normal vectors on the mesh surface",
        default=False,
    )

    explosiafx_collider_pressure: FloatProperty(
        name="Add Pressure",
        description="Pressure from collider",
        default=0.0,
        soft_min=-100.0,
        soft_max=100.0,
    )

    explosiafx_collider_velocity_scale: FloatProperty(
        name="Velocity Scale",
        description="Percentage of object velocity to transfer to fluid",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )


def _sync_explosiafx_collider_tree(
    _spec,
    container,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
):
    del _spec, scene
    if obj is None:
        return
    from ..modifiers.nx_explosiafx import _sync_colliderobjects_tree

    original_props = collection_source if collection_source is not None else props
    _sync_colliderobjects_tree(obj, container, original_props, props, depsgraph)


_EXPLOSIAFX_COLLIDER_OBJECTS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EXPLOSIAFX_COLLIDER_OBJECTSTREE",
    collection_attr="explosiafx_collider_objects",
    tree_syncer=_sync_explosiafx_collider_tree,
)

_EXPLOSIAFX_COLLIDER_OBJECTS = NodeTreeDef(
    "Colliders",
    item_type=NexusEFXColliderItem,
    allowed_types=["MESH"],
    nodetree_sync=_EXPLOSIAFX_COLLIDER_OBJECTS_TREE_SPEC,
)


def _force_layer_name_extra(self, context) -> bool:
    del context
    if _ensure_force_layer_curves(self):
        self.is_renamed = False
        return True
    return False


_on_efx_turbulence_type_update = auto_rename.on_trigger(
    base_name_fn=_get_force_layer_base_name,
    collection_attr="explosiafx_force_layers",
    only_if_type="TURBULENCE",
)


# Item sheet for force layers
class NexusEFXForceLayerItem(bpy.types.PropertyGroup):
    # Place-holder
    curve_id: StringProperty(name="", default="", options={"HIDDEN"})

    name: bpy.props.StringProperty(
        name="Name",
        description="Force layer type",
        default="",
        update=auto_rename.on_name_update(extra=_force_layer_name_extra),
    )

    is_renamed: BoolProperty(
        name="",
        default=False,
        options={"HIDDEN"},
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this force layer",
        default=True,
    )

    item_type: EnumProperty(
        name="Force Layer Type",
        description="Type of force layer",
        items=_get_explosiafx_force_layer_items,
        default=0,
    )

    strength: FloatProperty(
        name="Strength",
        description="Force strength",
        default=0.5,
        soft_min=0.0,
        soft_max=10.0,
        step=10,
        precision=2,
    )

    variation: FloatProperty(
        name="Variation",
        description="Force strength random variation",
        default=0.0,
        min=0.0,
        max=100.0,
        step=100,
        precision=1,
        subtype="PERCENTAGE",
    )

    # Wind-specific
    wind_dirn: FloatVectorProperty(
        name="Direction",
        description="World-space direction of wind",
        subtype="DIRECTION",
        size=3,
        default=(-1.0, 0.0, 0.0),
    )

    # Turbulence-specific
    turbulence_type: EnumProperty(
        name="Noise Type",
        description="Sub-type of turbulence to apply",
        items=_get_explosiafx_turbulence_type_items,
        default=0,
        update=_on_efx_turbulence_type_update,
    )

    length_scale: FloatProperty(
        name="Length Scale",
        description="Primary length scale of noise variations",
        default=0.4,
        min=0.0,
        soft_max=1.0,
        step=1,
        unit="LENGTH",
    )

    persistence: FloatProperty(
        name="Persistence",
        description="Amplitude decay per octave",
        default=80.0,
        min=0.0,
        soft_max=100.0,
        precision=1,
        step=100,
        subtype="PERCENTAGE",
    )

    lacunarity: FloatProperty(
        name="Lacunarity",
        description="Frequency multiplier per octave",
        default=1.0,
        min=0.0,
        soft_max=10.0,
        step=10,
        precision=1,
    )

    frequency: FloatProperty(
        name="Frequency",
        description="Noise frequency",
        default=100.0,
        min=0.0,
        soft_max=200.0,
        step=100,
        precision=1,
        subtype="PERCENTAGE",
    )

    octaves: IntProperty(
        name="Octaves",
        description="Number of noise octaves",
        default=1,
        min=1,
        max=20,
    )

    # Strength data mapping
    mapto: EnumProperty(
        name="Map To",
        description="Data source for mapping force strength",
        items=_get_explosiafx_force_datamap_items,
        default=0,
    )

    mapmin: FloatProperty(
        name="Min",
        description="Minimum of property data mapping range",
        default=0.0,
        step=100,
        precision=1,
    )

    mapmax: FloatProperty(
        name="Max",
        description="Maximum of property data mapping range",
        default=1.0,
        step=100,
        precision=1,
    )

    def get_list_icon(self):
        if self.item_type == "TURBULENCE":
            return next(
                (
                    icon
                    for id_, _, _, icon, _ in _EXPLOSIAFX_TURBULENCE_TYPE_ITEMS
                    if id_ == self.turbulence_type
                ),
                None,
            )
        return None


def _sync_explosiafx_force_layers_tree(
    _spec,
    container,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
):
    del _spec, scene
    if obj is None:
        return
    from ..modifiers.nx_explosiafx import _sync_forcelayers_tree

    original_props = collection_source if collection_source is not None else props
    _sync_forcelayers_tree(obj, container, original_props, props, depsgraph)


_EXPLOSIAFX_FORCE_LAYERS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EXPLOSIAFX_FORCES_TREE",
    collection_attr="explosiafx_force_layers",
    tree_syncer=_sync_explosiafx_force_layers_tree,
)

_EXPLOSIAFX_FORCE_LAYERS = NodeTreeDef(
    "Forces",
    item_type=NexusEFXForceLayerItem,
    menu_id="explosiafx_force_layers",
    nodetree_sync=_EXPLOSIAFX_FORCE_LAYERS_TREE_SPEC,
)


def _draw_force_layer_mapping_settings(col, item):
    col.separator(type="LINE")
    col.prop(item, "mapto", text="Map To")
    sub = col.column()
    sub.enabled = item.mapto != "NONE"
    sub.prop(item, "mapmin", text="Min")
    sub.prop(item, "mapmax", text="Max")
    NexusCurve(item.id_data, f"explosiafx_force_mapping_{item.curve_id}").draw_ui(sub, "Map")


def _draw_force_turbulence_settings(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")

    col.prop(item, "turbulence_type", text="Noise Type")
    col.prop(item, "strength", text="Strength")
    col.prop(item, "length_scale", text="Length Scale")
    col.prop(item, "octaves", text="Octaves")
    col.prop(item, "persistence", text="Persistence")
    col.prop(item, "frequency", text="Frequency")
    row = col.row()
    row.enabled = item.turbulence_type != "SIMPLEX"
    row.prop(item, "lacunarity", text="Lacunarity")

    _draw_force_layer_mapping_settings(col, item)


def _draw_force_vorticity_settings(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")

    col.prop(item, "strength", text="Strength")

    _draw_force_layer_mapping_settings(col, item)


def _draw_force_wind_settings(layout, item):
    col = layout.column()
    col.use_property_split = True
    col.separator(type="LINE")

    col.prop(item, "strength", text="Strength")
    col.prop(item, "variation", text="Variation")
    col.prop(item, "wind_dirn", text="Direction")

    _draw_force_layer_mapping_settings(col, item)


FORCE_LAYER_DRAW_FUNCS = {
    "TURBULENCE": _draw_force_turbulence_settings,
    "VORTICITY": _draw_force_vorticity_settings,
    "WIND": _draw_force_wind_settings,
}


def draw_explosiafx_force_layer_settings(layout, item):
    draw_func = FORCE_LAYER_DRAW_FUNCS.get(item.item_type)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unknown layer type", icon="ERROR")


def add_default_force_layers(props):
    layers = props.explosiafx_force_layers

    item = layers.add()
    item.item_type = "TURBULENCE"
    item.enabled = True
    auto_rename.initialize_added(item, layers, _get_force_layer_base_name(item))

    item = layers.add()
    item.item_type = "VORTICITY"
    item.enabled = True
    auto_rename.initialize_added(item, layers, _get_force_layer_base_name(item))

    props.explosiafx_force_layers_index = 0


# Item sheet for particle advect nodetree item properties
class NexusEFXPAdvectItem(bpy.types.PropertyGroup):
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    enabled: BoolProperty(name="Enabled", default=True)

    explosiafx_padvect_mode: EnumProperty(
        name="Advect Mode",
        description="The particle property that is affected by the nxExplosiaFX flow",
        items=_get_explosiafx_padvect_mode_items,
        default=2,
    )

    explosiafx_padvect_strength: FloatProperty(
        name="Strength",
        description="Strength of particle motion change by nxExplosiaFX flow",
        default=100.0,
        soft_min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_padvect_propxfertype: EnumProperty(
        name="Property Transfer",
        description="How properties are transferred to particles",
        items=_get_explosiafx_padvect_propxfertype_items,
        default=0,
    )

    explosiafx_padvect_smoke: FloatProperty(
        name="Smoke",
        description="Transfer nxExplosiaFX smoke to particles",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_padvect_temperature: FloatProperty(
        name="Temperature",
        description="Transfer nxExplosiaFX temperature to particles",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_padvect_fuel: FloatProperty(
        name="Fuel",
        description="Transfer nxExplosiaFX fuel to particles",
        default=100.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )

    explosiafx_padvect_color: FloatProperty(
        name="Color",
        description="Transfer nxExplosiaFX color channel to particles",
        default=0.0,
        min=0.0,
        soft_max=100.0,
        precision=0,
        subtype="PERCENTAGE",
    )


def _sync_explosiafx_padvect_tree(
    _spec,
    container,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
):
    del _spec
    if obj is None:
        return
    from ..modifiers.nx_explosiafx import _sync_padvect_tree

    src = collection_source if collection_source is not None else props
    _sync_padvect_tree(obj, container, src, scene, depsgraph)


_EXPLOSIAFX_PADVECT_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EXPLOSIAFX_PARTICLEADVECT_OBJECTSTREE",
    collection_attr="explosiafx_padvect_objects",
    tree_syncer=_sync_explosiafx_padvect_tree,
)

_EXPLOSIAFX_PADVECT_OBJECTS = NodeTreeDef(
    "Emitters",
    item_type=NexusEFXPAdvectItem,
    allowed_types=["NX_EMITTER"],
    nodetree_sync=_EXPLOSIAFX_PADVECT_TREE_SPEC,
)


def _sync_explosiafx_modifiers_tree(
    _spec,
    container,
    props,
    *,
    obj=None,
    scene=None,
    depsgraph=None,
    collection_source=None,
):
    del _spec
    if obj is None:
        return
    from ..modifiers.nx_explosiafx import _sync_modifiers_tree

    src = collection_source if collection_source is not None else props
    _sync_modifiers_tree(obj, container, src, scene, depsgraph)


_EXPLOSIAFX_MODIFIERS_TREE_SPEC = NodeTreeSyncSpec(
    tree_id_name="ID_NX_EXPLOSIAFX_MODIFIERS_OBJECTSTREE",
    collection_attr="explosiafx_modifiers_objects",
    tree_syncer=_sync_explosiafx_modifiers_tree,
)

_EXPLOSIAFX_MODIFIERS_OBJECTS = NodeTreeDef(
    "Modifiers",
    item_type=None,
    allowed_types=["NX_*"],
    nodetree_sync=_EXPLOSIAFX_MODIFIERS_TREE_SPEC,
)


_EXPLOSIAFX_ENUM_DEFAULTS = {
    "explosiafx_object_tab": "SIMULATION",
    "explosiafx_dynamics_tab": "FORCES",
    "explosiafx_display_tab": "VOLUME",
    "explosiafx_display_volume_drawmode": "RAYMARCHER",
    "explosiafx_display_draw_voxelgrid": "NONE",
    "ID_NX_EXPLOSIAFX_ADVECTION_SMOKE": "ACCURATE",
    "ID_NX_EXPLOSIAFX_ADVECTION_TEMP": "ACCURATE",
    "ID_NX_EXPLOSIAFX_ADVECTION_FUEL": "FAST",
    "ID_NX_EXPLOSIAFX_ADVECTION_VELOCITY": "ACCURATE",
    "ID_NX_EXPLOSIAFX_ADVECTION_COLOR": "FAST",
}


def _draw_expand_header(layout, item, expanded_prop, value_prop, label):
    """Draw a row with a twirl-down arrow on the left and ``value_prop`` beside it.

    Neighboring rows in the same panel must be indented by 1u via ``_pad_row`` so that
    their label/value split aligns with this header's.
    """
    expanded = getattr(item, expanded_prop)
    row = layout.row(align=True)
    arrow = row.row(align=True)
    arrow.ui_units_x = 1.0
    arrow.prop(
        item,
        expanded_prop,
        text="",
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    row.prop(item, value_prop, text=label)
    return expanded


def _pad_row(layout):
    """Return a row indented 1u to compensate for a neighbor's twirl-down arrow column."""
    row = layout.row(align=True)
    pad = row.row(align=True)
    pad.ui_units_x = 1.0
    pad.label(text="")
    return row


def _draw_attribute_warning(
    layout, mesh_data, attr_name, collection, allowed_types, allowed_domains=("POINT",)
):
    """Warn when the picked attribute doesn't satisfy the domain/data_type filter.
    Silent return if nothing is picked yet."""
    if not attr_name or mesh_data is None:
        return
    attr = getattr(mesh_data, collection).get(attr_name)
    if attr is None:
        row = _pad_row(layout)
        row.alert = True
        row.label(text=f"Attribute '{attr_name}' not found", icon="ERROR")
        return
    if attr.domain not in allowed_domains or attr.data_type not in allowed_types:
        row = _pad_row(layout)
        row.alert = True
        domain_label = "/".join(d.lower() for d in allowed_domains)
        row.label(text=f"Requires {domain_label}-domain " + "/".join(allowed_types), icon="ERROR")


def _draw_source_mesh_settings(layout, item):
    _pad_row(layout).prop(item, "explosiafx_sourcemesh_emit_from")
    layout.separator(type="LINE")
    if item.explosiafx_sourcemesh_emit_from == "SURFACE":
        _pad_row(layout).prop(
            item, "explosiafx_sourcemesh_surface_emitwidth", text="Surface Width"
        )
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_surface_taperwidth", text="Taper Width")
        layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcemesh_smoke_expanded",
        "explosiafx_sourcemesh_smoke",
        "Smoke",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcemesh_smoke_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcemesh_smoke_framelimit_enabled
        sub.prop(item, "explosiafx_sourcemesh_smoke_framelimit_min")
        sub.prop(item, "explosiafx_sourcemesh_smoke_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_mode", expand=True)
        if item.explosiafx_sourcemesh_smoke_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_mixpc")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_weight")
        match item.explosiafx_sourcemesh_smoke_weight:
            case "VERTEX_GROUP":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_smoke_vertex_group",
                    item.obj,
                    "vertex_groups",
                    text="Vertex Group",
                    icon="GROUP_VERTEX",
                )
            case "ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_smoke_attribute",
                    item.obj.data,
                    "attributes",
                    text="Attribute",
                    icon="MESH_DATA",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_smoke_attribute,
                    "attributes",
                    {"FLOAT"},
                )
            case "COLOR_ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_smoke_color_attribute",
                    item.obj.data,
                    "color_attributes",
                    text="Color Attribute",
                    icon="GROUP_VCOL",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_smoke_color_attribute,
                    "color_attributes",
                    {"FLOAT_COLOR", "BYTE_COLOR"},
                    allowed_domains=("POINT", "CORNER"),
                )
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_color_channel")
            case "TEXTURE":
                _pad_row(layout).template_ID(
                    item,
                    "explosiafx_sourcemesh_smoke_image",
                    new="image.new",
                    open="image.open",
                )
                _pad_row(layout).prop(
                    item, "explosiafx_sourcemesh_smoke_texture_coords", expand=True
                )
                if item.explosiafx_sourcemesh_smoke_texture_coords == "UV":
                    _pad_row(layout).prop_search(
                        item,
                        "explosiafx_sourcemesh_smoke_uv_map",
                        item.obj.data,
                        "uv_layers",
                        text="UV Map",
                        icon="GROUP_UVS",
                    )
            case "NOISE":
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_noisewt_strength")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_noisewt_lenscl")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_noisewt_octaves")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_noisewt_persistence")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_smoke_noisewt_freq")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcemesh_temperature_expanded",
        "explosiafx_sourcemesh_temperature",
        "Temperature",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcemesh_temperature_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcemesh_temperature_framelimit_enabled
        sub.prop(item, "explosiafx_sourcemesh_temperature_framelimit_min")
        sub.prop(item, "explosiafx_sourcemesh_temperature_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_mode", expand=True)
        if item.explosiafx_sourcemesh_temperature_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_mixpc")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_weight")
        match item.explosiafx_sourcemesh_temperature_weight:
            case "VERTEX_GROUP":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_temperature_vertex_group",
                    item.obj,
                    "vertex_groups",
                    text="Vertex Group",
                    icon="GROUP_VERTEX",
                )
            case "ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_temperature_attribute",
                    item.obj.data,
                    "attributes",
                    text="Attribute",
                    icon="MESH_DATA",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_temperature_attribute,
                    "attributes",
                    {"FLOAT"},
                )
            case "COLOR_ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_temperature_color_attribute",
                    item.obj.data,
                    "color_attributes",
                    text="Color Attribute",
                    icon="GROUP_VCOL",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_temperature_color_attribute,
                    "color_attributes",
                    {"FLOAT_COLOR", "BYTE_COLOR"},
                    allowed_domains=("POINT", "CORNER"),
                )
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_color_channel")
            case "TEXTURE":
                _pad_row(layout).template_ID(
                    item,
                    "explosiafx_sourcemesh_temperature_image",
                    new="image.new",
                    open="image.open",
                )
                _pad_row(layout).prop(
                    item, "explosiafx_sourcemesh_temperature_texture_coords", expand=True
                )
                if item.explosiafx_sourcemesh_temperature_texture_coords == "UV":
                    _pad_row(layout).prop_search(
                        item,
                        "explosiafx_sourcemesh_temperature_uv_map",
                        item.obj.data,
                        "uv_layers",
                        text="UV Map",
                        icon="GROUP_UVS",
                    )
            case "NOISE":
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_noisewt_strength")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_noisewt_lenscl")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_noisewt_octaves")
                _pad_row(layout).prop(
                    item, "explosiafx_sourcemesh_temperature_noisewt_persistence"
                )
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_temperature_noisewt_freq")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcemesh_fuel_expanded",
        "explosiafx_sourcemesh_fuel",
        "Fuel",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcemesh_fuel_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcemesh_fuel_framelimit_enabled
        sub.prop(item, "explosiafx_sourcemesh_fuel_framelimit_min")
        sub.prop(item, "explosiafx_sourcemesh_fuel_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_mode", expand=True)
        if item.explosiafx_sourcemesh_fuel_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_mixpc")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_weight")
        match item.explosiafx_sourcemesh_fuel_weight:
            case "VERTEX_GROUP":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_fuel_vertex_group",
                    item.obj,
                    "vertex_groups",
                    text="Vertex Group",
                    icon="GROUP_VERTEX",
                )
            case "ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_fuel_attribute",
                    item.obj.data,
                    "attributes",
                    text="Attribute",
                    icon="MESH_DATA",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_fuel_attribute,
                    "attributes",
                    {"FLOAT"},
                )
            case "COLOR_ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_fuel_color_attribute",
                    item.obj.data,
                    "color_attributes",
                    text="Color Attribute",
                    icon="GROUP_VCOL",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_fuel_color_attribute,
                    "color_attributes",
                    {"FLOAT_COLOR", "BYTE_COLOR"},
                    allowed_domains=("POINT", "CORNER"),
                )
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_color_channel")
            case "TEXTURE":
                _pad_row(layout).template_ID(
                    item,
                    "explosiafx_sourcemesh_fuel_image",
                    new="image.new",
                    open="image.open",
                )
                _pad_row(layout).prop(
                    item, "explosiafx_sourcemesh_fuel_texture_coords", expand=True
                )
                if item.explosiafx_sourcemesh_fuel_texture_coords == "UV":
                    _pad_row(layout).prop_search(
                        item,
                        "explosiafx_sourcemesh_fuel_uv_map",
                        item.obj.data,
                        "uv_layers",
                        text="UV Map",
                        icon="GROUP_UVS",
                    )
            case "NOISE":
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_noisewt_strength")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_noisewt_lenscl")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_noisewt_octaves")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_noisewt_persistence")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_fuel_noisewt_freq")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcemesh_pressure_expanded",
        "explosiafx_sourcemesh_pressure",
        "Pressure",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcemesh_pressure_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcemesh_pressure_framelimit_enabled
        sub.prop(item, "explosiafx_sourcemesh_pressure_framelimit_min")
        sub.prop(item, "explosiafx_sourcemesh_pressure_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_weight")
        match item.explosiafx_sourcemesh_pressure_weight:
            case "VERTEX_GROUP":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_pressure_vertex_group",
                    item.obj,
                    "vertex_groups",
                    text="Vertex Group",
                    icon="GROUP_VERTEX",
                )
            case "ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_pressure_attribute",
                    item.obj.data,
                    "attributes",
                    text="Attribute",
                    icon="MESH_DATA",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_pressure_attribute,
                    "attributes",
                    {"FLOAT"},
                )
            case "COLOR_ATTRIBUTE":
                _pad_row(layout).prop_search(
                    item,
                    "explosiafx_sourcemesh_pressure_color_attribute",
                    item.obj.data,
                    "color_attributes",
                    text="Color Attribute",
                    icon="GROUP_VCOL",
                )
                _draw_attribute_warning(
                    layout,
                    item.obj.data,
                    item.explosiafx_sourcemesh_pressure_color_attribute,
                    "color_attributes",
                    {"FLOAT_COLOR", "BYTE_COLOR"},
                    allowed_domains=("POINT", "CORNER"),
                )
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_color_channel")
            case "TEXTURE":
                _pad_row(layout).template_ID(
                    item,
                    "explosiafx_sourcemesh_pressure_image",
                    new="image.new",
                    open="image.open",
                )
                _pad_row(layout).prop(
                    item, "explosiafx_sourcemesh_pressure_texture_coords", expand=True
                )
                if item.explosiafx_sourcemesh_pressure_texture_coords == "UV":
                    _pad_row(layout).prop_search(
                        item,
                        "explosiafx_sourcemesh_pressure_uv_map",
                        item.obj.data,
                        "uv_layers",
                        text="UV Map",
                        icon="GROUP_UVS",
                    )
            case "NOISE":
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_noisewt_strength")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_noisewt_lenscl")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_noisewt_octaves")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_noisewt_persistence")
                _pad_row(layout).prop(item, "explosiafx_sourcemesh_pressure_noisewt_freq")
    layout.separator(type="LINE")
    flow = (
        _pad_row(layout)
        .column()
        .grid_flow(columns=2, row_major=True, even_columns=True, align=True)
    )
    flow.prop(item, "explosiafx_sourcemesh_velocity_from")
    match item.explosiafx_sourcemesh_velocity_from:
        case "OBJMOTION":
            flow.prop(item, "explosiafx_sourcemesh_velocity_objpercent")
        case "MESHPERP":
            flow.prop(item, "explosiafx_sourcemesh_velocity_perpsize")
        case "CUSTOM":
            flow.prop(item, "explosiafx_sourcemesh_velocity_custom")
    flow = (
        _pad_row(layout)
        .column()
        .grid_flow(columns=2, row_major=True, even_columns=True, align=True)
    )
    flow.prop(item, "explosiafx_sourcemesh_color_from")
    flow.prop(item, "explosiafx_sourcemesh_color_objpercent")
    match item.explosiafx_sourcemesh_color_from:
        case "ATTRIBUTE":
            _pad_row(layout).prop_search(
                item,
                "explosiafx_sourcemesh_color_attribute",
                item.obj.data,
                "color_attributes",
                text="Color Attribute",
                icon="GROUP_VCOL",
            )
            _draw_attribute_warning(
                layout,
                item.obj.data,
                item.explosiafx_sourcemesh_color_attribute,
                "color_attributes",
                {"FLOAT_COLOR", "BYTE_COLOR"},
            )
        case "CUSTOM":
            _pad_row(layout).prop(item, "explosiafx_sourcemesh_color_custom")


def _draw_source_spline_settings(layout, item):
    row = layout.row()
    row.use_property_split = False
    row.prop(item, "explosiafx_sourcespline_custom_radius")
    sub = row.row()
    sub.enabled = item.explosiafx_sourcespline_custom_radius
    sub.prop(item, "explosiafx_sourcespline_radius")

    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcespline_smoke_expanded",
        "explosiafx_sourcespline_smoke",
        "Smoke",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcespline_smoke_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcespline_smoke_framelimit_enabled
        sub.prop(item, "explosiafx_sourcespline_smoke_framelimit_min")
        sub.prop(item, "explosiafx_sourcespline_smoke_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcespline_smoke_mode", expand=True)
        if item.explosiafx_sourcespline_smoke_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcespline_smoke_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcespline_temperature_expanded",
        "explosiafx_sourcespline_temperature",
        "Temperature",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcespline_temperature_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcespline_temperature_framelimit_enabled
        sub.prop(item, "explosiafx_sourcespline_temperature_framelimit_min")
        sub.prop(item, "explosiafx_sourcespline_temperature_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcespline_temperature_mode", expand=True)
        if item.explosiafx_sourcespline_temperature_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcespline_temperature_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcespline_fuel_expanded",
        "explosiafx_sourcespline_fuel",
        "Fuel",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcespline_fuel_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcespline_fuel_framelimit_enabled
        sub.prop(item, "explosiafx_sourcespline_fuel_framelimit_min")
        sub.prop(item, "explosiafx_sourcespline_fuel_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcespline_fuel_mode", expand=True)
        if item.explosiafx_sourcespline_fuel_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcespline_fuel_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcespline_pressure_expanded",
        "explosiafx_sourcespline_pressure",
        "Pressure",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcespline_pressure_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcespline_pressure_framelimit_enabled
        sub.prop(item, "explosiafx_sourcespline_pressure_framelimit_min")
        sub.prop(item, "explosiafx_sourcespline_pressure_framelimit_max")
    layout.separator(type="LINE")

    _pad_row(layout).prop(item, "explosiafx_sourcespline_velocity_objpercent")

    flow = (
        _pad_row(layout)
        .column()
        .grid_flow(columns=2, row_major=True, even_columns=True, align=True)
    )
    flow.prop(item, "explosiafx_sourcespline_color_from")
    flow.prop(item, "explosiafx_sourcespline_color_objpercent")
    if item.explosiafx_sourcespline_color_from == "CUSTOM":
        _pad_row(layout).prop(item, "explosiafx_sourcespline_color_custom")


def _draw_source_emitter_settings(layout, item):
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcexp_smoke_expanded",
        "explosiafx_sourcexp_smoke",
        "Smoke",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcexp_smoke_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcexp_smoke_framelimit_enabled
        sub.prop(item, "explosiafx_sourcexp_smoke_framelimit_min")
        sub.prop(item, "explosiafx_sourcexp_smoke_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcexp_smoke_mode", expand=True)
        if item.explosiafx_sourcexp_smoke_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcexp_smoke_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcexp_temperature_expanded",
        "explosiafx_sourcexp_temperature",
        "Temperature",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcexp_temperature_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcexp_temperature_framelimit_enabled
        sub.prop(item, "explosiafx_sourcexp_temperature_framelimit_min")
        sub.prop(item, "explosiafx_sourcexp_temperature_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcexp_temperature_mode", expand=True)
        if item.explosiafx_sourcexp_temperature_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcexp_temperature_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcexp_fuel_expanded",
        "explosiafx_sourcexp_fuel",
        "Fuel",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcexp_fuel_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcexp_fuel_framelimit_enabled
        sub.prop(item, "explosiafx_sourcexp_fuel_framelimit_min")
        sub.prop(item, "explosiafx_sourcexp_fuel_framelimit_max")
        _pad_row(layout).prop(item, "explosiafx_sourcexp_fuel_mode", expand=True)
        if item.explosiafx_sourcexp_fuel_mode == "BLEND":
            _pad_row(layout).prop(item, "explosiafx_sourcexp_fuel_mixpc")
    layout.separator(type="LINE")
    #
    if _draw_expand_header(
        layout,
        item,
        "explosiafx_sourcexp_pressure_expanded",
        "explosiafx_sourcexp_pressure",
        "Pressure",
    ):
        row = _pad_row(layout)
        row.use_property_split = False
        row.prop(item, "explosiafx_sourcexp_pressure_framelimit_enabled")
        sub = row.row()
        sub.enabled = item.explosiafx_sourcexp_pressure_framelimit_enabled
        sub.prop(item, "explosiafx_sourcexp_pressure_framelimit_min")
        sub.prop(item, "explosiafx_sourcexp_pressure_framelimit_max")
    layout.separator(type="LINE")

    _pad_row(layout).prop(item, "explosiafx_sourcexp_velocity_objpercent")

    flow = (
        _pad_row(layout)
        .column()
        .grid_flow(columns=2, row_major=True, even_columns=True, align=True)
    )
    flow.prop(item, "explosiafx_sourcexp_color_from")
    flow.prop(item, "explosiafx_sourcexp_color_objpercent")
    if item.explosiafx_sourcexp_color_from == "CUSTOM":
        _pad_row(layout).prop(item, "explosiafx_sourcexp_color_custom")


SOURCE_ITEM_DRAW_FUNCS = {
    "MESH": _draw_source_mesh_settings,
    "CURVE": _draw_source_spline_settings,
    "NX_EMITTER": _draw_source_emitter_settings,
}


def draw_explosiafx_source_item_settings(layout, item):
    if not item.obj:
        layout.label(text="No object assigned", icon="INFO")
        return

    nx_type = item.obj.get("nexus_modifier_type")
    key = nx_type if nx_type else item.obj.type
    draw_func = SOURCE_ITEM_DRAW_FUNCS.get(key)
    if draw_func:
        draw_func(layout, item)
    else:
        layout.label(text="Unsupported source type", icon="ERROR")


def draw_explosiafx_collider_item_settings(layout, item):
    layout.prop(item, "explosiafx_collider_insidenormals")
    layout.prop(item, "explosiafx_collider_pressure")
    layout.prop(item, "explosiafx_collider_velocity_scale")


def draw_explosiafx_padvect_item_settings(layout, item):
    layout.prop(item, "explosiafx_padvect_mode")
    layout.prop(item, "explosiafx_padvect_strength")
    layout.separator(type="LINE")
    row = layout.row(align=True)
    row.prop(item, "explosiafx_padvect_propxfertype", expand=True)
    layout.prop(item, "explosiafx_padvect_smoke")
    layout.prop(item, "explosiafx_padvect_fuel")
    layout.prop(item, "explosiafx_padvect_temperature")
    layout.prop(item, "explosiafx_padvect_color")


_EXPLOSIAFX_UI_CONFIG = {
    "explosiafx_simulation_burning_expanded": {"use_property_split": False},
    "explosiafx_simulation_ambient_expanded": {"use_property_split": False},
    "explosiafx_simulation_diffusion_expanded": {"use_property_split": False},
    "explosiafx_simulation_dissipation_expanded": {"use_property_split": False},
    "explosiafx_simulation_buoyancy_expanded": {"use_property_split": False},
    "explosiafx_solver_adaptivebounds_expanded": {"use_property_split": False},
    "explosiafx_solver_walls_expanded": {"use_property_split": False},
    "explosiafx_display_volume_smoke_expanded": {"use_property_split": False},
    "explosiafx_display_volume_flame_expanded": {"use_property_split": False},
    "explosiafx_display_volume_light_expanded": {"use_property_split": False},
    **_EXPLOSIAFX_SOURCE_OBJECTS.ui_config("explosiafx_source_objects"),
    **_EXPLOSIAFX_COLLIDER_OBJECTS.ui_config("explosiafx_collider_objects"),
    **_EXPLOSIAFX_FORCE_LAYERS.ui_config("explosiafx_force_layers"),
    **_EXPLOSIAFX_PADVECT_OBJECTS.ui_config("explosiafx_padvect_objects"),
    **_EXPLOSIAFX_MODIFIERS_OBJECTS.ui_config("explosiafx_modifiers_objects"),
}
_EXPLOSIAFX_UI_CONFIG["explosiafx_source_objects"]["draw_item_settings"] = (
    draw_explosiafx_source_item_settings
)
_EXPLOSIAFX_UI_CONFIG["explosiafx_collider_objects"]["draw_item_settings"] = (
    draw_explosiafx_collider_item_settings
)
_EXPLOSIAFX_UI_CONFIG["explosiafx_force_layers"]["draw_item_settings"] = (
    draw_explosiafx_force_layer_settings
)
_EXPLOSIAFX_UI_CONFIG["explosiafx_padvect_objects"]["draw_item_settings"] = (
    draw_explosiafx_padvect_item_settings
)


def get_explosiafx_ui_config():
    return _EXPLOSIAFX_UI_CONFIG


# -----------------------------------------------------------------------------
# Theron Sync Specification
# -----------------------------------------------------------------------------
# Sync specs are now inlined on PropertyDescriptors below.
_EXPLOSIAFX_PRESET_PROPERTIES = {
    "explosiafx_object_tab",
    "ID_NX_EXPLOSIAFX_VOXELSIZE",
    "explosiafx_domain_size",
    "ID_NX_EXPLOSIAFX_RETIME",
    "ID_NX_EXPLOSIAFX_UPRES",
    "explosiafx_simulation_burning_expanded",
    "ID_NX_EXPLOSIAFX_NXBURNING_BURNRATE",
    "ID_NX_EXPLOSIAFX_NXBURNING_TEMPPRODUCTION",
    "ID_NX_EXPLOSIAFX_NXBURNING_SMOKEPRODUCTION",
    "ID_NX_EXPLOSIAFX_NXBURNING_GASEXPANSION",
    "ID_NX_EXPLOSIAFX_NXBURNING_IGNITIONTEMP",
    "explosiafx_simulation_ambient_expanded",
    "ID_NX_EXPLOSIAFX_AMBIENT_TEMP",
    "ID_NX_EXPLOSIAFX_AMBIENT_FUEL",
    "explosiafx_simulation_diffusion_expanded",
    "ID_NX_EXPLOSIAFX_DIFFUSION_SMOKE",
    "ID_NX_EXPLOSIAFX_DIFFUSION_TEMP",
    "ID_NX_EXPLOSIAFX_DIFFUSION_FUEL",
    "ID_NX_EXPLOSIAFX_DIFFUSION_VISCOSITY",
    "explosiafx_simulation_dissipation_expanded",
    "ID_NX_EXPLOSIAFX_DISSIPATION_SMOKE",
    "ID_NX_EXPLOSIAFX_DISSIPATION_TEMP",
    "ID_NX_EXPLOSIAFX_DISSIPATION_FUEL",
    "ID_NX_EXPLOSIAFX_DISSIPATION_VELOCITY_DAMP",
    "explosiafx_simulation_buoyancy_expanded",
    "ID_NX_EXPLOSIAFX_BUOYANCY_GRAVITY",
    "ID_NX_EXPLOSIAFX_BUOYANCY_SMOKE",
    "ID_NX_EXPLOSIAFX_BUOYANCY_TEMP",
    "ID_NX_EXPLOSIAFX_BUOYANCY_FUEL",
    "ID_NX_EXPLOSIAFX_PRESSUREACCURACY",
    "ID_NX_EXPLOSIAFX_PRESSUREITERS",
    "ID_NX_EXPLOSIAFX_DIFFUSIONACCURACY",
    "ID_NX_EXPLOSIAFX_DIFFUSIONITERS",
    "ID_NX_EXPLOSIAFX_CFLNUMBER",
    "ID_NX_EXPLOSIAFX_MINSUBSTEPS",
    "ID_NX_EXPLOSIAFX_MAXSUBSTEPS",
    "ID_NX_EXPLOSIAFX_ADVECTION_SMOKE",
    "ID_NX_EXPLOSIAFX_ADVECTION_TEMP",
    "ID_NX_EXPLOSIAFX_ADVECTION_FUEL",
    "ID_NX_EXPLOSIAFX_ADVECTION_VELOCITY",
    "ID_NX_EXPLOSIAFX_ADVECTION_COLOR",
    "explosiafx_solver_adaptivebounds_expanded",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_EXTRAVOXELS",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_SMOKETHRESH",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKTEMP",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TEMPTHRESH",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKFUEL",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_FUELTHRESH",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKVEL",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_VELTHRESH",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKCOLOR",
    "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_COLORTHRESH",
    "explosiafx_solver_walls_expanded",
    "ID_NX_EXPLOSIAFX_WALLS_XPLUS",
    "ID_NX_EXPLOSIAFX_WALLS_YPLUS",
    "ID_NX_EXPLOSIAFX_WALLS_ZPLUS",
    "ID_NX_EXPLOSIAFX_WALLS_XMINUS",
    "ID_NX_EXPLOSIAFX_WALLS_YMINUS",
    "ID_NX_EXPLOSIAFX_WALLS_ZMINUS",
    "explosiafx_dynamics_tab",
    "explosiafx_force_layers",
    "explosiafx_force_layers_index",
    "explosiafx_display_tab",
    "explosiafx_display_volume_show_in_rendered",
    "explosiafx_display_volume_drawupres",
    "explosiafx_display_volume_drawmode",
    "explosiafx_display_draw_voxelgrid",
    "explosiafx_display_draw_domainbox",
    "explosiafx_display_draw_solidvoxels",
    "explosiafx_display_draw_adaptivedomain",
    "explosiafx_display_vrm_flame_emit_min_t",
    "explosiafx_display_vrm_flame_intensity",
    "explosiafx_display_vrm_light_dirn",
    "explosiafx_display_vrm_light_intensity",
    "explosiafx_display_vrm_light_color",
    "explosiafx_display_vrm_hot_gas_emit_color",
    "explosiafx_display_vrm_hot_gas_emit_strength",
    "explosiafx_display_vrm_hot_gas_emit_type",
    "explosiafx_display_vrm_ray_max_steps",
    "explosiafx_display_vrm_global_transparency",
    "explosiafx_display_vrm_smoke_tint_color",
    "explosiafx_display_vrm_smoke_extinction_coef",
    "explosiafx_display_vrm_smoke_albedo",
    "explosiafx_display_vrm_smoke_scatter_anisotropy",
    "explosiafx_render_volume_mode",
    "explosiafx_render_cache_dir",
    "ID_NX_EXPLOSIAFX_SOURCE_MOTIONGAPFILL",
}


_explosiafx_force_layer_props = _EXPLOSIAFX_FORCE_LAYERS.properties("explosiafx_force_layers")
_explosiafx_source_object_props = _EXPLOSIAFX_SOURCE_OBJECTS.properties(
    "explosiafx_source_objects"
)
_explosiafx_collider_object_props = _EXPLOSIAFX_COLLIDER_OBJECTS.properties(
    "explosiafx_collider_objects"
)
_explosiafx_padvect_object_props = _EXPLOSIAFX_PADVECT_OBJECTS.properties(
    "explosiafx_padvect_objects"
)
_explosiafx_modifiers_object_props = _EXPLOSIAFX_MODIFIERS_OBJECTS.properties(
    "explosiafx_modifiers_objects"
)

_EXPLOSIAFX_DESCRIPTORS = (
    # --- Shared ---
    ENABLED_DESCRIPTOR,
    PropertyDescriptor(
        name="explosiafx_object_tab",
        prop=EnumProperty(
            name="Section",
            description="ExplosiaFX simulation settings section",
            items=_get_explosiafx_object_tab_items,
            default=0,
        ),
        preset="explosiafx_object_tab" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- DOMAIN ---
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_VOXELSIZE",
        prop=FloatProperty(
            name="Voxel Size",
            description="Size of each voxel in the simulation grid",
            default=0.04,
            min=0.001,
            unit="LENGTH",
        ),
        transform=Transform.UNIT_SCALE,
        preset="ID_NX_EXPLOSIAFX_VOXELSIZE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_domain_size",
        prop=FloatVectorProperty(
            name="Domain Size",
            description="Size of the simulation domain",
            default=(4.0, 4.0, 4.0),
            min=0.1,
            soft_max=100.0,
            unit="LENGTH",
            size=3,
            step=10,
            precision=3,
            subtype="XYZ",
        ),
        preset="explosiafx_domain_size" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_UPRES",
        prop=IntProperty(
            name="Upscaling",
            description="Resolution increase factor in upscaled simulation channels",
            default=1,
            min=1,
            max=8,
        ),
        preset="ID_NX_EXPLOSIAFX_UPRES" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_RETIME",
        prop=FloatProperty(
            name="Retiming",
            description="Alter the pace of fluid simulation timing",
            default=100.0,
            min=0.0,
            soft_max=1000.0,
            precision=1,
            subtype="PERCENTAGE",
        ),
        transform=Transform.PERCENT_TO_DECIMAL,
        preset="ID_NX_EXPLOSIAFX_RETIME" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- BURNING ---
    PropertyDescriptor(
        name="explosiafx_simulation_burning_expanded",
        prop=BoolProperty(
            name="Burning",
            description="Expand burning settings",
            default=False,
        ),
        preset="explosiafx_simulation_burning_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_NXBURNING_BURNRATE",
        prop=FloatProperty(
            name="Burn Rate",
            description="Rate at which available fuel is burned",
            default=2.0,
            min=0.0,
            soft_max=50.0,
            precision=1,
            step=10.0,
            subtype="FACTOR",
        ),
        preset="ID_NX_EXPLOSIAFX_NXBURNING_BURNRATE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_NXBURNING_TEMPPRODUCTION",
        prop=FloatProperty(
            name="Temperature Production",
            description="Temperature increase per unit of fuel burned",
            default=5000.0,
            min=0.0,
            soft_max=10000.0,
            precision=0,
            step=1000.0,
            unit="TEMPERATURE",
        ),
        preset="ID_NX_EXPLOSIAFX_NXBURNING_TEMPPRODUCTION" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_NXBURNING_SMOKEPRODUCTION",
        prop=FloatProperty(
            name="Smoke Production",
            description="Smoke produced per unit of fuel burned",
            default=1.0,
            min=0.0,
            soft_max=10.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_NXBURNING_SMOKEPRODUCTION" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_NXBURNING_GASEXPANSION",
        prop=FloatProperty(
            name="Gas Expansion",
            description="Combustion-induced pressure expansion",
            default=2.0,
            min=0.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_NXBURNING_GASEXPANSION" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_NXBURNING_IGNITIONTEMP",
        prop=FloatProperty(
            name="Ignition Temperature",
            description="Temperature above which burning begins",
            default=600.0,
            min=0.0,
            soft_max=10000.0,
            precision=0,
            step=1000.0,
            unit="TEMPERATURE",
        ),
        preset="ID_NX_EXPLOSIAFX_NXBURNING_IGNITIONTEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- AMBIENT ---
    PropertyDescriptor(
        name="explosiafx_simulation_ambient_expanded",
        prop=BoolProperty(
            name="Ambient Conditions",
            description="Conditions of the environment far from emission sources",
            default=False,
        ),
        preset="explosiafx_simulation_ambient_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_AMBIENT_TEMP",
        prop=FloatProperty(
            name="Ambient Temperature",
            description="Temperature of environment far from emission sources",
            default=300.0,
            min=0.0,
            soft_max=1000.0,
            precision=0,
            step=100.0,
            unit="TEMPERATURE",
        ),
        preset="ID_NX_EXPLOSIAFX_AMBIENT_TEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_AMBIENT_FUEL",
        prop=FloatProperty(
            name="Ambient Fuel",
            description="Fuel concentration in environment far from emission sources",
            default=0.0,
            min=0.0,
            soft_max=1.0,
            precision=2,
            step=1.0,
        ),
        preset="ID_NX_EXPLOSIAFX_AMBIENT_FUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- DIFFUSION ---
    PropertyDescriptor(
        name="explosiafx_simulation_diffusion_expanded",
        prop=BoolProperty(
            name="Diffusion",
            description="Diffusion (spreading and smoothing) of fields",
            default=False,
        ),
        preset="explosiafx_simulation_diffusion_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSION_SMOKE",
        prop=FloatProperty(
            name="Smoke Diffusion",
            description="Smoke diffusion coefficient",
            default=0.0,
            min=0.0,
            soft_max=1000.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DIFFUSION_SMOKE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSION_TEMP",
        prop=FloatProperty(
            name="Temperature Diffusion",
            description="Temperature diffusion coefficient",
            default=0.0,
            min=0.0,
            soft_max=1000.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DIFFUSION_TEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSION_FUEL",
        prop=FloatProperty(
            name="Fuel Diffusion",
            description="Fuel diffusion coefficient",
            default=0.0,
            min=0.0,
            soft_max=1000.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DIFFUSION_FUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSION_VISCOSITY",
        prop=FloatProperty(
            name="Viscosity",
            description="Velocity diffusion (viscosity) coefficient",
            default=0.0,
            min=0.0,
            soft_max=1000.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DIFFUSION_VISCOSITY" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- DISSIPATION ---
    PropertyDescriptor(
        name="explosiafx_simulation_dissipation_expanded",
        prop=BoolProperty(
            name="Dissipation",
            description="Dissipation (decay) of fields",
            default=False,
        ),
        preset="explosiafx_simulation_dissipation_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DISSIPATION_SMOKE",
        prop=FloatProperty(
            name="Smoke Dissipation",
            description="Smoke decay coefficient",
            default=1.0,
            min=0.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DISSIPATION_SMOKE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DISSIPATION_TEMP",
        prop=FloatProperty(
            name="Temperature Dissipation",
            description="Temperature decay coefficient",
            default=0.5,
            min=0.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DISSIPATION_TEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DISSIPATION_FUEL",
        prop=FloatProperty(
            name="Fuel Dissipation",
            description="Fuel decay coefficient",
            default=0.0,
            min=0.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DISSIPATION_FUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DISSIPATION_VELOCITY_DAMP",
        prop=FloatProperty(
            name="Velocity Dissipation",
            description="Velocity decay coefficient",
            default=0.0,
            min=0.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_DISSIPATION_VELOCITY_DAMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- BUOYANCY ---
    PropertyDescriptor(
        name="explosiafx_simulation_buoyancy_expanded",
        prop=BoolProperty(
            name="Buoyancy",
            description="Composition- and temperature-dependent buoyant acceleration",
            default=False,
        ),
        preset="explosiafx_simulation_buoyancy_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_BUOYANCY_GRAVITY",
        prop=FloatProperty(
            name="Gravity",
            description="Strength of gravitational acceleration",
            default=9.81,
            min=0.0,
            soft_max=20.0,
            precision=3,
            step=1.0,
            unit="ACCELERATION",
        ),
        transform=Transform.UNIT_SCALE,
        preset="ID_NX_EXPLOSIAFX_BUOYANCY_GRAVITY" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_BUOYANCY_SMOKE",
        prop=FloatProperty(
            name="Smoke Buoyancy",
            description="Smoke buoyancy coefficient",
            default=4.0,
            soft_min=-100.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_BUOYANCY_SMOKE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_BUOYANCY_TEMP",
        prop=FloatProperty(
            name="Temperature Buoyancy",
            description="Temperature buoyancy coefficient",
            default=0.04,
            soft_min=-1.0,
            soft_max=1.0,
            precision=2,
            step=1.0,
        ),
        preset="ID_NX_EXPLOSIAFX_BUOYANCY_TEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_BUOYANCY_FUEL",
        prop=FloatProperty(
            name="Fuel Buoyancy",
            description="Fuel buoyancy coefficient",
            default=-20.0,
            soft_min=-100.0,
            soft_max=100.0,
            precision=1,
            step=10.0,
        ),
        preset="ID_NX_EXPLOSIAFX_BUOYANCY_FUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- SOURCES ---
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_SOURCE_MOTIONGAPFILL",
        prop=IntProperty(
            name="Motion Gap Fill",
            description=(
                "Set the number of additional images to fill inter-frame gaps"
                " in emission from moving sources"
            ),
            default=0,
            min=0,
            max=10,
        ),
        preset="ID_NX_EXPLOSIAFX_SOURCE_MOTIONGAPFILL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- SOLVERS ---
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_CHANNEL_SMOKE",
        prop=BoolProperty(
            name="Smoke",
            description="Enable smoke channel in simulation",
            default=True,
        ),
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_CHANNEL_FUEL",
        prop=BoolProperty(
            name="Fuel",
            description="Enable fuel channel in simulation",
            default=True,
        ),
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_CHANNEL_TEMP",
        prop=BoolProperty(
            name="Temperature",
            description="Enable temperature channel in simulation",
            default=True,
        ),
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_CHANNEL_COLOR",
        prop=BoolProperty(
            name="Color",
            description="Enable color channel in simulation",
            default=False,
        ),
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_PRESSUREACCURACY",
        prop=FloatProperty(
            name="Accuracy",
            description="Set accuracy for termination of the pressure solver",
            default=20.0,
            min=0.0,
            max=100.0,
            precision=0,
            step=100.0,
            subtype="PERCENTAGE",
        ),
        transform=Transform.PERCENT_TO_DECIMAL,
        preset="ID_NX_EXPLOSIAFX_PRESSUREACCURACY" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_PRESSUREITERS",
        prop=IntProperty(
            name="Iterations",
            description="Set the maximum iterations allowed for the solver to find the pressure",
            default=10,
            min=0,
            soft_max=100,
        ),
        preset="ID_NX_EXPLOSIAFX_PRESSUREITERS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSIONACCURACY",
        prop=FloatProperty(
            name="Accuracy",
            description="Set accuracy for termination of the diffusion solver",
            default=50.0,
            min=0.0,
            max=100.0,
            precision=0,
            step=100.0,
            subtype="PERCENTAGE",
        ),
        transform=Transform.PERCENT_TO_DECIMAL,
        preset="ID_NX_EXPLOSIAFX_DIFFUSIONACCURACY" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_DIFFUSIONITERS",
        prop=IntProperty(
            name="Iterations",
            description="Set the maximum iterations allowed for the diffusion solvers",
            default=10,
            min=0,
            soft_max=20,
        ),
        preset="ID_NX_EXPLOSIAFX_DIFFUSIONITERS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- ADVECTION ---
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_CFLNUMBER",
        prop=FloatProperty(
            name="CFL Number",
            description="Set the CFL criterion for automatically adjusting substep count",
            default=5.0,
            min=0.0,
            soft_max=5.0,
            precision=2,
            step=10,
        ),
        preset="ID_NX_EXPLOSIAFX_CFLNUMBER" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_MINSUBSTEPS",
        prop=IntProperty(
            name="Min Substeps",
            description="Minimum number of sub-frame steps taken each frame advance",
            default=1,
            min=1,
        ),
        preset="ID_NX_EXPLOSIAFX_MINSUBSTEPS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_MAXSUBSTEPS",
        prop=IntProperty(
            name="Max Substeps",
            description="Maximum number of sub-frame steps taken each frame advance",
            default=3,
            min=1,
        ),
        preset="ID_NX_EXPLOSIAFX_MAXSUBSTEPS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADVECTION_SMOKE",
        prop=EnumProperty(
            name="Smoke",
            description="Method for advecting smoke channel",
            items=_get_explosiafx_advection_method_items,
            default=1,
        ),
        enum_map=_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP,
        preset="ID_NX_EXPLOSIAFX_ADVECTION_SMOKE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADVECTION_TEMP",
        prop=EnumProperty(
            name="Temperature",
            description="Method for advecting temperature channel",
            items=_get_explosiafx_advection_method_items,
            default=1,
        ),
        enum_map=_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP,
        preset="ID_NX_EXPLOSIAFX_ADVECTION_TEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADVECTION_FUEL",
        prop=EnumProperty(
            name="Fuel",
            description="Method for advecting fuel channel",
            items=_get_explosiafx_advection_method_items,
            default=0,
        ),
        enum_map=_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP,
        preset="ID_NX_EXPLOSIAFX_ADVECTION_FUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADVECTION_VELOCITY",
        prop=EnumProperty(
            name="Velocity",
            description="Method for advecting velocity field",
            items=_get_explosiafx_advection_method_items,
            default=1,
        ),
        enum_map=_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP,
        preset="ID_NX_EXPLOSIAFX_ADVECTION_VELOCITY" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADVECTION_COLOR",
        prop=EnumProperty(
            name="Color",
            description="Method for advecting color channel",
            items=_get_explosiafx_advection_method_items,
            default=0,
        ),
        enum_map=_EXPLOSIAFX_ADVECTIONMETHODS_ENUM_MAP,
        preset="ID_NX_EXPLOSIAFX_ADVECTION_COLOR" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- ADAPTIVE BOUNDS ---
    PropertyDescriptor(
        name="explosiafx_solver_adaptivebounds_expanded",
        prop=BoolProperty(
            name="Adaptive Bounds",
            description="Dynamically adjust size of active solver domain",
            default=False,
        ),
        preset="explosiafx_solver_adaptivebounds_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE",
        prop=BoolProperty(
            name="Enabled",
            description="Dynamically adjust size of active solver domain",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_EXTRAVOXELS",
        prop=IntProperty(
            name="Extra Voxels",
            description="Extra padding voxels at the boundary of the adaptive domain",
            default=4,
            min=0,
            soft_max=10,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_EXTRAVOXELS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE",
        prop=BoolProperty(
            name="Smoke",
            description="Adaptive bounds expand with smoke channel",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_SMOKETHRESH",
        prop=FloatProperty(
            name="Threshold",
            description="Smoke values above threshold are inside adaptive domain",
            default=0.01,
            min=0.0,
            soft_max=1.0,
            precision=2,
            step=1,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_SMOKETHRESH" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKTEMP",
        prop=BoolProperty(
            name="Temperature",
            description="Adaptive bounds expand with temperature channel",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKTEMP" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TEMPTHRESH",
        prop=FloatProperty(
            name="Threshold",
            description="Temperature values above threshold are inside adaptive domain",
            default=500.0,
            min=0.0,
            soft_max=1000.0,
            step=1000,
            subtype="TEMPERATURE",
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TEMPTHRESH" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKFUEL",
        prop=BoolProperty(
            name="Fuel",
            description="Adaptive bounds expand with fuel channel",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKFUEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_FUELTHRESH",
        prop=FloatProperty(
            name="Threshold",
            description="Fuel values above threshold are inside adaptive domain",
            default=0.01,
            min=0.0,
            soft_max=1.0,
            precision=2,
            step=1,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_FUELTHRESH" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKVEL",
        prop=BoolProperty(
            name="Velocity",
            description="Adaptive bounds expand with velocity field",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKVEL" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_VELTHRESH",
        prop=FloatProperty(
            name="Threshold",
            description="Velocity values above threshold are inside adaptive domain",
            default=250.0,
            min=0.0,
            soft_max=1000.0,
            step=1000,
            unit="VELOCITY",
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_VELTHRESH" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKCOLOR",
        prop=BoolProperty(
            name="Color",
            description="Adaptive bounds expand with color channel",
            default=True,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKCOLOR" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_COLORTHRESH",
        prop=FloatProperty(
            name="Threshold",
            description="Color values above threshold are inside adaptive domain",
            default=0.01,
            min=0.0,
            soft_max=1.0,
            precision=2,
            step=1,
        ),
        preset="ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_COLORTHRESH" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_dynamics_tab",
        prop=EnumProperty(
            name="Section",
            description="ExplosiaFX dynamics settings section",
            items=_get_explosiafx_dynamics_tab_items,
            default=0,
        ),
        preset="explosiafx_dynamics_tab" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_tab",
        prop=EnumProperty(
            name="Section",
            description="ExplosiaFX display settings section",
            items=_get_explosiafx_display_tab_items,
            default=0,
        ),
        preset="explosiafx_display_tab" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_volume_show_in_rendered",
        prop=BoolProperty(
            name="Show in Rendered Modes",
            description=(
                "Continue to show the NeXus volume preview when the viewport "
                "is in Material Preview or Rendered shading. Disable to let Cycles/Eevee "
                "draw the volume via its material without the preview overlapping."
            ),
            default=False,
        ),
        preset="explosiafx_display_volume_show_in_rendered" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_volume_drawupres",
        prop=BoolProperty(
            name="Draw Upscaled",
            description="Toggle between drawing volume data from upscaled and base simualtions",
            default=True,
        ),
        preset="explosiafx_display_volume_drawupres" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_volume_drawmode",
        prop=EnumProperty(
            name="Draw Mode",
            description="Renderer for displaying volume data in viewport",
            items=_get_explosiafx_display_volume_drawmode_items,
            default=2,
        ),
        preset="explosiafx_display_volume_drawmode" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # Walls
    PropertyDescriptor(
        name="explosiafx_solver_walls_expanded",
        prop=BoolProperty(
            name="Domain Boundary Walls",
            description="Close domain boundary walls",
            default=False,
        ),
        preset="explosiafx_solver_walls_expanded" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_XPLUS",
        prop=BoolProperty(
            name="+X",
            description="Closed wall on domain +X",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_XPLUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_YPLUS",
        prop=BoolProperty(
            name="+Y",
            description="Closed wall on domain +Y",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_YPLUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_ZPLUS",
        prop=BoolProperty(
            name="+Z",
            description="Closed wall on domain +Z",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_ZPLUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_XMINUS",
        prop=BoolProperty(
            name="-X",
            description="Closed wall on domain -X",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_XMINUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_YMINUS",
        prop=BoolProperty(
            name="-Y",
            description="Closed wall on domain -Y",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_YMINUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="ID_NX_EXPLOSIAFX_WALLS_ZMINUS",
        prop=BoolProperty(
            name="-Z",
            description="Closed wall on domain -Z",
            default=False,
        ),
        preset="ID_NX_EXPLOSIAFX_WALLS_ZMINUS" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_draw_voxelgrid",
        prop=EnumProperty(
            name="Draw Grid",
            description="Visualize the simulation grid",
            items=_get_explosiafx_display_draw_voxelgrid_items,
            default=0,  # 0 = None
        ),
        preset="explosiafx_display_draw_voxelgrid" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_draw_domainbox",
        prop=BoolProperty(
            name="Draw Domain",
            description="Draw the outline of the full simulation domain",
            default=True,
        ),
        preset="explosiafx_display_draw_domainbox" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_draw_adaptivedomain",
        prop=BoolProperty(
            name="Draw Adaptive Bounds",
            description="Draw a marker for voxels that are within the simulation adaptive bounds",
            default=False,
        ),
        preset="explosiafx_display_draw_adaptivedomain" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_draw_solidvoxels",
        prop=BoolProperty(
            name="Draw Solid Voxels",
            description="Draw a marker for voxels that are treated as solid colliders",
            default=False,
        ),
        preset="explosiafx_display_draw_solidvoxels" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # ---------------------------------------------------------------------------
    # HUD vel field
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_draw_velocity",
        prop=BoolProperty(
            name="Draw Velocity Field",
            description="Visualize particle velocities",
            default=False,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_velocity_speed_auto_range",
        prop=BoolProperty(
            name="Auto Range",
            description=("Automatically determine speed color range"),
            default=True,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_velocity_speed_transparency",
        prop=FloatProperty(
            name="Transparency",
            description="Global transparency of velocity field",
            default=20.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_velocity_speed_min",
        prop=FloatProperty(
            name="Speed Min",
            description="Minimum speed for color mapping",
            default=0.0,
            min=0.0,
            soft_max=10.0,
            unit="VELOCITY",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_velocity_speed_max",
        prop=FloatProperty(
            name="Speed Max",
            description="Maximum speed for color mapping",
            default=10.0,
            min=0.0,
            soft_max=2000.0,
            unit="VELOCITY",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_velocity_trail_length",
        prop=FloatProperty(
            name="Trail Length",
            description=("Length of velocity trails for visualization"),
            default=0.2,
            min=0.0,
            soft_max=1.0,
            unit="LENGTH",
        ),
    ),
    # ---------------------------------------------------------------------------
    # Viewport slicer
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_slicer_channel",
        prop=EnumProperty(
            name="Display Channel",
            description="Volume field channel to display through the slice stack",
            items=_get_explosiafx_display_slicer_channel_items,
            default=0,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_count",
        prop=IntProperty(
            name="Slices",
            description="Number of view-aligned slicing planes",
            default=256,
            min=1,
            max=1024,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_transparency",
        prop=FloatProperty(
            name="Transparency",
            description="Global transparency of the slice stack",
            default=20.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_speed_min",
        prop=FloatProperty(
            name="Speed Min",
            description="Lower velocity bound for the speed channel mapping",
            default=0.0,
            min=0.0,
            max=5.0,
            unit="VELOCITY",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_speed_max",
        prop=FloatProperty(
            name="Speed Max",
            description="Upper velocity bound for the speed channel mapping",
            default=2.0,
            min=0.0,
            max=5.0,
            unit="VELOCITY",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_smoke_min_opacity_clip",
        prop=FloatProperty(
            name="Min Opacity Clip",
            description="Discard slice contributions below this opacity threshold",
            default=0.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_smoke_max_opacity_clip",
        prop=FloatProperty(
            name="Max Opacity Clip",
            description="Saturate slice contributions above this opacity threshold",
            default=100.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_smoke_transparency",
        prop=FloatProperty(
            name="Smoke Transparency",
            description="Transparency applied to the smoke channel",
            default=30.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_fuel_min_opacity_clip",
        prop=FloatProperty(
            name="Min Opacity Clip",
            description="Discard slice contributions below this opacity threshold",
            default=0.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_fuel_max_opacity_clip",
        prop=FloatProperty(
            name="Max Opacity Clip",
            description="Saturate slice contributions above this opacity threshold",
            default=100.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_fuel_transparency",
        prop=FloatProperty(
            name="Fuel Transparency",
            description="Transparency applied to the fuel channel",
            default=80.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_fuel_min",
        prop=FloatProperty(
            name="Min Fuel",
            description="Lower bound of the fuel field range mapped through the transfer function",
            default=0.0,
            min=0.0,
            soft_max=1.0,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_fuel_max",
        prop=FloatProperty(
            name="Max Fuel",
            description="Upper bound of the fuel field range mapped through the transfer function",
            default=0.25,
            min=0.0,
            soft_max=1.0,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_color_mode",
        prop=EnumProperty(
            name="Color Mode",
            description="Source of the temperature channel's color mapping",
            items=_get_explosiafx_display_slicer_temp_color_mode_items,
            default=0,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_min_opacity_clip",
        prop=FloatProperty(
            name="Min Opacity Clip",
            description="Discard slice contributions below this opacity threshold",
            default=0.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_max_opacity_clip",
        prop=FloatProperty(
            name="Max Opacity Clip",
            description="Saturate slice contributions above this opacity threshold",
            default=100.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_transparency",
        prop=FloatProperty(
            name="Temperature Transparency",
            description="Transparency applied to the temperature channel",
            default=10.0,
            min=0.0,
            max=100.0,
            subtype="PERCENTAGE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_min",
        prop=FloatProperty(
            name="Min Temperature",
            description=(
                "Lower bound of the temperature range mapped through the manual color gradient"
            ),
            default=300.0,
            min=0.0,
            soft_max=10000.0,
            step=10000,
            precision=0,
            unit="TEMPERATURE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_max",
        prop=FloatProperty(
            name="Max Temperature",
            description=(
                "Upper bound of the temperature range mapped through the manual color gradient"
            ),
            default=5000.0,
            min=0.0,
            soft_max=10000.0,
            step=10000,
            precision=0,
            unit="TEMPERATURE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_bb_power",
        prop=IntProperty(
            name="Blackbody Power",
            description=(
                "Stefan-Boltzmann power exponent applied to the blackbody emission intensity"
            ),
            default=4,
            min=0,
            max=10,
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_bb_min",
        prop=FloatProperty(
            name="Blackbody Min T",
            description="Lower bound of the blackbody emission curve",
            default=300.0,
            min=0.0,
            soft_max=16000.0,
            step=10000,
            precision=0,
            unit="TEMPERATURE",
        ),
    ),
    PropertyDescriptor(
        name="explosiafx_display_slicer_temp_bb_max",
        prop=FloatProperty(
            name="Blackbody Max T",
            description="Upper bound of the blackbody emission curve",
            default=4300.0,
            min=0.0,
            soft_max=16000.0,
            step=10000,
            precision=0,
            unit="TEMPERATURE",
        ),
    ),
    # ---------------------------------------------------------------------------
    # Viewport ray marcher — flame emission
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_vrm_flame_emit_min_t",
        prop=FloatProperty(
            name="Flame Emit Above T",
            description="Temperature (K) above which flame emission begins",
            min=0.0,
            default=1000.0,
            step=1000,
            precision=0,
            unit="TEMPERATURE",
        ),
        preset="explosiafx_display_vrm_flame_emit_min_t" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_flame_intensity",
        prop=FloatProperty(
            name="Hot Soot Emit Intensity",
            description="Scale factor for flame brightness from glowing smoke / soot",
            min=0.0,
            soft_max=100.0,
            default=10.0,
            step=10,
            precision=1,
        ),
        preset="explosiafx_display_vrm_flame_intensity" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # ---------------------------------------------------------------------------
    # Viewport ray marcher — ambient lighting
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_vrm_light_dirn",
        prop=FloatVectorProperty(
            name="Direction",
            description="World-space direction toward the light source",
            subtype="DIRECTION",
            size=3,
            default=(0.0, 0.9, 0.44),
        ),
        preset="explosiafx_display_vrm_light_dirn" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_light_intensity",
        prop=FloatProperty(
            name="Intensity",
            description="Strength of the ambient directional light",
            min=0.0,
            default=1.0,
            step=10,
            precision=2,
        ),
        preset="explosiafx_display_vrm_light_intensity" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_light_color",
        prop=FloatVectorProperty(
            name="Color",
            description="Color of the ambient directional light",
            subtype="COLOR",
            size=3,
            min=0.0,
            max=1.0,
            default=(1.0, 1.0, 1.0),
        ),
        preset="explosiafx_display_vrm_light_color" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # ---------------------------------------------------------------------------
    # Viewport ray marcher — hot gas emission
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_vrm_hot_gas_emit_color",
        prop=FloatVectorProperty(
            name="Hot Gas Color",
            description="Custom emission color for hot gas",
            subtype="COLOR",
            size=3,
            min=0.0,
            max=1.0,
            default=(0.2, 0.4, 1.0),
        ),
        preset="explosiafx_display_vrm_hot_gas_emit_color" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_hot_gas_emit_strength",
        prop=FloatProperty(
            name="Hot Gas Emit Intensity",
            description="Flame emission intensity for hot gas",
            min=0.0,
            soft_max=100.0,
            default=5.0,
            step=10,
            precision=1,
        ),
        preset="explosiafx_display_vrm_hot_gas_emit_strength" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_hot_gas_emit_type",
        prop=EnumProperty(
            name="Hot Gas Color Mode",
            description="How to color the radiation from hot gases",
            items=_EXPLOSIAFX_DISPLAY_VRM_GASEMIT_ITEMS,
            default="BB",
        ),
        preset="explosiafx_display_vrm_hot_gas_emit_type" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # ---------------------------------------------------------------------------
    # Viewport ray marcher — ray marching quality
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_vrm_ray_max_steps",
        prop=IntProperty(
            name="Ray Max Steps",
            description="Maximum number of ray marching steps per pixel",
            min=1,
            soft_max=500,
            default=150,
        ),
        preset="explosiafx_display_vrm_ray_max_steps" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_global_transparency",
        prop=FloatProperty(
            name="Transparency",
            description="Global transparency applied to the nxExplosiaFX visualization",
            min=0.0,
            max=100.0,
            default=0.0,
            step=100,
            precision=1,
            subtype="PERCENTAGE",
        ),
        preset="explosiafx_display_vrm_global_transparency" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # ---------------------------------------------------------------------------
    # Viewport ray marcher — smoke scattering appearance
    # ---------------------------------------------------------------------------
    PropertyDescriptor(
        name="explosiafx_display_vrm_smoke_tint_color",
        prop=FloatVectorProperty(
            name="Smoke Tint",
            description="Per-channel absorption tint of the smoke",
            subtype="COLOR",
            size=3,
            min=0.0,
            max=1.0,
            default=(1.0, 1.0, 1.0),
        ),
        preset="explosiafx_display_vrm_smoke_tint_color" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_smoke_extinction_coef",
        prop=FloatProperty(
            name="Smoke Extinction",
            description="Molar extinction coefficient of the smoke (higher = denser)",
            min=0.0,
            default=80.0,
            step=100,
            precision=1,
        ),
        preset="explosiafx_display_vrm_smoke_extinction_coef" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_smoke_albedo",
        prop=FloatProperty(
            name="Smoke Albedo",
            description="Single-scattering albedo: 0 = pure absorption, 1 = pure scattering",
            min=0.0,
            max=1.0,
            default=0.8,
            step=1,
            precision=2,
        ),
        preset="explosiafx_display_vrm_smoke_albedo" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_display_vrm_smoke_scatter_anisotropy",
        prop=FloatProperty(
            name="Smoke Scatter Anisotropy",
            description=(
                "Henyey-Greenstein scatter anisotropy: -1 back-scatter, 0 isotropic, +1 forward"
            ),
            min=-1.0,
            max=1.0,
            default=0.4,
            step=1,
            precision=2,
        ),
        preset="explosiafx_display_vrm_smoke_scatter_anisotropy" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    # --- RENDER OUTPUT (Eevee / Cycles via OpenVDB Files) ---
    PropertyDescriptor(
        name="explosiafx_render_volume_mode",
        prop=EnumProperty(
            name="VDB Output",
            description="When to write per-frame OpenVDB files",
            items=[
                ("OFF", "Off", "Do not write any OpenVDB files"),
                (
                    "ON_RENDER",
                    "On Render",
                    "Write the VDB only when rendering (F12 / animation render)",
                ),
                (
                    "LIVE",
                    "Live",
                    "Write the VDB on every frame change and on render — viewport in "
                    "Cycles/Eevee shading mode stays in sync while scrubbing",
                ),
            ],
            default="OFF",
        ),
        preset="explosiafx_render_volume_mode" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_render_cache_dir",
        prop=StringProperty(
            name="VDB Output Directory",
            description=(
                "Directory for per-frame temporary .vdb files. "
                "Leave empty to use Blender's session temp directory"
            ),
            default="",
            subtype="DIR_PATH",
        ),
        preset="explosiafx_render_cache_dir" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_render_volume_obj",
        prop=PointerProperty(
            name="Render Volume Object",
            description="Linked Volume datablock that exposes the simulation to renderers",
            type=bpy.types.Object,
            poll=lambda self, obj: obj.type == "VOLUME",
        ),
        preset=False,
    ),
    PropertyDescriptor(
        name="explosiafx_force_layers",
        prop=_explosiafx_force_layer_props["explosiafx_force_layers"],
        preset="explosiafx_force_layers" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_force_layers_index",
        prop=_explosiafx_force_layer_props["explosiafx_force_layers_index"],
        preset="explosiafx_force_layers_index" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_source_objects",
        prop=_explosiafx_source_object_props["explosiafx_source_objects"],
        preset="explosiafx_source_objects" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_source_objects_index",
        prop=_explosiafx_source_object_props["explosiafx_source_objects_index"],
        preset="explosiafx_source_objects_index" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_source_objects_drop_target",
        prop=_explosiafx_source_object_props.get("explosiafx_source_objects_drop_target"),
        preset=False,
    ),
    PropertyDescriptor(
        name="explosiafx_collider_objects",
        prop=_explosiafx_collider_object_props["explosiafx_collider_objects"],
        preset="explosiafx_collider_objects" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_collider_objects_index",
        prop=_explosiafx_collider_object_props["explosiafx_collider_objects_index"],
        preset="explosiafx_collider_objects_index" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_collider_objects_drop_target",
        prop=_explosiafx_collider_object_props.get("explosiafx_collider_objects_drop_target"),
        preset=False,
    ),
    PropertyDescriptor(
        name="explosiafx_padvect_objects",
        prop=_explosiafx_padvect_object_props["explosiafx_padvect_objects"],
        preset="explosiafx_padvect_objects" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_padvect_objects_index",
        prop=_explosiafx_padvect_object_props["explosiafx_padvect_objects_index"],
        preset="explosiafx_padvect_objects_index" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_padvect_objects_drop_target",
        prop=_explosiafx_padvect_object_props.get("explosiafx_padvect_objects_drop_target"),
        preset=False,
    ),
    PropertyDescriptor(
        name="explosiafx_modifiers_objects",
        prop=_explosiafx_modifiers_object_props["explosiafx_modifiers_objects"],
        preset="explosiafx_modifiers_objects" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_modifiers_objects_index",
        prop=_explosiafx_modifiers_object_props["explosiafx_modifiers_objects_index"],
        preset="explosiafx_modifiers_objects_index" in _EXPLOSIAFX_PRESET_PROPERTIES,
    ),
    PropertyDescriptor(
        name="explosiafx_modifiers_objects_drop_target",
        prop=_explosiafx_modifiers_object_props.get("explosiafx_modifiers_objects_drop_target"),
        preset=False,
    ),
)

SPEC = ModifierPropertySpec(
    modifier_type="NX_EXPLOSIAFX",
    item_classes=(
        NexusEFXSourceItem,
        NexusEFXColliderItem,
        NexusEFXForceLayerItem,
        NexusEFXPAdvectItem,
    ),
    enum_builders=(build_explosiafx_enum_items,),
    enum_defaults=_EXPLOSIAFX_ENUM_DEFAULTS,
    descriptors=_EXPLOSIAFX_DESCRIPTORS,
    nodetree_sync=combine_nodetree_sync(
        _EXPLOSIAFX_SOURCE_OBJECTS,
        _EXPLOSIAFX_COLLIDER_OBJECTS,
        _EXPLOSIAFX_FORCE_LAYERS,
        _EXPLOSIAFX_PADVECT_OBJECTS,
        _EXPLOSIAFX_MODIFIERS_OBJECTS,
    ),
)


register_collection_preset(
    "NX_EXPLOSIAFX",
    CollectionPresetSpec(
        collection_attr="explosiafx_force_layers",
        menu_id="explosiafx_force_layers",
        curve_specs=EXPLOSIAFX_FORCE_DATAMAP_CURVE_SPECS,
        suffix_attr="curve_id",
    ),
)

# `explosiafx_source_objects` / `explosiafx_collider_objects`: scene-link lists.
