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

import math

import bpy
import gpu
from bpy.types import Gizmo, GizmoGroup
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import intersect_line_plane

from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED
from ..utils.splash_data import (
    FLOATS_PER_HANDLE,
    PART_BOTTOM_ANCHOR,
    PART_BOTTOM_TANGENT_LEFT,
    PART_BOTTOM_TANGENT_RIGHT,
    PART_STRENGTH,
    PART_TOP_ANCHOR,
    PART_TOP_TANGENT_LEFT,
    PART_TOP_TANGENT_RIGHT,
    get_handle_vec,
    get_splash_handle_data,
    set_handle_vec,
    set_splash_handle_data,
)
from ..utils.splash_drawing import draw_splash_cone

COLOR_ANCHOR = XP_COLOR_MODS_RED
COLOR_TANGENT = (*XP_COLOR_MODS_RED[:3], 0.5)
COLOR_TANGENT_LINE = (*XP_COLOR_MODS_BLUE[:3], 0.4)
COLOR_STRENGTH = (*XP_COLOR_MODS_RED[:3], 0.7)

_HIGHLIGHT_SCALE = 1.4
COLOR_ANCHOR_HL = (
    *(min(c * _HIGHLIGHT_SCALE, 1.0) for c in XP_COLOR_MODS_RED[:3]),
    1.0,
)
COLOR_TANGENT_HL = (
    *(min(c * _HIGHLIGHT_SCALE, 1.0) for c in XP_COLOR_MODS_RED[:3]),
    0.85,
)
COLOR_STRENGTH_HL = (
    *(min(c * _HIGHLIGHT_SCALE, 1.0) for c in XP_COLOR_MODS_RED[:3]),
    1.0,
)

HIT_THRESHOLD = 14.0
DISC_SEGMENTS = 12


def _generate_disc_tris(segments=DISC_SEGMENTS):
    verts = []
    for i in range(segments):
        a0 = (i / segments) * math.pi * 2
        a1 = ((i + 1) / segments) * math.pi * 2
        verts.append((0.0, 0.0))
        verts.append((math.cos(a0), math.sin(a0)))
        verts.append((math.cos(a1), math.sin(a1)))
    return verts


DISC_TRIS = _generate_disc_tris()


def _draw_discs(rv3d, shader, positions, color, world_radius):
    if not positions:
        return
    view_mat = rv3d.view_matrix
    cam_right = Vector((view_mat[0][0], view_mat[0][1], view_mat[0][2]))
    cam_up = Vector((view_mat[1][0], view_mat[1][1], view_mat[1][2]))

    all_verts = []
    for pos in positions:
        for dx, dy in DISC_TRIS:
            all_verts.append(pos + cam_right * dx * world_radius + cam_up * dy * world_radius)

    shader.uniform_float("color", color)
    batch = batch_for_shader(shader, "TRIS", {"pos": all_verts})
    batch.draw(shader)


class NX_GT_splash_handles(Gizmo):
    bl_idname = "NX_GT_splash_handles"
    bl_target_properties = ()

    __slots__ = (
        "_active_handle",
        "_handle_part",
        "_init_bhandles",
        "_init_strengths",
        "_init_mouse",
        "_drag_plane_normal",
        "_drag_plane_origin",
        "_drag_axis",
    )

    def setup(self):
        self._active_handle = -1
        self._handle_part = -1

    def draw(self, context):
        obj = context.object
        if not obj:
            return

        bhandles, strengths = get_splash_handle_data(obj)
        if bhandles is None:
            return

        props = getattr(obj, "nexus_modifier", None)
        if props is None:
            return

        handle_count = props.ID_NX_SPLASH_HANDLE_COUNT
        if handle_count * FLOATS_PER_HANDLE > len(bhandles):
            return

        mx = obj.matrix_world
        rv3d = context.region_data

        is_hover = self.is_highlight or self.is_modal
        hover_hi = self._active_handle if is_hover else -1
        hover_part = self._handle_part if is_hover else -1

        disc_radius = rv3d.view_distance * 0.003

        draw_splash_cone(context, mx, bhandles, strengths, handle_count)

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader.bind()
        gpu.state.blend_set("ALPHA")

        # Tangent lines
        shader.uniform_float("color", COLOR_TANGENT_LINE)
        tangent_coords = []
        for i in range(handle_count):
            for anchor_part, tr_part, tl_part in [
                (PART_TOP_ANCHOR, PART_TOP_TANGENT_RIGHT, PART_TOP_TANGENT_LEFT),
                (PART_BOTTOM_ANCHOR, PART_BOTTOM_TANGENT_RIGHT, PART_BOTTOM_TANGENT_LEFT),
            ]:
                anchor = mx @ get_handle_vec(bhandles, i, anchor_part)
                tr = mx @ get_handle_vec(bhandles, i, tr_part)
                tl = mx @ get_handle_vec(bhandles, i, tl_part)
                tangent_coords.extend([anchor, tr, anchor, tl])

        if tangent_coords:
            batch = batch_for_shader(shader, "LINES", {"pos": tangent_coords})
            batch.draw(shader)

        # Anchor discs
        anchor_normal = []
        anchor_highlight = []
        for i in range(handle_count):
            for part in (PART_TOP_ANCHOR, PART_BOTTOM_ANCHOR):
                pos = mx @ get_handle_vec(bhandles, i, part)
                if hover_hi == i and hover_part == part:
                    anchor_highlight.append(pos)
                else:
                    anchor_normal.append(pos)

        _draw_discs(rv3d, shader, anchor_normal, COLOR_ANCHOR, disc_radius)
        _draw_discs(rv3d, shader, anchor_highlight, COLOR_ANCHOR_HL, disc_radius * 1.3)

        # Tangent discs
        tangent_normal = []
        tangent_highlight = []
        for i in range(handle_count):
            for part in (
                PART_TOP_TANGENT_RIGHT,
                PART_TOP_TANGENT_LEFT,
                PART_BOTTOM_TANGENT_RIGHT,
                PART_BOTTOM_TANGENT_LEFT,
            ):
                pos = mx @ get_handle_vec(bhandles, i, part)
                if hover_hi == i and hover_part == part:
                    tangent_highlight.append(pos)
                else:
                    tangent_normal.append(pos)

        _draw_discs(rv3d, shader, tangent_normal, COLOR_TANGENT, disc_radius * 0.7)
        _draw_discs(rv3d, shader, tangent_highlight, COLOR_TANGENT_HL, disc_radius)

        # Strength discs
        strength_normal = []
        strength_highlight = []
        for i in range(handle_count):
            top_anchor = mx @ get_handle_vec(bhandles, i, PART_TOP_ANCHOR)
            bot_anchor = mx @ get_handle_vec(bhandles, i, PART_BOTTOM_ANCHOR)
            direction = top_anchor - bot_anchor
            d_len = direction.length
            if d_len > 1e-8:
                direction /= d_len
            pos = top_anchor + direction * strengths[i]
            if hover_hi == i and hover_part == PART_STRENGTH:
                strength_highlight.append(pos)
            else:
                strength_normal.append(pos)

        _draw_discs(rv3d, shader, strength_normal, COLOR_STRENGTH, disc_radius * 0.85)
        _draw_discs(rv3d, shader, strength_highlight, COLOR_STRENGTH_HL, disc_radius * 1.15)

        gpu.state.blend_set("NONE")

    def test_select(self, context, location):
        obj = context.object
        if not obj:
            return -1

        bhandles, strengths = get_splash_handle_data(obj)
        if bhandles is None:
            return -1

        props = getattr(obj, "nexus_modifier", None)
        if props is None:
            return -1

        handle_count = props.ID_NX_SPLASH_HANDLE_COUNT
        if handle_count * FLOATS_PER_HANDLE > len(bhandles):
            return -1

        region = context.region
        rv3d = context.region_data
        mx = obj.matrix_world

        best_dist = HIT_THRESHOLD
        best_id = -1

        mval = Vector((location[0], location[1]))

        for i in range(handle_count - 1, -1, -1):
            top_anchor = mx @ get_handle_vec(bhandles, i, PART_TOP_ANCHOR)
            bot_anchor = mx @ get_handle_vec(bhandles, i, PART_BOTTOM_ANCHOR)
            direction = top_anchor - bot_anchor
            d_len = direction.length
            if d_len > 1e-8:
                direction /= d_len
            world_pos = top_anchor + direction * strengths[i]
            screen = location_3d_to_region_2d(region, rv3d, world_pos)
            if screen is None:
                continue
            dist = (mval - screen).length
            if dist < best_dist:
                best_dist = dist
                best_id = i * 10 + PART_STRENGTH

        for i in range(handle_count - 1, -1, -1):
            for part in (
                PART_BOTTOM_TANGENT_LEFT,
                PART_BOTTOM_TANGENT_RIGHT,
                PART_BOTTOM_ANCHOR,
                PART_TOP_TANGENT_LEFT,
                PART_TOP_TANGENT_RIGHT,
                PART_TOP_ANCHOR,
            ):
                world_pos = mx @ get_handle_vec(bhandles, i, part)
                screen = location_3d_to_region_2d(region, rv3d, world_pos)
                if screen is None:
                    continue
                dist = (mval - screen).length
                if dist < best_dist:
                    best_dist = dist
                    best_id = i * 10 + part

        if best_id >= 0:
            self._active_handle = best_id // 10
            self._handle_part = best_id % 10
            return best_id

        return -1

    def invoke(self, context, event):
        obj = context.object
        if obj is None:
            return {"CANCELLED"}

        bhandles, strengths = get_splash_handle_data(obj)
        if bhandles is None:
            return {"CANCELLED"}

        self._init_bhandles = bhandles[:]
        self._init_strengths = strengths[:]
        self._init_mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        mx = obj.matrix_world
        handle_count = obj.nexus_modifier.ID_NX_SPLASH_HANDLE_COUNT
        hi = self._active_handle
        part = self._handle_part

        if hi < 0 or hi >= handle_count:
            return {"CANCELLED"}

        if part == PART_STRENGTH:
            top_anchor = mx @ get_handle_vec(bhandles, hi, PART_TOP_ANCHOR)
            bot_anchor = mx @ get_handle_vec(bhandles, hi, PART_BOTTOM_ANCHOR)
            self._drag_axis = top_anchor - bot_anchor
            d_len = self._drag_axis.length
            if d_len > 1e-8:
                self._drag_axis /= d_len
            self._drag_plane_origin = top_anchor
        else:
            world_pos = mx @ get_handle_vec(bhandles, hi, part)
            view_dir = region_2d_to_vector_3d(
                context.region, context.region_data, self._init_mouse
            )
            self._drag_plane_normal = view_dir.normalized()
            self._drag_plane_origin = world_pos

        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        obj = context.object
        if obj is None:
            return {"CANCELLED"}

        bhandles, strengths = get_splash_handle_data(obj)
        if bhandles is None:
            return {"CANCELLED"}

        mx = obj.matrix_world
        mx_inv = mx.inverted_safe()
        hi = self._active_handle
        part = self._handle_part
        mouse_co = Vector((event.mouse_region_x, event.mouse_region_y))
        region = context.region
        rv3d = context.region_data

        if part == PART_STRENGTH:
            from ..utils.viewport import ray_axis_signed_distance

            signed_dist = ray_axis_signed_distance(
                region,
                rv3d,
                mouse_co,
                self._drag_plane_origin,
                self._drag_axis,
            )
            if signed_dist is None:
                return {"RUNNING_MODAL"}

            init_strength = self._init_strengths[hi]

            init_signed = ray_axis_signed_distance(
                region,
                rv3d,
                self._init_mouse,
                self._drag_plane_origin,
                self._drag_axis,
            )
            if init_signed is None:
                init_signed = 0.0

            delta = signed_dist - init_signed
            new_strength = init_strength + delta

            if "PRECISE" in tweak:
                new_strength = init_strength + (new_strength - init_strength) * 0.1

            new_strength = max(0.0, new_strength)
            strengths[hi] = new_strength
            set_splash_handle_data(obj, bhandles, strengths)
        else:
            ray_origin = region_2d_to_origin_3d(region, rv3d, mouse_co)
            ray_dir = region_2d_to_vector_3d(region, rv3d, mouse_co)

            hit = intersect_line_plane(
                ray_origin,
                ray_origin + ray_dir * 10000.0,
                self._drag_plane_origin,
                self._drag_plane_normal,
            )
            if hit is None:
                return {"RUNNING_MODAL"}

            init_world = mx @ get_handle_vec(self._init_bhandles, hi, part)
            delta_world = hit - init_world

            init_mouse_ray_origin = region_2d_to_origin_3d(region, rv3d, self._init_mouse)
            init_mouse_ray_dir = region_2d_to_vector_3d(region, rv3d, self._init_mouse)
            init_hit = intersect_line_plane(
                init_mouse_ray_origin,
                init_mouse_ray_origin + init_mouse_ray_dir * 10000.0,
                self._drag_plane_origin,
                self._drag_plane_normal,
            )
            if init_hit is not None:
                delta_world = hit - init_hit

            if "PRECISE" in tweak:
                delta_world *= 0.1

            new_world = init_world + delta_world
            new_local = mx_inv @ new_world
            old_local = get_handle_vec(self._init_bhandles, hi, part)

            if part in (PART_TOP_ANCHOR, PART_BOTTOM_ANCHOR):
                local_delta = new_local - old_local
                set_handle_vec(bhandles, hi, part, new_local)

                if part == PART_TOP_ANCHOR:
                    for tang in (PART_TOP_TANGENT_RIGHT, PART_TOP_TANGENT_LEFT):
                        old_tang = get_handle_vec(self._init_bhandles, hi, tang)
                        set_handle_vec(bhandles, hi, tang, old_tang + local_delta)
                else:
                    for tang in (PART_BOTTOM_TANGENT_RIGHT, PART_BOTTOM_TANGENT_LEFT):
                        old_tang = get_handle_vec(self._init_bhandles, hi, tang)
                        set_handle_vec(bhandles, hi, tang, old_tang + local_delta)

            elif part in (PART_TOP_TANGENT_RIGHT, PART_TOP_TANGENT_LEFT):
                set_handle_vec(bhandles, hi, part, new_local)
                anchor = get_handle_vec(bhandles, hi, PART_TOP_ANCHOR)
                mirror_part = (
                    PART_TOP_TANGENT_LEFT
                    if part == PART_TOP_TANGENT_RIGHT
                    else PART_TOP_TANGENT_RIGHT
                )
                mirrored = anchor + (anchor - new_local)
                set_handle_vec(bhandles, hi, mirror_part, mirrored)

            elif part in (PART_BOTTOM_TANGENT_RIGHT, PART_BOTTOM_TANGENT_LEFT):
                set_handle_vec(bhandles, hi, part, new_local)
                anchor = get_handle_vec(bhandles, hi, PART_BOTTOM_ANCHOR)
                mirror_part = (
                    PART_BOTTOM_TANGENT_LEFT
                    if part == PART_BOTTOM_TANGENT_RIGHT
                    else PART_BOTTOM_TANGENT_RIGHT
                )
                mirrored = anchor + (anchor - new_local)
                set_handle_vec(bhandles, hi, mirror_part, mirrored)

            set_splash_handle_data(obj, bhandles, strengths)

        obj.update_tag()
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        if cancel:
            obj = context.object
            if obj is not None and hasattr(self, "_init_bhandles"):
                set_splash_handle_data(obj, self._init_bhandles, self._init_strengths)

        context.area.tag_redraw()


def create_splash_gizmo_group(modifier_cls):
    modifier_type = modifier_cls.object_type
    class_name = f"NX_GGT_{modifier_type.lower()}_handles"

    class SplashGizmoGroup(GizmoGroup):
        bl_idname = class_name
        bl_label = "Splash Handles"
        bl_space_type = "VIEW_3D"
        bl_region_type = "WINDOW"
        bl_options = {"3D", "PERSISTENT", "DEPTH_3D", "SHOW_MODAL_ALL"}

        @classmethod
        def poll(cls, context):
            from ..libs import theron

            if not theron.is_initialized():
                return False
            obj = context.object
            if obj is None:
                return False
            if obj.get("nexus_modifier_type") != modifier_type:
                return False
            props = getattr(obj, "nexus_modifier", None)
            if props is None:
                return False
            if not getattr(props, "visible_in_editor", True):
                return False
            if not props.enabled:
                return False
            from ..pipeline_manager.utils import is_modifier_effectively_disabled

            scene = context.scene
            if hasattr(scene, "nexus_pipeline"):
                if is_modifier_effectively_disabled(scene.nexus_pipeline, obj):
                    return False
            return True

        def setup(self, context):
            gz = self.gizmos.new("NX_GT_splash_handles")
            gz.use_draw_modal = True
            self.splash_gizmo = gz

        def refresh(self, context):
            obj = context.object
            if obj is not None:
                self.splash_gizmo.matrix_basis = obj.matrix_world.copy()

        def draw_prepare(self, context):
            obj = context.object
            if obj is not None:
                self.splash_gizmo.matrix_basis = obj.matrix_world.copy()

    SplashGizmoGroup.__name__ = class_name
    SplashGizmoGroup.__qualname__ = class_name

    return SplashGizmoGroup


_registered_classes = []


def register():
    try:
        bpy.utils.register_class(NX_GT_splash_handles)
    except ValueError:
        pass

    from ..modifiers import MODIFIER_REGISTRY

    for modifier_cls in MODIFIER_REGISTRY.values():
        if modifier_cls.object_type != "NX_SPLASH":
            continue

        cls = create_splash_gizmo_group(modifier_cls)
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
        _registered_classes.append(cls)


def unregister():
    for cls in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _registered_classes.clear()

    try:
        bpy.utils.unregister_class(NX_GT_splash_handles)
    except RuntimeError:
        pass
