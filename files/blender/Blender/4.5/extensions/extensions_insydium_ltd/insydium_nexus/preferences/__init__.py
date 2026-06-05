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
from datetime import datetime

from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import AddonPreferences

from ..libs import theron
from ..properties.nx_cache import _DEFAULT_CACHE_DIR

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    import PyQt6  # noqa: F401

    _PYQT6_AVAILABLE = True
except ImportError:
    _PYQT6_AVAILABLE = False


def _mask_license_key(key: str) -> str:
    if not key:
        return ""
    parts = key.split("-")
    if len(parts) <= 4:
        return key
    return "-".join(parts[:3] + ["###"] * (len(parts) - 4) + [parts[-1]])


_license_display_updating = False
_license_revert_in_progress = False
_last_valid_license = None
_pending_check = False
_check_token = 0


def _license_fields_complete(prefs) -> bool:
    return (
        bool(prefs.license_key.strip())
        and bool(prefs.license_name.strip())
        and bool(prefs.license_email.strip())
    )


def _redraw_prefs_panels() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "PREFERENCES":
                    area.tag_redraw()
    except Exception:
        pass


def _revert_license_fields(prefs, key: str, name: str, email: str) -> None:
    global _license_display_updating, _license_revert_in_progress
    _license_display_updating = True
    _license_revert_in_progress = True
    try:
        prefs.license_name = name
        prefs.license_email = email
        prefs.license_key = key
        prefs.license_key_display = _mask_license_key(key)
    finally:
        _license_display_updating = False
        _license_revert_in_progress = False


def _try_register_license(prefs) -> None:
    global _pending_check, _check_token, _last_valid_license

    if _license_revert_in_progress:
        return

    _check_token += 1
    my_token = _check_token

    if not _license_fields_complete(prefs):
        _pending_check = False
        theron.shutdown()
        _redraw_prefs_panels()
        return

    new_state = (prefs.license_key, prefs.license_name, prefs.license_email)

    if new_state == _last_valid_license and theron.is_initialized():
        _pending_check = False
        _redraw_prefs_panels()
        return

    _pending_check = True
    _redraw_prefs_panels()

    def _do_check():
        global _pending_check, _last_valid_license, _license_display_updating
        if my_token != _check_token:
            return None
        theron.shutdown()
        try:
            ok = theron.init()
        except Exception:
            ok = False
        if ok:
            _last_valid_license = new_state
            try:
                from .. import register_full

                register_full()
            except Exception:
                pass
            try:
                from ..handlers import start_precompile_if_needed

                start_precompile_if_needed()
            except Exception:
                pass

            def _do_mask():
                global _license_display_updating
                if my_token != _check_token:
                    return None
                masked = _mask_license_key(prefs.license_key)
                if prefs.license_key_display != masked:
                    _license_display_updating = True
                    prefs.license_key_display = masked
                    _license_display_updating = False
                    _redraw_prefs_panels()
                return None

            bpy.app.timers.register(_do_mask, first_interval=2.0)
        elif _last_valid_license is not None:
            _revert_license_fields(prefs, *_last_valid_license)
            try:
                theron.init()
            except Exception:
                pass
        _pending_check = False
        _redraw_prefs_panels()
        return None

    bpy.app.timers.register(_do_check, first_interval=0.05)


def _on_license_identity_update(self, context):
    if _license_revert_in_progress:
        return
    _try_register_license(self)


def get_license_status() -> tuple:
    if _pending_check:
        return ("Checking license...", "SORTTIME", False)
    if theron.is_initialized():
        return ("License active", "CHECKMARK", False)
    msg = theron.get_license_message() if hasattr(theron, "get_license_message") else ""
    if msg:
        return (msg, "ERROR", True)
    return ("", "NONE", False)


def _on_license_key_display_update(self, context):
    global _license_display_updating
    if _license_display_updating:
        return

    new_val = self.license_key_display
    masked = _mask_license_key(self.license_key)

    if new_val == masked:
        return

    if new_val == "":
        self.license_key = ""
        _try_register_license(self)
        return

    if new_val == self.license_key:
        return

    self.license_key = new_val
    _try_register_license(self)


def _on_time_display_mode_update(self, context):
    """Convert all existing time property values when the user switches mode."""
    from ..libs.nexus_time import convert_all_time_properties

    new_mode = self.time_display_mode
    old_mode = "SECONDS" if new_mode == "FRAMES" else "FRAMES"

    fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-6)
    count = convert_all_time_properties(old_mode, new_mode, fps)

    if count > 0:
        for area in context.screen.areas:
            area.tag_redraw()


@bpy.app.handlers.persistent
def _init_license_display(dummy):
    global _license_display_updating, _last_valid_license
    try:
        pkg = __package__.rsplit(".", 1)[0]
        prefs = bpy.context.preferences.addons[pkg].preferences
        masked = _mask_license_key(prefs.license_key)
        if prefs.license_key_display != masked:
            _license_display_updating = True
            prefs.license_key_display = masked
            _license_display_updating = False
        if theron.is_initialized() and _license_fields_complete(prefs):
            _last_valid_license = (
                prefs.license_key,
                prefs.license_name,
                prefs.license_email,
            )
    except Exception:
        _license_display_updating = False


def _on_accelerated_viewport_update(self, context):
    """Reset the runtime Basic lock and redraw 3D viewports when the pref toggles."""
    from ..viewport import registry

    registry._LOCK_TO_BASIC = False

    import bpy

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _on_vram_limit_update(self, context):
    if not theron.is_initialized():
        return
    gb = self.vram_limit_gb
    total_bytes = theron.get_total_vram()
    if total_bytes > 0 and gb > 0.0:
        gb = min(gb, total_bytes / 1_000_000_000)
    vram_bytes = int(gb * 1_000_000_000) if gb > 0.0 else 0
    theron.set_vram_limit(vram_bytes)


class NeXusPreferences(AddonPreferences):
    bl_idname = __package__.rsplit(".", 1)[0]

    license_name: StringProperty(
        name="Name",
        description="Registered name",
        default="",
        update=_on_license_identity_update,
    )

    license_email: StringProperty(
        name="Email",
        description="Registered email",
        default="",
        update=_on_license_identity_update,
    )

    license_key: StringProperty(
        name="License",
        description="Your INSYDIUM license",
        default="",
        options={"HIDDEN"},
        update=_on_license_identity_update,
    )

    license_key_display: StringProperty(
        name="License",
        description="Your INSYDIUM license",
        default="",
        update=_on_license_key_display_update,
    )

    cache_directory: StringProperty(
        name="Cache Directory",
        description="Default directory for new cache objects",
        default=_DEFAULT_CACHE_DIR,
        subtype="DIR_PATH",
    )

    time_display_mode: EnumProperty(
        name="Default Time Display",
        description=(
            "Default display mode for time properties. "
            "FRAMES: values are frame counts (e.g. 90). "
            "SECONDS: values are in seconds (e.g. 3.75). "
            "Switching converts all existing values that match the old default. "
            "Individual properties can be toggled by clicking their label"
        ),
        items=[
            ("FRAMES", "Frames (f)", "Display time values as frame counts"),
            ("SECONDS", "Seconds (s)", "Display time values in seconds"),
        ],
        default="FRAMES",
        update=_on_time_display_mode_update,
    )

    vram_limit_gb: FloatProperty(
        name="VRAM Limit (GB)",
        description=(
            "Maximum GPU memory NeXus may use, in gigabytes. Set to 0 to use all available VRAM"
        ),
        default=0.0,
        min=0.0,
        soft_max=64.0,
        step=50,
        precision=1,
        update=_on_vram_limit_update,
    )

    accelerated_viewport: BoolProperty(
        name="Accelerated Viewport",
        description=(
            "Use the platform's accelerated zero-copy renderer "
            "(Vulkan/OpenGL on Windows & Linux, Metal on macOS) "
            "with automatic fallback to Basic if it isn't available. "
            "Untick to force Basic CPU upload for all emitters"
        ),
        default=True,
        update=_on_accelerated_viewport_update,
    )

    def draw(self, context):
        from .. import version

        layout = self.layout

        if not _PYQT6_AVAILABLE:
            layout.label(
                text="PyQt6 not found: some dialogs may not work."
                " Try reinstalling the add-on to fix this.",
                icon="ERROR",
            )

        # Licensing
        layout.label(text="Licensing", icon="LOCKED")
        col = layout.column()
        col.prop(self, "license_name")
        col.prop(self, "license_email")
        col.prop(self, "license_key_display", text="License")

        status_text, status_icon, status_alert = get_license_status()
        if status_text:
            status_row = layout.row()
            status_row.alert = status_alert
            status_row.label(text=status_text, icon=status_icon)

        if not theron.is_initialized():
            return

        layout.separator()

        # General
        layout.label(text="General", icon="PREFERENCES")
        col = layout.column()
        col.prop(self, "accelerated_viewport")
        if self.accelerated_viewport:
            from ..viewport.registry import is_locked_to_basic

            if is_locked_to_basic():
                col.label(
                    text=(
                        "Accelerated path failed this session — using Basic. "
                        "Untick and re-tick to retry."
                    ),
                    icon="INFO",
                )
        col.prop(self, "vram_limit_gb")

        layout.separator()

        # Time display
        layout.label(text="Time Display", icon="TIME")
        layout.prop(self, "time_display_mode", expand=True)

        layout.separator()

        # Cache
        layout.label(text="Cache", icon="FILE_FOLDER")
        layout.prop(self, "cache_directory", text="Default Directory")

        layout.separator()

        # Version info
        _bd = theron.get_build_date()
        build_date_str = (
            datetime.fromtimestamp(_bd).strftime("%Y-%m-%d %H:%M:%S") if _bd else "N/A"
        )
        layout.label(text="Version Details", icon="INFO")
        col = layout.column(align=True)
        for label, value in (
            ("Add-on version:", f"v{version.get_blender_version_str()}"),
            ("Core version:", f"v{theron.get_version_str()}"),
            ("Build type:", theron.get_build_type()),
            ("Build date:", build_date_str),
        ):
            row = col.split(factor=0.2)
            lhs = row.column()
            lhs.alignment = "RIGHT"
            lhs.label(text=label)
            row.label(text=value)


classes = [
    NeXusPreferences,
]


def register():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError:
            pass

    bpy.app.handlers.load_post.append(_init_license_display)
    _init_license_display(None)


def unregister():
    from bpy.utils import unregister_class

    if _init_license_display in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_init_license_display)

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass
