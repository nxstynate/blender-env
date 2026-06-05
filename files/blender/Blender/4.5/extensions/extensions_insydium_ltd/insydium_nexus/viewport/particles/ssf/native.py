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

"""Native (Vulkan / Metal) screen-space fluid staging."""

from __future__ import annotations


class SSFNativeStager:
    def __init__(self, bridge) -> None:
        self._bridge = bridge

    def stage(self, params) -> None:
        bridge = self._bridge
        active = "SSF" in (params.emitter_display_shapes or ())
        bridge.stage_ssf_enabled(active)
        if not active:
            return
        bridge.stage_ssf_params(
            fluid_color=tuple(float(c) for c in params.color[:3]),
            background=tuple(
                float(c) for c in getattr(params, "ssf_background_color", (0.55, 0.65, 0.78))[:3]
            ),
            absorption=float(getattr(params, "ssf_absorption", 2.0)),
            fresnel_power=float(getattr(params, "ssf_fresnel_power", 5.0)),
            min_alpha=float(getattr(params, "ssf_min_alpha", 0.3)),
            anisotropy_scale=float(getattr(params, "ssf_anisotropy_scale", 0.2)),
            anisotropy_max_stretch=float(getattr(params, "ssf_anisotropy_max_stretch", 3.0)),
            use_anisotropy=bool(getattr(params, "ssf_use_anisotropy", False)),
            blur_iterations=int(getattr(params, "ssf_blur_iterations", 3)),
            blur_radius=int(getattr(params, "ssf_blur_radius", 8)),
            blur_depth_falloff=float(getattr(params, "ssf_blur_depth_falloff", 50.0)),
            thickness_blur_iterations=int(getattr(params, "ssf_thickness_blur_iterations", 2)),
        )
        bridge.stage_ssf_emitter_sizes(tuple(float(s) for s in (params.emitter_point_sizes or ())))
