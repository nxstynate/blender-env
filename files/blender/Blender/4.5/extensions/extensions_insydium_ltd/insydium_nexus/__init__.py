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

from . import (
    editors,
    gizmos,
    handlers,
    icons,
    menus,
    modifiers,
    operators,
    panels,
    pipeline_manager,
    preferences,
    properties,
    ui,
    viewport,
)

bl_info = {
    "name": "INSYDIUM NeXus (BETA)",
    "author": "INSYDIUM LTD <support@insydium.ltd>",
    "version": (2026, 0, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Add > INSYDIUM > NeXus",
    "description": "NeXus tools for Blender",
    "category": "Physics",
}

_needs_reload = "bpy" in locals()
_fully_registered = locals().get("_fully_registered", False)

if _needs_reload:
    if _fully_registered:
        from .libs import mapping_metadata as _mapping_metadata
        from .libs import theron

        theron.begin_shutdown()

        from .handlers import _remove_all_nexus_handlers

        _remove_all_nexus_handlers()

        from .handlers import pipeline as _pipeline_handler

        _pipeline_handler.destroy_all_pipelines()

        theron.shutdown()
        _mapping_metadata.invalidate_cache()

    import importlib

    icons = importlib.reload(icons)
    ui = importlib.reload(ui)
    editors = importlib.reload(editors)
    modifiers = importlib.reload(modifiers)
    operators = importlib.reload(operators)
    gizmos = importlib.reload(gizmos)
    panels = importlib.reload(panels)
    properties = importlib.reload(properties)
    preferences = importlib.reload(preferences)
    menus = importlib.reload(menus)
    viewport = importlib.reload(viewport)
    handlers = importlib.reload(handlers)
    pipeline_manager = importlib.reload(pipeline_manager)

    _fully_registered = False


def _show_no_license_status():
    import bpy as _bpy
    try:
        from .libs import theron as _theron
        if _theron.is_initialized():
            return None
        for ws in _bpy.data.workspaces:
            ws.status_text_set(
                text="INSYDIUM NeXus: No valid license. Open Preferences to enter your license."
            )
        _bpy.app.timers.register(_clear_no_license_status, first_interval=10.0)
        return None
    except Exception:
        return None


def _clear_no_license_status():
    import bpy as _bpy
    for ws in _bpy.data.workspaces:
        ws.status_text_set(text=None)
    return None


def register():
    icons.register()
    preferences.register()

    import bpy

    def _try_init_on_start():
        from .libs import theron
        try:
            prefs = bpy.context.preferences.addons[__package__].preferences
        except (KeyError, AttributeError):
            return
        if prefs.license_key and prefs.license_name and prefs.license_email:
            theron.init()
        register_full()
        if not theron.is_initialized():
            if not bpy.app.timers.is_registered(_show_no_license_status):
                bpy.app.timers.register(_show_no_license_status, first_interval=1.0)

    bpy.app.timers.register(_try_init_on_start, first_interval=0.0)


def register_full():
    """Register all NeXus components. Called once at startup and after runtime license entry."""

    global _fully_registered
    if _fully_registered:
        return

    ui.register()
    properties.register()
    modifiers.register()
    operators.register()
    gizmos.register()
    panels.register()
    menus.register()
    viewport.register()
    pipeline_manager.register()
    handlers.register()

    from .ui import validate_pending_nx_types

    validate_pending_nx_types()

    _fully_registered = True


def unregister():
    global _fully_registered

    if _fully_registered:
        from .libs import mapping_metadata, theron

        theron.begin_shutdown()

        from .handlers import _remove_all_nexus_handlers

        _remove_all_nexus_handlers()

        viewport.unregister()

        from .handlers import pipeline as pipeline_handler

        pipeline_handler.destroy_all_pipelines()

        theron.shutdown()
        mapping_metadata.invalidate_cache()

        handlers.unregister()
        pipeline_manager.unregister()
        menus.unregister()
        panels.unregister()
        gizmos.unregister()
        operators.unregister()
        modifiers.unregister()
        properties.unregister()
        ui.unregister()

        _fully_registered = False

    preferences.unregister()
    icons.unregister()


if __name__ == "__main__":
    register()
