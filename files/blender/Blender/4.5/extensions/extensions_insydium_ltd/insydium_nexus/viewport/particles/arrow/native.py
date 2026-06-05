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

"""Native (Vulkan / Metal) arrow renderer — indirect binned path."""

from __future__ import annotations

from ..native_base import NativeParticleBase

_ARROW_OUTLINE_MODE_INDEX = 9
_ARROW_FILLED_MODE_INDEX = 10


class ArrowNativeRenderer(NativeParticleBase):
    def __init__(self, bridge, *, filled: bool = False) -> None:
        super().__init__(bridge)
        self._filled = filled

    def draw(self, context, pipeline, scene, params) -> bool:
        bridge = self._bridge
        if not bridge.load():
            return False

        pos = self.fetch_gpu_buffer(pipeline, "position")
        if pos is None or not pos.valid:
            return False
        count = params.count
        if count <= 0:
            return False

        mode_buffers = self.fetch_draw_mode_buffers(pipeline)
        emit_idx = self.fetch_gpu_buffer(pipeline, "emitter_index")
        if mode_buffers is None or emit_idx is None or not emit_idx.valid:
            return False
        prefix_buf, binned_buf = mode_buffers

        vel = self.fetch_gpu_buffer(pipeline, "velocity")
        rad = self.fetch_gpu_buffer(pipeline, "radius")
        col = self.fetch_gpu_buffer(pipeline, "color")

        mode = int(getattr(params, "line_length_mode", 0))
        fixed_length = float(getattr(params, "line_fixed_length", 0.1))
        line_scale = fixed_length if mode == 2 else 1.0

        mode_index = _ARROW_FILLED_MODE_INDEX if self._filled else _ARROW_OUTLINE_MODE_INDEX
        shape_id = 5 if self._filled else 4
        bridge.stage_display_shape(shape_id, 0, 0, 0.0, line_scale, mode)
        bridge.stage_indirect_mode(mode_index)
        self._stage_emitter_settings(params)
        bridge.stage_color_mode(col is not None and col.valid)

        needs_geo = bridge.tracker.needs_reconfigure(
            "INDIRECT",
            count,
            position=pos,
            velocity=vel,
            radius=rad,
            color=col,
            emitter_index=emit_idx,
            prefix=prefix_buf,
            binned=binned_buf,
        )
        if needs_geo:
            bridge.configure_indirect_points(
                pos.handle,
                pos.size,
                prefix_buf.handle,
                prefix_buf.size,
                binned_buf.handle,
                binned_buf.size,
                emit_idx.handle,
                emit_idx.size,
                rad.handle if rad and rad.valid else None,
                rad.size if rad and rad.valid else 0,
                vel.handle if vel and vel.valid else None,
                vel.size if vel and vel.valid else 0,
                None,
                0,
                col.handle if col and col.valid else None,
                col.size if col and col.valid else 0,
                mode_index,
                count,
            )
            bridge.tracker.update(
                "INDIRECT",
                count,
                position=pos,
                velocity=vel,
                radius=rad,
                color=col,
                emitter_index=emit_idx,
                prefix=prefix_buf,
                binned=binned_buf,
            )

        return self._stage_and_draw(context, params)


class ArrowFilledNativeRenderer(ArrowNativeRenderer):
    def __init__(self, bridge) -> None:
        super().__init__(bridge, filled=True)
