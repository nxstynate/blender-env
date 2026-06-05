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

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)

from ..libs.modifier_spec import ENABLED_DESCRIPTOR, ModifierPropertySpec, PropertyDescriptor
from ..libs.theron_sync import Transform

_FALLOFF_MODE_DEFS = {
    "ID_NX_FALLOFF_MODE_BOX": {
        "name": "Box",
        "description": "Box-shaped falloff",
        "icon_name": "nx_falloff_box",
    },
    "ID_NX_FALLOFF_MODE_LINEAR": {
        "name": "Linear",
        "description": "Linear falloff",
        "icon_name": "nx_falloff_linear",
    },
    "ID_NX_FALLOFF_MODE_SPHERE": {
        "name": "Sphere",
        "description": "Sphere-shaped falloff",
        "icon_name": "nx_falloff_sphere",
    },
    "ID_NX_FALLOFF_MODE_NOISE": {
        "name": "Noise",
        "description": "Noise-based falloff",
        "icon_name": "nx_falloff_noise",
    },
}

_FALLOFF_MODE_ITEMS = []

_FALLOFF_NOISE_TYPE_DEFS = {
    "ID_NX_FALLOFF_NOISE_TYPE_SIMPLEX": {
        "name": "Simplex",
        "description": "Simplex noise",
        "icon_name": "nx_noise_simplex",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_CURL": {
        "name": "Curl",
        "description": "Curl noise",
        "icon_name": "nx_noise_curl",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_TURBULENCE": {
        "name": "Turbulence",
        "description": "Turbulence noise",
        "icon_name": "nx_noise_turbulence",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_WAVE_TURBULENCE": {
        "name": "Wavy Turbulence",
        "description": "Wavy turbulence noise",
        "icon_name": "nx_noise_wavy_turbulence",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_VORONOISE": {
        "name": "VoroNoise",
        "description": "Voronoi noise",
        "icon_name": "nx_noise_voronoise",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_FBM": {
        "name": "FBM",
        "description": "Fractional Brownian Motion",
        "icon_name": "nx_noise_fbm",
    },
    "ID_NX_FALLOFF_NOISE_TYPE_CUBIC": {
        "name": "Cubic",
        "description": "Cubic noise",
        "icon_name": "nx_noise_cubic",
    },
}

_FALLOFF_NOISE_TYPE_ITEMS = []


def build_falloff_enum_items():
    global _FALLOFF_MODE_ITEMS, _FALLOFF_NOISE_TYPE_ITEMS
    from ..icons import get_icon

    _FALLOFF_MODE_ITEMS = []
    for idx, (type_id, d) in enumerate(_FALLOFF_MODE_DEFS.items()):
        icon_id = get_icon(d["icon_name"]) if d.get("icon_name") else 0
        if icon_id and icon_id > 0:
            _FALLOFF_MODE_ITEMS.append((type_id, d["name"], d["description"], icon_id, idx))
        else:
            _FALLOFF_MODE_ITEMS.append((type_id, d["name"], d["description"], "NONE", idx))

    _FALLOFF_NOISE_TYPE_ITEMS = []
    for idx, (type_id, d) in enumerate(_FALLOFF_NOISE_TYPE_DEFS.items()):
        icon_id = get_icon(d["icon_name"]) if d.get("icon_name") else 0
        if icon_id and icon_id > 0:
            _FALLOFF_NOISE_TYPE_ITEMS.append((type_id, d["name"], d["description"], icon_id, idx))
        else:
            _FALLOFF_NOISE_TYPE_ITEMS.append((type_id, d["name"], d["description"], "NONE", idx))


def _get_falloff_mode_items(self, context):
    return _FALLOFF_MODE_ITEMS


def _get_falloff_noise_type_items(self, context):
    return _FALLOFF_NOISE_TYPE_ITEMS


FALLOFF_MODE_DISPLAY_NAMES = {
    "ID_NX_FALLOFF_MODE_BOX": "nxBox Falloff",
    "ID_NX_FALLOFF_MODE_LINEAR": "nxLinear Falloff",
    "ID_NX_FALLOFF_MODE_SPHERE": "nxSpherical Falloff",
    "ID_NX_FALLOFF_MODE_NOISE": "nxNoise Falloff",
}

FALLOFF_MODE_ICONS = {
    "ID_NX_FALLOFF_MODE_BOX": "nx_falloff_box",
    "ID_NX_FALLOFF_MODE_LINEAR": "nx_falloff_linear",
    "ID_NX_FALLOFF_MODE_SPHERE": "nx_falloff_sphere",
    "ID_NX_FALLOFF_MODE_NOISE": "nx_falloff_noise",
}


def _apply_falloff_preview_icon(obj, icon_name):
    import bpy

    from ..icons import get_icon_path

    icon_path = get_icon_path(icon_name)
    if not icon_path:
        return

    try:
        obj.preview_ensure()
        img = bpy.data.images.load(icon_path, check_existing=True)

        if img and obj.preview:
            obj.preview.image_size = (32, 32)
            img.scale(32, 32)

            if len(img.pixels) >= 32 * 32 * 4:
                obj.preview.image_pixels_float = img.pixels[:]

            if img.users == 0:
                bpy.data.images.remove(img)
    except Exception:
        pass


def _on_falloff_mode_update(self, context):
    obj = self.id_data
    mode = self.ID_NX_FALLOFF_MODE
    if not obj:
        return
    icon_name = FALLOFF_MODE_ICONS.get(mode)
    if icon_name:
        _apply_falloff_preview_icon(obj, icon_name)
    new_name = FALLOFF_MODE_DISPLAY_NAMES.get(mode)
    if new_name:
        obj.name = new_name


# ---------------------------------------------------------------------------
# Curve / Gradient definitions
# ---------------------------------------------------------------------------

FALLOFF_CURVE_SPECS = None
FALLOFF_GRADIENT_SPECS = None


def _get_falloff_curve_specs():
    from ..utils.curve import CurveSpec

    return [
        CurveSpec(
            slot_name="falloff_spline",
            label="Falloff Spline",
            default_points=[(0.0, 0.0), (1.0, 1.0)],
            theron_ids=("ID_NX_FALLOFF_SPLINE",),
            sync_condition=lambda props, _orig: (
                props.ID_NX_FALLOFF_MODE != "ID_NX_FALLOFF_MODE_NOISE"
            ),
        ),
    ]


def _get_falloff_gradient_specs():
    from ..utils.gradient import GradientSpec

    return [
        GradientSpec(
            slot_name="falloff_noise_contrast",
            label="Contrast",
            default_stops=[
                (0.0, (1.0, 1.0, 1.0, 1.0)),
                (1.0, (0.0, 0.0, 0.0, 1.0)),
            ],
            theron_ids=("ID_NX_FALLOFF_NOISE_CONTRAST",),
            sync_condition=lambda props, _orig: (
                props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE"
            ),
        ),
    ]


def get_falloff_curve_specs():
    global FALLOFF_CURVE_SPECS
    if FALLOFF_CURVE_SPECS is None:
        FALLOFF_CURVE_SPECS = _get_falloff_curve_specs()
    return FALLOFF_CURVE_SPECS


def get_falloff_gradient_specs():
    global FALLOFF_GRADIENT_SPECS
    if FALLOFF_GRADIENT_SPECS is None:
        FALLOFF_GRADIENT_SPECS = _get_falloff_gradient_specs()
    return FALLOFF_GRADIENT_SPECS


# ---------------------------------------------------------------------------
# Dynamic offset clamping helpers
# ---------------------------------------------------------------------------


def _enforce_box_offset_limit(self):
    outer = self.ID_NX_FALLOFF_BOX_SIZE_OUTER
    limit = -min(outer[0], outer[1], outer[2]) * 0.5
    if self.ID_NX_FALLOFF_BOX_SIZE_OFFSET < limit:
        self.ID_NX_FALLOFF_BOX_SIZE_OFFSET = limit


def _enforce_sphere_offset_limit(self):
    limit = -self.ID_NX_FALLOFF_SPHERE_RADIUS_OUTER
    if self.ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET < limit:
        self.ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET = limit


def _on_box_offset_update(self, context):
    _enforce_box_offset_limit(self)


def _on_box_outer_update(self, context):
    _enforce_box_offset_limit(self)


def _on_sphere_offset_update(self, context):
    _enforce_sphere_offset_limit(self)


def _on_sphere_outer_update(self, context):
    _enforce_sphere_offset_limit(self)


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

SPEC = ModifierPropertySpec(
    modifier_type="NX_FALLOFF",
    descriptors=(
        ENABLED_DESCRIPTOR,
        PropertyDescriptor(
            name="ID_NX_FALLOFF_MODE",
            prop=EnumProperty(
                name="Mode",
                description="Falloff shape mode",
                items=_get_falloff_mode_items,
                default=0,
                update=_on_falloff_mode_update,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_INVERT",
            prop=BoolProperty(
                name="Invert",
                description="Invert the falloff",
                default=False,
            ),
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_WEIGHT",
            prop=FloatProperty(
                name="Weight",
                description="Falloff weight",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                step=1,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Falloff scale",
                default=100.0,
                min=0.0,
                soft_max=100.0,
                step=1,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_LINEAR_DIR",
            prop=EnumProperty(
                name="Direction",
                description="Linear falloff direction",
                items=[
                    ("ID_NX_FALLOFF_LINEAR_DIR_X_P", "+X", "Positive X direction"),
                    ("ID_NX_FALLOFF_LINEAR_DIR_X_N", "-X", "Negative X direction"),
                    ("ID_NX_FALLOFF_LINEAR_DIR_Y_P", "+Y", "Positive Y direction"),
                    ("ID_NX_FALLOFF_LINEAR_DIR_Y_N", "-Y", "Negative Y direction"),
                    ("ID_NX_FALLOFF_LINEAR_DIR_Z_P", "+Z", "Positive Z direction"),
                    ("ID_NX_FALLOFF_LINEAR_DIR_Z_N", "-Z", "Negative Z direction"),
                ],
                default="ID_NX_FALLOFF_LINEAR_DIR_Y_P",
            ),
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_LINEAR",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_LINEAR_SIZE_OFFSET",
            prop=FloatProperty(
                name="Offset",
                description="Linear falloff offset",
                default=1.0,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_LINEAR",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_SPHERE_RADIUS_OFFSET",
            prop=FloatProperty(
                name="Offset",
                description="Sphere falloff offset",
                default=-0.25,
                max=0.0,
                soft_min=-1.0,
                unit="LENGTH",
                subtype="DISTANCE",
                update=_on_sphere_offset_update,
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_SPHERE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_SPHERE_RADIUS_OUTER",
            prop=FloatProperty(
                name="Outer Radius",
                description="Sphere outer radius",
                default=0.5,
                min=0.0,
                soft_max=10.0,
                unit="LENGTH",
                subtype="DISTANCE",
                update=_on_sphere_outer_update,
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_SPHERE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_BOX_SIZE_OFFSET",
            prop=FloatProperty(
                name="Offset",
                description="Box falloff offset",
                default=-0.25,
                max=0.0,
                soft_min=-1.0,
                unit="LENGTH",
                subtype="DISTANCE",
                update=_on_box_offset_update,
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_BOX",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_BOX_SIZE_OUTER",
            prop=FloatVectorProperty(
                name="Outer Box",
                description="Box outer dimensions",
                default=(1.0, 1.0, 1.0),
                min=0.0,
                size=3,
                subtype="XYZ",
                unit="LENGTH",
                update=_on_box_outer_update,
            ),
            transform=Transform.UNIT_SCALE,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_BOX",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_TYPE",
            prop=EnumProperty(
                name="Noise Type",
                description="Type of noise for falloff",
                items=_get_falloff_noise_type_items,
                default=4,
            ),
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_SEED",
            prop=IntProperty(
                name="Seed",
                description="Noise seed",
                default=1,
                min=0,
            ),
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_SCALE",
            prop=FloatProperty(
                name="Scale",
                description="Noise scale",
                default=100.0,
                min=0.0,
                soft_max=1000.0,
                step=1,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_PERSISTENCE",
            prop=FloatProperty(
                name="Persistence",
                description="Noise persistence",
                default=100.0,
                min=0.0,
                max=100.0,
                step=1,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_LACUNARITY",
            prop=FloatProperty(
                name="Lacunarity",
                description="Noise lacunarity",
                default=1.0,
                min=0.0,
                soft_max=10.0,
                step=10,
            ),
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_FREQUENCY",
            prop=FloatProperty(
                name="Frequency",
                description="Noise frequency",
                default=100.0,
                min=0.0,
                soft_max=200.0,
                step=1,
                subtype="PERCENTAGE",
            ),
            transform=Transform.PERCENT_TO_DECIMAL,
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
        PropertyDescriptor(
            name="ID_NX_FALLOFF_NOISE_OCTAVES",
            prop=IntProperty(
                name="Octaves",
                description="Noise octaves",
                default=1,
                min=0,
                soft_max=20,
            ),
            condition=lambda props: props.ID_NX_FALLOFF_MODE == "ID_NX_FALLOFF_MODE_NOISE",
        ),
    ),
    enum_builders=(build_falloff_enum_items,),
    enum_defaults={
        "ID_NX_FALLOFF_MODE": 0,
        "ID_NX_FALLOFF_NOISE_TYPE": 4,
    },
)
