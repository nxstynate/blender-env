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

"""Shared draw logic for all native (Vulkan/Metal) particle modes."""

from __future__ import annotations

from ..bridges.native import NativeBridge
from ..core.particle_renderer import ParticleRenderer


class NativeParticleBase(ParticleRenderer):
    """Base for native zero-copy particle renderers.

    Subclasses override ``draw`` to fetch mode-specific buffers and call
    the appropriate ``bridge.configure_*`` method. Frame staging and the
    sentinel draw are shared.
    """

    def __init__(self, bridge: NativeBridge) -> None:
        self._bridge = bridge

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _stage_emitter_settings(self, params) -> None:
        sizes = tuple(float(x) for x in getattr(params, "emitter_point_sizes", ()) or ())
        colors = tuple(
            tuple(float(c) for c in rgba[:4])
            for rgba in (getattr(params, "emitter_colors", ()) or ())
        )
        rotation_modes = tuple(
            int(x) for x in (getattr(params, "emitter_rotation_modes", ()) or ())
        )
        up_vectors = tuple(
            tuple(float(c) for c in vec[:3])
            for vec in (getattr(params, "emitter_rotation_up_vectors", ()) or ())
        )
        line_length_modes = tuple(
            int(x) for x in (getattr(params, "emitter_line_length_modes", ()) or ())
        )
        line_fixed_lengths = tuple(
            float(x) for x in (getattr(params, "emitter_line_fixed_lengths", ()) or ())
        )
        line_min_lengths = tuple(
            float(x) for x in (getattr(params, "emitter_line_min_lengths", ()) or ())
        )
        line_max_lengths = tuple(
            float(x) for x in (getattr(params, "emitter_line_max_lengths", ()) or ())
        )
        self._bridge.stage_emitter_settings(
            sizes,
            colors,
            rotation_modes,
            up_vectors,
            line_length_modes,
            line_fixed_lengths,
            line_min_lengths,
            line_max_lengths,
            default_size=float(params.size),
            default_color=tuple(float(c) for c in params.color[:4]),
        )

    def _stage_and_draw(self, context, params) -> bool:
        """Stage frame parameters and issue the sentinel draw."""
        bridge = self._bridge
        region_data, region = self.get_region_info(context)
        if region_data is None or region is None:
            return False
        bridge.stage_particle_params(params.color, params.size)
        vm = [region_data.view_matrix[i][j] for i in range(4) for j in range(4)]
        pm = [region_data.window_matrix[i][j] for i in range(4) for j in range(4)]
        bridge.stage_frame(vm, pm, region.width, region.height)
        return bridge.draw_sentinel()

    def shutdown(self) -> None:
        pass
