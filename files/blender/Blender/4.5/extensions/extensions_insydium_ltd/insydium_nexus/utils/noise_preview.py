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

from ..libs import theron
from ..libs.theron_bindings import TrNoiseType
from .gradient import get_lut

PREVIEW_RESOLUTION = 128
_PREVIEW_IMAGE_PREFIX = ".NX_NoisePreview_"

_NOISE_TYPE_MAP = {
    "SIMPLEX": int(TrNoiseType.TR_NOISE_TYPE_SIMPLEX),
    "FBM": int(TrNoiseType.TR_NOISE_TYPE_FBM),
    "TURBULENCE": int(TrNoiseType.TR_NOISE_TYPE_TURBULENCE),
    "WAVY_TURBULENCE": int(TrNoiseType.TR_NOISE_TYPE_WAVY_TURBULENCE),
    "VORONOISE": int(TrNoiseType.TR_NOISE_TYPE_VORONOISE),
    "CUBIC": int(TrNoiseType.TR_NOISE_TYPE_CUBIC),
}

_CHANNEL_MAP = {
    "GRADIENT": 0,
    "NOISE": 1,
}


def _ensure_image(obj) -> bpy.types.Image:
    """Get or create the preview image for an emitter object."""
    name = _PREVIEW_IMAGE_PREFIX + obj.name
    img = bpy.data.images.get(name)
    if img is None or img.size[0] != PREVIEW_RESOLUTION:
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(
            name,
            width=PREVIEW_RESOLUTION,
            height=PREVIEW_RESOLUTION,
            alpha=True,
            float_buffer=True,
        )
        img.use_fake_user = False
    return img


def _collect_params(props):
    """Extract noise parameters from an emitter's property group."""
    noise_type = _NOISE_TYPE_MAP.get(props.ID_NX_EMITTER_NOISE_TYPE, 0)
    noise_channel = _CHANNEL_MAP.get(props.ID_NX_EMITTER_NOISE_CHANNEL, 0)

    prefs = theron.create_prefs(
        octaves=props.ID_NX_EMITTER_NOISE_OCTAVES,
        scale=props.ID_NX_EMITTER_NOISE_SCALE * 0.01,
        persistence=props.ID_NX_EMITTER_NOISE_PERSISTENCE * 0.01,
        lacunarity=props.ID_NX_EMITTER_NOISE_LACUNARITY,
        frequency=props.ID_NX_EMITTER_NOISE_FREQUENCY * 0.01,
    )

    return (
        noise_type,
        noise_channel,
        props.ID_NX_EMITTER_NOISE_SEED,
        prefs,
        props.ID_NX_EMITTER_NOISE_LOW_CLIP * 0.01,
        props.ID_NX_EMITTER_NOISE_HIGH_CLIP * 0.01,
        props.ID_NX_EMITTER_NOISE_BRIGHTNESS * 0.01,
        props.ID_NX_EMITTER_NOISE_CONTRAST * 0.01,
    )


def update_noise_preview(obj) -> bool:
    """Regenerate the noise preview image for the given emitter object.

    Creates the image datablock if needed, generates pixel data via Theron GPU,
    and writes it into the image's preview icon. Safe to call from property update
    callbacks (not from draw!).

    Returns True if the preview was updated, False on error.
    """
    if not theron.is_initialized():
        return False

    props = obj.nexus_modifier
    if getattr(props, "ID_NX_EMITTER_COLOR_MODE", "SINGLE") != "NOISE":
        return False

    (
        noise_type,
        noise_channel,
        seed,
        prefs,
        low_clip,
        high_clip,
        brightness,
        contrast,
    ) = _collect_params(props)

    gradient_lut = None
    if noise_channel == 0:
        gradient_lut = get_lut(obj, "emitter_noise_gradient")

    pixels = theron.generate_noise_preview(
        resolution=PREVIEW_RESOLUTION,
        noise_type=noise_type,
        noise_channel=noise_channel,
        seed=seed,
        prefs=prefs,
        low_clip=low_clip,
        high_clip=high_clip,
        brightness=brightness,
        contrast=contrast,
        gradient_lut=gradient_lut,
    )

    if pixels is None:
        return False

    img = _ensure_image(obj)
    img.pixels.foreach_set(pixels)
    img.update()

    img.preview_ensure()
    img.preview.image_size = (PREVIEW_RESOLUTION, PREVIEW_RESOLUTION)
    img.preview.image_pixels_float[:] = pixels
    return True


def draw_noise_preview(layout, obj):
    """Draw the noise preview in the given UI layout as a single image.

    Only draws if the image preview already exists (created by update_noise_preview).
    Does not create any ID data — safe to call during draw.
    """
    name = _PREVIEW_IMAGE_PREFIX + obj.name
    img = bpy.data.images.get(name)
    if img is None or img.preview is None:
        return

    sub = layout.column()
    sub.use_property_split = False
    sub.use_property_decorate = False
    split = sub.split(factor=0.4)
    split.column()
    icon_row = split.row()
    icon_row.alignment = "LEFT"
    icon_row.template_icon(icon_value=img.preview.icon_id, scale=7.0)


def cleanup_preview(obj):
    """Remove the preview image for an emitter object."""
    img_name = _PREVIEW_IMAGE_PREFIX + obj.name
    img = bpy.data.images.get(img_name)
    if img is not None:
        bpy.data.images.remove(img)
