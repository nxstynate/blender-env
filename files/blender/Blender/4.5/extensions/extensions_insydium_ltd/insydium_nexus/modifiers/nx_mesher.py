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

from ..libs.theron_ids import get
from ..properties.nx_mesher import SPEC, get_mesher_ui_config
from ..ui import PerItemToggle
from ..utils import XP_COLOR_MODS_BLUE, XP_COLOR_MODS_RED, draw_lines, draw_thick_lines
from .base import MenuCategory, NexusModifier, UIFlags


def _update_mesh(obj, handle, props):

    import numpy as np

    from ..libs import theron

    container = theron.get_modifier_container(handle)
    if container is None:
        return

    mesh_obj = None
    for child in obj.children:
        if child.get("nexus_object_type") == "NX_MESHER_MESH":
            mesh_obj = child
            break
    if mesh_obj is None or mesh_obj.data is None:
        return

    mesh = mesh_obj.data

    vert_result = theron.get_memory(container, get("ID_NX_MESHER_VERTICES_OUT"))
    poly_result = theron.get_memory(container, get("ID_NX_MESHER_POLYGONS_OUT"))

    # Normals are per vertex
    norm_result = theron.get_memory(container, get("ID_NX_MESHER_NORMALS_OUT"))

    if vert_result is None or poly_result is None or norm_result is None:
        mesh.clear_geometry()
        return

    vert_ptr, vert_bytes = vert_result
    poly_ptr, poly_bytes = poly_result
    norm_ptr, norm_bytes = norm_result

    vert_count = vert_bytes // 12
    poly_count = poly_bytes // 16

    if vert_count == 0 or poly_count == 0 or norm_bytes != vert_bytes:
        mesh.clear_geometry()
        return

    c_floats = (ctypes.c_float * (vert_count * 3)).from_address(vert_ptr)
    raw_verts = np.ctypeslib.as_array(c_floats).reshape(vert_count, 3)

    c_ints = (ctypes.c_int32 * (poly_count * 4)).from_address(poly_ptr)
    raw_polys = np.ctypeslib.as_array(c_ints).reshape(poly_count, 4)

    is_tris = props.ID_NX_MESHER_POLY_TYPE == "ID_NX_MESHER_POLY_TYPE_TRIS"
    verts_per_face = 3 if is_tris else 4
    loop_count = poly_count * verts_per_face

    loop_verts = raw_polys[:, :verts_per_face].ravel().copy()
    loops = np.arange(0, loop_count + 1, verts_per_face, dtype=np.int32)

    mesh.clear_geometry()

    mesh.vertices.add(vert_count)
    mesh.polygons.add(poly_count)
    mesh.loops.add(loop_count)

    # (Tavis)
    # foreach_set even as the fast option is remarkably slow -- instead we can directly copy into
    # vertex, corner, and loop arrays. I measured this to be almost 200x faster...
    pos_ptr = mesh.attributes["position"].data[0].as_pointer()
    ctypes.memmove(pos_ptr, raw_verts.ctypes.data, vert_count * 12)

    corner_ptr = mesh.attributes[".corner_vert"].data[0].as_pointer()
    ctypes.memmove(corner_ptr, loop_verts.ctypes.data, loop_count * 4)

    # The loops array is a bit more hacky as this isn't an attribute. Instead we must use the
    # offset of the face_offset_indices pointer in the Mesh struct. This could break if the
    # Blender ABI changes!

    # Magic offset for the Mesh struct -- see the blender source code in
    # source/blender/makesdna/DNA_mesh_types.h
    offsetof_face_offset_indices = 448
    face_offset_indices = ctypes.cast(
        mesh.as_pointer() + offsetof_face_offset_indices,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_int32)),
    )

    ctypes.memmove(face_offset_indices.contents, loops.ctypes.data, (poly_count + 1) * 4)

    # ==== Normals ====
    if "custom_normal" not in mesh.attributes:
        mesh.attributes.new(name="custom_normal", type="FLOAT_VECTOR", domain="POINT")

    normals_ptr = mesh.attributes["custom_normal"].data[0].as_pointer()
    ctypes.memmove(normals_ptr, norm_ptr, vert_count * 12)

    ########

    emitter_map_result = theron.get_memory(container, get("ID_NX_MESHER_VERTEX_MAP_OUT"))
    vel_result = theron.get_memory(container, get("ID_NX_MESHER_VELOCITY_OUT"))
    color_result = theron.get_memory(container, get("ID_NX_MESHER_COLOR_OUT"))

    # ==== Emitter vertex maps ====
    if emitter_map_result is not None:
        emitter_map_ptr, emitter_map_bytes = emitter_map_result
        emitter_count = emitter_map_bytes // (4 * vert_count)

        emitter_names = []
        for layer in props.mesher_layers:
            if layer.obj and layer.item_type == "ID_NX_MESHER_LAYER_TYPE_EMITTER":
                emitter_names.append(layer.obj.name)

        for i in range(emitter_count):
            if i >= len(emitter_names):
                break

            c_floats_weight = (ctypes.c_float * vert_count).from_address(
                emitter_map_ptr + i * vert_count * 4
            )
            weights = np.ctypeslib.as_array(c_floats_weight).reshape(vert_count)

            attr_name = emitter_names[i]
            if attr_name not in mesh.attributes:
                mesh.attributes.new(name=attr_name, type="FLOAT", domain="POINT")
            attr_ptr = mesh.attributes[attr_name].data[0].as_pointer()
            ctypes.memmove(attr_ptr, weights.ctypes.data, vert_count * 4)

    # ==== Velocity ====
    if vel_result is not None:
        vel_ptr, vel_bytes = vel_result
        if vel_bytes == vert_count * 12:
            c_floats_vel = (ctypes.c_float * (vert_count * 3)).from_address(vel_ptr)
            vel_flat = np.ctypeslib.as_array(c_floats_vel).reshape(3, vert_count)

            # Stored as component-wise arrays, need to convert to (N, 3) shape
            vel_data = vel_flat.transpose().copy()

            if "velocity" not in mesh.attributes:
                mesh.attributes.new(name="velocity", type="FLOAT_VECTOR", domain="POINT")
            vel_attr_ptr = mesh.attributes["velocity"].data[0].as_pointer()
            ctypes.memmove(vel_attr_ptr, vel_data.ctypes.data, vert_count * 12)

    # ==== Color ====
    if color_result is not None:
        color_ptr, color_bytes = color_result
        if color_bytes == vert_count * 12:
            if "color" not in mesh.color_attributes:
                mesh.color_attributes.new(name="color", type="FLOAT_COLOR", domain="POINT")
            c_floats_color = (ctypes.c_float * (vert_count * 3)).from_address(color_ptr)
            rgb = np.ctypeslib.as_array(c_floats_color).reshape(vert_count, 3)

            # Need to pad to RGBA for Blender colour attribute, set alpha=1.0
            rgba = np.empty((vert_count, 4), dtype=np.float32)
            rgba[:, :3] = rgb
            rgba[:, 3] = 1.0

            color_attr_ptr = mesh.color_attributes["color"].data[0].as_pointer()
            ctypes.memmove(color_attr_ptr, rgba.ctypes.data, vert_count * 16)
            mesh.color_attributes.active_color_index = mesh.color_attributes.find("color")

    mesh.update()


class NXMesherModifier(NexusModifier):
    object_type = "NX_MESHER"
    object_name = "nxMesher"
    object_label = "Mesher Modifier"
    object_description = "Generates polygon mesh from particle emitters"
    icon_name = "nx_mesher"
    category = "Generators"
    menu_category = MenuCategory.GENERATORS

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    always_execute = True

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        mesh_data = bpy.data.meshes.new(f"{obj.name}_mesh")
        mesh_obj = bpy.data.objects.new(f"{obj.name}_mesh", mesh_data)

        for col in obj.users_collection:
            col.objects.link(mesh_obj)
            break

        mesh_obj.parent = obj
        mesh_obj["nexus_object_type"] = "NX_MESHER_MESH"

    @classmethod
    def post_execute_object(cls, obj, handle, props, _scene, *, depsgraph=None):
        _update_mesh(obj, handle, props)

    @classmethod
    def on_destroy(cls, mod_uid: str) -> None:
        orphans = [
            o
            for o in bpy.data.objects
            if o.get("nexus_object_type") == "NX_MESHER_MESH"
            and (o.parent is None or o.parent.name not in bpy.data.objects)
        ]
        for o in orphans:
            bpy.data.objects.remove(o, do_unlink=True)

    @classmethod
    def on_state_clear(cls, *, free_resources: bool = True) -> None:
        for obj in bpy.data.objects:
            if obj.get("nexus_object_type") == "NX_MESHER_MESH" and obj.data:
                obj.data.clear_geometry()

    @classmethod
    def on_reset(cls, obj, _props):
        for child in obj.children:
            if child.get("nexus_object_type") == "NX_MESHER_MESH":
                if child.data:
                    child.data.clear_geometry()
                break

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        row = layout.row(align=True)
        row.prop(data, "mesher_tab", expand=True)

        tab = data.mesher_tab

        if tab == "GENERAL":
            cls._draw_general_tab(layout, data)
        elif tab == "EXPORT_TAGS":
            cls._draw_export_tags_tab(layout, data)
        elif tab == "DOMAIN":
            cls._draw_domain_tab(layout, data)

    @classmethod
    def _draw_general_tab(cls, layout, data):
        ui_config = get_mesher_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_MESHER_GRID_SIZE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_MESHER_GRID_SIZE")
        col.prop(data, "ID_NX_MESHER_SURFACE_SIZE_MODE")

        if data.ID_NX_MESHER_SURFACE_SIZE_MODE == "ID_NX_MESHER_SURFACE_SIZE_MODE_FIXED":
            col.prop(data, "ID_NX_MESHER_SURFACE_SIZE")
        else:
            col.prop(data, "ID_NX_MESHER_SURFACE_SIZE_MULT")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_MESHER_SURFACE_TYPE")

        if data.ID_NX_MESHER_SURFACE_TYPE == "ID_NX_MESHER_SURFACE_TYPE_ANISOTROPIC":
            col.prop(data, "ID_NX_MESHER_ANISOTROPY_USE_SPEED")

            if data.ID_NX_MESHER_ANISOTROPY_USE_SPEED:
                col.prop(data, "ID_NX_MESHER_ANISOTROPY_MAX_SPEED")
            else:
                col.prop(data, "ID_NX_MESHER_KERNEL_ECCENTRICITY")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_MESHER_POLY_TYPE")

        col.separator(type="LINE")

        cls._draw_layers_section(layout, data)

    @classmethod
    def _draw_export_tags_tab(cls, layout, data):
        ui_config = get_mesher_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_MESHER_EXPORT_COLOUR", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_MESHER_EXPORT_COLOUR")

        if data.ID_NX_MESHER_EXPORT_COLOUR:
            col.prop(data, "ID_NX_MESHER_EXPORT_BLEND_COLOUR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_MESHER_EXPORT_VELOCITY")

        if data.ID_NX_MESHER_EXPORT_VELOCITY:
            col.prop(data, "ID_NX_MESHER_EXPORT_MAX_VELOCITY_X")
            col.prop(data, "ID_NX_MESHER_EXPORT_MAX_VELOCITY_Y")
            col.prop(data, "ID_NX_MESHER_EXPORT_MAX_VELOCITY_Z")
            col.prop(data, "ID_NX_MESHER_EXPORT_BLEND_VELOCITY")

    @classmethod
    def _draw_domain_tab(cls, layout, data):
        ui_config = get_mesher_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_MESHER_DOMAIN", {}).get(
            "use_property_split", True
        )

        row = col.row()
        row.enabled = not data.ID_NX_MESHER_ADAPTIVE_DOMAIN
        row.prop(data, "ID_NX_MESHER_DOMAIN")

        col.prop(data, "ID_NX_MESHER_ADAPTIVE_DOMAIN")

        row = col.row()
        row.enabled = data.ID_NX_MESHER_ADAPTIVE_DOMAIN
        row.prop(data, "mesher_adaptive_color")

        col.separator(type="LINE")

        col.prop(data, "mesher_draw_domain")

    @classmethod
    def _draw_layers_section(cls, layout, data):
        from ..properties.nx_mesher import (
            draw_mesher_layer_settings,
        )
        from ..ui import draw_nodetree

        split = layout.split(factor=0.385)
        split.use_property_split = False

        #        label_col = split.column()
        #        label_col.alignment = "RIGHT"
        #        label_col.label(text="Add Modifier")
        #
        #        content_col = split.column()
        #        op = content_col.operator(
        #            "nexus.nodetree_add",
        #            text="Smoothing",
        #            icon_value=get_icon("nx_mesher_layer_smoothing"),
        #        )
        #        op.list_prop = "mesher_layers"
        #        op.index_prop = "mesher_layers_index"
        #        op.item_type = "ID_NX_MESHER_LAYER_TYPE_SMOOTHING"
        #        op.menu_id = "mesher_layers"

        layout.separator(factor=0.5)

        draw_nodetree(
            layout,
            data,
            "mesher_layers",
            "mesher_layers_index",
            label="Layers",
            draw_item_settings=draw_mesher_layer_settings,
            menu_id="mesher_layers",
            per_item_toggles=(
                PerItemToggle(
                    bit=0,
                    icons=("nx_mesher_idmap_on", "nx_mesher_idmap_off"),
                    tooltip_a="Enable emitter vertex map",
                    tooltip_b="Disable emitter vertex map",
                    show_condition=lambda item: (
                        item.item_type == "ID_NX_MESHER_LAYER_TYPE_EMITTER"
                    ),
                ),
            ),
        )

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        draw_domain = getattr(props, "mesher_draw_domain", False)

        if not draw_domain:
            return

        adaptive = getattr(props, "ID_NX_MESHER_ADAPTIVE_DOMAIN", True)

        if adaptive:
            from ..handlers.pipeline import get_nexus_obj_handle
            from ..libs import theron

            handle = get_nexus_obj_handle(context.scene, obj)
            container = theron.get_modifier_container(handle) if handle is not None else None
            cls._draw_adaptive_domain(obj, props, context, container)
        else:
            cls._draw_static_domain(obj, props, context)

    @classmethod
    def _draw_static_domain(cls, obj: bpy.types.Object, props, context) -> None:
        domain_size = Vector(getattr(props, "ID_NX_MESHER_DOMAIN", (4.0, 4.0, 4.0)))

        half = domain_size / 2.0
        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.line_width_set(1.5)

        corners = [
            Vector((-half.x, -half.y, -half.z)),
            Vector((half.x, -half.y, -half.z)),
            Vector((half.x, half.y, -half.z)),
            Vector((-half.x, half.y, -half.z)),
            Vector((-half.x, -half.y, half.z)),
            Vector((half.x, -half.y, half.z)),
            Vector((half.x, half.y, half.z)),
            Vector((-half.x, half.y, half.z)),
        ]
        world_corners = [mx @ c for c in corners]

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)
        box_edges = [
            (world_corners[0], world_corners[1]),
            (world_corners[1], world_corners[2]),
            (world_corners[2], world_corners[3]),
            (world_corners[3], world_corners[0]),
            (world_corners[4], world_corners[5]),
            (world_corners[5], world_corners[6]),
            (world_corners[6], world_corners[7]),
            (world_corners[7], world_corners[4]),
            (world_corners[0], world_corners[4]),
            (world_corners[1], world_corners[5]),
            (world_corners[2], world_corners[6]),
            (world_corners[3], world_corners[7]),
        ]
        draw_lines(shader, box_edges)

        corner_len_x = min(0.25, half.x * 0.5)
        corner_len_y = min(0.25, half.y * 0.5)
        corner_len_z = min(0.25, half.z * 0.5)

        corner_lines = []
        corner_dirs = [
            [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],
            [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],
            [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],
            [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
            [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],
        ]

        for i, corner in enumerate(corners):
            world_corner = mx @ corner
            for direction in corner_dirs[i]:
                if abs(direction.x) > 0.5:
                    corner_len = corner_len_x
                elif abs(direction.y) > 0.5:
                    corner_len = corner_len_y
                else:
                    corner_len = corner_len_z

                end_local = corner + direction * corner_len
                end_world = mx @ end_local
                corner_lines.append((world_corner, end_world))

        draw_thick_lines(context, corner_lines, XP_COLOR_MODS_RED, 4.0)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(1.0)

    @classmethod
    def _draw_adaptive_domain(cls, obj: bpy.types.Object, props, context, container) -> None:

        import numpy as np

        from ..libs import theron

        # Should this be cached somewhere?
        regions_result = theron.get_memory(container, get("ID_NX_MESHER_REGIONS_OUT"))
        min_domain = theron.get_vector(container, get("ID_NX_MESHER_MIN_DOMAIN_OUT"))

        if not regions_result or not min_domain:
            return

        # Get regions as a numpy array
        regions_ptr, regions_bytes = regions_result
        regions_count = regions_bytes // 12

        c_ints = (ctypes.c_int32 * (regions_count * 3)).from_address(regions_ptr)
        regions = np.ctypeslib.as_array(c_ints).reshape(regions_count, 3)

        voxel_size = getattr(props, "ID_NX_MESHER_GRID_SIZE", 0.05)
        region_size = voxel_size * 16  # ACTIVE_REGION_MULT

        adaptive_color = tuple(getattr(props, "mesher_adaptive_color", (1.0, 0.29, 0.39, 1.0)))

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")

        # Fast lookups for regions
        region_set = {tuple(v) for v in regions.tolist()}
        lines = []

        def _draw_adaptive_condition(region, region_set, v1, v2):
            """
            Check the 3 other voxels that share the line that will be drawn, only draw if we need
            to highlight two perpendicular surfaces
            """

            grid1 = tuple(region + v1) in region_set
            grid2 = tuple(region + v2) in region_set
            grid3 = tuple(region + v1 + v2) in region_set

            if not grid3:
                return not (grid1 ^ grid2)
            else:
                return not (grid1 and grid2)

        def _draw_adaptive_voxel_rect(region, region_set, off, v1, v2, size=1.0):
            """
            Draws a single face for an active voxel, used by DrawAdaptiveDomainVoxel. By
            DrawAdapativeCondition, we ensure to only draw lines of the face where needed, i.e. at
            a boundary.
            """

            v3 = np.cross(v1, v2)
            centre = off + size * v3

            if _draw_adaptive_condition(region, region_set, -v2, v3):
                lines.append(
                    (
                        centre + size * (-v1 - v2),
                        centre + size * (v1 - v2),
                    )
                )
            if _draw_adaptive_condition(region, region_set, v1, v3):
                lines.append(
                    (
                        centre + size * (v1 - v2),
                        centre + size * (v1 + v2),
                    )
                )
            if _draw_adaptive_condition(region, region_set, v2, v3):
                lines.append(
                    (
                        centre + size * (v1 + v2),
                        centre + size * (-v1 + v2),
                    )
                )
            if _draw_adaptive_condition(region, region_set, -v1, v3):
                lines.append(
                    (
                        centre + size * (-v1 + v2),
                        centre + size * (-v1 - v2),
                    )
                )

        def _draw_adaptive_domain_voxel(region, region_set, off, region_size):
            """
            Draws a single voxel in the active domain using minimal lines to only show the outline
            of each continuous surface.
            """

            # X
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([0, 1, 0]),
                np.array([0, 0, 1]),
                region_size * 0.5,
            )
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([0, 0, 1]),
                np.array([0, 1, 0]),
                region_size * 0.5,
            )

            # Y
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([1, 0, 0]),
                np.array([0, 0, 1]),
                region_size * 0.5,
            )
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([0, 0, 1]),
                np.array([1, 0, 0]),
                region_size * 0.5,
            )

            # Z
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([1, 0, 0]),
                np.array([0, 1, 0]),
                region_size * 0.5,
            )
            _draw_adaptive_voxel_rect(
                region,
                region_set,
                off,
                np.array([0, 1, 0]),
                np.array([1, 0, 0]),
                region_size * 0.5,
            )

        for region in regions.tolist():
            off = min_domain + region_size * (region + np.full(3, 0.5))
            _draw_adaptive_domain_voxel(region, region_set, off, region_size)

        draw_thick_lines(context, lines, adaptive_color, 4.0)

        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
