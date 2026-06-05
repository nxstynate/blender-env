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
import numpy as np
import ctypes
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

from ..libs import theron, theron_ids
from ..libs.nexus_rate import draw_rate_prop
from ..libs.nexus_time import draw_time_prop
from ..properties.nx_emitter import (
    EMITTER_LINE_SPEC,
    EMITTER_POLY_SPEC,
    SPEC,
    get_emitter_extended_data_ui_config,
    get_emitter_ui_config,
)
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_RED,
    draw_circle,
    draw_lines,
)
from ..utils.gradient import GradientSpec, NexusGradient
from .base import MenuCategory, NexusObject, UIFlags


def _void_ptr_to_ndarray(ptr, dtype, shape):
    dtype = np.dtype(dtype)
    ctype = np.ctypeslib.as_ctypes_type(dtype.base)

    shape = shape + dtype.shape  # Build full shape combining dtype
    n_elements = int(np.prod(shape))

    c_array = (ctype * n_elements).from_address(ptr.value)
    return np.ctypeslib.as_array(c_array).reshape(shape)


def _is_ptr_null(ptr):
    return ptr is None or ptr.value is None


def _add_mesh_vertex_property(mesh, handle, count, prop, bpy_type=None):

    prop_ptr = theron.get_emitter_particle_data(handle, prop)
    prop_name = theron.PARTICLE_PROPERTY_NAMES[prop].lower().replace(" ", "_")
    prop_type = theron.PARTICLE_PROPERTY_TYPES[prop]

    _vec4 = np.dtype((np.float32, 4))

    if bpy_type is None:
        if prop_type == np.float32:
            bpy_type = "FLOAT"
        elif prop_type == np.int32:
            bpy_type = "INT"
        elif prop_type == _vec4:
            bpy_type = "FLOAT_VECTOR"
        else:
            return

    if not _is_ptr_null(prop_ptr):
        if prop_name not in mesh.attributes:
            mesh.attributes.new(name=prop_name, type=bpy_type, domain="POINT")

        property_arr = _void_ptr_to_ndarray(prop_ptr, prop_type, (count,))

        if prop_type == _vec4:
            # For vec4 properties, we never actually use the w component
            if bpy_type != "FLOAT_COLOR":
                property_arr = property_arr[:, :3].copy()
            else:
                # For colour set all A components to 1.0
                property_arr[:, 3] = 1.0

        dst = mesh.attributes[prop_name].data[0].as_pointer()
        ctypes.memmove(dst, property_arr.ctypes.data, property_arr.nbytes)


def _setup_point_cloud_geonodes(obj):
    """
    Creates geometry nodes to convert the mesh vertices to a point cloud.
    """

    mod = obj.modifiers.get("NX_PointCloud_GN")
    if mod is None:
        mod = obj.modifiers.new("NX_PointCloud_GN", "NODES")

    group_name = "NX_PointCloud_GN"
    if group_name in bpy.data.node_groups:
        mod.node_group = bpy.data.node_groups[group_name]
        return

    ng = bpy.data.node_groups.new(group_name, "GeometryNodeTree")
    mod.node_group = ng
    nodes = ng.nodes
    links = ng.links

    # Interface: geometry in/out
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    # Nodes
    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")
    m2p = nodes.new("GeometryNodeMeshToPoints")

    named_attr = nodes.new("GeometryNodeInputNamedAttribute")
    named_attr.data_type = "FLOAT"
    named_attr.inputs["Name"].default_value = "radius"

    # Layout
    input_node.location = (-200, 0)
    named_attr.location = (-200, -100)
    m2p.location = (0, 0)
    output_node.location = (200, 0)

    # Links
    links.new(input_node.outputs["Geometry"], m2p.inputs["Mesh"])
    links.new(named_attr.outputs["Attribute"], m2p.inputs["Radius"])
    links.new(m2p.outputs["Points"], output_node.inputs["Geometry"])


_SQRT2 = math.sqrt(2)
_SQRT3 = math.sqrt(3)


def _estimate_regular_emission_count(data):
    """Estimate particle count for Regular/Hex emission via area/volume heuristic.

    Divides the shape's area (2D) or volume (3D) by the unit cell size
    for the packing mode.  Regular packing: (2R)^n, Hex: 2*sqrt(3)*R^2 (2D)
    or 4*sqrt(2)*R^3 (3D), where R = spacing_fraction * particle_radius.
    """
    spacing_pct = data.ID_NX_EMITTER_SPACING
    particle_radius = data.ID_NX_EMITTER_RADIUS

    if particle_radius <= 0.0 or spacing_pct <= 0.0:
        return 0

    r = (spacing_pct / 100.0) * particle_radius
    if r <= 0.0:
        return 0

    shape = data.ID_NX_EMITTER_SHAPE
    mode = data.ID_NX_EMITTER_MODE
    is_3d = shape in ("BOX", "SPHERE")

    if shape == "RECT":
        extent = data.ID_NX_EMITTER_SHAPE_RECT_W * data.ID_NX_EMITTER_SHAPE_RECT_H
    elif shape == "DISC":
        extent = math.pi * data.ID_NX_EMITTER_SHAPE_RADIUS**2
    elif shape == "BOX":
        s = data.emitter_shape_box_size
        extent = s[0] * s[1] * s[2]
    elif shape == "SPHERE":
        extent = (4.0 / 3.0) * math.pi * data.ID_NX_EMITTER_SHAPE_RADIUS**3
    else:
        return 0

    if mode == "REGULAR":
        unit = (2.0 * r) ** 3 if is_3d else (2.0 * r) ** 2
    else:  # HEX
        unit = 4.0 * _SQRT2 * r**3 if is_3d else 2.0 * _SQRT3 * r**2

    if unit <= 0.0:
        return 0

    return round(extent / unit)


def _get_orientation_matrix(orientation):
    if orientation == "Y_NEG":
        return Matrix.Rotation(math.pi, 4, "X")
    elif orientation == "X_POS":
        return Matrix.Rotation(-math.pi / 2, 4, "Z")
    elif orientation == "X_NEG":
        return Matrix.Rotation(math.pi / 2, 4, "Z")
    elif orientation == "Z_POS":
        return Matrix.Rotation(math.pi / 2, 4, "X")
    elif orientation == "Z_NEG":
        return Matrix.Rotation(-math.pi / 2, 4, "X")
    else:
        return Matrix.Identity(4)


_EMITTER_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="emitter_color_gradient",
        label="Color",
        default_stops=[
            (0.0, (0.008, 0.000, 1.000, 1.0)),
            (1.0 / 3.0, (0.002, 0.259, 1.000, 1.0)),
            (2.0 / 3.0, (0.265, 0.714, 1.000, 1.0)),
            (1.0, (1.000, 1.000, 1.000, 1.0)),
        ],
        theron_ids=("ID_NX_EMITTER_COLOR_GRADIENT",),
        sync_condition=lambda props, _orig: props.ID_NX_EMITTER_COLOR_MODE == "GRADIENT",
    ),
    GradientSpec(
        slot_name="emitter_noise_gradient",
        label="Gradient",
        default_stops=[
            (0.0, (1.0, 1.0, 1.0, 1.0)),
            (1.0, (0.0, 0.0, 0.0, 1.0)),
        ],
        theron_ids=("ID_NX_EMITTER_NOISE_GRADIENT",),
        sync_condition=lambda props, _orig: (
            props.ID_NX_EMITTER_COLOR_MODE == "NOISE"
            and props.ID_NX_EMITTER_NOISE_CHANNEL == "GRADIENT"
        ),
    ),
]


class NXEmitterModifier(NexusObject):
    object_type = "NX_EMITTER"
    object_name = "nxEmitter"
    object_label = "Emitter"
    object_description = "Particle emitter - source of particle birth"
    icon_name = "nx_emitter"
    category = "Emitters"
    menu_category = MenuCategory.EMITTER

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON
    gizmo_max_handles = 3
    cache_specs = (EMITTER_POLY_SPEC, EMITTER_LINE_SPEC)

    @classmethod
    def get_gradient_specs(cls):
        return _EMITTER_GRADIENT_SPECS

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        shape = props.ID_NX_EMITTER_SHAPE
        if shape == "RECT":
            return [
                HandleConfig(
                    Vector((1, 0, 0)),
                    "ID_NX_EMITTER_SHAPE_RECT_W",
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 0, 1)),
                    "ID_NX_EMITTER_SHAPE_RECT_H",
                    position_factor=0.5,
                    min_value=0.001,
                ),
            ]
        elif shape == "DISC":
            return [
                HandleConfig(Vector((1, 0, 0)), "ID_NX_EMITTER_SHAPE_RADIUS", min_value=0.001),
            ]
        elif shape == "SPHERE":
            return [
                HandleConfig(Vector((1, 0, 0)), "ID_NX_EMITTER_SHAPE_RADIUS", min_value=0.001),
            ]
        elif shape == "BOX":
            return [
                HandleConfig(
                    Vector((1, 0, 0)),
                    "emitter_shape_box_size",
                    prop_component=0,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 1, 0)),
                    "emitter_shape_box_size",
                    prop_component=1,
                    position_factor=0.5,
                    min_value=0.001,
                ),
                HandleConfig(
                    Vector((0, 0, 1)),
                    "emitter_shape_box_size",
                    prop_component=2,
                    position_factor=0.5,
                    min_value=0.001,
                ),
            ]
        return []

    @classmethod
    def get_gizmo_matrix(cls, obj, props):
        return obj.matrix_world @ _get_orientation_matrix(props.ID_NX_EMITTER_SHAPE_ROTATION)

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def draw_ui(cls, layout, data):
        # row = layout.row(align=True)
        # row.prop(data, "emitter_section", expand=True)

        # if data.emitter_section == "EMITTER":
        cls._draw_emitter_section(layout, data)
        # elif data.emitter_section == "INITIAL_STATE":
        # cls._draw_initial_state_section(layout, data)

    @classmethod
    def _draw_emitter_section(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        col.prop(data, "create_point_cloud")
        col.prop(data, "ID_NX_EMITTER_SUBFRAME_EMIT")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_EMITTER_SHAPE")

        if data.ID_NX_EMITTER_SHAPE != "OBJECT":
            col.prop(data, "ID_NX_EMITTER_SHAPE_ROTATION")

        if data.ID_NX_EMITTER_SHAPE == "RECT":
            col.prop(data, "ID_NX_EMITTER_SHAPE_RECT_W")
            col.prop(data, "ID_NX_EMITTER_SHAPE_RECT_H")
        elif data.ID_NX_EMITTER_SHAPE in ("DISC", "SPHERE"):
            col.prop(data, "ID_NX_EMITTER_SHAPE_RADIUS")
        elif data.ID_NX_EMITTER_SHAPE == "BOX":
            col.prop(data, "emitter_shape_box_size")
        elif data.ID_NX_EMITTER_SHAPE == "OBJECT":
            ui_config = get_emitter_ui_config()
            cls.draw_property(col, data, "emitter_objects", ui_config)

        if data.ID_NX_EMITTER_SHAPE in ("RECT", "DISC"):
            col.prop(data, "ID_NX_EMITTER_SHAPE_ANGLE")

        if data.ID_NX_EMITTER_SHAPE in ("SPHERE", "BOX"):
            col.prop(data, "ID_NX_EMITTER_DIRECTION")

        is_random = data.ID_NX_EMITTER_MODE == "RANDOM"
        if data.ID_NX_EMITTER_SHAPE == "RECT":
            row = col.row()
            row.enabled = is_random and not data.ID_NX_EMITTER_ORIGIN_ONLY
            row.prop(data, "ID_NX_EMITTER_EDGE_ONLY")
            row = col.row()
            row.enabled = is_random and not data.ID_NX_EMITTER_EDGE_ONLY
            row.prop(data, "ID_NX_EMITTER_ORIGIN_ONLY")
        elif data.ID_NX_EMITTER_SHAPE == "DISC":
            row = col.row()
            row.enabled = is_random and not data.ID_NX_EMITTER_ORIGIN_ONLY
            row.prop(data, "ID_NX_EMITTER_EDGE_ONLY")
            row = col.row()
            row.enabled = is_random and not data.ID_NX_EMITTER_EDGE_ONLY
            row.prop(data, "ID_NX_EMITTER_ORIGIN_ONLY")
        elif data.ID_NX_EMITTER_SHAPE in ("SPHERE", "BOX"):
            row = col.row()
            row.enabled = is_random
            row.prop(data, "ID_NX_EMITTER_SURFACE_ONLY")

        layout.separator(factor=0.5)

        # split = layout.split(factor=0.385)
        # split.column()
        # sub_row = split.row(align=True)
        # sub_row.prop(data, "emitter_tab", expand=True)

        # if data.emitter_tab == "EMISSION":
        cls._draw_emission_tab(layout, data)
        # elif data.emitter_tab == "MOTION_INHERITANCE":
        #     cls._draw_motion_inheritance_tab(layout, data)

    @classmethod
    def _draw_initial_state_section(cls, layout, data):
        col = layout.column()
        col.label(text="Not yet implemented")

    @classmethod
    def _draw_emission_tab(cls, layout, data):
        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_EMITTER_EMITTYPE")

        if data.ID_NX_EMITTER_EMITTYPE in ("RATE", "SHOT"):
            col.prop(data, "ID_NX_EMITTER_MODE", text="Mode")
            if data.ID_NX_EMITTER_MODE in ("REGULAR", "HEX"):
                col.prop(data, "ID_NX_EMITTER_SPACING")
                if data.ID_NX_EMITTER_SHAPE != "OBJECT":
                    count = _estimate_regular_emission_count(data)
                    split = col.split(factor=0.385)
                    split.label(text="")
                    info = split.row()
                    info.active = False
                    info.alignment = "RIGHT"
                    info.label(text=f"~{count:,} particles per emission")

        if data.ID_NX_EMITTER_EMITTYPE == "SHOT":
            col.separator(type="LINE")
            if data.ID_NX_EMITTER_MODE not in ("REGULAR", "HEX"):
                draw_rate_prop(col, data, "ID_NX_EMITTER_SHOT_COUNT")
            draw_time_prop(col, data, "ID_NX_EMITTER_SHOT_START")
            draw_time_prop(col, data, "ID_NX_EMITTER_SHOT_DURATION")
        elif data.ID_NX_EMITTER_EMITTYPE == "PULSE":
            col.separator(type="LINE")
            draw_time_prop(col, data, "ID_NX_EMITTER_PULSE_LENGTH")
            draw_time_prop(col, data, "ID_NX_EMITTER_PULSE_INTERVAL")

        if data.ID_NX_EMITTER_EMITTYPE != "SHOT" and data.ID_NX_EMITTER_MODE not in (
            "REGULAR",
            "HEX",
        ):
            col.separator(type="LINE")
            col.prop(data, "ID_NX_EMITTER_BIRTHRATE")
            col.prop(data, "ID_NX_EMITTER_BIRTHRATE_VAR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_EMITTER_SPEED")
        col.prop(data, "ID_NX_EMITTER_SPEED_VAR")
        col.prop(data, "ID_NX_EMITTER_RADIUS", text="Radius")
        col.prop(data, "ID_NX_EMITTER_RADIUS_VAR")
        col.prop(data, "ID_NX_EMITTER_MASS")
        col.prop(data, "ID_NX_EMITTER_MASS_VAR")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_EMITTER_EMIT_ALL")
        timing_col = col.column()
        timing_col.enabled = not data.ID_NX_EMITTER_EMIT_ALL
        draw_time_prop(timing_col, data, "ID_NX_EMITTER_EMIT_START")
        draw_time_prop(timing_col, data, "ID_NX_EMITTER_EMIT_END")

        col.separator(type="LINE")

        col.prop(data, "ID_NX_EMITTER_FULL_LIFETIME")
        life_col = col.column()
        life_col.enabled = not data.ID_NX_EMITTER_FULL_LIFETIME
        draw_time_prop(life_col, data, "ID_NX_EMITTER_LIFETIME")
        draw_time_prop(life_col, data, "ID_NX_EMITTER_LIFETIME_VAR")

    @classmethod
    def _draw_motion_inheritance_tab(cls, layout, data):
        col = layout.column()
        col.label(text="Not yet implemented", icon="INFO")

    @classmethod
    def post_sync(cls, obj, container, handle, props, scene, depsgraph=None, original_props=None):
        if props.ID_NX_EMITTER_SHAPE == "BOX":
            size = props.emitter_shape_box_size
            theron.set_vector(
                container,
                theron_ids.get("ID_NX_EMITTER_SHAPE_BOX_SIZE"),
                size[0],
                size[1],
                size[2],
            )

        if props.ID_NX_EMITTER_COLOR_MODE == "SINGLE":
            color = props.emitter_particle_color
            theron.set_vector(
                container,
                theron_ids.get("ID_NX_EMITTER_PARTICLE_COLOR"),
                float(color[0]),
                float(color[1]),
                float(color[2]),
            )

        if props.ID_NX_EMITTER_COLOR_MODE == "GRADIENT":
            if not props.ID_NX_EMITTER_GRADIENT_PARAMETER_AUTOSCALE:
                # Only length/speed parameters need m->cm conversion
                _LENGTH_GRAD_PARAMS = {
                    "SPEED",
                    "SPEED_WORLD",
                    "RADIUS",
                    "DISTANCE_TRAVELED",
                    "PP_DISTANCE",
                }
                grad_param = props.ID_NX_EMITTER_GRADIENT_PARAMETER
                scale = 100.0 if grad_param in _LENGTH_GRAD_PARAMS else 1.0
                grad_min = float(props.emitter_gradient_min) * scale
                grad_max = float(props.emitter_gradient_max) * scale
                if grad_max <= grad_min:
                    grad_max = grad_min + 1.0
                theron.set_float(
                    container,
                    theron_ids.get("ID_NX_EMITTER_GRADIENT_PARAMETER_MIN"),
                    grad_min,
                )
                theron.set_float(
                    container,
                    theron_ids.get("ID_NX_EMITTER_GRADIENT_PARAMETER_MAX"),
                    grad_max,
                )

        # Sync emitter groups
        col_src = original_props if original_props is not None else props
        groups = getattr(col_src, "emitter_groups", None)
        if groups is not None:
            from ..handlers import pipeline as pipeline_manager
            from ..pipeline_manager.identity import get_object_uid

            desired = {}
            for item in groups:
                if not item.enabled:
                    continue
                group_obj = item.obj
                if group_obj is None or group_obj.get("nexus_modifier_type") != "NX_GROUP":
                    continue
                group_handle = pipeline_manager.get_nexus_obj_handle(scene, group_obj)
                if group_handle is None:
                    continue
                group_uid = get_object_uid(group_obj)
                if group_uid is None:
                    continue
                desired[group_uid] = group_handle

            pipeline_manager.sync_emitter_group_memberships(scene, obj, handle, desired)

    @classmethod
    def post_execute_object(cls, obj, handle, props, _scene, *, depsgraph=None):

        from ..handlers.pipeline import get_pipeline
        from ..libs.theron import TrParticleProperty

        points_obj = None

        for child in obj.children:
            if child.get("nexus_object_type") == "NX_EMITTER_POINT_CLOUD":
                points_obj = child
                break

        if not props.create_point_cloud:
            if points_obj is not None:
                bpy.data.objects.remove(points_obj, do_unlink=True)
            return

        if points_obj is None:
            # Create new point cloud object as a mesh
            pointcloud_name = obj.name + "_PointCloud"
            mesh = bpy.data.meshes.new(pointcloud_name)
            points_obj = bpy.data.objects.new(pointcloud_name, mesh)
            bpy.context.collection.objects.link(points_obj)
            points_obj.parent = obj
            points_obj.matrix_parent_inverse = obj.matrix_world.inverted()
            points_obj["nexus_object_type"] = "NX_EMITTER_POINT_CLOUD"
        else:
            mesh = points_obj.data

        particle_count = theron.get_emitter_particle_count(handle)

        pos_ptr = theron.get_emitter_particle_data(
            handle, TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION
        )

        if particle_count == 0 or _is_ptr_null(pos_ptr):
            mesh.clear_geometry()
            return

        positions = _void_ptr_to_ndarray(pos_ptr, np.float32, (particle_count, 4))[:, :3].copy()

        # Rebuild mesh with new vertex positions
        mesh.clear_geometry()
        mesh.vertices.add(particle_count)

        dst = mesh.attributes["position"].data[0].as_pointer()
        ctypes.memmove(
            dst, positions.ctypes.data, len(positions) * np.dtype((np.float32, 3)).itemsize
        )

        _add_mesh_vertex_property(
            mesh, handle, particle_count, TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS
        )
        _add_mesh_vertex_property(
            mesh,
            handle,
            particle_count,
            TrParticleProperty.TR_PARTICLE_PROPERTY_COLOR,
            "FLOAT_COLOR",
        )
        _add_mesh_vertex_property(
            mesh, handle, particle_count, TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY
        )
        _add_mesh_vertex_property(
            mesh, handle, particle_count, TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION
        )

        mesh.update()

        # Create geom nodes to convert mesh vertices to point cloud
        _setup_point_cloud_geonodes(points_obj)

    @classmethod
    def get_tabs(cls, props):
        tabs = []
        if cls.should_show_display_section(props):
            tabs.append(("DISPLAY", "Display"))
        # tabs.append(("EXTENDED_DATA", "Extended Data"))
        tabs.append(("GROUPS", "Groups"))
        tabs.append(("MODIFIERS", "Modifiers"))
        return tabs

    @classmethod
    def draw_tab(cls, section_id, layout, props):
        col = layout.column()
        col.use_property_split = True

        if section_id == "DISPLAY":
            cls.draw_display_section(layout, props)
        # elif section_id == "EXTENDED_DATA":
        #     ui_config = get_emitter_extended_data_ui_config()
        #     cls.draw_property(col, props, "emitter_extended_data", ui_config)
        elif section_id == "GROUPS":
            cls.draw_groups_section(layout, props)
        elif section_id == "MODIFIERS":
            cls.draw_modifiers_section(layout, props)

    @classmethod
    def draw_display_section(cls, layout, data):
        """Display section: viewport emitter and particle draw options."""
        col = layout.column()
        col.use_property_split = True

        col.label(text="Viewport Emitter")
        col.prop(data, "visible_in_editor")

        col.label(text="Viewport Particles")
        col.prop(data, "emitter_show_particles")
        col.prop(data, "ID_NX_EMITTER_COLOR_MODE")

        if data.ID_NX_EMITTER_COLOR_MODE == "SINGLE":
            col.prop(data, "emitter_particle_color")
        elif data.ID_NX_EMITTER_COLOR_MODE == "GRADIENT":
            import bpy

            for obj in bpy.data.objects:
                if obj.get("nexus_modifier_type") == "NX_EMITTER":
                    gradient = NexusGradient(obj, "emitter_color_gradient")
                    gradient.draw_ui(col, "Color")
                    break
            col.prop(data, "ID_NX_EMITTER_GRADIENT_PARAMETER")
            col.prop(data, "ID_NX_EMITTER_GRADIENT_PARAMETER_AUTOSCALE")
            grad_range_col = col.column()
            grad_range_col.enabled = not data.ID_NX_EMITTER_GRADIENT_PARAMETER_AUTOSCALE
            grad_range_col.prop(data, "emitter_gradient_min")
            grad_range_col.prop(data, "emitter_gradient_max")
        elif data.ID_NX_EMITTER_COLOR_MODE == "NOISE":
            import bpy

            from ..utils.noise_preview import draw_noise_preview

            emitter_obj = None
            for obj in bpy.data.objects:
                if obj.get("nexus_modifier_type") == "NX_EMITTER":
                    emitter_obj = obj
                    break

            col.prop(data, "ID_NX_EMITTER_NOISE_TYPE")
            col.prop(data, "ID_NX_EMITTER_NOISE_CHANNEL")

            if data.ID_NX_EMITTER_NOISE_CHANNEL == "GRADIENT" and emitter_obj is not None:
                gradient = NexusGradient(emitter_obj, "emitter_noise_gradient")
                gradient.draw_ui(col, "Gradient")

            if emitter_obj is not None:
                draw_noise_preview(col, emitter_obj)

            col.separator(type="LINE")
            col.prop(data, "ID_NX_EMITTER_NOISE_SEED")
            col.separator(type="LINE")
            col.prop(data, "ID_NX_EMITTER_NOISE_SCALE")
            col.prop(data, "ID_NX_EMITTER_NOISE_PERSISTENCE")
            col.prop(data, "ID_NX_EMITTER_NOISE_LACUNARITY")
            col.prop(data, "ID_NX_EMITTER_NOISE_FREQUENCY")
            col.prop(data, "ID_NX_EMITTER_NOISE_OCTAVES")
            col.separator(type="LINE")
            col.prop(data, "ID_NX_EMITTER_NOISE_LOW_CLIP")
            col.prop(data, "ID_NX_EMITTER_NOISE_HIGH_CLIP")
            col.separator(type="LINE")
            col.prop(data, "ID_NX_EMITTER_NOISE_BRIGHTNESS")
            col.prop(data, "ID_NX_EMITTER_NOISE_CONTRAST")

        col.prop(data, "ID_NX_EMITTER_DISPLAY_MODE", text="Mode")

        if data.ID_NX_EMITTER_DISPLAY_MODE == "POINTS":
            col.prop(data, "emitter_particle_size")

        if data.ID_NX_EMITTER_DISPLAY_MODE in (
            "DIRECTION",
            "ARROW",
            "ARROW_FILLED",
        ):
            col.prop(data, "ID_NX_EMITTER_LINES_LENGTHMODE")
            if data.ID_NX_EMITTER_LINES_LENGTHMODE == "FIXED":
                col.prop(data, "ID_NX_EMITTER_LINES_FIXEDLENGTH")
            else:
                col.prop(data, "ID_NX_EMITTER_LINES_CLAMP")
                if data.ID_NX_EMITTER_LINES_CLAMP:
                    clamp_col = col.column(align=True)
                    clamp_col.prop(data, "ID_NX_EMITTER_LINES_MINLENGTH")
                    clamp_col.prop(data, "ID_NX_EMITTER_LINES_MAXLENGTH")

        if data.ID_NX_EMITTER_DISPLAY_MODE in (
            "BOX3D",
            "BOX3D_FILLED",
            "PYRAMID",
            "PYRAMID_FILLED",
            "ARROW",
            "ARROW_FILLED",
            "AXIS",
        ):
            col.separator(type="LINE")
            col.label(text="Particle Rotation")
            col.prop(data, "emitter_particle_rotation_mode")
            col.prop(data, "emitter_particle_up_vector")

        if data.ID_NX_EMITTER_DISPLAY_MODE == "SSF":
            col.separator(type="LINE")
            col.label(text="Screen-Space Fluid")
            col.prop(data, "emitter_ssf_preset")
            ssf_custom_col = col.column()
            ssf_custom_col.enabled = data.emitter_ssf_preset == "CUSTOM"
            ssf_custom_col.prop(data, "emitter_ssf_blur_iterations")
            ssf_custom_col.prop(data, "emitter_ssf_blur_radius")
            ssf_custom_col.prop(data, "emitter_ssf_blur_depth_falloff")
            ssf_custom_col.prop(data, "emitter_ssf_thickness_blur_iterations")
            ssf_custom_col.prop(data, "emitter_ssf_absorption")
            ssf_custom_col.prop(data, "emitter_ssf_fresnel_power")
            ssf_custom_col.prop(data, "emitter_ssf_use_anisotropy")
            aniso_col = ssf_custom_col.column()
            aniso_col.enabled = data.emitter_ssf_use_anisotropy
            aniso_col.prop(data, "emitter_ssf_anisotropy_scale")
            aniso_col.prop(data, "emitter_ssf_anisotropy_max_stretch")
            ssf_custom_col.prop(data, "emitter_ssf_min_alpha")
            ssf_custom_col.prop(data, "emitter_ssf_background_color")
        col.separator(type="LINE")
        cls._draw_display_constraints_section(col, data)

    @classmethod
    def _draw_display_constraints_section(cls, layout, data):
        """Header toggle + 2-column grid of 8 per-type constraint colour swatches."""
        header = layout.row(align=True)
        header.use_property_split = False
        header.prop(
            data,
            "display_constraints",
            text="Display Constraints",
            toggle=False,
        )

        body = layout.column(align=True)
        body.use_property_split = False
        body.enabled = bool(data.display_constraints)

        rows = (
            ("constraint_color_birth", "constraint_color_distance"),
            ("constraint_color_custom", "constraint_color_viscosity"),
        )
        for left, right in rows:
            row = body.row(align=True)
            row.prop(data, left)
            row.prop(data, right)

    @classmethod
    def draw_groups_section(cls, layout, data):
        from ..icons import get_icon
        from ..ui import draw_nodetree

        col = layout.column()
        col.use_property_split = True

        col.prop(data, "ID_NX_EMITTER_GROUP_MODE")

        draw_nodetree(
            layout,
            data,
            "emitter_groups",
            "emitter_groups_index",
            label="Groups",
            allowed_types=["NX_GROUP"],
            extra_operators=[
                {
                    "operator": "nexus.nodetree_create_and_add",
                    "icon": get_icon("nx_emitter_group"),
                    "text": "",
                    "properties": {
                        "list_prop": "emitter_groups",
                        "index_prop": "emitter_groups_index",
                        "modifier_type": "NX_GROUP",
                    },
                },
            ],
        )

    @classmethod
    def draw_modifiers_section(cls, layout, data):
        from ..ui import draw_nodetree

        col = layout.column()
        col.use_property_split = True

        draw_nodetree(
            layout,
            data,
            "emitter_modifier_objects",
            "emitter_modifier_objects_index",
            label="Modifiers",
            tree_type="inexclude",
        )

    @classmethod
    def _draw_rectangle(cls, shader, matrix: Matrix, width: float, height: float) -> None:
        half_w = width / 2.0
        half_h = height / 2.0
        corners = [
            Vector((-half_w, 0.0, -half_h)),
            Vector((half_w, 0.0, -half_h)),
            Vector((half_w, 0.0, half_h)),
            Vector((-half_w, 0.0, half_h)),
        ]
        coords = [matrix @ c for c in corners]
        lines = [
            (coords[0], coords[1]),
            (coords[1], coords[2]),
            (coords[2], coords[3]),
            (coords[3], coords[0]),
        ]
        draw_lines(shader, lines)

    @classmethod
    def _draw_rect_angle_spurs(
        cls, shader, matrix: Matrix, width: float, height: float, angle: float
    ) -> None:
        spur_length = 0.3
        half_w = width / 2.0
        half_h = height / 2.0
        corners = [
            Vector((-half_w, 0.0, -half_h)),
            Vector((half_w, 0.0, -half_h)),
            Vector((half_w, 0.0, half_h)),
            Vector((-half_w, 0.0, half_h)),
        ]
        up = Vector((0.0, 1.0, 0.0))
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        lines = []
        cone_verts = []
        for corner in corners:
            outward_xz = Vector((corner.x, 0.0, corner.z)).normalized()
            spur_dir = cos_a * up + sin_a * outward_xz
            spur_end = corner + spur_dir * spur_length
            lines.append((matrix @ corner, matrix @ spur_end))
            cls._append_cone_verts(cone_verts, matrix, spur_end, spur_dir.normalized())
        draw_lines(shader, lines)
        if cone_verts:
            batch = batch_for_shader(shader, "TRIS", {"pos": cone_verts})
            batch.draw(shader)

    @classmethod
    def _draw_circle_angle_spurs(cls, shader, matrix: Matrix, radius: float, angle: float) -> None:
        spur_length = 0.3
        cardinal_dirs = [
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
            Vector((-1.0, 0.0, 0.0)),
            Vector((0.0, 0.0, -1.0)),
        ]
        up = Vector((0.0, 1.0, 0.0))
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        lines = []
        cone_verts = []
        for direction in cardinal_dirs:
            point = direction * radius
            spur_dir = cos_a * up + sin_a * direction
            spur_end = point + spur_dir * spur_length
            lines.append((matrix @ point, matrix @ spur_end))
            cls._append_cone_verts(cone_verts, matrix, spur_end, spur_dir.normalized())
        draw_lines(shader, lines)
        if cone_verts:
            batch = batch_for_shader(shader, "TRIS", {"pos": cone_verts})
            batch.draw(shader)

    @staticmethod
    def _draw_bounding_box(shader, mx: Matrix, size: Vector) -> None:
        hx = size.x / 2.0
        hy = size.y / 2.0
        hz = size.z / 2.0

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
    def _append_cone_verts(
        verts,
        matrix,
        tip_local,
        direction_local,
        cone_length=0.06,
        cone_radius=0.015,
        segments=12,
    ):
        base_center = tip_local - direction_local * cone_length

        ref = Vector((0, 0, 1))
        if abs(direction_local.dot(ref)) > 0.99:
            ref = Vector((0, 1, 0))
        tangent = direction_local.cross(ref).normalized()
        bitangent = direction_local.cross(tangent).normalized()

        base_pts = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            pt = (
                base_center
                + math.cos(a) * cone_radius * tangent
                + math.sin(a) * cone_radius * bitangent
            )
            base_pts.append(pt)

        tip_world = matrix @ tip_local
        base_center_world = matrix @ base_center
        base_pts_world = [matrix @ p for p in base_pts]

        for i in range(segments):
            next_i = (i + 1) % segments
            verts.extend([tip_world, base_pts_world[i], base_pts_world[next_i]])
            verts.extend([base_center_world, base_pts_world[next_i], base_pts_world[i]])

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, _context) -> None:
        mx = obj.matrix_world @ _get_orientation_matrix(props.ID_NX_EMITTER_SHAPE_ROTATION)

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader.bind()

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(True)
        gpu.state.line_width_set(1.0)

        shader.uniform_float("color", XP_COLOR_MODS_BLUE)

        if props.ID_NX_EMITTER_SHAPE == "RECT":
            cls._draw_rectangle(
                shader, mx, props.ID_NX_EMITTER_SHAPE_RECT_W, props.ID_NX_EMITTER_SHAPE_RECT_H
            )
            shader.uniform_float("color", XP_COLOR_MODS_RED)
            cls._draw_rect_angle_spurs(
                shader,
                mx,
                props.ID_NX_EMITTER_SHAPE_RECT_W,
                props.ID_NX_EMITTER_SHAPE_RECT_H,
                props.ID_NX_EMITTER_SHAPE_ANGLE,
            )
        elif props.ID_NX_EMITTER_SHAPE == "DISC":
            draw_circle(shader, mx, props.ID_NX_EMITTER_SHAPE_RADIUS, plane="XZ")
            shader.uniform_float("color", XP_COLOR_MODS_RED)
            cls._draw_circle_angle_spurs(
                shader, mx, props.ID_NX_EMITTER_SHAPE_RADIUS, props.ID_NX_EMITTER_SHAPE_ANGLE
            )
        elif props.ID_NX_EMITTER_SHAPE == "SPHERE":
            draw_circle(shader, mx, props.ID_NX_EMITTER_SHAPE_RADIUS, plane="XZ")

            rot_z = mx @ Matrix.Rotation(math.pi / 2, 4, "Z")
            draw_circle(shader, rot_z, props.ID_NX_EMITTER_SHAPE_RADIUS, plane="XZ")

            rot_x = mx @ Matrix.Rotation(math.pi / 2, 4, "X")
            draw_circle(shader, rot_x, props.ID_NX_EMITTER_SHAPE_RADIUS, plane="XZ")

        elif props.ID_NX_EMITTER_SHAPE == "BOX":
            cls._draw_bounding_box(shader, mx, Vector(props.emitter_shape_box_size))

        gpu.state.line_width_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set("NONE")

    @classmethod
    def _draw_particles(cls, context, props) -> None:
        """Draw all particles from the simulation pipeline."""
        from ..handlers import pipeline as pipeline_manager
        from ..libs import theron

        if not theron.is_initialized():
            return

        pipeline = pipeline_manager.get_pipeline(context.scene)
        if pipeline is None:
            return

        count = theron.get_particle_count(pipeline)
        if count == 0:
            return

        positions = theron.get_all_particle_positions(pipeline)
        if not positions:
            return

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader.bind()

        color = tuple(props.emitter_particle_color)
        shader.uniform_float("color", color)

        pt_size = (
            props.emitter_particle_size if props.ID_NX_EMITTER_DISPLAY_MODE == "POINTS" else 1.0
        )
        gpu.state.point_size_set(pt_size)

        batch = batch_for_shader(shader, "POINTS", {"pos": positions})
        batch.draw(shader)

        gpu.state.point_size_set(1.0)
