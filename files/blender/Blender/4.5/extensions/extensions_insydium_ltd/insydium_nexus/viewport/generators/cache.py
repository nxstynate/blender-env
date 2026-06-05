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

"""Python-side cache for NX_GENERATOR mesh extraction.

Per-loop extraction runs on the CPU each frame and becomes meaningful overhead
for high-poly meshes even when the GPU upload is already cached. This module
memoises the result and invalidates entries from ``depsgraph.updates`` so users
still see edits immediately.
"""

from __future__ import annotations

import bpy

from ...utils import extract_mesh_loop_data

# Key: (mesh_object.session_uid, mesh_data.session_uid)
# Value: (loop_positions_f32, corner_normals_f32, smooth_normals_f32,
#         tri_idx_u32, loop_count, tri_count)
_MESH_CACHE: dict[tuple[int, int], tuple] = {}


def _cache_key(mesh_obj) -> tuple[int, int] | None:
    if mesh_obj is None or mesh_obj.data is None:
        return None
    return (mesh_obj.session_uid, mesh_obj.data.session_uid)


def get_or_extract_mesh(mesh_obj, depsgraph):
    """Return cached per-loop mesh data for *mesh_obj* or extract.

    Returns (loop_positions, corner_normals, smooth_normals, tri_idx,
    loop_count, tri_count) or ``None`` if extraction fails or yields empty
    geometry.
    """
    key = _cache_key(mesh_obj)
    if key is None:
        return None
    cached = _MESH_CACHE.get(key)
    if cached is not None:
        return cached

    extracted = extract_mesh_loop_data(mesh_obj, depsgraph)
    if extracted is None:
        return None

    _MESH_CACHE[key] = extracted
    return extracted


def invalidate_from_depsgraph(depsgraph) -> None:
    """Drop cache entries whose source mesh changed since the last evaluation."""
    if depsgraph is None or not _MESH_CACHE:
        return

    invalid_obj_uids: set[int] = set()
    invalid_data_uids: set[int] = set()
    for upd in depsgraph.updates:
        if not getattr(upd, "is_updated_geometry", False):
            continue
        id_block = upd.id
        if isinstance(id_block, bpy.types.Mesh):
            invalid_data_uids.add(id_block.session_uid)
        elif isinstance(id_block, bpy.types.Object) and id_block.type == "MESH":
            invalid_obj_uids.add(id_block.session_uid)
            if id_block.data is not None:
                invalid_data_uids.add(id_block.data.session_uid)

    if not invalid_obj_uids and not invalid_data_uids:
        return

    stale = [k for k in _MESH_CACHE if k[0] in invalid_obj_uids or k[1] in invalid_data_uids]
    for k in stale:
        _MESH_CACHE.pop(k, None)


def clear() -> None:
    """Drop all cached meshes (called on shutdown)."""
    _MESH_CACHE.clear()
    _FROZEN_MESH_CACHE.clear()


# In-memory only; the load-restore path repopulates it after .blend reopen.
_FROZEN_MESH_CACHE: dict[tuple[int, int], tuple] = {}

# Set while load-restore is briefly seeking to each frozen_frame so the
# frame-change handler skips a sim step during the seek.
_LOAD_CAPTURE_IN_PROGRESS = False


def load_capture_in_progress() -> bool:
    return _LOAD_CAPTURE_IN_PROGRESS


def restore_frozen_meshes_for_scene(scene) -> None:
    global _LOAD_CAPTURE_IN_PROGRESS

    wanted: dict[tuple[int, int], object] = {}
    for obj in scene.objects:
        if obj.get("nexus_modifier_type") != "NX_GENERATOR":
            continue
        props = obj.nexus_modifier
        for layer in props.generator_layers:
            if not getattr(layer, "freeze_animation", False):
                continue
            mesh_obj = layer.obj
            if mesh_obj is None or mesh_obj.data is None:
                continue
            frame = int(getattr(layer, "frozen_frame", 0))
            key = (mesh_obj.original.session_uid, frame)
            if key in _FROZEN_MESH_CACHE:
                continue
            wanted[key] = mesh_obj

    if not wanted:
        return

    saved_frame = scene.frame_current
    _LOAD_CAPTURE_IN_PROGRESS = True
    try:
        for (_uid, frame), mesh_obj in wanted.items():
            if scene.frame_current != frame:
                scene.frame_set(frame)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            capture_frozen_mesh(mesh_obj, frame, depsgraph)
        if scene.frame_current != saved_frame:
            scene.frame_set(saved_frame)
    finally:
        _LOAD_CAPTURE_IN_PROGRESS = False


def _frozen_key(mesh_obj, frame: int) -> tuple[int, int]:
    # ``.original`` normalises eval-wrapped objects (session_uid == 0) to
    # match the orig-side key used by the capture path.
    return (mesh_obj.original.session_uid, int(frame))


def capture_frozen_mesh(mesh_obj, frame: int, depsgraph) -> bool:
    if mesh_obj is None or mesh_obj.data is None:
        return False
    extracted = extract_mesh_loop_data(mesh_obj, depsgraph)
    if extracted is None:
        return False
    _FROZEN_MESH_CACHE[_frozen_key(mesh_obj, frame)] = extracted
    return True


def get_frozen_mesh(mesh_obj, frame: int):
    if mesh_obj is None:
        return None
    return _FROZEN_MESH_CACHE.get(_frozen_key(mesh_obj, frame))
