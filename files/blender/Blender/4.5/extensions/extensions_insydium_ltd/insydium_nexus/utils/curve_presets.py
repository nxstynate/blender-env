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
class CurvePreset(BasePreset):
    category: str
    points: list[tuple[float, float]]
    handle_type: str = "AUTO"
    point_handles: list[str] | None = None


CURVE_PRESET_CATEGORIES = {
    "RAMP": "Ramp",
    "FALLOFF": "Falloff",
    "SPECIAL": "Special",
}

CURVE_PRESETS: list[CurvePreset] = [
    # -------------------------------------------------------------------------
    # Ramp
    # -------------------------------------------------------------------------
    CurvePreset(
        "ramp_linear",
        "Linear",
        "RAMP",
        [(0, 0), (1, 1)],
    ),
    CurvePreset(
        "ramp_linear_inv",
        "Linear Inverse",
        "RAMP",
        [(0, 1), (1, 0)],
    ),
    CurvePreset(
        "ramp_flat_zero",
        "Flat Zero",
        "RAMP",
        [(0, 0), (1, 0)],
    ),
    CurvePreset(
        "ramp_flat_one",
        "Flat One",
        "RAMP",
        [(0, 1), (1, 1)],
    ),
    # -------------------------------------------------------------------------
    # Falloff
    # -------------------------------------------------------------------------
    CurvePreset(
        "falloff_smooth",
        "Smooth Falloff",
        "FALLOFF",
        [(0, 1), (1, 0)],
    ),
    CurvePreset(
        "falloff_sharp",
        "Sharp Falloff",
        "FALLOFF",
        [(0, 1), (0.2, 0.05), (1, 0)],
    ),
    CurvePreset(
        "falloff_soft",
        "Soft Falloff",
        "FALLOFF",
        [(0, 1), (0.8, 0.95), (1, 0)],
    ),
    CurvePreset(
        "falloff_step",
        "Step",
        "FALLOFF",
        [(0, 1), (0.49, 1), (0.51, 0), (1, 0)],
        handle_type="VECTOR",
    ),
    # -------------------------------------------------------------------------
    # Special
    # -------------------------------------------------------------------------
    CurvePreset(
        "special_bell",
        "Bell",
        "SPECIAL",
        [(0, 0), (0.5, 1), (1, 0)],
    ),
    CurvePreset(
        "special_trough",
        "Trough",
        "SPECIAL",
        [(0, 1), (0.5, 0), (1, 1)],
    ),
    CurvePreset(
        "special_bounce",
        "Bounce",
        "SPECIAL",
        [(0, 0), (0.35, 1), (0.65, 0.6), (0.85, 0.85), (1, 0.75)],
    ),
    CurvePreset(
        "special_stairs",
        "Stairs",
        "SPECIAL",
        [
            (0, 0),
            (0.24, 0),
            (0.26, 0.33),
            (0.49, 0.33),
            (0.51, 0.66),
            (0.74, 0.66),
            (0.76, 1),
            (1, 1),
        ],
        handle_type="VECTOR",
    ),
]

_preset_map: dict[str, CurvePreset] = {p.preset_id: p for p in CURVE_PRESETS}


def get_preset(preset_id: str) -> CurvePreset | None:
    return _preset_map.get(preset_id) or _store.get(preset_id)


def get_presets_by_category() -> dict[str, list[CurvePreset]]:
    grouped: dict[str, list[CurvePreset]] = {}
    for cat_key in CURVE_PRESET_CATEGORIES:
        grouped[cat_key] = []
    for preset in CURVE_PRESETS:
        if preset.category in grouped:
            grouped[preset.category].append(preset)
    return grouped


def get_all_preset_ids() -> list[str]:
    return [p.preset_id for p in CURVE_PRESETS]


# ---------------------------------------------------------------------------
# Curve sampling for icon generation
# ---------------------------------------------------------------------------


def _sample_curve(
    points: list[tuple[float, float]],
    handle_type: str,
    point_handles: list[str] | None,
    x: float,
) -> float:
    sorted_pts = sorted(points, key=lambda p: p[0])

    if not sorted_pts:
        return 0.0
    if x <= sorted_pts[0][0]:
        return sorted_pts[0][1]
    if x >= sorted_pts[-1][0]:
        return sorted_pts[-1][1]

    seg_idx = 0
    for i in range(len(sorted_pts) - 1):
        if sorted_pts[i][0] <= x <= sorted_pts[i + 1][0]:
            seg_idx = i
            break

    x0, y0 = sorted_pts[seg_idx]
    x1, y1 = sorted_pts[seg_idx + 1]
    span = x1 - x0
    if span <= 0:
        return y0

    t = (x - x0) / span

    h0 = point_handles[seg_idx] if point_handles and seg_idx < len(point_handles) else handle_type
    h1 = (
        point_handles[seg_idx + 1]
        if point_handles and (seg_idx + 1) < len(point_handles)
        else handle_type
    )

    if h0 == "VECTOR" and h1 == "VECTOR":
        y = y0 + (y1 - y0) * t
    else:
        n = len(sorted_pts)
        if seg_idx > 0:
            dx_prev = sorted_pts[seg_idx][0] - sorted_pts[seg_idx - 1][0]
            dy_prev = sorted_pts[seg_idx][1] - sorted_pts[seg_idx - 1][1]
            slope_prev = dy_prev / dx_prev if dx_prev > 0 else 0.0
        else:
            slope_prev = None

        dx_curr = x1 - x0
        dy_curr = y1 - y0
        slope_curr = dy_curr / dx_curr if dx_curr > 0 else 0.0

        if seg_idx + 2 < n:
            dx_next = sorted_pts[seg_idx + 2][0] - sorted_pts[seg_idx + 1][0]
            dy_next = sorted_pts[seg_idx + 2][1] - sorted_pts[seg_idx + 1][1]
            slope_next = dy_next / dx_next if dx_next > 0 else 0.0
        else:
            slope_next = None

        if h0 == "VECTOR" or slope_prev is None:
            m0 = slope_curr
        else:
            m0 = (slope_prev + slope_curr) * 0.5

        if h1 == "VECTOR" or slope_next is None:
            m1 = slope_curr
        else:
            m1 = (slope_curr + slope_next) * 0.5

        m0 *= span
        m1 *= span

        t2 = t * t
        t3 = t2 * t
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2

        y = h00 * y0 + h10 * m0 + h01 * y1 + h11 * m1

    return max(0.0, min(1.0, y))


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

_BG = (0.15, 0.15, 0.15, 1.0)
_LINE = (0.9, 0.9, 0.9, 1.0)


def _blend_pixel(bg, fg, alpha):
    return (
        bg[0] + (fg[0] - bg[0]) * alpha,
        bg[1] + (fg[1] - bg[1]) * alpha,
        bg[2] + (fg[2] - bg[2]) * alpha,
        1.0,
    )


def _generate_single_preview(pcoll, preset):
    if preset.preset_id in pcoll:
        return

    ico_w, ico_h = 32, 32
    img_w, img_h = 128, 32

    pixels_ico = list(_BG) * (ico_w * ico_h)
    pixels_img = list(_BG) * (img_w * img_h)

    def _draw_line(pixels, width, height, points, handle_type, point_handles):
        prev_y_float = None
        for col in range(width):
            x = col / (width - 1) if width > 1 else 0.0
            y_float = _sample_curve(points, handle_type, point_handles, x) * (height - 1)

            row_lo = int(y_float)
            row_hi = min(row_lo + 1, height - 1)

            for row in (row_lo, row_hi):
                if 0 <= row < height:
                    alpha = 1.0 - abs(y_float - row)
                    alpha = max(0.0, min(1.0, alpha))
                    if alpha > 0:
                        idx = (row * width + col) * 4
                        bg = tuple(pixels[idx : idx + 4])
                        blended = _blend_pixel(bg, _LINE, alpha)
                        pixels[idx : idx + 4] = list(blended)

            if prev_y_float is not None:
                gap_lo = min(prev_y_float, y_float)
                gap_hi = max(prev_y_float, y_float)
                fill_start = int(gap_lo) + 1
                fill_end = int(gap_hi)
                for row in range(fill_start, fill_end + 1):
                    if 0 <= row < height:
                        idx = (row * width + col) * 4
                        bg = tuple(pixels[idx : idx + 4])
                        blended = _blend_pixel(bg, _LINE, 0.9)
                        pixels[idx : idx + 4] = list(blended)

            prev_y_float = y_float

    _draw_line(pixels_ico, ico_w, ico_h, preset.points, preset.handle_type, preset.point_handles)
    _draw_line(pixels_img, img_w, img_h, preset.points, preset.handle_type, preset.point_handles)

    preview = pcoll.new(preset.preset_id)
    preview.icon_size = (ico_w, ico_h)
    preview.icon_pixels_float[:] = pixels_ico
    preview.image_size = (img_w, img_h)
    preview.image_pixels_float[:] = pixels_img


def generate_preset_previews(pcoll):
    for preset in CURVE_PRESETS:
        _generate_single_preview(pcoll, preset)


def generate_user_preset_previews(pcoll):
    for preset in _store.get_all():
        _generate_single_preview(pcoll, preset)


# ---------------------------------------------------------------------------
# User presets
# ---------------------------------------------------------------------------


class CurvePresetStore(PresetStore[CurvePreset]):
    log_label = "curve preset"

    def _serialise(self, preset: CurvePreset) -> dict:
        return {
            "preset_id": preset.preset_id,
            "name": preset.name,
            "points": [list(pt) for pt in preset.points],
            "handle_type": preset.handle_type,
            "point_handles": preset.point_handles,
        }

    def _deserialise(self, entry: dict) -> CurvePreset | None:
        try:
            points = [(p[0], p[1]) for p in entry["points"]]
            return CurvePreset(
                preset_id=entry["preset_id"],
                name=entry["name"],
                category="USER",
                points=points,
                handle_type=entry.get("handle_type", "AUTO"),
                point_handles=entry.get("point_handles"),
            )
        except (KeyError, IndexError, TypeError) as e:
            print(f"NeXus: Skipping corrupt user curve preset entry: {e}")
            return None


_store = CurvePresetStore("user_curve_presets.json")


def init_user_presets(addon_package: str) -> None:
    _store.init(addon_package)


def add_user_preset(name, points, handle_type="AUTO", point_handles=None) -> str:
    preset = CurvePreset(
        preset_id=_store.new_id(),
        name=name,
        category="USER",
        points=points,
        handle_type=handle_type,
        point_handles=point_handles,
    )
    return _store.add(preset)


def rename_user_preset(preset_id: str, new_name: str) -> bool:
    return _store.rename(preset_id, new_name)


def remove_user_preset(preset_id: str) -> bool:
    return _store.remove(preset_id)


def get_user_presets() -> list[CurvePreset]:
    return _store.get_all()
