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

"""Shared staging helper for the native (Vulkan/Metal) constraint backends.

Each frame the stager:

1. Fetches the three external GPU buffers Theron publishes for constraints —
   the constraint array, the centralised id-LUT (with its capacity), and the
   per-particle id buffer that the LUT walks against.
2. Calls ``bridge.configure_constraints`` to forward the handles + sizes
   into the C++ DLL (vk_constraints / metal_constraints), which import them
   and rewrite the descriptor set.
3. Stages the per-emitter palette + global enable flag.

The actual draw is recorded on the C++ side as part of
``vk_indirect_record_all_modes`` / ``metal_indirect_record_all_modes``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bridges.native import NativeBridge
    from ..registry import ConstraintDrawParams

# Cache sentinel: matched by value so a steady disabled state doesn't re-clear.
_CLEARED_STATE = (None, 0, None, 0, 0, None, 0)


class ConstraintsNativeStager:
    """Stage per-frame constraint overlay data into a NativeBridge."""

    def __init__(self, bridge: "NativeBridge") -> None:
        self._bridge = bridge
        self._configured: tuple | None = None

    def shutdown(self) -> None:
        self._configured = None

    def stage(self, context, pipeline, params: "ConstraintDrawParams") -> bool:  # noqa: ARG002
        if not self._bridge.is_available() or not self._bridge.load():
            return False

        self._bridge.stage_constraint_overlay_enabled(params.overlay_enabled)
        if params.emitter_constraint_palettes or params.emitter_display_constraints:
            self._bridge.stage_emitter_constraint_palette(
                params.emitter_constraint_palettes,
                params.emitter_display_constraints,
            )

        from ..core.buffer_state import buf_identity
        from ..core.particle_renderer import ParticleRenderer as PR

        constraints_buf = None
        lut_buf = None
        lut_capacity = 0
        particle_id_buffer = None

        if params.overlay_enabled and pipeline is not None:
            constraints_buf = PR.fetch_constraints_buffer(int(pipeline))
            lut_pair = PR.fetch_id_lut_buffer(int(pipeline))
            particle_id_buffer = PR.fetch_gpu_buffer(int(pipeline), "id")
            if lut_pair is not None:
                lut_buf, lut_capacity = lut_pair
            if constraints_buf is None or lut_buf is None or particle_id_buffer is None:
                constraints_buf = lut_buf = particle_id_buffer = None
                lut_capacity = 0

        if constraints_buf is None:
            desired = _CLEARED_STATE
        else:
            desired = (
                buf_identity(constraints_buf),
                constraints_buf.size,
                buf_identity(lut_buf),
                lut_buf.size,
                lut_capacity,
                buf_identity(particle_id_buffer),
                particle_id_buffer.size,
            )

        if desired == self._configured:
            return True

        self._bridge.configure_constraints(
            constraints_buf.handle if constraints_buf is not None else None,
            constraints_buf.size if constraints_buf is not None else 0,
            lut_buf.handle if lut_buf is not None else None,
            lut_buf.size if lut_buf is not None else 0,
            lut_capacity,
            particle_id_buffer.handle if particle_id_buffer is not None else None,
            particle_id_buffer.size if particle_id_buffer is not None else 0,
        )
        self._configured = desired
        return True
