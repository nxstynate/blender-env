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

"""NeXus Time System

Usage in property files::

    from ..libs.nexus_time import nexus_time_property

    NX_FOO_PROPERTIES = {
        "foo_duration": nexus_time_property(
            "foo_duration",
            name="Duration",
            description="How long the effect lasts",
            default=10.0,   # frames (default display mode)
            min=0.0,
            soft_max=1000.0,
        ),
    }

Usage in draw_ui::

    from ..libs.nexus_time import draw_time_prop

    @classmethod
    def draw_ui(cls, layout, data):
        col = layout.column()
        col.use_property_split = True
        draw_time_prop(col, data, "foo_duration")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bpy.props import FloatProperty

if TYPE_CHECKING:
    import bpy

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_cached_fps: float = 24.0

# All property names created via nexus_time_property().
_TIME_PROPERTY_REGISTRY: set[str] = set()

# Collection-based time properties: (collection_attr, prop_name)
_TIME_COLLECTION_REGISTRY: list[tuple[str, str]] = []

# ID-property key prefix for per-property time mode storage.
_MODE_KEY_PREFIX = "_nx_tm_"


# ---------------------------------------------------------------------------
# FPS cache (updated from pipeline handler every frame)
# ---------------------------------------------------------------------------


def get_fps() -> float:
    """Return the cached scene FPS."""
    return _cached_fps


def update_fps_cache(scene: bpy.types.Scene) -> None:
    """Update the cached FPS from the given scene. Called by pipeline handler."""
    global _cached_fps
    fps_base = scene.render.fps_base
    if fps_base > 0.0:
        _cached_fps = scene.render.fps / fps_base
    else:
        _cached_fps = scene.render.fps


# ---------------------------------------------------------------------------
# Global default display mode (preference)
# ---------------------------------------------------------------------------


def get_display_mode() -> str:
    """Return the global default ``'FRAMES'`` or ``'SECONDS'`` from preferences.
    fallback
    """

    try:
        from ..utils import get_blender_addon

        prefs = get_blender_addon().preferences
        return getattr(prefs, "time_display_mode", "FRAMES")
    except (KeyError, AttributeError):
        return "FRAMES"


# ---------------------------------------------------------------------------
# Per-property time mode
# ---------------------------------------------------------------------------


def get_prop_time_mode(data, prop_name: str) -> str:
    """Return the display mode for a specific time property.

    Reads from ``data["_nx_tm_<prop_name>"]``.  Falls back to the global
    preference if no per-property mode has been set.
    """
    key = _MODE_KEY_PREFIX + prop_name
    mode = data.get(key)
    if mode in ("FRAMES", "SECONDS"):
        return mode
    return get_display_mode()


def set_prop_time_mode(data, prop_name: str, mode: str) -> None:
    """Persist the display mode for a specific time property."""
    key = _MODE_KEY_PREFIX + prop_name
    data[key] = mode


# ---------------------------------------------------------------------------
# Conversion utils
# ---------------------------------------------------------------------------


def to_seconds(
    value: float,
    fps: float | None = None,
    mode: str | None = None,
) -> float:
    """Convert a value to seconds based on the given or current display mode.
    value:
        The stored property value.
    fps:
        Scene FPS. Uses the cached value when ``None``.
    mode:
        ``"FRAMES"`` or ``"SECONDS"``. If ``None``, reads the global default.
    """
    if mode is None:
        mode = get_display_mode()
    if mode == "FRAMES":
        return value / (fps or _cached_fps)
    return value


def to_time_fraction(
    value: float,
    fps: float | None = None,
    mode: str | None = None,
) -> tuple[int, int]:
    """Convert a time property value to a rational fraction for TrTime.

    Returns (numerator, denominator) suitable for theron.set_time().
    In FRAMES mode: (round(value * 1000), round(fps * 1000)).
    In SECONDS mode: (round(value * 1000), 1000).
    """
    if mode is None:
        mode = get_display_mode()
    if mode == "FRAMES":
        return (round(value * 1000), round((fps or _cached_fps) * 1000))
    return (round(value * 1000), 1000)


def from_seconds(
    seconds: float,
    fps: float | None = None,
    mode: str | None = None,
) -> float:
    """Convert seconds to the given or current display mode value."""
    if mode is None:
        mode = get_display_mode()
    if mode == "FRAMES":
        return seconds * (fps or _cached_fps)
    return seconds


def frames_to_seconds(frames: float, fps: float | None = None) -> float:
    """Explicit frames-to-seconds conversion (mode-independent)."""
    return frames / (fps or _cached_fps)


def seconds_to_frames(seconds: float, fps: float | None = None) -> float:
    """Explicit seconds-to-frames conversion (mode-independent)."""
    return seconds * (fps or _cached_fps)


# ---------------------------------------------------------------------------
# Property factory
# ---------------------------------------------------------------------------


def nexus_time_property(
    prop_id: str,
    *,
    name: str,
    description: str,
    default: float = 0.0,
    min: float = 0.0,
    soft_max: float = 1000.0,
    collection_path: str | tuple[str, ...] | list[str] | None = None,
    **kwargs,
) -> FloatProperty:
    """Create a time property and register it in the global time registry.

    prop_id:
        Unique identifier — must match the dict key in the PROPERTIES dict.
    name:
        Human-readable label shown in the UI.
    description:
        Tooltip text.
    default:
        Default value **in FRAMES** (the default display mode).
    min:
        Minimum allowed value.
    soft_max:
        Soft maximum for the slider range.
    collection_path:
        If this property lives on ``CollectionProperty`` items, specify the
        attribute name or names on ``NexusObjectProperties`` that hold them.
    **kwargs:
        Extra keyword arguments forwarded to ``FloatProperty()``.
    """
    if collection_path is not None:
        if isinstance(collection_path, str):
            _TIME_COLLECTION_REGISTRY.append((collection_path, prop_id))
        else:
            for path in collection_path:
                _TIME_COLLECTION_REGISTRY.append((path, prop_id))
    else:
        _TIME_PROPERTY_REGISTRY.add(prop_id)

    return FloatProperty(
        name=name,
        description=description,
        default=default,
        min=min,
        soft_max=soft_max,
        **kwargs,
    )


def get_time_property_names() -> set[str]:
    """Return the set of all registered time property names (direct props only)."""
    return set(_TIME_PROPERTY_REGISTRY)


def get_time_collection_properties() -> list[tuple[str, str]]:
    """Return ``[(collection_attr, prop_name), ...]`` for collection-based time props."""
    return list(_TIME_COLLECTION_REGISTRY)


# ---------------------------------------------------------------------------
# UI draw helper
# ---------------------------------------------------------------------------


def draw_time_prop(
    layout,
    data,
    prop_name: str,
    *,
    text: str | None = None,
    enabled: bool = True,
) -> None:
    """Draw a time property with a clickable ``f`` / ``s`` label.

    Click the label to toggle between Frames and Seconds for this property.
    Drop-in replacement for ``layout.prop(data, prop_name)``.

    layout:
        The ``bpy.types.UILayout`` to draw into.
    data:
        The data block owning the property (e.g. ``obj.nexus_modifier``
        or a collection item).
    prop_name:
        The property attribute name.
    text:
        Override label text.  If ``None``, uses the property's own ``name``.
    enabled:
        Whether the row is interactive.  Set ``False`` to grey it out.
    """
    mode = get_prop_time_mode(data, prop_name)

    rna_prop = data.bl_rna.properties.get(prop_name)
    label = text if text is not None else (rna_prop.name if rna_prop else prop_name)

    try:
        id_data = data.id_data
        obj_name = id_data.name if id_data else ""
        data_path = data.path_from_id() if id_data else ""
    except (AttributeError, TypeError):
        obj_name = ""
        data_path = ""

    row = layout.row(align=True)
    row.enabled = enabled
    row.prop(data, prop_name, text=label)

    sub = row.row(align=True)
    sub.ui_units_x = 1.2
    op = sub.operator(
        "nexus.toggle_time_mode",
        text="f" if mode == "FRAMES" else "s",
    )
    op.prop_name = prop_name
    op.object_name = obj_name
    op.data_path = data_path


# ---------------------------------------------------------------------------
# Object creation helpers
# ---------------------------------------------------------------------------


def init_time_modes(data, prop_names: set[str] | None = None) -> None:
    """Initialise per-property time modes on data to the global default."""
    mode = get_display_mode()
    fps = _cached_fps
    target_props = prop_names or _TIME_PROPERTY_REGISTRY

    for prop_name in target_props:
        rna_prop = data.bl_rna.properties.get(prop_name)
        if rna_prop is None:
            continue

        set_prop_time_mode(data, prop_name, mode)

        if mode == "SECONDS" and fps > 0:
            frame_value = getattr(data, prop_name)
            if frame_value != 0.0:
                setattr(data, prop_name, frame_value / fps)


def ensure_time_modes(data, prop_names: set[str] | None = None) -> None:
    mode = get_display_mode()
    fps = _cached_fps
    target_props = prop_names or _TIME_PROPERTY_REGISTRY

    for prop_name in target_props:
        rna_prop = data.bl_rna.properties.get(prop_name)
        if rna_prop is None:
            continue

        key = _MODE_KEY_PREFIX + prop_name
        if data.get(key) in ("FRAMES", "SECONDS"):
            continue

        set_prop_time_mode(data, prop_name, mode)
        if mode == "SECONDS" and fps > 0:
            frame_value = getattr(data, prop_name)
            if frame_value != 0.0:
                setattr(data, prop_name, frame_value / fps)


def convert_object_time_defaults(obj: bpy.types.Object, fps: float) -> None:
    """Initialise time modes and convert defaults on a newly created object."""
    try:
        props = obj.nexus_modifier
    except AttributeError:
        return

    init_time_modes(props)


# ---------------------------------------------------------------------------
# Bulk conversion (global preference switch)
# ---------------------------------------------------------------------------


def convert_all_time_properties(old_mode: str, new_mode: str, fps: float) -> int:
    """Convert every time property value on every NeXus object in the file."""
    import bpy

    if old_mode == new_mode or fps <= 0.0:
        return 0

    count = 0

    for obj in bpy.data.objects:
        if not obj.get("nexus_modifier_type"):
            continue

        try:
            props = obj.nexus_modifier
        except AttributeError:
            continue

        for prop_name in _TIME_PROPERTY_REGISTRY:
            rna_prop = props.bl_rna.properties.get(prop_name)
            if rna_prop is None:
                continue

            prop_mode = get_prop_time_mode(props, prop_name)
            if prop_mode != old_mode:
                continue

            old_value = getattr(props, prop_name)
            new_value = _convert_value(old_value, old_mode, new_mode, fps)
            if old_value != new_value:
                setattr(props, prop_name, new_value)
                count += 1
            set_prop_time_mode(props, prop_name, new_mode)

        for coll_attr, prop_name in _TIME_COLLECTION_REGISTRY:
            collection = getattr(props, coll_attr, None)
            if collection is None:
                continue
            for item in collection:
                if not hasattr(item, prop_name):
                    continue

                prop_mode = get_prop_time_mode(item, prop_name)
                if prop_mode != old_mode:
                    continue

                old_value = getattr(item, prop_name)
                new_value = _convert_value(old_value, old_mode, new_mode, fps)
                if old_value != new_value:
                    setattr(item, prop_name, new_value)
                    count += 1
                set_prop_time_mode(item, prop_name, new_mode)

    return count


def _convert_value(value: float, old_mode: str, new_mode: str, fps: float) -> float:
    """Convert a single value between display modes."""
    if old_mode == "FRAMES" and new_mode == "SECONDS":
        return value / fps
    elif old_mode == "SECONDS" and new_mode == "FRAMES":
        return value * fps
    return value
