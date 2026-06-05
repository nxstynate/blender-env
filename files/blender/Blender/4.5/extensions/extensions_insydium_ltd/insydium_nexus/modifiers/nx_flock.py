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

import bpy
import gpu

from ..properties.nx_flock import FLOCK_AVOIDANCE_POLY_SPEC, REACTOR_COLORS, SPEC
from .base import MenuCategory, NexusModifier, UIFlags


def _draw_reactor_cross(shader, pos, size, color):
    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector

    coords = [
        pos + Vector((-size, 0, 0)),
        pos + Vector((size, 0, 0)),
        pos + Vector((0, -size, 0)),
        pos + Vector((0, size, 0)),
        pos + Vector((0, 0, -size)),
        pos + Vector((0, 0, size)),
    ]

    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", 2.0)
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
    batch.draw(shader)


def _draw_reactor_sphere(shader, pos, radius, color):
    import math

    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector

    segments = 32
    coords = []

    # XY circle
    for i in range(segments):
        a1 = (i / segments) * 2 * math.pi
        a2 = ((i + 1) / segments) * 2 * math.pi
        coords.append(pos + Vector((math.cos(a1) * radius, math.sin(a1) * radius, 0)))
        coords.append(pos + Vector((math.cos(a2) * radius, math.sin(a2) * radius, 0)))

    # XZ circle
    for i in range(segments):
        a1 = (i / segments) * 2 * math.pi
        a2 = ((i + 1) / segments) * 2 * math.pi
        coords.append(pos + Vector((math.cos(a1) * radius, 0, math.sin(a1) * radius)))
        coords.append(pos + Vector((math.cos(a2) * radius, 0, math.sin(a2) * radius)))

    # YZ circle
    for i in range(segments):
        a1 = (i / segments) * 2 * math.pi
        a2 = ((i + 1) / segments) * 2 * math.pi
        coords.append(pos + Vector((0, math.cos(a1) * radius, math.sin(a1) * radius)))
        coords.append(pos + Vector((0, math.cos(a2) * radius, math.sin(a2) * radius)))

    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", 1.5)
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
    batch.draw(shader)


def _draw_reactor_box(shader, pos, size, color):
    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector

    s = size / 2
    corners = [
        pos + Vector((-s, -s, -s)),
        pos + Vector((s, -s, -s)),
        pos + Vector((s, s, -s)),
        pos + Vector((-s, s, -s)),
        pos + Vector((-s, -s, s)),
        pos + Vector((s, -s, s)),
        pos + Vector((s, s, s)),
        pos + Vector((-s, s, s)),
    ]

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

    coords = []
    for e in edges:
        coords.append(corners[e[0]])
        coords.append(corners[e[1]])

    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", 1.5)
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
    batch.draw(shader)


class NXFlockModifier(NexusModifier):
    object_type = "NX_FLOCK"
    object_name = "nxFlock"
    object_label = "Flock Modifier"
    object_description = "Apply flocking behavior to particles"
    icon_name = "nx_flock"
    category = "Motion"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    cache_specs = (FLOCK_AVOIDANCE_POLY_SPEC,)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_flock import add_default_behaviors

        props = obj.nexus_modifier
        add_default_behaviors(props)

    @classmethod
    def draw_ui(cls, layout, data):
        from ..properties.nx_flock import (
            get_flock_ui_config,
        )

        ui_config = get_flock_ui_config()

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_FLOCK_WEIGHT")
        col.prop(data, "ID_NX_FLOCK_MIN_SPEED")
        col.prop(data, "ID_NX_FLOCK_MAX_SPEED")

        layout.separator()

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_FLOCK_NATLIMITS_ENABLED")

        limits_col = col.column()
        limits_col.enabled = data.ID_NX_FLOCK_NATLIMITS_ENABLED
        limits_col.prop(data, "ID_NX_FLOCK_NATLIMITS_ANGLE")
        limits_col.prop(data, "ID_NX_FLOCK_NATLIMITS_LERP")

        layout.separator()

        row = layout.row(align=True)
        row.prop(data, "flock_tab", expand=True)

        layout.separator()

        if data.flock_tab == "BEHAVIORS":
            cls._draw_behaviors_tab(layout, data, ui_config)
        elif data.flock_tab == "REACTIONS":
            cls._draw_reactions_tab(layout, data)
        elif data.flock_tab == "AVOIDANCE":
            cls._draw_avoidance_tab(layout, data)

    @classmethod
    def _draw_behaviors_tab(cls, layout, data, ui_config):
        from ..properties.nx_flock import (
            draw_flock_behavior_settings,
        )
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            data,
            "flock_behaviors",
            "flock_behaviors_index",
            label="Behaviors",
            draw_item_settings=draw_flock_behavior_settings,
            menu_id="flock_behaviors",
        )

    @classmethod
    def _draw_reactions_tab(cls, layout, data):
        from ..properties.nx_flock import (
            draw_flock_reaction_settings,
        )
        from ..ui import draw_nodetree

        draw_nodetree(
            layout,
            data,
            "flock_reactions",
            "flock_reactions_index",
            label="Reactions",
            draw_item_settings=draw_flock_reaction_settings,
            menu_id="flock_reactions",
        )

    @classmethod
    def _draw_avoidance_tab(cls, layout, data):
        from ..ui import draw_nodetree

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_FLOCK_AVOIDGEO_WEIGHT")
        col.prop(data, "ID_NX_FLOCK_AVOIDGEO_DIST")
        col.prop(data, "ID_NX_FLOCK_AVOIDGEO_MODE")

        layout.separator()

        draw_nodetree(
            layout,
            data,
            "flock_avoidance_objects",
            "flock_avoidance_objects_index",
            label="Geometry",
            allowed_types=["MESH"],
        )

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, _context: bpy.types.Context) -> None:
        if not hasattr(props, "flock_reactions") or len(props.flock_reactions) == 0:
            return

        shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(2.0)

        for item in props.flock_reactions:
            if not item.enabled:
                continue

            reactor = item.reactor_object
            if reactor is None:
                continue

            if reactor.hide_viewport or reactor.hide_get():
                continue

            display = item.reactor_display
            if display == "NONE":
                continue

            pos = reactor.matrix_world.translation

            color = REACTOR_COLORS.get(item.item_type, (1.0, 1.0, 1.0, 1.0))

            if item.reaction_activation_mode == "DISTANCE":
                size = item.reaction_activation_distance
            else:
                size = 0.5

            if display == "CROSS":
                _draw_reactor_cross(shader, pos, size * 0.5, color)
            elif display == "SPHERE":
                _draw_reactor_sphere(shader, pos, size, color)
            elif display == "BOX":
                _draw_reactor_box(shader, pos, size, color)

        gpu.state.blend_set("NONE")
