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

"""Real-geometry export path for nxGenerator.

When ``export_real_geometry`` is on, the generator owns a hidden child Points
object that mirrors the simulation each frame. Each particle becomes a vertex
with per-instance attributes (layer index, scale, rotation, colour, seed) that
an Instance-on-Points geo-node tree consumes to materialise the instances.
"""

from __future__ import annotations

import ctypes

import bpy
import numpy as np

from ..libs import theron
from ..libs.theron import TrParticleProperty

NX_GEN_POINTS_TAG = "NX_GENERATOR_POINTS"
MAX_LAYERS = 16
ATTRS_NODE_GROUP_NAME = "NX_Generator_Attrs"
ATTRS_GN_NODE_GROUP_NAME = "NX_Generator_GN_Attrs"
STARTER_MATERIAL_NAME = "NX_Generator_Tint"


# ---------------------------------------------------------------------------
# PCG classifier (NumPy port of generator_classify.comp)
# ---------------------------------------------------------------------------


def _pcg_hash(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.uint32, copy=False)
    state = x * np.uint32(747796405) + np.uint32(2891336453)
    word = ((state >> ((state >> np.uint32(28)) + np.uint32(4))) ^ state) * np.uint32(277803737)
    return (word >> np.uint32(22)) ^ word


def _classify(pids: np.ndarray, cumulative: np.ndarray) -> np.ndarray:
    # ``searchsorted`` finds the first j where cumulative[j] >= r — equivalent
    # to the GLSL `if (r < layers[j].classifier.x) return j;` loop, with the
    # last layer pinned at 1.0 so out-of-range hashes still resolve.
    r = _pcg_hash(pids).astype(np.float32) / 4294967295.0
    return np.clip(np.searchsorted(cumulative, r, side="right"), 0, len(cumulative) - 1).astype(
        np.int32
    )


def _hash01(seeds: np.ndarray) -> np.ndarray:
    return _pcg_hash(seeds).astype(np.float32) / 4294967295.0


def _per_particle_jitter(pids: np.ndarray, salt_offset: int) -> np.ndarray:
    # Match the GLSL: hash01(pid * 11 + N) for N = salt_offset..salt_offset+2.
    a = _hash01(pids * np.uint32(11) + np.uint32(salt_offset))
    b = _hash01(pids * np.uint32(11) + np.uint32(salt_offset + 1))
    c = _hash01(pids * np.uint32(11) + np.uint32(salt_offset + 2))
    return np.stack([a, b, c], axis=-1) * 2.0 - 1.0


def _broadcast_jitter(j: np.ndarray, per_axis: bool) -> np.ndarray:
    if per_axis:
        return j
    return np.broadcast_to(j[:, 0:1], j.shape).copy()


def _euler_xyz_to_matrix(eulers: np.ndarray) -> np.ndarray:
    """Blender Euler XYZ -> 3x3 matrices, shape (N, 3, 3). M = Rz * Ry * Rx."""
    cx, sx = np.cos(eulers[:, 0]), np.sin(eulers[:, 0])
    cy, sy = np.cos(eulers[:, 1]), np.sin(eulers[:, 1])
    cz, sz = np.cos(eulers[:, 2]), np.sin(eulers[:, 2])
    n = eulers.shape[0]
    r = np.empty((n, 3, 3), dtype=np.float32)
    r[:, 0, 0] = cy * cz
    r[:, 0, 1] = sx * sy * cz - cx * sz
    r[:, 0, 2] = cx * sy * cz + sx * sz
    r[:, 1, 0] = cy * sz
    r[:, 1, 1] = sx * sy * sz + cx * cz
    r[:, 1, 2] = cx * sy * sz - sx * cz
    r[:, 2, 0] = -sy
    r[:, 2, 1] = sx * cy
    r[:, 2, 2] = cx * cy
    return r


def _matrix_to_euler_xyz(mats: np.ndarray) -> np.ndarray:
    """Inverse of the above. Handles the ±π/2 gimbal-lock case explicitly."""
    sy_neg = np.clip(mats[:, 2, 0], -1.0, 1.0)
    y = np.arcsin(-sy_neg)
    locked = np.abs(sy_neg) > 0.99999
    x = np.where(
        locked,
        np.arctan2(-mats[:, 1, 2], mats[:, 1, 1]),
        np.arctan2(mats[:, 2, 1], mats[:, 2, 2]),
    )
    z = np.where(
        locked,
        np.zeros_like(y),
        np.arctan2(mats[:, 1, 0], mats[:, 0, 0]),
    )
    return np.stack([x, y, z], axis=-1).astype(np.float32, copy=False)


def _particle_hpb_to_matrix(raw_hpb: np.ndarray) -> np.ndarray:
    """GPU shader's particle-rotation composition: Rz(raw.x) * Rx(raw.y) * Ry(raw.z).

    The shader's ``rot_x/y/z`` helpers are the transpose of the standard math
    rotation matrices (``rot_x(α) == Rx_std(-α)``) — same convention as
    ``basic_utils._rot_mats_hpb``. Building with negated angles in the
    standard convention gives the same matrix.
    """
    raw_hpb = -raw_hpb
    cx, sx = np.cos(raw_hpb[:, 1]), np.sin(raw_hpb[:, 1])
    cy, sy = np.cos(raw_hpb[:, 2]), np.sin(raw_hpb[:, 2])
    cz, sz = np.cos(raw_hpb[:, 0]), np.sin(raw_hpb[:, 0])
    n = raw_hpb.shape[0]
    # Rx * Ry first
    rxy = np.empty((n, 3, 3), dtype=np.float32)
    rxy[:, 0, 0] = cy
    rxy[:, 0, 1] = 0.0
    rxy[:, 0, 2] = sy
    rxy[:, 1, 0] = sx * sy
    rxy[:, 1, 1] = cx
    rxy[:, 1, 2] = -sx * cy
    rxy[:, 2, 0] = -cx * sy
    rxy[:, 2, 1] = sx
    rxy[:, 2, 2] = cx * cy
    # Rz * Rxy
    out = np.empty_like(rxy)
    out[:, 0, 0] = cz * rxy[:, 0, 0] - sz * rxy[:, 1, 0]
    out[:, 0, 1] = cz * rxy[:, 0, 1] - sz * rxy[:, 1, 1]
    out[:, 0, 2] = cz * rxy[:, 0, 2] - sz * rxy[:, 1, 2]
    out[:, 1, 0] = sz * rxy[:, 0, 0] + cz * rxy[:, 1, 0]
    out[:, 1, 1] = sz * rxy[:, 0, 1] + cz * rxy[:, 1, 1]
    out[:, 1, 2] = sz * rxy[:, 0, 2] + cz * rxy[:, 1, 2]
    out[:, 2] = rxy[:, 2]
    return out


# ---------------------------------------------------------------------------
# Layer descriptor (small CPU mirror of NexusGeneratorLayerItem)
# ---------------------------------------------------------------------------


def _expand_variation(layer_item, scalar_attr, axis_attrs, per_axis_attr):
    if bool(getattr(layer_item, per_axis_attr, False)):
        return (
            float(getattr(layer_item, axis_attrs[0], 0.0)) / 100.0,
            float(getattr(layer_item, axis_attrs[1], 0.0)) / 100.0,
            float(getattr(layer_item, axis_attrs[2], 0.0)) / 100.0,
        )
    v = float(getattr(layer_item, scalar_attr, 0.0)) / 100.0
    return (v, v, v)


class _LayerView:
    __slots__ = (
        "index",
        "mesh_obj",
        "instance_material",
        "spawn_chance",
        "scale_source",
        "color_source",
        "rotation_source",
        "custom_scale",
        "custom_color",
        "custom_rotation",
        "mesh_scale",
        "mesh_color",
        "mesh_rotation_euler",
        "scale_variation",
        "color_variation",
        "rotation_variation",
        "scale_variation_per_axis",
        "color_variation_per_axis",
        "rotation_variation_per_axis",
    )

    def __init__(self, index, layer_item):
        self.index = index
        self.mesh_obj = layer_item.obj
        self.instance_material = getattr(layer_item, "instance_material", None)
        self.spawn_chance = max(0.0, float(layer_item.spawn_chance))
        self.scale_source = str(layer_item.scale_source)
        self.color_source = str(layer_item.color_source)
        self.rotation_source = str(layer_item.rotation_source)
        if layer_item.custom_scale_per_axis:
            self.custom_scale = tuple(float(c) for c in layer_item.custom_scale)
        else:
            v = float(layer_item.custom_scale_uniform)
            self.custom_scale = (v, v, v)
        self.custom_color = tuple(float(c) for c in layer_item.custom_color)
        if layer_item.custom_rotation_per_axis:
            self.custom_rotation = tuple(float(c) for c in layer_item.custom_rotation)
        else:
            v = float(layer_item.custom_rotation_uniform)
            self.custom_rotation = (v, v, v)
        mesh_obj = layer_item.obj
        if mesh_obj is not None:
            _, rot_quat, scale_v = mesh_obj.matrix_world.decompose()
            euler = rot_quat.to_euler("XYZ")
            self.mesh_scale = (float(scale_v.x), float(scale_v.y), float(scale_v.z))
            self.mesh_color = tuple(float(c) for c in mesh_obj.color)
            self.mesh_rotation_euler = (float(euler.x), float(euler.y), float(euler.z))
        else:
            self.mesh_scale = (1.0, 1.0, 1.0)
            self.mesh_color = (1.0, 1.0, 1.0, 1.0)
            self.mesh_rotation_euler = (0.0, 0.0, 0.0)
        self.scale_variation = _expand_variation(
            layer_item,
            "scale_variation",
            ("scale_variation_x", "scale_variation_y", "scale_variation_z"),
            "scale_variation_per_axis",
        )
        self.color_variation = _expand_variation(
            layer_item,
            "color_variation",
            ("color_variation_r", "color_variation_g", "color_variation_b"),
            "color_variation_per_axis",
        )
        self.rotation_variation = _expand_variation(
            layer_item,
            "rotation_variation",
            ("rotation_variation_x", "rotation_variation_y", "rotation_variation_z"),
            "rotation_variation_per_axis",
        )
        self.scale_variation_per_axis = bool(
            getattr(layer_item, "scale_variation_per_axis", False)
        )
        self.color_variation_per_axis = bool(
            getattr(layer_item, "color_variation_per_axis", False)
        )
        self.rotation_variation_per_axis = bool(
            getattr(layer_item, "rotation_variation_per_axis", False)
        )


def _collect_layer_views(props) -> list[_LayerView]:
    out = []
    for i, layer in enumerate(props.generator_layers):
        if not layer.enabled:
            continue
        if layer.obj is None or layer.obj.type != "MESH":
            continue
        out.append(_LayerView(i, layer))
        if len(out) >= MAX_LAYERS:
            break
    return out


def _cumulative_weights(layers: list[_LayerView]) -> np.ndarray:
    if not layers:
        return np.empty(0, dtype=np.float32)
    weights = np.asarray([layer.spawn_chance for layer in layers], dtype=np.float64)
    total = weights.sum()
    if total <= 0.0:
        weights = np.full(len(layers), 1.0 / len(layers), dtype=np.float64)
    else:
        weights = weights / total
    cumulative = np.cumsum(weights).astype(np.float32)
    cumulative[-1] = 1.0
    return cumulative


# ---------------------------------------------------------------------------
# Child Points object lifecycle
# ---------------------------------------------------------------------------


def _points_child_name(obj) -> str:
    return f"{obj.name}_NX_GEN_POINTS"


def _find_points_child(obj):
    for child in obj.children:
        if child.get("nexus_object_type") == NX_GEN_POINTS_TAG:
            return child
    return None


def _ensure_points_child(obj):
    points_obj = _find_points_child(obj)
    if points_obj is not None:
        return points_obj
    name = _points_child_name(obj)
    mesh = bpy.data.meshes.new(name)
    points_obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(points_obj)
    points_obj.parent = obj
    points_obj.matrix_parent_inverse = obj.matrix_world.inverted()
    points_obj["nexus_object_type"] = NX_GEN_POINTS_TAG
    points_obj.hide_select = True
    return points_obj


def _remove_points_child(obj) -> None:
    points_obj = _find_points_child(obj)
    if points_obj is not None:
        mesh = points_obj.data
        bpy.data.objects.remove(points_obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


# ---------------------------------------------------------------------------
# Shader node group + starter material (utility for the user's materials)
# ---------------------------------------------------------------------------


def ensure_attrs_node_group():
    """Return the ``NX_Generator_Attrs`` shader node group, creating it if missing.

    Outputs Colour / Scale / Rotation / Seed / Layer Index pulled from the
    Instancer-domain attributes the real-geo path writes. Users append this
    group into any of their materials to get one-node access to the data.
    """
    ng = bpy.data.node_groups.get(ATTRS_NODE_GROUP_NAME)
    if ng is not None and ng.bl_idname == "ShaderNodeTree":
        return ng

    ng = bpy.data.node_groups.new(ATTRS_NODE_GROUP_NAME, "ShaderNodeTree")
    iface = ng.interface
    iface.new_socket("Colour", in_out="OUTPUT", socket_type="NodeSocketColor")
    iface.new_socket("Scale", in_out="OUTPUT", socket_type="NodeSocketVector")
    iface.new_socket("Rotation", in_out="OUTPUT", socket_type="NodeSocketVector")
    iface.new_socket("Seed", in_out="OUTPUT", socket_type="NodeSocketFloat")
    iface.new_socket("Layer Index", in_out="OUTPUT", socket_type="NodeSocketFloat")

    nodes = ng.nodes
    links = ng.links
    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (300, 0)

    def _attr(name, location):
        node = nodes.new("ShaderNodeAttribute")
        node.attribute_type = "INSTANCER"
        node.attribute_name = name
        node.location = location
        return node

    links.new(_attr("nx_color", (-200, 200)).outputs["Color"], output_node.inputs["Colour"])
    links.new(_attr("nx_scale", (-200, 80)).outputs["Vector"], output_node.inputs["Scale"])
    links.new(_attr("nx_rotation", (-200, -40)).outputs["Vector"], output_node.inputs["Rotation"])
    links.new(_attr("nx_seed", (-200, -160)).outputs["Fac"], output_node.inputs["Seed"])
    links.new(
        _attr("nx_layer_index", (-200, -280)).outputs["Fac"],
        output_node.inputs["Layer Index"],
    )
    return ng


def ensure_attrs_gn_node_group():
    """Geometry-nodes twin of NX_Generator_Attrs — field outputs only."""
    ng = bpy.data.node_groups.get(ATTRS_GN_NODE_GROUP_NAME)
    if ng is not None and ng.bl_idname == "GeometryNodeTree":
        return ng

    ng = bpy.data.node_groups.new(ATTRS_GN_NODE_GROUP_NAME, "GeometryNodeTree")
    iface = ng.interface
    iface.new_socket("Colour", in_out="OUTPUT", socket_type="NodeSocketColor")
    iface.new_socket("Scale", in_out="OUTPUT", socket_type="NodeSocketVector")
    iface.new_socket("Rotation", in_out="OUTPUT", socket_type="NodeSocketVector")
    iface.new_socket("Seed", in_out="OUTPUT", socket_type="NodeSocketInt")
    iface.new_socket("Layer Index", in_out="OUTPUT", socket_type="NodeSocketInt")

    nodes = ng.nodes
    links = ng.links
    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (300, 0)

    def _attr(name, data_type, location):
        node = nodes.new("GeometryNodeInputNamedAttribute")
        node.data_type = data_type
        node.inputs["Name"].default_value = name
        node.location = location
        return node

    links.new(
        _named_attr_output(_attr("nx_color", "FLOAT_COLOR", (-200, 200))),
        output_node.inputs["Colour"],
    )
    links.new(
        _named_attr_output(_attr("nx_scale", "FLOAT_VECTOR", (-200, 80))),
        output_node.inputs["Scale"],
    )
    links.new(
        _named_attr_output(_attr("nx_rotation", "FLOAT_VECTOR", (-200, -40))),
        output_node.inputs["Rotation"],
    )
    links.new(
        _named_attr_output(_attr("nx_seed", "INT", (-200, -160))),
        output_node.inputs["Seed"],
    )
    links.new(
        _named_attr_output(_attr("nx_layer_index", "INT", (-200, -280))),
        output_node.inputs["Layer Index"],
    )
    return ng


def create_starter_material(viewport_color=(0.8, 0.8, 0.8, 1.0)):
    """Return a new material with NX_Generator_Attrs wired to Base Color.

    ``viewport_color`` becomes ``material.diffuse_color`` so Solid-mode
    viewport (which can't read instance shader attributes) shows a sensible
    flat tint instead of the default grey.
    """
    mat = bpy.data.materials.new(STARTER_MATERIAL_NAME)
    mat.use_nodes = True
    mat.diffuse_color = tuple(viewport_color)
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")

    attrs = nodes.new("ShaderNodeGroup")
    attrs.node_tree = ensure_attrs_node_group()
    attrs.location = (-300, 200)

    links.new(attrs.outputs["Colour"], bsdf.inputs["Base Color"])
    return mat


# ---------------------------------------------------------------------------
# Geometry-nodes tree (Instance-on-Points per enabled layer)
# ---------------------------------------------------------------------------

GN_MODIFIER_NAME = "NX_Generator_GN"
GN_SIGNATURE_TAG = "nx_generator_gn_signature"

# GeometryNodeInputNamedAttribute exposes one output per data type, all named
# "Attribute". outputs["Attribute"] resolves to the first match (Float), so we
# pick by identifier instead.
_NAMED_ATTR_OUTPUT_IDENT = {
    "FLOAT": "Attribute_Float",
    "INT": "Attribute_Int",
    "FLOAT_VECTOR": "Attribute_Vector",
    "FLOAT_COLOR": "Attribute_Color",
    "BOOLEAN": "Attribute_Bool",
    "QUATERNION": "Attribute_Quaternion",
}


def _named_attr_output(node):
    ident = _NAMED_ATTR_OUTPUT_IDENT.get(node.data_type, "Attribute_Float")
    for output in node.outputs:
        if output.identifier == ident:
            return output
    return node.outputs[0]


def _layer_signature(layers) -> str:
    # (layer_index, source_mesh_name, instance_material_name) per enabled
    # layer — captures everything that affects the tree's topology so we
    # only rebuild when something structural changes. Stored as a single
    # string because Blender ID-property arrays don't allow mixed types.
    return repr(
        [
            (
                int(layer.index),
                layer.mesh_obj.name,
                layer.instance_material.name if layer.instance_material else "",
            )
            for layer in layers
        ]
    )


def _read_stored_signature(obj) -> str:
    return str(obj.get(GN_SIGNATURE_TAG, ""))


def _clear_tree(tree) -> None:
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    for item in list(tree.interface.items_tree):
        tree.interface.remove(item)


def _build_tree(tree, layers) -> None:
    _clear_tree(tree)
    iface = tree.interface
    iface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    iface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = tree.nodes
    links = tree.links

    input_node = nodes.new("NodeGroupInput")
    input_node.location = (-400, 0)
    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (1200, 0)

    if not layers:
        links.new(input_node.outputs["Geometry"], output_node.inputs["Geometry"])
        return

    join = nodes.new("GeometryNodeJoinGeometry")
    join.location = (1000, 0)
    links.new(join.outputs["Geometry"], output_node.inputs["Geometry"])

    row_height = 320
    for slot, layer in enumerate(layers):
        y = -row_height * slot

        layer_attr = nodes.new("GeometryNodeInputNamedAttribute")
        layer_attr.data_type = "INT"
        layer_attr.inputs["Name"].default_value = "nx_layer_index"
        layer_attr.location = (-200, y - 80)

        # FLOAT compare with a generous epsilon — Blender auto-casts the
        # INT-typed `nx_layer_index` to float when wired into a FLOAT input,
        # which avoids needing the type-conditional A/B socket indices on
        # an INT-mode Compare.
        compare = nodes.new("FunctionNodeCompare")
        compare.data_type = "FLOAT"
        compare.operation = "EQUAL"
        compare.location = (0, y - 80)
        compare.inputs["B"].default_value = float(layer.index)
        compare.inputs["Epsilon"].default_value = 0.5
        links.new(_named_attr_output(layer_attr), compare.inputs["A"])

        sep = nodes.new("GeometryNodeSeparateGeometry")
        sep.domain = "POINT"
        sep.location = (200, y)
        links.new(input_node.outputs["Geometry"], sep.inputs["Geometry"])
        links.new(compare.outputs["Result"], sep.inputs["Selection"])

        obj_info = nodes.new("GeometryNodeObjectInfo")
        # ORIGINAL = raw local-space geometry. RELATIVE would bake in the
        # source's world transform and additionally offset every instance.
        obj_info.transform_space = "ORIGINAL"
        obj_info.location = (400, y - 200)
        obj_info.inputs["Object"].default_value = layer.mesh_obj

        scale_attr = nodes.new("GeometryNodeInputNamedAttribute")
        scale_attr.data_type = "FLOAT_VECTOR"
        scale_attr.inputs["Name"].default_value = "nx_scale"
        scale_attr.location = (400, y - 360)

        rot_attr = nodes.new("GeometryNodeInputNamedAttribute")
        rot_attr.data_type = "FLOAT_VECTOR"
        rot_attr.inputs["Name"].default_value = "nx_rotation"
        rot_attr.location = (400, y - 460)

        iop = nodes.new("GeometryNodeInstanceOnPoints")
        iop.location = (700, y)
        links.new(sep.outputs["Selection"], iop.inputs["Points"])
        links.new(obj_info.outputs["Geometry"], iop.inputs["Instance"])
        links.new(_named_attr_output(scale_attr), iop.inputs["Scale"])
        links.new(_named_attr_output(rot_attr), iop.inputs["Rotation"])

        # IoP auto-propagates per-point attributes (nx_color etc.) onto the
        # instance domain, so the source mesh's material can read them via a
        # shader Attribute(Instancer) node without an explicit Store step.
        tail = iop.outputs["Instances"]
        if layer.instance_material is not None:
            set_mat = nodes.new("GeometryNodeSetMaterial")
            set_mat.location = (1080, y)
            set_mat.inputs["Material"].default_value = layer.instance_material
            links.new(tail, set_mat.inputs["Geometry"])
            tail = set_mat.outputs["Geometry"]

        links.new(tail, join.inputs["Geometry"])


def _ensure_gn_tree(generator_obj, points_obj, layers) -> None:
    mod = points_obj.modifiers.get(GN_MODIFIER_NAME)
    if mod is None:
        mod = points_obj.modifiers.new(GN_MODIFIER_NAME, "NODES")

    tree = mod.node_group
    if tree is None:
        name = f"{generator_obj.name}_NX_GN"
        tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
        mod.node_group = tree

    new_sig = _layer_signature(layers)
    if new_sig == _read_stored_signature(generator_obj) and tree.nodes:
        return

    _build_tree(tree, layers)
    generator_obj[GN_SIGNATURE_TAG] = new_sig


def _remove_gn_tree(generator_obj) -> None:
    points_obj = _find_points_child(generator_obj)
    if points_obj is not None:
        mod = points_obj.modifiers.get(GN_MODIFIER_NAME)
        if mod is not None and mod.node_group is not None:
            tree = mod.node_group
            mod.node_group = None
            if tree.users == 0:
                bpy.data.node_groups.remove(tree)
    generator_obj[GN_SIGNATURE_TAG] = ""


# ---------------------------------------------------------------------------
# Per-frame attribute population
# ---------------------------------------------------------------------------


_ATTR_SPEC = (
    # (name, blender_type, domain, numpy_shape_per_point, numpy_dtype)
    ("nx_layer_index", "INT", "POINT", (), np.int32),
    ("nx_scale", "FLOAT_VECTOR", "POINT", (3,), np.float32),
    ("nx_rotation", "FLOAT_VECTOR", "POINT", (3,), np.float32),
    ("nx_color", "FLOAT_COLOR", "POINT", (4,), np.float32),
    ("nx_seed", "INT", "POINT", (), np.int32),
)


def _ensure_attribute(mesh, name, btype, domain):
    attr = mesh.attributes.get(name)
    if attr is None or attr.data_type != btype or attr.domain != domain:
        if attr is not None:
            mesh.attributes.remove(attr)
        mesh.attributes.new(name=name, type=btype, domain=domain)


def _memmove_attribute(mesh, name, ndarray: np.ndarray) -> None:
    attr = mesh.attributes[name]
    if len(attr.data) == 0:
        return
    dst = attr.data[0].as_pointer()
    src = np.ascontiguousarray(ndarray).ctypes.data
    ctypes.memmove(dst, src, ndarray.nbytes)


def _fetch_particle_property(pipeline_handle, prop):
    result = theron.get_particle_property_for_gpu(pipeline_handle, int(prop))
    if result is None:
        return None
    arr, _count = result
    return arr


def _populate_points(
    points_obj,
    pipeline_handle: int,
    layers: list[_LayerView],
    emitter_filter_mask: int = 0,
) -> None:
    mesh = points_obj.data
    P = TrParticleProperty
    pos = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_POSITION)
    pids_view = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_ID)
    if pos is None or pids_view is None or pos.shape[0] == 0:
        mesh.clear_geometry()
        return

    count = pos.shape[0]
    pids = np.asarray(pids_view, dtype=np.uint32)
    if pids.shape[0] != count:
        mesh.clear_geometry()
        return

    emit_view = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_EMITTER_INDEX)
    if emit_view is None or emit_view.shape[0] != count:
        mesh.clear_geometry()
        return
    emit_idx = np.asarray(emit_view, dtype=np.int32)
    valid = (emit_idx >= 0) & (emit_idx < 32)
    keep_mask = np.zeros(count, dtype=np.bool_)
    keep_mask[valid] = ((emitter_filter_mask >> emit_idx[valid].astype(np.int64)) & 1) != 0
    if not keep_mask.any():
        mesh.clear_geometry()
        return

    radii = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_RADIUS)
    scales_buf = None  # PER_PARTICLE_SCALE isn't exposed CPU-side.
    colors = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_COLOR)
    rotations = _fetch_particle_property(pipeline_handle, P.TR_PARTICLE_PROPERTY_ROTATION)

    pos = pos[keep_mask]
    pids = pids[keep_mask]
    if radii is not None:
        radii = np.asarray(radii)[keep_mask]
    if colors is not None:
        colors = np.asarray(colors)[keep_mask]
    if rotations is not None:
        rotations = np.asarray(rotations)[keep_mask]
    count = int(pos.shape[0])

    cumulative = _cumulative_weights(layers)
    if cumulative.size == 0:
        mesh.clear_geometry()
        return
    layer_idx = _classify(pids, cumulative)

    scale_out = np.empty((count, 3), dtype=np.float32)
    color_out = np.empty((count, 4), dtype=np.float32)
    color_out[:, 3] = 1.0
    # Accumulate rotation as 3x3 matrices so jitter*base composes correctly,
    # then convert the whole batch to Blender Euler XYZ at the end.
    base_rot_mat = np.empty((count, 3, 3), dtype=np.float32)

    # Per-particle jitter, salt offsets match the GLSL helper (pid*11+1..9).
    j_scale = _per_particle_jitter(pids, 1)
    j_color = _per_particle_jitter(pids, 4)
    j_rot = _per_particle_jitter(pids, 7)

    for li, layer in enumerate(layers):
        mask = layer_idx == li
        if not np.any(mask):
            continue
        # ---- Scale (base + variation) -------------------------------------
        s_src = layer.scale_source
        if s_src == "PARTICLE_RADIUS" and radii is not None:
            r = np.asarray(radii, dtype=np.float32)[mask]
            scale_out[mask] = r[:, None]
        elif s_src == "PARTICLE_SCALE" and scales_buf is not None:
            scale_out[mask] = scales_buf[mask]
        elif s_src == "CUSTOM":
            scale_out[mask] = layer.custom_scale
        else:  # MESH
            scale_out[mask] = layer.mesh_scale
        s_var = np.asarray(layer.scale_variation, dtype=np.float32)
        if np.any(s_var > 0.0):
            js = _broadcast_jitter(j_scale[mask], layer.scale_variation_per_axis)
            scale_out[mask] *= 1.0 + js * s_var

        # ---- Colour (base + variation) ------------------------------------
        c_src = layer.color_source
        if c_src == "PARTICLE" and colors is not None:
            color_out[mask, :3] = np.asarray(colors, dtype=np.float32)[mask]
        elif c_src == "CUSTOM":
            color_out[mask] = layer.custom_color
        else:  # MESH
            color_out[mask] = layer.mesh_color
        c_var = np.asarray(layer.color_variation, dtype=np.float32)
        if np.any(c_var > 0.0):
            jc = _broadcast_jitter(j_color[mask], layer.color_variation_per_axis)
            color_out[mask, :3] = np.clip(color_out[mask, :3] + jc * c_var, 0.0, 1.0)

        r_src = layer.rotation_source
        if r_src == "PARTICLE" and rotations is not None:
            raw = np.ascontiguousarray(np.asarray(rotations, dtype=np.float32)[mask])
            base_rot_mat[mask] = _particle_hpb_to_matrix(raw)
        elif r_src == "CUSTOM":
            base_rot_mat[mask] = _euler_xyz_to_matrix(
                np.broadcast_to(
                    -np.asarray(layer.custom_rotation, dtype=np.float32),
                    (int(mask.sum()), 3),
                ).copy()
            )
        else:  # MESH
            base_rot_mat[mask] = _euler_xyz_to_matrix(
                np.broadcast_to(
                    np.asarray(layer.mesh_rotation_euler, dtype=np.float32),
                    (int(mask.sum()), 3),
                ).copy()
            )
        r_var = np.asarray(layer.rotation_variation, dtype=np.float32)
        if np.any(r_var > 0.0):
            jr = _broadcast_jitter(j_rot[mask], layer.rotation_variation_per_axis)
            # Jitter uses the same shader helpers — negate to match.
            jitter_euler = -(jr * (r_var * (2.0 * np.pi)))
            jitter_mat = _euler_xyz_to_matrix(np.ascontiguousarray(jitter_euler))
            base_rot_mat[mask] = jitter_mat @ base_rot_mat[mask]

    rotation_out = _matrix_to_euler_xyz(base_rot_mat)

    mesh.clear_geometry()
    mesh.vertices.add(count)

    pos_np = np.ascontiguousarray(pos[:, :3], dtype=np.float32)
    pos_dst = mesh.attributes["position"].data[0].as_pointer()
    ctypes.memmove(pos_dst, pos_np.ctypes.data, pos_np.nbytes)

    for name, btype, domain, _shape, _dt in _ATTR_SPEC:
        _ensure_attribute(mesh, name, btype, domain)

    _memmove_attribute(mesh, "nx_layer_index", layer_idx)
    _memmove_attribute(mesh, "nx_scale", scale_out)
    _memmove_attribute(mesh, "nx_rotation", rotation_out)
    _memmove_attribute(mesh, "nx_color", color_out)
    _memmove_attribute(mesh, "nx_seed", pids.astype(np.int32))

    mesh.update()


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def ensure_realgeo_setup(obj, props) -> None:
    """Toggle ON: create the child Points object and build GN tree."""
    ensure_attrs_node_group()
    ensure_attrs_gn_node_group()
    layers = _collect_layer_views(props)
    points_obj = _ensure_points_child(obj)
    _ensure_gn_tree(obj, points_obj, layers)


def teardown_realgeo(obj, props) -> None:
    """Toggle OFF: remove the child Points object + GN tree."""
    _remove_gn_tree(obj)
    _remove_points_child(obj)


def refresh_realgeo(obj, props, pipeline_handle: int) -> None:
    """Per-frame: populate attributes; rebuild GN tree if the layer set changed."""
    points_obj = _ensure_points_child(obj)
    layers = _collect_layer_views(props)
    if not layers:
        points_obj.data.clear_geometry()
        _ensure_gn_tree(obj, points_obj, layers)
        return
    _ensure_gn_tree(obj, points_obj, layers)
    from ..properties.nx_generator import compute_emitter_filter_mask

    scene = bpy.context.scene
    emitter_filter_mask = compute_emitter_filter_mask(scene, obj) if scene is not None else 0
    _populate_points(points_obj, pipeline_handle, layers, emitter_filter_mask=emitter_filter_mask)


def clear_points_geometry(obj) -> None:
    """on_disable hook: leave the child object in place but empty its data."""
    points_obj = _find_points_child(obj)
    if points_obj is not None and points_obj.data is not None:
        points_obj.data.clear_geometry()


def cleanup_orphaned_points() -> None:
    """Sweep child Points objects whose parent generator no longer exists."""
    orphans = [
        o
        for o in bpy.data.objects
        if o.get("nexus_object_type") == NX_GEN_POINTS_TAG
        and (o.parent is None or o.parent.name not in bpy.data.objects)
    ]
    for o in orphans:
        mesh = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
