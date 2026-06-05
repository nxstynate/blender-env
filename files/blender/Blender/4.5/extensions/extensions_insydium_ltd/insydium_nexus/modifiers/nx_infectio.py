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
import math

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from ..properties.nx_infectio import SPEC
from ..utils.gradient import GradientSpec, NexusGradient
from .base import MenuCategory, NexusModifier, UIFlags

INFECTIO_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="infectio_color_gradient",
        label="Incubation Gradient",
        default_stops=[
            (0.0, (0.078, 0.0, 1.0, 1.0)),
            (0.333, (0.0, 0.549, 1.0, 1.0)),
            (0.666, (0.549, 0.862, 1.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
        theron_ids=("ID_NX_INFECTIO_COLOR_GRADIENT",),
    ),
]


def _sync_infectio_post(obj, container, props, scene, original_props=None):
    from ..libs import theron, theron_ids
    from ..libs.theron_sync import TRANSFORM_FACTORS, Transform

    get = theron_ids.get
    unit = TRANSFORM_FACTORS[Transform.UNIT_SCALE]

    c = props.infectio_color_incubating
    theron.set_vector(
        container,
        get("ID_NX_INFECTIO_COLOR_INCUBATING"),
        float(c[0]),
        float(c[1]),
        float(c[2]),
    )

    c = props.infectio_color_infected
    theron.set_vector(
        container,
        get("ID_NX_INFECTIO_COLOR_INFECTED"),
        float(c[0]),
        float(c[1]),
        float(c[2]),
    )

    lim = props.infectio_limit
    theron.set_vector(
        container,
        get("ID_NX_INFECTIO_LIMIT"),
        float(lim[0]),
        float(lim[1]),
        float(lim[2]),
    )

    # Pack and sync seed data
    # InfectioSeed struct: { float rad; float threshold; Vector32 pos; } = 5 floats
    col_src = original_props if original_props is not None else props
    seeds = col_src.infectio_seeds
    num_seeds = 0
    seed_floats = []

    for item in seeds:
        if not item.enabled:
            continue

        seed_obj = item.seed_object
        if seed_obj is None:
            continue

        pos = seed_obj.matrix_world.translation

        seed_floats.append(item.seed_radius * unit)
        seed_floats.append(item.seed_threshold)
        seed_floats.append(pos.x * unit)
        seed_floats.append(pos.y * unit)
        seed_floats.append(pos.z * unit)
        num_seeds += 1

    theron.set_int32(container, get("ID_NX_INFECTIO_SEED_COUNT"), num_seeds)

    if num_seeds > 0:
        buf = (ctypes.c_float * len(seed_floats))(*seed_floats)
        theron.set_memory(
            container,
            get("ID_NX_INFECTIO_SEED_DATA"),
            buf,
            ctypes.sizeof(buf),
        )


def _draw_seed_sphere(shader, pos, radius, color):
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


class NXInfectioModifier(NexusModifier):
    object_type = "NX_INFECTIO"
    object_name = "nxInfectio"
    object_label = "Infectio Modifier"
    object_description = "Simulate infection and contagion spread between particles"
    icon_name = "nx_infectio"
    category = "Force"
    menu_category = MenuCategory.FORCE

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_gradient_specs(cls):
        return INFECTIO_GRADIENT_SPECS

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_infectio import _on_seed_add

        props = obj.nexus_modifier
        item = props.infectio_seeds.add()
        item.item_type = "SEED"
        _on_seed_add(bpy.context, obj, item)
        props.infectio_seeds_index = 0

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        orphans = [
            o
            for o in bpy.data.objects
            if o.get("nexus_object_type") == "NX_INFECTIO_SEED"
            and (o.parent is None or o.parent.name not in bpy.data.objects)
        ]
        for o in orphans:
            bpy.data.objects.remove(o, do_unlink=True)

    @classmethod
    def on_state_clear(cls, *, free_resources: bool = True) -> None:
        orphans = [
            o
            for o in bpy.data.objects
            if o.get("nexus_object_type") == "NX_INFECTIO_SEED"
            and (o.parent is None or o.parent.name not in bpy.data.objects)
        ]
        for o in orphans:
            bpy.data.objects.remove(o, do_unlink=True)

    @classmethod
    def post_sync(cls, obj, container, _handle, props, scene, depsgraph=None, original_props=None):
        _sync_infectio_post(obj, container, props, scene, original_props=original_props)

    @classmethod
    def draw_ui(cls, layout, data):
        from ..libs.nexus_time import draw_time_prop
        from ..properties.nx_infectio import draw_seed_settings
        from ..ui import draw_nodetree

        # -- Seed Objects --
        draw_nodetree(
            layout,
            data,
            "infectio_seeds",
            "infectio_seeds_index",
            label="Seeds",
            draw_item_settings=draw_seed_settings,
            menu_id="infectio_seeds",
        )

        layout.separator()

        # -- Color --
        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_INFECTIO_COLOR_MODE")

        mode = data.ID_NX_INFECTIO_COLOR_MODE

        if mode == "ID_NX_INFECTIO_COLOR_MODE_FIXED":
            col.prop(data, "infectio_color_incubating")
            col.prop(data, "infectio_color_infected")

        elif mode == "ID_NX_INFECTIO_COLOR_MODE_USE_GROUPS":
            col.prop(data, "ID_NX_INFECTIO_COLOR_GROUPS_INCUBATING")
            col.prop(data, "ID_NX_INFECTIO_COLOR_GROUPS_INFECTED")
            col.prop(data, "ID_NX_INFECTIO_COLOR_GROUPS_COLOR_CHANGE")

        elif mode == "ID_NX_INFECTIO_COLOR_MODE_GRADIENT":
            obj = bpy.context.object
            if obj:
                NexusGradient(obj, "infectio_color_gradient").draw_ui(col, "Incubation Gradient")

        col.separator(type="LINE")

        # -- Search --
        col.prop(data, "ID_NX_INFECTIO_SEARCH_RAD")
        col.prop(data, "ID_NX_INFECTIO_MAX_INFECTED")
        draw_time_prop(col, data, "ID_NX_INFECTIO_INFECTED_LIFESPAN")
        col.prop(data, "ID_NX_INFECTIO_SEARCH_ONCE")

        col.prop(data, "ID_NX_INFECTIO_CONSTRAIN_SEARCH")

        limit_col = col.column()
        limit_col.enabled = data.ID_NX_INFECTIO_CONSTRAIN_SEARCH
        limit_col.prop(data, "infectio_limit")

        col.separator(type="LINE")

        # -- Incubation --
        col.label(text="Incubation")

        icol = col.column()
        icol.use_property_split = True

        icol.prop(data, "ID_NX_INFECTIO_INCUBATION_MODE")

        inc_mode = data.ID_NX_INFECTIO_INCUBATION_MODE

        if inc_mode == "ID_NX_INFECTIO_INCUBATION_MODE_RATE":
            icol.prop(data, "ID_NX_INFECTIO_INCUBATION_RATE")
            icol.prop(data, "ID_NX_INFECTIO_INCUBATION_VAR")
        elif inc_mode in (
            "ID_NX_INFECTIO_INCUBATION_MODE_RADIUS",
            "ID_NX_INFECTIO_INCUBATION_MODE_MASS",
        ):
            icol.prop(data, "ID_NX_INFECTIO_INCUBATION_MIN")
            icol.prop(data, "ID_NX_INFECTIO_INCUBATION_MAX")

        icol.prop(data, "ID_NX_INFECTIO_INCUBATION_MULTI")
        if inc_mode != "ID_NX_INFECTIO_INCUBATION_MODE_RATE":
            icol.prop(data, "ID_NX_INFECTIO_INCUBATION_INVERT")

        col.separator(type="LINE")

        # -- Immunity --
        col.label(text="Immunity")

        col.prop(data, "ID_NX_INFECTIO_IMMUNITY_USE")

        immunity_col = col.column()
        immunity_col.enabled = data.ID_NX_INFECTIO_IMMUNITY_USE
        immunity_col.prop(data, "ID_NX_INFECTIO_IMMUNITY_LEVEL")

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        if not hasattr(props, "infectio_seeds") or len(props.infectio_seeds) == 0:
            return

        shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        prev_depth_test = gpu.state.depth_test_get()
        prev_depth_mask = gpu.state.depth_mask_get()
        try:
            gpu.state.blend_set("ALPHA")
            gpu.state.line_width_set(2.0)
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.depth_mask_set(True)

            for item in props.infectio_seeds:
                if not item.enabled:
                    continue

                seed_obj = item.seed_object
                if seed_obj is None:
                    continue

                if seed_obj.hide_viewport or seed_obj.hide_get():
                    continue

                pos = seed_obj.matrix_world.translation
                radius = item.seed_radius

                _draw_seed_sphere(shader, pos, radius, tuple(item.seed_color))
        finally:
            gpu.state.depth_mask_set(prev_depth_mask)
            gpu.state.depth_test_set(prev_depth_test)
            gpu.state.blend_set("NONE")
