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

"""Persistent per-object UID for NeXus modifier objects."""

from __future__ import annotations

import uuid
from typing import Iterable, Optional

import bpy

UID_KEY = "_nexus_object_uid"


def get_object_uid(obj: Optional[bpy.types.Object]) -> Optional[str]:
    if obj is None:
        return None
    try:
        uid = obj.get(UID_KEY)
    except (ReferenceError, AttributeError):
        return None
    return str(uid) if uid else None


def ensure_object_uid(obj: bpy.types.Object) -> str:
    """Read the UID, assigning a new one if missing. Write-safe contexts only."""
    existing = get_object_uid(obj)
    if existing:
        return existing
    uid = uuid.uuid4().hex
    obj[UID_KEY] = uid
    return uid


def regenerate_object_uid(obj: bpy.types.Object) -> str:
    uid = uuid.uuid4().hex
    obj[UID_KEY] = uid
    return uid


def get_object_key(obj: Optional[bpy.types.Object]) -> Optional[str]:
    if obj is None:
        return None
    try:
        return ensure_object_uid(obj)
    except (ReferenceError, AttributeError):
        return None


def resolve_uid_collisions(
    objects: Iterable[bpy.types.Object],
    session_uids: Optional[dict] = None,
) -> None:
    """Regenerate UIDs on Shift+D duplicates that copied a UID from the original.

    ``session_uids`` is the ``uid -> obj.session_uid`` map recorded when each
    handle was bound. The original is the obj whose session_uid matches; any
    other obj sharing the UID gets regenerated. A lone occupant whose
    session_uid no longer matches is the case where the duplicate survived
    the original's deletion — also regenerated, so the deletion-detection
    pass that follows frees the orphan handle.
    """
    grouped: dict[str, list[bpy.types.Object]] = {}
    for obj in objects:
        uid = get_object_uid(obj)
        if uid is None:
            continue
        grouped.setdefault(uid, []).append(obj)

    for uid, dupes in grouped.items():
        recorded = session_uids.get(uid) if session_uids is not None else None

        if len(dupes) == 1:
            if recorded is None:
                continue
            obj = dupes[0]
            try:
                if obj.session_uid != recorded:
                    regenerate_object_uid(obj)
            except (ReferenceError, AttributeError):
                pass
            continue

        original: Optional[bpy.types.Object] = None
        if recorded is not None:
            for obj in dupes:
                try:
                    if obj.session_uid == recorded:
                        original = obj
                        break
                except (ReferenceError, AttributeError):
                    continue
        if original is None:
            original = dupes[0]

        for obj in dupes:
            if obj is not original:
                regenerate_object_uid(obj)
