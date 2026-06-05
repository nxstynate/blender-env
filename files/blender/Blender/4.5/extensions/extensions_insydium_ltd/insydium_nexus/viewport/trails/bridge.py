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

"""Shared staging for native NX_TRAIL line backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .constants import TRAIL_DEFAULT_COLOR, TRAIL_HEADER_BYTES, TRAIL_SEGMENT_BYTES

if TYPE_CHECKING:
    from ..bridges.native import NativeBridge
    from ..registry import TrailDrawParams

_RADIUS_THICKNESS_MODES = frozenset({"RADIUS_CURRENT"})


@dataclass(frozen=True)
class TrailNativeFrame:
    default_color: tuple[float, float, float, float]
    slots_per_particle: int
    history_capacity: int
    segment_count: int
    max_points_per_segment: int
    view_matrix: tuple[float, ...]
    projection_matrix: tuple[float, ...]
    viewport_width: int
    viewport_height: int


def source_has_thickness(params: "TrailDrawParams", index: int) -> bool:
    if index >= len(params.source_enabled_flags) or not params.source_enabled_flags[index]:
        return False
    if index < len(params.source_no_data_flags) and params.source_no_data_flags[index]:
        return False
    if index >= len(params.source_thickness_modes):
        return False
    return params.source_thickness_modes[index] != "NONE"


def _fetch_trail_bundle(pipeline: int):
    from ...libs import theron

    fetch = getattr(theron, "get_trail_buffer_exports", None)
    if fetch is None:
        return None
    return fetch(pipeline)


def _fetch_radius_export(pipeline: int, params: "TrailDrawParams"):
    from ...libs import theron
    from ...libs.theron_bindings import TrParticleProperty

    needs_radius = any(
        source_has_thickness(params, i) and mode in _RADIUS_THICKNESS_MODES
        for i, mode in enumerate(params.source_thickness_modes)
    )
    if not needs_radius:
        return None
    particle_count = theron.get_particle_count(pipeline)
    if particle_count <= 0:
        return None
    radius_export = theron.get_particle_data_buffer_export(
        pipeline, TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS
    )
    if radius_export is None:
        return None
    handle, size, _uid = radius_export
    live_size = min(int(size), particle_count * 4)
    return (handle, live_size)


def _topology_segment_capacity(topology: tuple[int, ...] | None, params: "TrailDrawParams") -> int:
    # Conservative draw bound; the native shader clamps to the live header count.
    if topology is not None:
        size = max(0, int(topology[1]) - TRAIL_HEADER_BYTES)
        capacity = size // TRAIL_SEGMENT_BYTES
        if capacity > 0:
            return capacity
    return int(params.source_count) * max(1, int(params.history_capacity))


class TrailsNativeStager:
    """Base class for native trail backends."""

    def __init__(
        self,
        bridge: "NativeBridge",
        backend_id: str,
        *,
        supports_lines: bool = False,
    ) -> None:
        self._bridge = bridge
        self.backend_id = backend_id
        self.supports_lines = supports_lines

    def stage(self, context, pipeline: int, params: "TrailDrawParams") -> bool:
        if not self.supports_lines:
            return False
        frame = self.prepare_frame(context, pipeline, params)
        if frame is None:
            return False
        return self.draw_staged(context, pipeline, params, frame)

    def prepare_frame(
        self,
        context,
        pipeline: int,
        params: "TrailDrawParams",
    ) -> TrailNativeFrame | None:
        if not self._bridge.is_available() or not self._bridge.load():
            self.reset(pipeline)
            return None
        trail_hook_ready = getattr(self._bridge, "trail_hook_ready", None)
        if trail_hook_ready is None or not trail_hook_ready():
            self.reset(pipeline)
            return None

        bundle = _fetch_trail_bundle(pipeline)
        if bundle is None:
            self.reset(pipeline)
            return None
        if bundle.history_particle_capacity <= 0 or bundle.slots_per_particle <= 0:
            self.reset(pipeline)
            return None

        history = getattr(bundle, "history", None)
        topology = getattr(bundle, "topology", None)
        if history is None or topology is None:
            self.reset(pipeline)
            return None

        configure_trail_bundle = getattr(self._bridge, "configure_trail_bundle", None)
        if configure_trail_bundle is None:
            self.reset(pipeline)
            return None
        if not configure_trail_bundle(
            pipeline=pipeline,
            bundle_uid=int(bundle.bundle_uid),
            history=history,
            topology=topology,
            color=bundle.color,
            thickness=bundle.thickness,
            radius=_fetch_radius_export(pipeline, params),
            live_endpoint=bundle.live_endpoint,
        ):
            self.reset(pipeline)
            return None

        slots_per_particle = int(bundle.slots_per_particle)
        history_capacity = int(bundle.history_particle_capacity)
        segment_count = _topology_segment_capacity(topology, params)
        if segment_count <= 0:
            return None

        max_pts = params.max_points_per_segment
        if max_pts <= 0 and slots_per_particle > 0:
            max_pts = slots_per_particle
        if max_pts <= 0:
            return None

        region_data = getattr(context, "region_data", None)
        region = getattr(context, "region", None)
        if region_data is None or region is None:
            return None

        default_color = TRAIL_DEFAULT_COLOR
        if params.source_colors:
            default_color = params.source_colors[0]

        return TrailNativeFrame(
            default_color=default_color,
            slots_per_particle=slots_per_particle,
            history_capacity=history_capacity,
            segment_count=segment_count,
            max_points_per_segment=max_pts,
            view_matrix=tuple(region_data.view_matrix[i][j] for i in range(4) for j in range(4)),
            projection_matrix=tuple(
                region_data.window_matrix[i][j] for i in range(4) for j in range(4)
            ),
            viewport_width=int(region.width),
            viewport_height=int(region.height),
        )

    def draw_staged(
        self,
        context,
        pipeline: int,
        params: "TrailDrawParams",
        frame: TrailNativeFrame,
    ) -> bool:
        return False

    def stage_pass(
        self,
        params: "TrailDrawParams",
        frame: TrailNativeFrame,
        source_enabled_flags: tuple[bool, ...],
    ) -> bool:
        self._bridge.stage_trail_params(
            frame.default_color,
            frame.slots_per_particle,
            frame.history_capacity,
            frame.segment_count,
            frame.max_points_per_segment,
        )
        self._bridge.stage_trail_palette(
            source_colors=params.source_colors,
            source_color_modes=params.source_color_modes,
            source_thickness_modes=params.source_thickness_modes,
            source_thickness_values=params.source_thickness_values,
            source_no_data_flags=params.source_no_data_flags,
            source_trail_color_modes=params.source_trail_color_modes,
            source_thickness_variations=params.source_thickness_variations,
            source_spline_max_values=params.source_spline_max_values,
            source_enabled_flags=source_enabled_flags,
        )
        self._bridge.stage_trail_frame(
            list(frame.view_matrix),
            list(frame.projection_matrix),
            frame.viewport_width,
            frame.viewport_height,
        )
        return self.draw_pass()

    def draw_pass(self) -> bool:
        return self._bridge.draw_trail_sentinel()

    def reset(self, pipeline: int | None = None) -> None:
        reset = getattr(self._bridge, "reset_trail_bundle_cache", None)
        if reset is not None:
            reset(pipeline)

    def shutdown(self) -> None:
        self.reset(None)
