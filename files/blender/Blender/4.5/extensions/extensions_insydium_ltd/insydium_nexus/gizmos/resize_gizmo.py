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
from dataclasses import dataclass

import bpy
import gpu
from bpy.types import Gizmo, GizmoGroup
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from ..utils import XP_COLOR_MODS_RED
from ..utils.viewport import ray_axis_signed_distance


def _generate_sphere_vertices(segments=8, rings=6):
    vertices = []

    for i in range(rings):
        lat0 = math.pi * (-0.5 + float(i) / rings)
        lat1 = math.pi * (-0.5 + float(i + 1) / rings)
        z0 = math.sin(lat0)
        z1 = math.sin(lat1)
        r0 = math.cos(lat0)
        r1 = math.cos(lat1)

        for j in range(segments):
            lng0 = 2 * math.pi * float(j) / segments
            lng1 = 2 * math.pi * float(j + 1) / segments

            x00 = r0 * math.cos(lng0)
            y00 = r0 * math.sin(lng0)
            x01 = r0 * math.cos(lng1)
            y01 = r0 * math.sin(lng1)
            x10 = r1 * math.cos(lng0)
            y10 = r1 * math.sin(lng0)
            x11 = r1 * math.cos(lng1)
            y11 = r1 * math.sin(lng1)

            vertices.append((x00, y00, z0))
            vertices.append((x10, y10, z1))
            vertices.append((x11, y11, z1))

            vertices.append((x00, y00, z0))
            vertices.append((x11, y11, z1))
            vertices.append((x01, y01, z0))

    return vertices


SPHERE_VERTICES = _generate_sphere_vertices(segments=8, rings=6)

HIGHLIGHT_SCALE = 1.5
COLOR_NORMAL = XP_COLOR_MODS_RED[:3]
COLOR_HIGHLIGHT = tuple(min(c * HIGHLIGHT_SCALE, 1.0) for c in COLOR_NORMAL)
COLOR_LINE = (*COLOR_NORMAL, 0.15)
COLOR_LINE_HIGHLIGHT = (*COLOR_HIGHLIGHT, 0.5)


# ---------------------------------------------------------------------------
# HandleConfig — declared by modifiers, consumed by the gizmo factory
# ---------------------------------------------------------------------------


@dataclass
class HandleConfig:
    drag_axis: Vector
    prop_name: str
    prop_component: int | None = None
    position_factor: float = 1.0
    min_value: float = 0.0
    min_value_fn: object = None
    max_value: float | None = None
    max_value_fn: object = None
    position_base_fn: object = None


# ---------------------------------------------------------------------------
# NX_GT_sphere_handle — the single reusable gizmo type
# ---------------------------------------------------------------------------


class NX_GT_sphere_handle(Gizmo):
    bl_idname = "NX_GT_sphere_handle"
    bl_target_properties = ()

    __slots__ = (
        "drag_axis",
        "prop_name",
        "prop_component",
        "position_factor",
        "min_value",
        "min_value_fn",
        "max_value",
        "max_value_fn",
        "position_base_fn",
        "matrix_fn",
        "custom_shape",
        "init_value",
        "init_mouse",
        "init_grab_offset",
    )

    def setup(self):
        if not hasattr(self, "custom_shape"):
            self.custom_shape = self.new_custom_shape("TRIS", SPHERE_VERTICES)

    def draw(self, context):
        self._draw_handle(context, select_id=None)

    def draw_select(self, context, select_id):
        self._draw_handle(context, select_id=select_id)

    def _draw_handle(self, context, select_id):
        self.color = COLOR_NORMAL
        self.color_highlight = COLOR_HIGHLIGHT

        if select_id is not None:
            gpu.select.load_id(select_id)

        self.draw_custom_shape(self.custom_shape)

    def test_select(self, context, location):
        return -1

    def _read_value(self, props):
        if self.prop_component is None:
            return getattr(props, self.prop_name)
        return getattr(props, self.prop_name)[self.prop_component]

    def _write_value(self, props, value):
        if self.prop_component is None:
            setattr(props, self.prop_name, value)
        else:
            vec = list(getattr(props, self.prop_name))
            vec[self.prop_component] = value
            setattr(props, self.prop_name, vec)

    def _get_matrix(self, obj, props):
        if self.matrix_fn is not None:
            return self.matrix_fn(obj, props)
        return obj.matrix_world

    def invoke(self, context, event):
        obj = context.object
        if obj is None:
            return {"CANCELLED"}

        props = getattr(obj, "nexus_modifier", None)
        if props is None:
            return {"CANCELLED"}

        self.init_value = self._read_value(props)
        self.init_mouse = (event.mouse_region_x, event.mouse_region_y)

        mx = self._get_matrix(obj, props)
        axis_origin = mx.translation.copy()
        axis_world = (mx.to_3x3() @ self.drag_axis).normalized()

        signed_dist = ray_axis_signed_distance(
            context.region,
            context.region_data,
            self.init_mouse,
            axis_origin,
            axis_world,
        )

        if self.position_base_fn is not None:
            position_base = self.position_base_fn(props)
        else:
            position_base = 0.0

        if signed_dist is not None:
            self.init_grab_offset = (
                position_base + self.init_value * self.position_factor
            ) - signed_dist
        else:
            self.init_grab_offset = 0.0

        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        obj = context.object
        if obj is None:
            return {"CANCELLED"}

        props = getattr(obj, "nexus_modifier", None)
        if props is None:
            return {"CANCELLED"}

        mx = self._get_matrix(obj, props)
        axis_origin = mx.translation.copy()
        axis_world = (mx.to_3x3() @ self.drag_axis).normalized()

        mouse_co = (event.mouse_region_x, event.mouse_region_y)
        signed_dist = ray_axis_signed_distance(
            context.region,
            context.region_data,
            mouse_co,
            axis_origin,
            axis_world,
        )

        if signed_dist is None:
            return {"RUNNING_MODAL"}
        adjusted_dist = signed_dist + self.init_grab_offset

        if self.position_base_fn is not None:
            position_base = self.position_base_fn(props)
        else:
            position_base = 0.0
        new_value = (adjusted_dist - position_base) / self.position_factor

        if "PRECISE" in tweak:
            new_value = self.init_value + (new_value - self.init_value) * 0.1

        if self.min_value_fn is not None:
            effective_min = self.min_value_fn(props)
        else:
            effective_min = self.min_value
        new_value = max(effective_min, new_value)
        if self.max_value_fn is not None:
            effective_max = self.max_value_fn(props)
        elif self.max_value is not None:
            effective_max = self.max_value
        else:
            effective_max = None
        if effective_max is not None:
            new_value = min(effective_max, new_value)

        self._write_value(props, new_value)

        if self.position_base_fn is not None:
            position_base = self.position_base_fn(props)
        else:
            position_base = 0.0
        offset = self.drag_axis * (position_base + new_value * self.position_factor)
        self.matrix_basis = mx @ Matrix.Translation(offset)

        obj.update_tag()
        context.area.tag_redraw()

        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        if cancel:
            obj = context.object
            if obj is not None:
                props = getattr(obj, "nexus_modifier", None)
                if props is not None and hasattr(self, "init_value"):
                    self._write_value(props, self.init_value)

        context.area.tag_redraw()


# ---------------------------------------------------------------------------
# Generic gizmo group factory
# ---------------------------------------------------------------------------


def create_gizmo_group(modifier_cls):
    """Create a GizmoGroup for any modifier that defines get_gizmo_handles()."""
    modifier_type = modifier_cls.object_type
    max_handles = getattr(modifier_cls, "gizmo_max_handles", 3)
    has_custom_matrix = hasattr(modifier_cls, "get_gizmo_matrix")
    matrix_fn = modifier_cls.get_gizmo_matrix if has_custom_matrix else None

    class_name = f"NX_GGT_{modifier_type.lower()}_resize"

    class DynamicGizmoGroup(GizmoGroup):
        bl_idname = class_name
        bl_label = f"{modifier_cls.object_label} Resize Handles"
        bl_space_type = "VIEW_3D"
        bl_region_type = "WINDOW"
        bl_options = {"3D", "PERSISTENT", "DEPTH_3D", "SCALE", "SHOW_MODAL_ALL"}

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
            self.handles = []

            for _ in range(max_handles):
                gz = self.gizmos.new("NX_GT_sphere_handle")
                gz.drag_axis = Vector((1, 0, 0))
                gz.prop_name = ""
                gz.prop_component = None
                gz.position_factor = 1.0
                gz.min_value = 0.0
                gz.min_value_fn = None
                gz.max_value = None
                gz.max_value_fn = None
                gz.position_base_fn = None
                gz.matrix_fn = matrix_fn
                gz.color = COLOR_NORMAL
                gz.alpha = 1.0
                gz.color_highlight = COLOR_HIGHLIGHT
                gz.alpha_highlight = 1.0
                gz.scale_basis = 0.018
                gz.use_draw_modal = True
                gz.hide = True
                self.handles.append(gz)

        def refresh(self, context):
            self._update_handles(context)

        def draw_prepare(self, context):
            self._update_handles(context)

            obj = context.object
            if obj is None:
                return

            origin = obj.matrix_world.translation
            lines = []
            for gz in self.handles:
                if gz.hide:
                    continue
                color = COLOR_LINE_HIGHLIGHT if gz.is_highlight else COLOR_LINE
                lines.append((origin, gz.matrix_basis.translation, color))

            if lines:
                self._draw_handle_lines(context, lines)

        def _update_handles(self, context):
            obj = context.object
            if obj is None:
                return

            props = getattr(obj, "nexus_modifier", None)
            if props is None:
                return

            configs = modifier_cls.get_gizmo_handles(obj, props)

            if has_custom_matrix:
                mx = modifier_cls.get_gizmo_matrix(obj, props)
            else:
                mx = obj.matrix_world

            for i, gz in enumerate(self.handles):
                if i < len(configs):
                    cfg = configs[i]
                    gz.drag_axis = cfg.drag_axis
                    gz.prop_name = cfg.prop_name
                    gz.prop_component = cfg.prop_component
                    gz.position_factor = cfg.position_factor
                    gz.min_value = cfg.min_value
                    gz.min_value_fn = cfg.min_value_fn
                    gz.max_value = cfg.max_value
                    gz.max_value_fn = cfg.max_value_fn
                    gz.position_base_fn = cfg.position_base_fn
                    gz.hide = False

                    if cfg.prop_component is None:
                        value = getattr(props, cfg.prop_name, 1.0)
                    else:
                        value = getattr(props, cfg.prop_name, (1.0, 1.0, 1.0))[cfg.prop_component]

                    base = cfg.position_base_fn(props) if cfg.position_base_fn is not None else 0.0
                    offset = cfg.drag_axis * (base + value * cfg.position_factor)
                    gz.matrix_basis = mx @ Matrix.Translation(offset)
                else:
                    gz.hide = True

        def _draw_handle_lines(self, context, lines):
            region = context.region
            shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
            shader.bind()
            shader.uniform_float("viewportSize", (region.width, region.height))
            shader.uniform_float("lineWidth", 1.0)

            for start, end, color in lines:
                shader.uniform_float("color", color)
                batch = batch_for_shader(shader, "LINE_STRIP", {"pos": [start, end]})
                batch.draw(shader)

    DynamicGizmoGroup.__name__ = class_name
    DynamicGizmoGroup.__qualname__ = class_name

    return DynamicGizmoGroup


_registered_gizmo_classes = []


def register():
    try:
        bpy.utils.register_class(NX_GT_sphere_handle)
    except ValueError:
        pass

    from ..modifiers import MODIFIER_REGISTRY

    for modifier_cls in MODIFIER_REGISTRY.values():
        if not hasattr(modifier_cls, "get_gizmo_handles"):
            continue

        gizmo_group_cls = create_gizmo_group(modifier_cls)
        try:
            bpy.utils.register_class(gizmo_group_cls)
        except ValueError:
            pass
        _registered_gizmo_classes.append(gizmo_group_cls)


def unregister():
    for cls in reversed(_registered_gizmo_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _registered_gizmo_classes.clear()

    try:
        bpy.utils.unregister_class(NX_GT_sphere_handle)
    except RuntimeError:
        pass
