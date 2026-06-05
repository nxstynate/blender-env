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

"""NX_TRAIL staging constants. Mirror viewport/backend/src/staged_common.h."""

from __future__ import annotations

TRAIL_HEADER_BYTES: int = 16  # NEXUS_TRAIL_HEADER_BYTES.

TRAIL_SEGMENT_BYTES: int = 16  # NEXUS_TRAIL_SEGMENT_BYTES.

TRAIL_DEFAULT_COLOR: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
