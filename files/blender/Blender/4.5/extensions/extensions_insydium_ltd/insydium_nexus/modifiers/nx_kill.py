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

from typing import Tuple

import gpu
from mathutils import Matrix, Vector

from ..libs import theron, theron_ids
from ..libs.cache_spec import (
    CacheKind,
    CacheSpec,
    ensure_camera_entry,
    evict_stale_entries_for,
)
from ..properties.nx_kill import (
    _KILL_POLY_SPEC,
    SPEC,
    _kill_active_meshes,
    get_kill_ui_config,
)
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_RED,
    draw_circle,
    draw_lines,
    draw_thick_lines,
)
from .base import MenuCategory, NexusModifier, UIFlags

_KILL_CAMERA_SPEC = CacheSpec(
    kind=CacheKind.CAMERA,
    collection_attr="kill_camera",
    cache_dict={},
)


class NXKillModifier(NexusModifier):
    object_type = "NX_KILL"
    object_name = "nxKill"
    object_label = "Kill Modifier"
    object_description = "Kill particles based on volume, objects, or count"
    icon_name = "nx_kill"
    category = "General"
    menu_category = MenuCategory.PARTICLE
    gizmo_max_handles = 3
    cache_specs = (_KILL_POLY_SPEC, _KILL_CAMERA_SPEC)

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        if props.ID_NX_KILL_TYPE not in ("ID_NX_KILL_TYPE_BOX_IN", "ID_NX_KILL_TYPE_BOX_OUT"):
            return []

        if props.ID_NX_KILL_SHAPE == "ID_NX_KILL_SHAPE_BOX":
            return [
                HandleConfig(
                    Vector((1, 0, 0)),
                    "kill_size",
                    prop_component=0,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 1, 0)),
                    "kill_size",
                    prop_component=1,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 0, 1)),
                    "kill_size",
                    prop_component=2,
                    position_factor=0.5,
                    min_value=0.001,
                ),
            ]
        elif props.ID_NX_KILL_SHAPE == "ID_NX_KILL_SHAPE_SPHERE":
            return [
                HandleConfig(Vector((1, 0, 0)), "ID_NX_KILL_RADIUS", min_value=0.001),
            ]

        return []

    @classmethod
    def post_sync(
        cls, obj, container, _handle, props, _scene, depsgraph=None, original_props=None
    ):
        kill_type = props.ID_NX_KILL_TYPE

        is_box_type = kill_type in ("ID_NX_KILL_TYPE_BOX_IN", "ID_NX_KILL_TYPE_BOX_OUT")
        if is_box_type and props.ID_NX_KILL_SHAPE == "ID_NX_KILL_SHAPE_BOX":
            size = props.kill_size
            x = float(size[0])
            y = float(size[1])
            z = float(size[2])
            theron.set_vector(container, theron_ids.get("ID_NX_KILL_SIZE"), x, y, z)

        from ..pipeline_manager.identity import ensure_object_uid

        mod_uid = ensure_object_uid(obj)

        kill_camera_id = theron_ids.get("ID_NX_KILL_CAMERA")
        cam_handle: int | None = None
        active_cams: set[str] = set()
        if kill_type == "ID_NX_KILL_TYPE_FOV" and original_props is not None:
            cam_obj = original_props.kill_camera
            if cam_obj is not None and cam_obj.type == "CAMERA":
                cam_handle = ensure_camera_entry(_KILL_CAMERA_SPEC, mod_uid, cam_obj)
                if cam_handle is not None:
                    active_cams.add(cam_obj.name)

        theron.set_link(container, kill_camera_id, cam_handle)

        evict_stale_entries_for(_KILL_POLY_SPEC, mod_uid, _kill_active_meshes)
        _kill_active_meshes.clear()

        evict_stale_entries_for(_KILL_CAMERA_SPEC, mod_uid, active_cams)

    @classmethod
    def draw_ui(cls, layout, data):
        ui_config = get_kill_ui_config()

        col = layout.column()
        col.use_property_split = True
        col.prop(data, "ID_NX_KILL_TYPE")

        kill_type = data.ID_NX_KILL_TYPE

        if kill_type in ("ID_NX_KILL_TYPE_BOX_IN", "ID_NX_KILL_TYPE_BOX_OUT"):
            col.prop(data, "ID_NX_KILL_SHAPE")

            if data.ID_NX_KILL_SHAPE == "ID_NX_KILL_SHAPE_BOX":
                col.prop(data, "kill_size")
            else:
                col.prop(data, "ID_NX_KILL_RADIUS")

        elif kill_type == "ID_NX_KILL_TYPE_OBJECTS":
            cls.draw_property(layout, data, "kill_objects", ui_config)

        elif kill_type == "ID_NX_KILL_TYPE_FOV":
            col.prop(data, "kill_camera")
            col.prop(data, "ID_NX_KILL_FOV")

        elif kill_type == "ID_NX_KILL_TYPE_CLAMP":
            col.prop(data, "ID_NX_KILL_CLAMP")

        col = layout.column()
        col.use_property_split = True
        col.separator(type="LINE")
        col.prop(data, "ID_NX_KILL_BORN")

    @classmethod
    def draw_viewport(cls, obj, props, context) -> None:
        kill_type = getattr(props, "ID_NX_KILL_TYPE", "ID_NX_KILL_TYPE_BOX_OUT")

        if kill_type not in ("ID_NX_KILL_TYPE_BOX_IN", "ID_NX_KILL_TYPE_BOX_OUT"):
            return

        mx = obj.matrix_world.copy()
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        kill_shape = getattr(props, "ID_NX_KILL_SHAPE", "ID_NX_KILL_SHAPE_BOX")

        if kill_shape == "ID_NX_KILL_SHAPE_BOX":
            size = Vector(getattr(props, "kill_size", (10.0, 10.0, 10.0)))
            half_size = size * 0.5

            shader.uniform_float("color", XP_COLOR_MODS_BLUE)
            cls._draw_bounding_box(shader, mx, half_size)

            cls._draw_corner_accents(context, mx, half_size, XP_COLOR_MODS_RED)

        elif kill_shape == "ID_NX_KILL_SHAPE_SPHERE":
            radius = getattr(props, "ID_NX_KILL_RADIUS", 5.0)

            shader.uniform_float("color", XP_COLOR_MODS_BLUE)
            draw_circle(shader, mx, radius, plane="XY")
            draw_circle(shader, mx, radius, plane="XZ")
            draw_circle(shader, mx, radius, plane="YZ")

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)

    @staticmethod
    def _draw_bounding_box(shader, mx: Matrix, half_size: Vector) -> None:
        hx, hy, hz = half_size.x, half_size.y, half_size.z

        corners = [
            Vector((-hx, -hy, -hz)),
            Vector((hx, -hy, -hz)),
            Vector((hx, -hy, hz)),
            Vector((-hx, -hy, hz)),
            Vector((-hx, hy, -hz)),
            Vector((hx, hy, -hz)),
            Vector((hx, hy, hz)),
            Vector((-hx, hy, hz)),
        ]
        corners = [mx @ c for c in corners]

        edges = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]

        lines = [(corners[e[0]], corners[e[1]]) for e in edges]
        draw_lines(shader, lines)

    @staticmethod
    def _draw_corner_accents(context, mx: Matrix, half_size: Vector, color: Tuple) -> None:
        hx, hy, hz = half_size.x, half_size.y, half_size.z
        accent_length = min(hx, hy, hz) * 0.2

        corners = [
            (
                Vector((-hx, -hy, -hz)),
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, -hy, -hz)),
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, -hy, hz)),
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, -hy, hz)),
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, hy, -hz)),
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, hy, -hz)),
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            ),
            (
                Vector((hx, hy, hz)),
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
            ),
            (
                Vector((-hx, hy, hz)),
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
            ),
        ]

        accent_lines = []
        for corner, directions in corners:
            corner_world = mx @ corner
            for d in directions:
                end_local = corner + d * accent_length
                end_world = mx @ end_local
                accent_lines.append((corner_world, end_world))

        draw_thick_lines(context, accent_lines, color, line_width=3.0)
