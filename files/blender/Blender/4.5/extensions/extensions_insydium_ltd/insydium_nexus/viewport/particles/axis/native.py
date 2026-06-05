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

"""Native (Vulkan / Metal) axis renderer — indirect binned path."""

from __future__ import annotations

from ..native_base import NativeParticleBase

_AXIS_MODE_INDEX = 12


class AxisNativeRenderer(NativeParticleBase):
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
        rot = self.fetch_gpu_buffer(pipeline, "rotation")
        rad = self.fetch_gpu_buffer(pipeline, "radius")
        col = self.fetch_gpu_buffer(pipeline, "color")

        bridge.stage_display_shape(10, 0, 0, 0.0, 1.0, 0)
        bridge.stage_indirect_mode(_AXIS_MODE_INDEX)
        self._stage_emitter_settings(params)
        bridge.stage_color_mode(col is not None and col.valid)

        needs_geo = bridge.tracker.needs_reconfigure(
            "INDIRECT",
            count,
            position=pos,
            velocity=vel,
            radius=rad,
            rotation=rot,
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
                rot.handle if rot and rot.valid else None,
                rot.size if rot and rot.valid else 0,
                col.handle if col and col.valid else None,
                col.size if col and col.valid else 0,
                _AXIS_MODE_INDEX,
                count,
            )
            bridge.tracker.update(
                "INDIRECT",
                count,
                position=pos,
                velocity=vel,
                radius=rad,
                rotation=rot,
                color=col,
                emitter_index=emit_idx,
                prefix=prefix_buf,
                binned=binned_buf,
            )

        return self._stage_and_draw(context, params)
