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

from . import cleanup, pipeline, render

_SHADER_COMPILE_SPINNER = "|/-\\"
_shader_compile_tick = 0


def _poll_shader_cache_progress():
    global _shader_compile_tick
    from ..libs import theron

    if not theron.is_initialized():
        return 0.5

    status = theron.check_shader_cache_status()
    if status is None:
        return 0.5

    compiled, total = status
    if total == 0:
        return None

    if compiled >= total:
        for ws in bpy.data.workspaces:
            ws.status_text_set(text=None)
        return None

    _shader_compile_tick += 1
    spinner = _SHADER_COMPILE_SPINNER[_shader_compile_tick % 4]
    pct = int(compiled / total * 100)
    filled = int(compiled / total * 20)
    bar = "█" * filled + "░" * (20 - filled)
    for ws in bpy.data.workspaces:
        ws.status_text_set(text=f"INSYDIUM NeXus: Compiling shaders  [{bar}]  {pct}%  {spinner}")
    return 0.5


def _remove_all_nexus_handlers():
    handler_lists = [
        bpy.app.handlers.frame_change_post,
        bpy.app.handlers.depsgraph_update_post,
        bpy.app.handlers.load_post,
        bpy.app.handlers.render_pre,
        bpy.app.handlers.render_complete,
        bpy.app.handlers.render_cancel,
    ]

    for handler_list in handler_lists:
        for i in range(len(handler_list) - 1, -1, -1):
            handler = handler_list[i]
            if getattr(handler, "_nexus_handler", False):
                handler_list.remove(handler)


def _eager_init_existing_scenes():
    from ..libs import theron

    if not theron.is_initialized():
        return None
    for scene in bpy.data.scenes:
        pipeline.ensure_pipeline_for_scene(scene)
    return None


def register():
    cleanup.register()
    from ..libs import theron

    theron.init()

    if not bpy.app.timers.is_registered(_poll_shader_cache_progress):
        bpy.app.timers.register(_poll_shader_cache_progress, first_interval=0.5)

    pipeline.register()
    render.register()

    bpy.app.timers.register(_eager_init_existing_scenes, first_interval=0.0)


def unregister():
    render.unregister()
    pipeline.unregister()
    cleanup.unregister()
