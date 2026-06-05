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

"""On-demand and live VDB export hooks for nxExplosiaFX.

Two paths feed into the same per-modifier output:

* ``render_pre`` — triggered before each rendered frame (e.g., F12 / animation render).
  Active for both ``ON_RENDER`` and ``LIVE`` modes.

* ``frame_change_post`` — triggered every time the scene timeline advances.
  Active only for ``LIVE`` mode. Registered after ``handlers/pipeline.py``
  own frame handler so that the Theron's pipeline has already run by the
  time we read its smoke and temperature fields.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ..pipeline_manager.identity import ensure_object_uid
from ..viewport.volume import render_volume, vdb_cache

# Set to True to output per-frame diagnostics to stdout.
_DEBUG = False
_TAG = "[nx_explosiafx render]"


def _log(msg: str) -> None:
    if _DEBUG:
        print(f"{_TAG} {msg}")


def _iter_efx_modifiers(scene: bpy.types.Scene, *, modes: frozenset[str]):
    """Yield (obj, props) for ExplosiaFX modifiers whose VDB mode is in ``modes``."""
    for obj in scene.objects:
        if obj.get("nexus_modifier_type") != "NX_EXPLOSIAFX":
            continue
        props = getattr(obj, "nexus_modifier", None)
        if props is None:
            continue
        if not getattr(props, "enabled", True):
            continue
        mode = getattr(props, "explosiafx_render_volume_mode", "OFF")
        if mode not in modes:
            continue
        yield obj, props


def _write_for_modifier(
    scene: bpy.types.Scene, obj: bpy.types.Object, props, *, source: str
) -> bool:
    """Write VDB for one modifier and rebind its Volume datablock. Returns True on success.

    At frames ``<= frame_start`` Theron has not yet run a simulation step,
    so we write an *empty* VDB (no active voxels). The writer compacts to non-zero
    region. Cycles / Eevee read that as no volume data, and nothing is displayed.
    """
    from .pipeline import get_modifier_handle

    mod_uid = ensure_object_uid(obj)

    if scene.frame_current <= scene.frame_start:
        path = render_volume.next_cache_filepath(props, mod_uid)
        if not vdb_cache.write_efx_vdb_blank(path):
            _log(f"  write_efx_vdb_blank returned False for {obj.name} ({source})")
            return False
        render_volume.update_render_volume(obj, scene, frame_filepath=path)
        render_volume.reload_render_volume(obj)
        render_volume.prune_cache(props, mod_uid)
        _log(f"  wrote BLANK {path} for {obj.name} ({source}) — at/before start frame")
        return True

    handle = get_modifier_handle(scene, obj)
    if handle is None:
        _log(f"  skip {obj.name} ({source}): no Theron handle")
        return False

    ambient_temperature = float(getattr(props, "ID_NX_EXPLOSIAFX_AMBIENT_TEMP", 0.0))

    # Unique filename per write:
    # The renderers have an internal cache of parsed VDB files that seems to be
    # keyed on absolute path, and revisiting any path results in stale data
    # (confirmed in testing, including when using ``volume.data.unload()`` to force cleanup).
    # ``prune_cache`` below bounds the on-disk file count.
    path = render_volume.next_cache_filepath(props, mod_uid)

    if not vdb_cache.write_efx_vdb(handle, path, ambient_temperature):
        _log(f"  write_efx_vdb returned False for {obj.name} ({source})")
        return False

    render_volume.update_render_volume(obj, scene, frame_filepath=path)
    render_volume.reload_render_volume(obj)
    render_volume.prune_cache(props, mod_uid)
    _log(f"  wrote {path} for {obj.name} ({source})")
    return True


# ---------------------------------------------------------------------------
# Render trigger (ON_RENDER and LIVE)
# ---------------------------------------------------------------------------


@persistent
def _on_render_pre(scene: bpy.types.Scene, _depsgraph=None):
    _log(f"render_pre fired for scene='{scene.name}' frame={scene.frame_current}")
    for obj, props in _iter_efx_modifiers(scene, modes=frozenset({"ON_RENDER", "LIVE"})):
        _write_for_modifier(scene, obj, props, source="render_pre")


@persistent
def _on_render_complete(_scene: bpy.types.Scene, _depsgraph=None):
    return


@persistent
def _on_render_cancel(_scene: bpy.types.Scene, _depsgraph=None):
    return


# ---------------------------------------------------------------------------
# Live trigger (LIVE only)
# ---------------------------------------------------------------------------


@persistent
def _on_frame_change_post(scene: bpy.types.Scene, _depsgraph=None):
    # Cheap fast path — most projects don't use LIVE.
    for obj, props in _iter_efx_modifiers(scene, modes=frozenset({"LIVE"})):
        _write_for_modifier(scene, obj, props, source="frame_change")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


_on_render_pre._nexus_handler = True
_on_render_complete._nexus_handler = True
_on_render_cancel._nexus_handler = True
_on_frame_change_post._nexus_handler = True


def register():
    if _on_render_pre not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(_on_render_pre)
    if _on_render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(_on_render_complete)
    if _on_render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(_on_render_cancel)
    if _on_frame_change_post not in bpy.app.handlers.frame_change_post:
        # Appended after pipeline.py's frame_change_post so Theron's sim step
        # has already executed before reading fields.
        bpy.app.handlers.frame_change_post.append(_on_frame_change_post)
    _log(
        f"registered render_pre + frame_change_post handlers "
        f"(render_pre={len(bpy.app.handlers.render_pre)}, "
        f"frame_change_post={len(bpy.app.handlers.frame_change_post)})"
    )


def unregister():
    if _on_render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(_on_render_pre)
    if _on_render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(_on_render_complete)
    if _on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(_on_render_cancel)
    if _on_frame_change_post in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_on_frame_change_post)
