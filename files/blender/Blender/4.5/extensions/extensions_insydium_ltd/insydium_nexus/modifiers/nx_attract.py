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

import ctypes

import bpy
import gpu
from mathutils import Vector

from ..properties.nx_attract import SPEC, get_attract_ui_config
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_circle, draw_lines
from .base import MenuCategory, NexusModifier, UIFlags

MAX_ATTRACT_COUNT = 1024


class NXAttractModifier(NexusModifier):
    object_type = "NX_ATTRACT"
    object_name = "nxAttract"
    object_label = "Attract Modifier"
    object_description = "Attract particles towards the modifier or target objects"
    icon_name = "nx_attract"
    category = "Forces"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def post_sync(cls, obj, container, handle, props, scene, depsgraph=None, original_props=None):
        from ..libs import theron, theron_ids

        get = theron_ids.get

        col_src = original_props if original_props is not None else props
        positions = []
        for item in col_src.attract_objects:
            if item.obj is None or not item.enabled:
                continue
            try:
                pos = item.obj.matrix_world.translation
            except ReferenceError:
                continue
            positions.append((pos.x, pos.y, pos.z))

        # Fall back to mods position if no attractor objects
        if not positions:
            pos = obj.matrix_world.translation
            positions.append((pos.x, pos.y, pos.z))

        count = min(len(positions), MAX_ATTRACT_COUNT)

        # Compute average position
        avg_x = sum(p[0] for p in positions[:count]) / count
        avg_y = sum(p[1] for p in positions[:count]) / count
        avg_z = sum(p[2] for p in positions[:count]) / count
        theron.set_vector(container, get("ID_NX_ATTRACT_AVG_POS"), avg_x, avg_y, avg_z)

        # Set point count
        theron.set_int32(container, get("ID_NX_ATTRACT_POINT_COUNT"), count)

        # Build padded float32 array (MAX_ATTRACT_COUNT * 3 floats) and set as memory
        buf = (ctypes.c_float * (MAX_ATTRACT_COUNT * 3))()
        for i, (px, py, pz) in enumerate(positions[:count]):
            buf[i * 3] = px
            buf[i * 3 + 1] = py
            buf[i * 3 + 2] = pz
        theron.set_memory(
            container,
            get("ID_NX_ATTRACT_POINTS"),
            buf,
            ctypes.sizeof(buf),
        )

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_attract_ui_config()

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "ID_NX_ATTRACT_TYPE")
        col.prop(data, "ID_NX_ATTRACT_FORCE")
        col.prop(data, "ID_NX_ATTRACT_GRAVITY")
        col.prop(data, "ID_NX_ATTRACT_SPEEDLIMIT")

        col.separator()

        col.prop(data, "ID_NX_ATTRACT_OBJMODE")

        if data.ID_NX_ATTRACT_OBJMODE == "ID_NX_ATTRACT_OBJMODE_INDEX":
            col.prop(data, "ID_NX_ATTRACT_OBJINDEX")

        col.separator()

        cls.draw_property(col, data, "attract_objects", ui_config)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, _context) -> None:
        draw_size = 1.0
        draw_offset = 0.25
        force = getattr(props, "ID_NX_ATTRACT_FORCE", 30.0)

        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        draw_circle(shader, mx, draw_size, plane="XY")

        shader.uniform_float("color", XP_COLOR_MODS_RED)

        inward = force >= 0
        line_start_offset = draw_size
        line_end_offset = draw_size * draw_offset
        barb_size = draw_size * 0.15

        if inward:
            line_start = line_start_offset
            line_end = line_end_offset
        else:
            line_start = line_end_offset
            line_end = line_start_offset

        attract_lines = []
        arrow_barbs = []

        directions = [
            Vector((1.0, 0.0, 0.0)),
            Vector((-1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, -1.0, 0.0)),
        ]

        for direction in directions:
            start = mx @ (direction * line_start)
            end = mx @ (direction * line_end)
            attract_lines.append((start, end))

            tip = end
            perp = Vector((-direction.y, direction.x, 0.0))

            if inward:
                barb_back = direction * barb_size
            else:
                barb_back = -direction * barb_size

            barb1 = mx @ (direction * line_end + barb_back + perp * barb_size)
            barb2 = mx @ (direction * line_end + barb_back - perp * barb_size)

            arrow_barbs.append((tip, barb1))
            arrow_barbs.append((tip, barb2))

        draw_lines(shader, attract_lines)
        draw_lines(shader, arrow_barbs)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)
