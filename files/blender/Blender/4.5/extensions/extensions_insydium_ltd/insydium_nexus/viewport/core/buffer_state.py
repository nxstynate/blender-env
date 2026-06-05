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

"""Buffer lifecycle tracking for zero-copy viewport rendering."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any


def _buffer_identity(handle: int | None, uid: int = 0) -> Any:
    """Stable identity for an external GPU buffer handle.

    Uses ``uid`` (export-time stable id) when available.
    """
    if not handle:
        return None
    if uid:
        return int(uid)
    return int(handle)


def _release_handle(handle: int) -> None:
    """Close a Theron-exported fd (Linux only).

    Win32 source closes are refcounted centrally in
    ``libs.theron._track_win32_source_handle`` — doing it per BufferExport
    here would double-close any HANDLE shared between fetches.
    """
    if sys.platform in ("win32", "darwin"):
        return
    try:
        h = int(handle)
    except (TypeError, ValueError):
        return
    if h <= 0:
        return
    try:
        os.close(h)
    except OSError:
        pass


@dataclass
class BufferExport:
    """A single GPU buffer export from Theron (handle + size + uid)."""

    handle: int = 0
    size: int = 0
    uid: int = 0

    @property
    def valid(self) -> bool:
        if self.handle in (None, 0) or self.size <= 0:
            return False
        try:
            return int(self.handle) > 0
        except (TypeError, ValueError):
            return False

    @property
    def identity(self) -> Any:
        return _buffer_identity(self.handle, self.uid)

    def consume(self) -> None:
        """Mark the underlying handle as transferred (driver took ownership)."""
        self.handle = 0

    def __del__(self) -> None:
        handle = self.handle
        self.handle = 0
        if handle:
            _release_handle(handle)


def buf_identity(buf: BufferExport | None) -> Any:
    """Cache key for any buffer slot.  Handles missing/invalid uniformly."""
    return buf.identity if (buf is not None and buf.valid) else None


@dataclass
class BufferState:
    """Tracks the last-known state of a single buffer handle."""

    handle: int | None = None
    size: int = 0
    identity: Any = None

    @property
    def valid(self) -> bool:
        return self.handle is not None and self.size > 0

    def changed(self, new_handle: int | None, new_size: int, new_uid: int = 0) -> bool:
        if self.size != new_size:
            return True
        return self.identity != _buffer_identity(new_handle, new_uid)

    def update(self, handle: int | None, size: int, uid: int = 0) -> None:
        self.handle = handle
        self.size = size
        self.identity = _buffer_identity(handle, uid)

    def reset(self) -> None:
        self.handle = None
        self.size = 0
        self.identity = None


_SLOT_NAMES: tuple[str, ...] = (
    "position",
    "velocity",
    "radius",
    "color",
    "rotation",
    "emitter_index",
    "prefix",
    "binned",
)


@dataclass
class BufferTracker:
    """Centralised change-detection for all particle buffer handles.

    Each slot is a ``BufferState`` keyed by name. Callers pass
    ``BufferExport`` objects by keyword to ``needs_reconfigure`` / ``update``.
    """

    position: BufferState = field(default_factory=BufferState)
    velocity: BufferState = field(default_factory=BufferState)
    radius: BufferState = field(default_factory=BufferState)
    color: BufferState = field(default_factory=BufferState)
    rotation: BufferState = field(default_factory=BufferState)
    emitter_index: BufferState = field(default_factory=BufferState)
    prefix: BufferState = field(default_factory=BufferState)
    binned: BufferState = field(default_factory=BufferState)
    shape: str | None = None
    count: int = 0

    def needs_reconfigure(
        self,
        shape: str,
        count: int,
        **buffers: BufferExport | None,
    ) -> bool:
        if self.shape != shape or self.count != count:
            return True
        for name in _SLOT_NAMES:
            buf = buffers.get(name)
            valid = buf is not None and buf.valid
            new_h = buf.handle if valid else None
            new_s = buf.size if valid else 0
            new_uid = buf.uid if valid else 0
            if getattr(self, name).changed(new_h, new_s, new_uid):
                return True
        return False

    def update(
        self,
        shape: str,
        count: int,
        **buffers: BufferExport | None,
    ) -> None:
        self.shape = shape
        self.count = count
        for name in _SLOT_NAMES:
            buf = buffers.get(name)
            state: BufferState = getattr(self, name)
            if buf is not None and buf.valid:
                state.update(buf.handle, buf.size, buf.uid)
            else:
                state.reset()

    def reset(self) -> None:
        for name in _SLOT_NAMES:
            getattr(self, name).reset()
        self.shape = None
        self.count = 0
