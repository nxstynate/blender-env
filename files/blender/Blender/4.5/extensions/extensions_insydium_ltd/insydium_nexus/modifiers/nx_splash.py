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

from ..libs.nexus_time import draw_time_prop
from ..properties.nx_splash import SPEC
from ..utils.curve import CurveSpec, NexusCurve
from ..utils.splash_data import (
    BEZIER_SUBDIVISIONS,
    FLOATS_PER_HANDLE,
    evaluate_bezier,
    generate_default_handles,
    get_splash_handle_data,
    set_splash_handle_data,
    store_splash_prev_values,
)
from ..utils.splash_drawing import draw_splash_cone, draw_splash_fallback
from .base import MenuCategory, NexusModifier, UIFlags

_HANDLE_KEY_BASE = 1000

SPLASH_CURVE_SPECS = [
    CurveSpec(
        "splash_cone_falloff",
        "Falloff",
        [(0.0, 1.0), (1.0, 0.0)],
        theron_ids=("ID_NX_SPLASH_CONE_FALLOFF",),
    ),
    CurveSpec(
        "splash_strength_falloff",
        "Strength Falloff",
        [(0.0, 1.0), (1.0, 1.0)],
        theron_ids=("ID_NX_SPLASH_STR_FALLOFF",),
    ),
]


class NXSplashModifier(NexusModifier):
    object_type = "NX_SPLASH"
    object_name = "nxSplash"
    object_label = "Splash Modifier"
    object_description = "Create splash cone effects that push particles outward"
    icon_name = "nx_splash"
    category = "Forces"
    menu_category = MenuCategory.SIMULATION

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_curve_specs(cls):
        return SPLASH_CURVE_SPECS

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        props = obj.nexus_modifier
        bhandles, strengths = generate_default_handles(
            props.ID_NX_SPLASH_HEIGHT,
            props.ID_NX_SPLASH_RADIUS_BOTTOM,
            props.ID_NX_SPLASH_RADIUS_TOP,
            props.ID_NX_SPLASH_HANDLE_COUNT,
        )
        set_splash_handle_data(obj, bhandles, strengths)
        store_splash_prev_values(obj, props)

    @classmethod
    def post_sync(
        cls, obj, container, _handle, props, _scene, depsgraph=None, original_props=None
    ):
        from ..libs import theron
        from ..libs.theron_ids import get as get_id

        handle_count = props.ID_NX_SPLASH_HANDLE_COUNT

        bhandles = obj.get("_nx_splash_bhandles")
        strengths = obj.get("_nx_splash_strengths")
        if bhandles is None or strengths is None:
            return
        if handle_count * FLOATS_PER_HANDLE > len(bhandles):
            return

        str_sub = theron.create_container()
        if str_sub is not None:
            for i in range(handle_count):
                theron.set_float(str_sub, _HANDLE_KEY_BASE + i, float(strengths[i]))
            theron.set_container(container, get_id("ID_NX_SPLASH_HANDLES"), str_sub)
            theron.free_container(str_sub)

        n = handle_count

        top_anchors = []
        top_slot1 = []
        top_slot2 = []
        bot_anchors = []
        bot_slot1 = []
        bot_slot2 = []

        bh_sub = theron.create_container()
        if bh_sub is not None:
            for i in range(n):
                base = i * FLOATS_PER_HANDLE
                ta = bhandles[base], bhandles[base + 1], bhandles[base + 2]
                tr = bhandles[base + 3], bhandles[base + 4], bhandles[base + 5]
                tl = bhandles[base + 6], bhandles[base + 7], bhandles[base + 8]
                ba = bhandles[base + 9], bhandles[base + 10], bhandles[base + 11]
                br = bhandles[base + 12], bhandles[base + 13], bhandles[base + 14]
                bl = bhandles[base + 15], bhandles[base + 16], bhandles[base + 17]

                top_anchors.append(ta)
                top_slot1.append(tr)
                top_slot2.append(tl)
                bot_anchors.append(ba)
                bot_slot1.append(br)
                bot_slot2.append(bl)

                key = _HANDLE_KEY_BASE + i * 3
                theron.set_vector(bh_sub, key, *ta)
                theron.set_vector(bh_sub, key + 1, *tr)
                theron.set_vector(bh_sub, key + 2, *tl)

                key = _HANDLE_KEY_BASE + 3 * n + i * 3
                theron.set_vector(bh_sub, key, *ba)
                theron.set_vector(bh_sub, key + 1, *br)
                theron.set_vector(bh_sub, key + 2, *bl)

            theron.set_container(container, get_id("ID_NX_SPLASH_BHANDLES"), bh_sub)
            theron.free_container(bh_sub)

        # Pre-evaluated bezier segments for C-side InitSplashCone()
        seg_sub = theron.create_container()
        if seg_sub is not None and top_anchors:
            for i in range(n):
                j = (i + 1) % n
                t_p0 = top_anchors[i]
                t_p1 = top_slot1[i]
                t_p2 = top_slot2[j]
                t_p3 = top_anchors[j]

                b_p0 = bot_anchors[i]
                b_p1 = bot_slot1[i]
                b_p2 = bot_slot2[j]
                b_p3 = bot_anchors[j]

                for sub in range(BEZIER_SUBDIVISIONS):
                    t = sub / BEZIER_SUBDIVISIONS

                    tp = evaluate_bezier(t_p0, t_p1, t_p2, t_p3, t)
                    bp = evaluate_bezier(b_p0, b_p1, b_p2, b_p3, t)

                    top_key = _HANDLE_KEY_BASE + i * BEZIER_SUBDIVISIONS + sub
                    bot_key = (
                        _HANDLE_KEY_BASE + BEZIER_SUBDIVISIONS * n + i * BEZIER_SUBDIVISIONS + sub
                    )
                    theron.set_vector(seg_sub, top_key, tp[0], tp[1], tp[2])
                    theron.set_vector(seg_sub, bot_key, bp[0], bp[1], bp[2])

            theron.set_container(container, get_id("ID_NX_SPLASH_SEGMENTS"), seg_sub)
            theron.free_container(seg_sub)

    @classmethod
    def draw_ui(cls, layout, data):
        obj = data.id_data

        col = layout.column()
        col.use_property_split = True

        col.operator("nexus.splash_reset_handles", icon="FILE_REFRESH")
        col.separator(type="LINE")

        col.prop(data, "ID_NX_SPLASH_RADIUS_BOTTOM")
        col.prop(data, "ID_NX_SPLASH_HEIGHT")
        col.prop(data, "ID_NX_SPLASH_RADIUS_TOP")
        col.prop(data, "ID_NX_SPLASH_HANDLE_COUNT")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_SPLASH_STR")
        draw_time_prop(col, data, "ID_NX_SPLASH_START_TIME")
        draw_time_prop(col, data, "ID_NX_SPLASH_DURATION")
        col.prop(data, "ID_NX_SPLASH_DISTANCE")

        NexusCurve(obj, "splash_cone_falloff").draw_ui(layout, "Falloff")

        strength_curve = NexusCurve(obj, "splash_strength_falloff")
        if strength_curve:
            layout.separator(type="LINE")
        strength_curve.draw_ui(layout, "Strength Falloff")

    @classmethod
    def draw_viewport(cls, obj, props, context):
        handle_count = getattr(props, "ID_NX_SPLASH_HANDLE_COUNT", 8)
        mx = obj.matrix_world

        bhandles, strengths = get_splash_handle_data(obj)
        if bhandles is None or len(bhandles) < handle_count * FLOATS_PER_HANDLE:
            draw_splash_fallback(context, mx, props, handle_count)
            return

        draw_splash_cone(context, mx, bhandles, strengths, handle_count)
