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

from dataclasses import dataclass

from .preset_base import BasePreset, PresetStore


@dataclass
class GradientPreset(BasePreset):
    category: str
    stops: list[tuple[float, tuple[float, float, float, float]]]
    interpolation: str = "LINEAR"


GRADIENT_PRESET_CATEGORIES = {
    "HEAT": "Heat",
    "RAINBOW": "Rainbow",
    "MONOCHROME": "Monochrome",
    "NATURE": "Nature",
    "SCIENCE": "Scientific",
    "ARTISTIC": "Artistic",
}

GRADIENT_PRESETS: list[GradientPreset] = [
    # -------------------------------------------------------------------------
    # Heat
    # -------------------------------------------------------------------------
    GradientPreset(
        "heat_inferno",
        "Inferno",
        "HEAT",
        [
            (0.0, (0.001, 0.000, 0.014, 1.0)),
            (0.25, (0.258, 0.039, 0.406, 1.0)),
            (0.5, (0.735, 0.215, 0.330, 1.0)),
            (0.75, (0.993, 0.553, 0.235, 1.0)),
            (1.0, (0.988, 0.998, 0.645, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_magma",
        "Magma",
        "HEAT",
        [
            (0.0, (0.001, 0.000, 0.014, 1.0)),
            (0.25, (0.270, 0.051, 0.430, 1.0)),
            (0.5, (0.716, 0.215, 0.475, 1.0)),
            (0.75, (0.993, 0.495, 0.380, 1.0)),
            (1.0, (0.987, 0.991, 0.750, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_plasma",
        "Plasma",
        "HEAT",
        [
            (0.0, (0.050, 0.030, 0.528, 1.0)),
            (0.25, (0.494, 0.012, 0.658, 1.0)),
            (0.5, (0.798, 0.280, 0.470, 1.0)),
            (0.75, (0.973, 0.585, 0.253, 1.0)),
            (1.0, (0.940, 0.975, 0.131, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_blackbody",
        "Blackbody",
        "HEAT",
        [
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.25, (0.455, 0.028, 0.0, 1.0)),
            (0.5, (0.851, 0.227, 0.004, 1.0)),
            (0.75, (1.0, 0.621, 0.133, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_hot_iron",
        "Hot Iron",
        "HEAT",
        [
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.2, (0.304, 0.0, 0.0, 1.0)),
            (0.4, (0.690, 0.090, 0.0, 1.0)),
            (0.6, (1.0, 0.353, 0.0, 1.0)),
            (0.8, (1.0, 0.725, 0.153, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_fire",
        "Fire",
        "HEAT",
        [
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.2, (0.220, 0.008, 0.0, 1.0)),
            (0.4, (0.680, 0.100, 0.003, 1.0)),
            (0.6, (0.960, 0.380, 0.010, 1.0)),
            (0.8, (1.0, 0.730, 0.050, 1.0)),
            (1.0, (1.0, 0.960, 0.560, 1.0)),
        ],
    ),
    GradientPreset(
        "heat_thermal",
        "Thermal",
        "HEAT",
        [
            (0.0, (0.016, 0.014, 0.200, 1.0)),
            (0.25, (0.120, 0.010, 0.510, 1.0)),
            (0.5, (0.720, 0.030, 0.210, 1.0)),
            (0.75, (1.0, 0.520, 0.050, 1.0)),
            (1.0, (1.0, 0.960, 0.800, 1.0)),
        ],
    ),
    # -------------------------------------------------------------------------
    # Rainbow
    # -------------------------------------------------------------------------
    GradientPreset(
        "rainbow_spectrum",
        "Full Spectrum",
        "RAINBOW",
        [
            (0.0, (0.610, 0.010, 0.050, 1.0)),
            (0.167, (0.920, 0.380, 0.010, 1.0)),
            (0.333, (0.950, 0.850, 0.050, 1.0)),
            (0.5, (0.050, 0.610, 0.110, 1.0)),
            (0.667, (0.040, 0.300, 0.750, 1.0)),
            (0.833, (0.290, 0.050, 0.560, 1.0)),
            (1.0, (0.610, 0.010, 0.050, 1.0)),
        ],
    ),
    GradientPreset(
        "rainbow_pastel",
        "Pastel Rainbow",
        "RAINBOW",
        [
            (0.0, (0.960, 0.650, 0.650, 1.0)),
            (0.2, (0.960, 0.830, 0.620, 1.0)),
            (0.4, (0.960, 0.960, 0.680, 1.0)),
            (0.6, (0.680, 0.920, 0.700, 1.0)),
            (0.8, (0.650, 0.760, 0.950, 1.0)),
            (1.0, (0.830, 0.680, 0.920, 1.0)),
        ],
    ),
    GradientPreset(
        "rainbow_neon",
        "Neon",
        "RAINBOW",
        [
            (0.0, (1.0, 0.0, 0.310, 1.0)),
            (0.25, (1.0, 0.850, 0.0, 1.0)),
            (0.5, (0.0, 1.0, 0.200, 1.0)),
            (0.75, (0.0, 0.530, 1.0, 1.0)),
            (1.0, (0.850, 0.0, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "rainbow_hsv",
        "HSV Wheel",
        "RAINBOW",
        [
            (0.0, (1.0, 0.0, 0.0, 1.0)),
            (0.167, (1.0, 1.0, 0.0, 1.0)),
            (0.333, (0.0, 1.0, 0.0, 1.0)),
            (0.5, (0.0, 1.0, 1.0, 1.0)),
            (0.667, (0.0, 0.0, 1.0, 1.0)),
            (0.833, (1.0, 0.0, 1.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
    ),
    # -------------------------------------------------------------------------
    # Monochrome
    # -------------------------------------------------------------------------
    GradientPreset(
        "mono_grayscale",
        "Grayscale",
        "MONOCHROME",
        [
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "mono_inverse",
        "Inverse Grayscale",
        "MONOCHROME",
        [
            (0.0, (1.0, 1.0, 1.0, 1.0)),
            (1.0, (0.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientPreset(
        "mono_sepia",
        "Sepia",
        "MONOCHROME",
        [
            (0.0, (0.150, 0.090, 0.035, 1.0)),
            (0.5, (0.580, 0.400, 0.220, 1.0)),
            (1.0, (0.960, 0.870, 0.700, 1.0)),
        ],
    ),
    GradientPreset(
        "mono_blue_tint",
        "Blue Tint",
        "MONOCHROME",
        [
            (0.0, (0.010, 0.020, 0.060, 1.0)),
            (0.5, (0.150, 0.280, 0.500, 1.0)),
            (1.0, (0.700, 0.830, 0.970, 1.0)),
        ],
    ),
    GradientPreset(
        "mono_green_tint",
        "Green Tint",
        "MONOCHROME",
        [
            (0.0, (0.010, 0.040, 0.010, 1.0)),
            (0.5, (0.120, 0.380, 0.120, 1.0)),
            (1.0, (0.650, 0.920, 0.650, 1.0)),
        ],
    ),
    GradientPreset(
        "mono_red_tint",
        "Red Tint",
        "MONOCHROME",
        [
            (0.0, (0.060, 0.010, 0.010, 1.0)),
            (0.5, (0.500, 0.100, 0.080, 1.0)),
            (1.0, (0.970, 0.650, 0.620, 1.0)),
        ],
    ),
    # -------------------------------------------------------------------------
    # Nature
    # -------------------------------------------------------------------------
    GradientPreset(
        "nature_ocean",
        "Ocean",
        "NATURE",
        [
            (0.0, (0.003, 0.020, 0.080, 1.0)),
            (0.3, (0.010, 0.100, 0.350, 1.0)),
            (0.6, (0.050, 0.350, 0.580, 1.0)),
            (0.8, (0.220, 0.650, 0.750, 1.0)),
            (1.0, (0.650, 0.920, 0.950, 1.0)),
        ],
    ),
    GradientPreset(
        "nature_sunset",
        "Sunset",
        "NATURE",
        [
            (0.0, (0.080, 0.010, 0.150, 1.0)),
            (0.25, (0.500, 0.040, 0.200, 1.0)),
            (0.5, (0.920, 0.250, 0.100, 1.0)),
            (0.75, (1.0, 0.600, 0.150, 1.0)),
            (1.0, (1.0, 0.900, 0.500, 1.0)),
        ],
    ),
    GradientPreset(
        "nature_forest",
        "Forest",
        "NATURE",
        [
            (0.0, (0.020, 0.050, 0.010, 1.0)),
            (0.3, (0.050, 0.200, 0.030, 1.0)),
            (0.6, (0.150, 0.450, 0.080, 1.0)),
            (0.85, (0.400, 0.650, 0.150, 1.0)),
            (1.0, (0.700, 0.850, 0.350, 1.0)),
        ],
    ),
    GradientPreset(
        "nature_earth",
        "Earth Tones",
        "NATURE",
        [
            (0.0, (0.180, 0.100, 0.040, 1.0)),
            (0.3, (0.420, 0.250, 0.100, 1.0)),
            (0.6, (0.650, 0.460, 0.220, 1.0)),
            (0.85, (0.820, 0.700, 0.450, 1.0)),
            (1.0, (0.930, 0.880, 0.720, 1.0)),
        ],
    ),
    GradientPreset(
        "nature_sky",
        "Sky",
        "NATURE",
        [
            (0.0, (0.010, 0.050, 0.200, 1.0)),
            (0.35, (0.100, 0.300, 0.650, 1.0)),
            (0.65, (0.350, 0.600, 0.880, 1.0)),
            (0.85, (0.650, 0.820, 0.960, 1.0)),
            (1.0, (0.900, 0.950, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "nature_desert",
        "Desert",
        "NATURE",
        [
            (0.0, (0.350, 0.180, 0.060, 1.0)),
            (0.3, (0.650, 0.380, 0.120, 1.0)),
            (0.6, (0.880, 0.650, 0.300, 1.0)),
            (0.8, (0.960, 0.830, 0.530, 1.0)),
            (1.0, (0.990, 0.950, 0.800, 1.0)),
        ],
    ),
    # -------------------------------------------------------------------------
    # Scientific
    # -------------------------------------------------------------------------
    GradientPreset(
        "sci_viridis",
        "Viridis",
        "SCIENCE",
        [
            (0.0, (0.267, 0.004, 0.329, 1.0)),
            (0.25, (0.283, 0.141, 0.458, 1.0)),
            (0.5, (0.127, 0.566, 0.551, 1.0)),
            (0.75, (0.369, 0.789, 0.383, 1.0)),
            (1.0, (0.993, 0.906, 0.144, 1.0)),
        ],
    ),
    GradientPreset(
        "sci_coolwarm",
        "Cool-Warm",
        "SCIENCE",
        [
            (0.0, (0.230, 0.299, 0.754, 1.0)),
            (0.5, (0.865, 0.865, 0.865, 1.0)),
            (1.0, (0.706, 0.016, 0.150, 1.0)),
        ],
    ),
    GradientPreset(
        "sci_jet",
        "Jet",
        "SCIENCE",
        [
            (0.0, (0.0, 0.0, 0.5, 1.0)),
            (0.125, (0.0, 0.0, 1.0, 1.0)),
            (0.375, (0.0, 1.0, 1.0, 1.0)),
            (0.625, (1.0, 1.0, 0.0, 1.0)),
            (0.875, (1.0, 0.0, 0.0, 1.0)),
            (1.0, (0.5, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientPreset(
        "sci_turbo",
        "Turbo",
        "SCIENCE",
        [
            (0.0, (0.190, 0.072, 0.232, 1.0)),
            (0.15, (0.130, 0.330, 0.850, 1.0)),
            (0.3, (0.050, 0.650, 0.780, 1.0)),
            (0.45, (0.190, 0.850, 0.460, 1.0)),
            (0.6, (0.620, 0.930, 0.220, 1.0)),
            (0.75, (0.950, 0.740, 0.130, 1.0)),
            (0.9, (0.950, 0.380, 0.070, 1.0)),
            (1.0, (0.600, 0.040, 0.040, 1.0)),
        ],
    ),
    GradientPreset(
        "sci_spectral",
        "Spectral",
        "SCIENCE",
        [
            (0.0, (0.620, 0.004, 0.259, 1.0)),
            (0.25, (0.957, 0.427, 0.263, 1.0)),
            (0.5, (1.0, 1.0, 0.749, 1.0)),
            (0.75, (0.530, 0.808, 0.498, 1.0)),
            (1.0, (0.369, 0.310, 0.635, 1.0)),
        ],
    ),
    GradientPreset(
        "sci_cividis",
        "Cividis",
        "SCIENCE",
        [
            (0.0, (0.0, 0.135, 0.304, 1.0)),
            (0.25, (0.260, 0.305, 0.395, 1.0)),
            (0.5, (0.480, 0.480, 0.420, 1.0)),
            (0.75, (0.730, 0.670, 0.380, 1.0)),
            (1.0, (0.995, 0.880, 0.320, 1.0)),
        ],
    ),
    # -------------------------------------------------------------------------
    # Artistic
    # -------------------------------------------------------------------------
    GradientPreset(
        "art_cyberpunk",
        "Cyberpunk",
        "ARTISTIC",
        [
            (0.0, (0.020, 0.005, 0.060, 1.0)),
            (0.25, (0.200, 0.010, 0.350, 1.0)),
            (0.5, (0.850, 0.020, 0.400, 1.0)),
            (0.75, (0.050, 0.850, 0.950, 1.0)),
            (1.0, (0.950, 0.980, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "art_vintage",
        "Vintage",
        "ARTISTIC",
        [
            (0.0, (0.220, 0.150, 0.100, 1.0)),
            (0.3, (0.520, 0.350, 0.200, 1.0)),
            (0.6, (0.750, 0.600, 0.380, 1.0)),
            (0.85, (0.880, 0.800, 0.620, 1.0)),
            (1.0, (0.950, 0.920, 0.820, 1.0)),
        ],
    ),
    GradientPreset(
        "art_pastel",
        "Pastel",
        "ARTISTIC",
        [
            (0.0, (0.960, 0.750, 0.790, 1.0)),
            (0.25, (0.780, 0.810, 0.960, 1.0)),
            (0.5, (0.750, 0.960, 0.830, 1.0)),
            (0.75, (0.960, 0.920, 0.750, 1.0)),
            (1.0, (0.880, 0.760, 0.960, 1.0)),
        ],
    ),
    GradientPreset(
        "art_duotone_blue_orange",
        "Duotone Blue-Orange",
        "ARTISTIC",
        [
            (0.0, (0.050, 0.100, 0.350, 1.0)),
            (1.0, (0.950, 0.500, 0.100, 1.0)),
        ],
    ),
    GradientPreset(
        "art_duotone_pink_teal",
        "Duotone Pink-Teal",
        "ARTISTIC",
        [
            (0.0, (0.800, 0.150, 0.400, 1.0)),
            (1.0, (0.100, 0.700, 0.650, 1.0)),
        ],
    ),
    GradientPreset(
        "art_synthwave",
        "Synthwave",
        "ARTISTIC",
        [
            (0.0, (0.050, 0.010, 0.120, 1.0)),
            (0.25, (0.280, 0.020, 0.380, 1.0)),
            (0.5, (0.900, 0.100, 0.500, 1.0)),
            (0.75, (1.0, 0.450, 0.200, 1.0)),
            (1.0, (1.0, 0.850, 0.200, 1.0)),
        ],
    ),
    GradientPreset(
        "art_aurora",
        "Aurora",
        "ARTISTIC",
        [
            (0.0, (0.010, 0.020, 0.100, 1.0)),
            (0.2, (0.020, 0.120, 0.300, 1.0)),
            (0.4, (0.050, 0.520, 0.350, 1.0)),
            (0.6, (0.200, 0.800, 0.400, 1.0)),
            (0.8, (0.400, 0.900, 0.650, 1.0)),
            (1.0, (0.700, 0.980, 0.850, 1.0)),
        ],
    ),
    GradientPreset(
        "art_candy",
        "Candy",
        "ARTISTIC",
        [
            (0.0, (0.950, 0.300, 0.500, 1.0)),
            (0.25, (0.950, 0.550, 0.650, 1.0)),
            (0.5, (0.850, 0.450, 0.900, 1.0)),
            (0.75, (0.550, 0.400, 0.950, 1.0)),
            (1.0, (0.350, 0.550, 1.0, 1.0)),
        ],
    ),
    GradientPreset(
        "art_ember",
        "Ember",
        "ARTISTIC",
        [
            (0.0, (0.020, 0.005, 0.005, 1.0)),
            (0.3, (0.250, 0.020, 0.010, 1.0)),
            (0.6, (0.700, 0.100, 0.010, 1.0)),
            (0.85, (1.0, 0.350, 0.050, 1.0)),
            (1.0, (1.0, 0.700, 0.200, 1.0)),
        ],
    ),
]

_preset_map: dict[str, GradientPreset] = {p.preset_id: p for p in GRADIENT_PRESETS}


def get_preset(preset_id: str) -> GradientPreset | None:
    return _preset_map.get(preset_id) or _store.get(preset_id)


def get_presets_by_category() -> dict[str, list[GradientPreset]]:
    grouped: dict[str, list[GradientPreset]] = {}
    for cat_key in GRADIENT_PRESET_CATEGORIES:
        grouped[cat_key] = []
    for preset in GRADIENT_PRESETS:
        if preset.category in grouped:
            grouped[preset.category].append(preset)
    return grouped


def get_all_preset_ids() -> list[str]:
    return [p.preset_id for p in GRADIENT_PRESETS]


def _lerp_color(
    c1: tuple[float, float, float, float],
    c2: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
        c1[3] + (c2[3] - c1[3]) * t,
    )


def _sample_gradient(
    stops: list[tuple[float, tuple[float, float, float, float]]], t: float
) -> tuple[float, float, float, float]:
    if not stops:
        return (0.0, 0.0, 0.0, 1.0)

    sorted_stops = sorted(stops, key=lambda s: s[0])

    if t <= sorted_stops[0][0]:
        return sorted_stops[0][1]
    if t >= sorted_stops[-1][0]:
        return sorted_stops[-1][1]

    for i in range(len(sorted_stops) - 1):
        p0, c0 = sorted_stops[i]
        p1, c1 = sorted_stops[i + 1]
        if p0 <= t <= p1:
            span = p1 - p0
            local_t = (t - p0) / span if span > 0 else 0.0
            return _lerp_color(c0, c1, local_t)

    return sorted_stops[-1][1]


def _generate_single_preview(pcoll, preset_id, stops):
    if preset_id in pcoll:
        return
    img_w, img_h = 128, 16
    ico_w, ico_h = 32, 32

    preview = pcoll.new(preset_id)

    preview.image_size = (img_w, img_h)
    img_row = []
    for x in range(img_w):
        img_row.extend(_sample_gradient(stops, x / (img_w - 1)))
    preview.image_pixels_float[:] = img_row * img_h

    preview.icon_size = (ico_w, ico_h)
    ico_row = []
    for x in range(ico_w):
        ico_row.extend(_sample_gradient(stops, x / (ico_w - 1)))
    preview.icon_pixels_float[:] = ico_row * ico_h


def generate_preset_previews(pcoll):
    for preset in GRADIENT_PRESETS:
        _generate_single_preview(pcoll, preset.preset_id, preset.stops)


def generate_user_preset_previews(pcoll):
    for preset in _store.get_all():
        _generate_single_preview(pcoll, preset.preset_id, preset.stops)


# ---------------------------------------------------------------------------
# User presets
# ---------------------------------------------------------------------------


class GradientPresetStore(PresetStore[GradientPreset]):
    log_label = "gradient preset"

    def _serialise(self, preset: GradientPreset) -> dict:
        return {
            "preset_id": preset.preset_id,
            "name": preset.name,
            "stops": [[s[0], list(s[1])] for s in preset.stops],
            "interpolation": preset.interpolation,
        }

    def _deserialise(self, entry: dict) -> GradientPreset | None:
        try:
            stops = [(s[0], tuple(s[1])) for s in entry["stops"]]
            return GradientPreset(
                preset_id=entry["preset_id"],
                name=entry["name"],
                category="USER",
                stops=stops,
                interpolation=entry.get("interpolation", "LINEAR"),
            )
        except (KeyError, IndexError, TypeError) as e:
            print(f"NeXus: Skipping corrupt user preset entry: {e}")
            return None


_store = GradientPresetStore("user_gradient_presets.json")


def init_user_presets(addon_package: str) -> None:
    _store.init(addon_package)


def add_user_preset(name, stops, interpolation="LINEAR") -> str:
    preset = GradientPreset(
        preset_id=_store.new_id(),
        name=name,
        category="USER",
        stops=stops,
        interpolation=interpolation,
    )
    return _store.add(preset)


def rename_user_preset(preset_id: str, new_name: str) -> bool:
    return _store.rename(preset_id, new_name)


def remove_user_preset(preset_id: str) -> bool:
    return _store.remove(preset_id)


def get_user_presets() -> list[GradientPreset]:
    return _store.get_all()
