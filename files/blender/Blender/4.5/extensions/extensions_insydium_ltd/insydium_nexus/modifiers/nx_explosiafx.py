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
from typing import Tuple

import bpy
import gpu
import numpy as np
from mathutils import Vector

from ..libs.theron_sync import TRANSFORM_FACTORS, Transform
from ..properties.nx_explosiafx import (
    EXPLOSIAFX_FORCE_DATAMAP_CURVE_SPECS,
    SPEC,
    get_explosiafx_ui_config,
)
from ..utils import (
    XP_COLOR_MODS_BLUE,
    XP_COLOR_MODS_RED,
    draw_lines,
    draw_thick_lines,
)
from ..utils.gradient import GradientSpec, NexusGradient
from .base import MenuCategory, NexusModifier, UIFlags

XP_COLOR_GRID = (0.5, 0.7, 0.9, 0.4)

EFX_GRADIENT_SPECS = [
    GradientSpec(
        slot_name="explosiafx_display_velocity_speed_color",
        label="Speed Color",
        default_stops=[
            (0.0, (0.0, 0.0, 1.0, 1.0)),
            (0.25, (0.0, 1.0, 1.0, 1.0)),
            (0.5, (0.0, 1.0, 0.0, 1.0)),
            (0.75, (1.0, 1.0, 0.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_velocity_speed_alpha",
        label="Speed Alpha",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.2, (0.8, 0.8, 0.8, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_speed_color",
        label="Speed Color",
        default_stops=[
            (0.0, (0.0, 1.0, 0.0, 1.0)),
            (0.5, (1.0, 1.0, 0.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_speed_alpha",
        label="Speed Alpha",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.25, (0.019606, 0.019606, 0.019606, 1.0)),  # sRGB 0.15 -> linear
            (0.5, (0.0432, 0.0432, 0.0432, 1.0)),  # sRGB 0.23 -> linear
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_smoke_color",
        label="Smoke Color",
        default_stops=[
            (0.0, (1.0, 1.0, 1.0, 1.0)),
            (0.01, (1.0, 1.0, 1.0, 1.0)),
            (0.25, (0.0, 0.0, 0.0, 1.0)),
            (1.0, (0.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_smoke_alpha",
        label="Smoke Alpha",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.05, (0.0, 0.0, 0.0, 1.0)),
            (0.5, (0.492, 0.492, 0.492, 1.0)),  # sRGB 0.73 -> linear
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_fuel_color",
        label="Fuel Color",
        default_stops=[
            (0.0, (0.0, 0.0, 1.0, 1.0)),
            (0.25, (0.0, 1.0, 1.0, 1.0)),
            (0.5, (0.0, 1.0, 0.0, 1.0)),
            (0.75, (1.0, 1.0, 0.0, 1.0)),
            (1.0, (1.0, 0.0, 0.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_fuel_alpha",
        label="Fuel Alpha",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.25, (0.004, 0.004, 0.004, 1.0)),  # sRGB 0.05 -> linear
            (0.7, (0.073, 0.073, 0.073, 1.0)),  # sRGB 0.30 -> linear
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_temp_color",
        label="Temperature Color",
        default_stops=[
            (0.13, (0.0, 0.0, 0.0, 1.0)),
            (0.39, (1.0, 0.014, 0.0, 1.0)),
            (0.62, (1.0, 1.0, 0.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
    GradientSpec(
        slot_name="explosiafx_display_slicer_temp_alpha",
        label="Temperature Opacity",
        default_stops=[
            (0.0, (0.0, 0.0, 0.0, 1.0)),
            (0.3, (0.0, 0.0, 0.0, 1.0)),
            (0.8, (1.0, 1.0, 1.0, 1.0)),
            (1.0, (1.0, 1.0, 1.0, 1.0)),
        ],
    ),
]

_EXPLOSIAFX_SOURCEMESH_EMIT_ENUM_MAP = {
    "VOLUME": "ID_NX_EXPLOSIAFX_SOURCEMESH_EMIT_VOLUME",
    "SURFACE": "ID_NX_EXPLOSIAFX_SOURCEMESH_EMIT_SURFACE",
}

_EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP = {
    "SET": "ID_NX_EXPLOSIAFX_SOURCE_MODE_SET",
    "BLEND": "ID_NX_EXPLOSIAFX_SOURCE_MODE_BLEND",
    "ADDRATE": "ID_NX_EXPLOSIAFX_SOURCE_MODE_ADDRATE",
    "SUBRATE": "ID_NX_EXPLOSIAFX_SOURCE_MODE_SUBTRACTRATE",
}

_EXPLOSIAFX_SOURCEMESH_EMIT_WEIGHT_ENUM_MAP = {
    "VERTEX_GROUP": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_WEIGHTS",
    "ATTRIBUTE": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_WEIGHTS",
    "COLOR_ATTRIBUTE": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_WEIGHTS",
    "TEXTURE": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_WEIGHTS",
    "NOISE": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_NOISE",
    "NONE": "ID_NX_EXPLOSIAFX_SOURCEMESH_CUSTOM_NONE",
}

# Channel WEIGHTBY values that require an external per-vertex weight buffer.
# NOISE and NONE do not use custom weights.
_EXPLOSIAFX_EXTERNAL_WEIGHT_MODES = frozenset(
    {"VERTEX_GROUP", "ATTRIBUTE", "COLOR_ATTRIBUTE", "TEXTURE"}
)

_EXPLOSIAFX_SOURCEMESH_VELOCITY_TYPE_MAP = {
    "OBJMOTION": "ID_NX_EXPLOSIAFX_SOURCE_VELOCITY_TYPE_OBJECT",
    "MESHPERP": "ID_NX_EXPLOSIAFX_SOURCE_VELOCITY_TYPE_NORMAL",
    "CUSTOM": "ID_NX_EXPLOSIAFX_SOURCE_VELOCITY_TYPE_CUSTOM",
}

_EXPLOSIAFX_SOURCEMESH_COLOR_TYPE_MAP = {
    "OBJECT": "ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_TYPE_UNIFORM",
    "ATTRIBUTE": "ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_TYPE_VERTEX",
    "CUSTOM": "ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_TYPE_UNIFORM",
}

_EXPLOSIAFX_SOURCEXP_COLOR_TYPE_MAP = {
    "PARTICLES": "ID_NX_EXPLOSIAFX_SOURCEXP_COLOR_TYPE_PARTICLES",
    "CUSTOM": "ID_NX_EXPLOSIAFX_SOURCEXP_COLOR_TYPE_CUSTOM",
}

_EXPLOSIAFX_FORCE_LAYER_TYPE_MAP = {
    "TURBULENCE": "ID_NX_EXPLOSIAFX_FORCE_TYPE_TURBULENCE",
    "VORTICITY": "ID_NX_EXPLOSIAFX_FORCE_TYPE_VORTICITY",
    "WIND": "ID_NX_EXPLOSIAFX_FORCE_TYPE_WIND",
}

_EXPLOSIAFX_TURBULENCE_TYPE_MAP = {
    "SIMPLEX": "ID_NX_EXPLOSIAFX_NOISE_TYPE_SIMPLEX",
    "FBM": "ID_NX_EXPLOSIAFX_NOISE_TYPE_FBM",
    "TURBULENCE": "ID_NX_EXPLOSIAFX_NOISE_TYPE_TURBULENCE",
    "WAVYTURBULENCE": "ID_NX_EXPLOSIAFX_NOISE_TYPE_WAVY_TURBULENCE",
    "VORONOISE": "ID_NX_EXPLOSIAFX_NOISE_TYPE_VORONOISE",
    "CUBIC": "ID_NX_EXPLOSIAFX_NOISE_TYPE_CUBIC",
}

_EXPLOSIAFX_FORCE_MAPPING_TYPE_MAP = {
    "NONE": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_NONE",
    "SMOKE": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_SMOKE",
    "TEMPERATURE": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_TEMPERATURE",
    "FUEL": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_FUEL",
    "COLORR": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_COLOR_R",
    "COLORG": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_COLOR_G",
    "COLORB": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_COLOR_B",
    "VELX": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_VELX",
    "VELY": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_VELY",
    "VELZ": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_VELZ",
    "SPEED": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_SPEED",
    "POSX": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_POSX",
    "POSY": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_POSY",
    "POSZ": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_POSZ",
    "PRESSURE": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_PRESSURE",
    "DOCTIME": "ID_NX_EXPLOSIAFX_FORCE_MAPPING_DOCTIME",
}

_EXPLOSIAFX_PADVECT_MODE_MAP = {
    "POSITION": "ID_NX_EXPLOSIAFX_PARTICLEADVECT_POSITION",
    "DIRECTION": "ID_NX_EXPLOSIAFX_PARTICLEADVECT_DIRECTION",
    "VELOCITY": "ID_NX_EXPLOSIAFX_PARTICLEADVECT_VELOCITY",
}

_EXPLOSIAFX_PADVECT_PROPXFERTYPE_MAP = {
    "SET": "ID_NX_EXPLOSIAFX_PARTICLEADVECT_TRANSFER_SET",
    "ADD": "ID_NX_EXPLOSIAFX_PARTICLEADVECT_TRANSFER_ADD",
}

# Polygon mesh cache: (modifier_name, mesh_name) -> (poly_handle, vert_count, tri_count)
_explosiafx_poly_cache: dict[tuple[str, str], tuple[int, int, int]] = {}
# Line object cache:
_explosiafx_line_cache: dict[tuple[str, str], tuple[int, int, int]] = {}


def clear_explosiafx_poly_cache(modifier_name=None):
    """Free cached polygon objects. Pass modifier_name for targeted cleanup, None for all."""
    from ..libs import theron

    if modifier_name is None:
        for poly_handle, _vc, _tc in _explosiafx_poly_cache.values():
            theron.free_polygon_object(poly_handle)
        _explosiafx_poly_cache.clear()
    else:
        to_remove = [k for k in _explosiafx_poly_cache if k[0] == modifier_name]
        for key in to_remove:
            poly_handle, _vc, _tc = _explosiafx_poly_cache.pop(key)
            theron.free_polygon_object(poly_handle)


def clear_explosiafx_line_cache(modifier_name=None):
    """Free cached line objects. Pass modifier_name for targeted cleanup, None for all."""
    from ..libs import theron

    if modifier_name is None:
        for line_handle, _vc, _sc in _explosiafx_line_cache.values():
            theron.free_line_object(line_handle)
        _explosiafx_line_cache.clear()
    else:
        to_remove = [k for k in _explosiafx_line_cache if k[0] == modifier_name]
        for key in to_remove:
            line_handle, _vc, _sc = _explosiafx_line_cache.pop(key)
            theron.free_line_object(line_handle)


def _resolve_texture_weights(item, mesh, vertex_count, channel_prefix):
    """Build per-vertex weights by sampling an image for the given channel.

    Require original mesh here, not the evaluated mesh, because the UV coords are in `mesh' obj.
    Need to guard against size mismatch between original mesh
    and `vertex_count' from evaluated mesh

    Pixel data is read once via foreach_get; per-vertex sampling is vectorised.
    """
    img = getattr(item, f"{channel_prefix}_image", None)
    if img is None or img.size[0] == 0 or img.size[1] == 0:
        return np.zeros(vertex_count, dtype=np.float32)

    # Original mesh vertex count
    src_count = len(mesh.vertices)
    # Guard size mismatch and pad
    n = min(src_count, vertex_count)
    weights = np.ones(vertex_count, dtype=np.float32)
    if n == 0:
        return weights

    # Build a (src_count, 2) array of (u, v), one per source-mesh vertex.
    coords_mode = getattr(item, f"{channel_prefix}_texture_coords", "UV")
    if coords_mode == "UV":
        uv_name = getattr(item, f"{channel_prefix}_uv_map", "")
        uv_layer = mesh.uv_layers.get(uv_name) if uv_name else mesh.uv_layers.active
        if uv_layer is None:
            return weights
        # Per-vertex UV: take the first loop that references each vertex.
        uvs = np.zeros((src_count, 2), dtype=np.float32)
        seen = np.zeros(src_count, dtype=bool)
        for loop in mesh.loops:
            vi = loop.vertex_index
            if not seen[vi]:
                u, v = uv_layer.data[loop.index].uv
                uvs[vi, 0] = u
                uvs[vi, 1] = v
                seen[vi] = True
    else:
        verts = np.empty(src_count * 3, dtype=np.float32)
        # Dump all vertex coords into a flat numpy array
        mesh.vertices.foreach_get("co", verts)
        # Reshape to (n, 3)
        verts = verts.reshape(src_count, 3)
        # OBJECT and GENERATED modes are the same, except
        # GENERATED normalizes the axes to [0, 1] first from local bbox
        if coords_mode == "GENERATED":
            mn = verts.min(axis=0)
            mx = verts.max(axis=0)
            # BBox size with /0 guard
            rng = np.where(mx - mn > 1e-6, mx - mn, 1.0)
            verts = (verts - mn) / rng
        # Take X, Y as texture coords
        uvs = verts[:, :2].astype(np.float32, copy=False)

    # Read img.pixels, row-major RGBA float in [0, 1].
    width, height = img.size[0], img.size[1]
    channels = img.channels
    pixels = np.empty(width * height * channels, dtype=np.float32)
    # Copy pixel data to numpy buffer then reshape
    img.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, channels)

    # Wrap u and v array elements into [0, 1)]
    # Shape u[n], v[n] for n vertices
    u = np.mod(uvs[:n, 0], 1.0)
    v = np.mod(uvs[:n, 1], 1.0)
    # Nearest-neighbour sample with safety clip
    # Shape x[n], y[n] for n vertices
    x = np.clip((u * width).astype(np.int32), 0, width - 1)
    y = np.clip((v * height).astype(np.int32), 0, height - 1)
    # Evaluate pixels for a sampled array by VERTEX index and channel
    # Shape sampled[n, 4] for 4 channels (RGBA)
    sampled = pixels[y, x]
    # Take average of RGB channels (:3 drop A)
    weights[:n] = sampled[:, :3].mean(axis=1)

    return weights


_COLOR_CHANNEL_INDEX = {"R": 0, "G": 1, "B": 2, "A": 3}
_LUMINANCE_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _reduce_color_channels(rgba: np.ndarray, channel: str) -> np.ndarray:
    """Collapse an (N, 4) RGBA array to (N,) scalar weights by channel selection."""
    if channel == "LUMINANCE":
        return rgba[:, :3] @ _LUMINANCE_WEIGHTS
    return rgba[:, _COLOR_CHANNEL_INDEX.get(channel, 0)]


def _fill_color_attribute_weights(item, mesh, vertex_count, channel_prefix):
    """Build per-vertex weights (scalar valued) from a color attribute.

    Accepts POINT or CORNER domain on FLOAT_COLOR / BYTE_COLOR attributes. Corner-domain
    attributes must be averaged into per-vertex values. Returns ones on any mismatch to
    gracefully recover unweighted case.
    """
    weights = np.ones(vertex_count, dtype=np.float32)
    attr_name = getattr(item, f"{channel_prefix}_color_attribute", "")
    # No attribute - full (unweighted) emission
    if not attr_name:
        return weights
    # Wrong attribute type - full (unweighted) emission
    attr = mesh.color_attributes.get(attr_name)
    if attr is None or attr.data_type not in {"FLOAT_COLOR", "BYTE_COLOR"}:
        return weights
    # Empty attributes - full (unweighted) emission
    elem_count = len(attr.data)
    if elem_count == 0:
        return weights

    buf = np.empty(elem_count * 4, dtype=np.float32)
    attr.data.foreach_get("color", buf)
    rgba = buf.reshape(elem_count, 4)

    # Handle different domains
    channel = getattr(item, f"{channel_prefix}_color_channel", "LUMINANCE")
    if attr.domain == "POINT":
        n = min(elem_count, vertex_count)
        weights[:n] = _reduce_color_channels(rgba[:n], channel)
    elif attr.domain == "CORNER":
        loop_count = len(mesh.loops)
        if loop_count == 0 or elem_count < loop_count:
            return weights
        loop_vi = np.empty(loop_count, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vi)
        src_count = len(mesh.vertices)
        sums = np.zeros((src_count, 4), dtype=np.float32)
        counts = np.zeros(src_count, dtype=np.float32)
        np.add.at(sums, loop_vi, rgba[:loop_count])
        np.add.at(counts, loop_vi, 1.0)
        np.maximum(counts, 1.0, out=counts)
        per_vertex_rgba = sums / counts[:, None]
        n = min(src_count, vertex_count)
        weights[:n] = _reduce_color_channels(per_vertex_rgba[:n], channel)

    return weights


def _sync_sourceobjects_tree(obj, container, props, evaluated_props, scene, depsgraph):
    """Sync all sources into the theron source node tree."""
    from ..libs import theron, theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item
    from ..pipeline_manager.identity import ensure_object_uid
    from ..utils import extract_line_data, extract_mesh_data

    get = theron_ids.get
    items_orig = props.explosiafx_source_objects
    items_eval = evaluated_props.explosiafx_source_objects

    pcxform = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

    tree = theron.create_node_tree(container, get("ID_NX_EXPLOSIAFX_SOURCE_OBJECTSTREE"))
    if tree is None:
        return

    mod_uid = ensure_object_uid(obj)
    prev_node = None
    active_curves: set[str] = set()

    for index, item_orig in enumerate(items_orig):
        item = resolve_evaluated_item(items_eval, index, item_orig)
        if not item.enabled:
            continue

        if item_orig.obj is None:
            continue

        cache_key = (mod_uid, item_orig.obj.name)

        # Support NX_EMITTER
        nx_type = item_orig.obj.get("nexus_modifier_type")
        obj_kind = nx_type if nx_type else item_orig.obj.type
        obj_handle = None

        if obj_kind == "MESH":
            mesh_data = extract_mesh_data(item_orig.obj, depsgraph)
            if mesh_data is None:
                continue
            vertices, polygons, vertex_count, tri_count, world_matrix = mesh_data

            if cache_key in _explosiafx_poly_cache:
                poly_handle, prev_verts, prev_tris = _explosiafx_poly_cache[cache_key]
                if vertex_count != prev_verts or tri_count != prev_tris:
                    theron.resize_polygon_object(poly_handle, vertex_count, tri_count)
                    _explosiafx_poly_cache[cache_key] = (poly_handle, vertex_count, tri_count)
                theron.update_polygon_object_points(poly_handle, vertices)
                obj_handle = poly_handle
            else:
                obj_handle = theron.create_polygon_object_with_data(vertices, polygons)
                if obj_handle is None:
                    continue
                _explosiafx_poly_cache[cache_key] = (obj_handle, vertex_count, tri_count)
            theron.set_matrix(obj_handle, world_matrix)

        elif obj_kind == "CURVE":
            line_data = extract_line_data(item_orig.obj, depsgraph)
            if line_data is None:
                continue
            vertices, segments, vertex_count, seg_count, world_matrix = line_data

            if cache_key in _explosiafx_line_cache:
                prev_handle, prev_verts, prev_segs = _explosiafx_line_cache[cache_key]
                if vertex_count != prev_verts or seg_count != prev_segs:
                    theron.free_line_object(prev_handle)
                    obj_handle = theron.create_line_object_with_data(vertices, segments)
                    if obj_handle is None:
                        del _explosiafx_line_cache[cache_key]
                        continue
                    _explosiafx_line_cache[cache_key] = (obj_handle, vertex_count, seg_count)
                else:
                    obj_handle = prev_handle
            else:
                obj_handle = theron.create_line_object_with_data(vertices, segments)
                if obj_handle is None:
                    continue
                _explosiafx_line_cache[cache_key] = (obj_handle, vertex_count, seg_count)
            theron.set_matrix(obj_handle, world_matrix)

        elif obj_kind == "NX_EMITTER":
            from ..handlers.pipeline import get_nexus_obj_handle

            obj_handle = get_nexus_obj_handle(scene, item_orig.obj)
            if obj_handle is None:
                continue

        else:
            continue

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_link(node, obj_handle)

        node_container = theron.create_node_container(node)
        if node_container is None:
            prev_node = node
            continue

        if obj_kind == "MESH":
            # Per-vertex weights buffer: one array per channel per source mesh,
            # built and sent only when that channel's WEIGHTBY selects for
            # mode that requires vertex weighting.
            channel_weights_ids = (
                (
                    item.explosiafx_sourcemesh_smoke_weight,
                    "ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_WEIGHTS_LINK",
                    "explosiafx_sourcemesh_smoke",
                ),
                (
                    item.explosiafx_sourcemesh_temperature_weight,
                    "ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_WEIGHTS_LINK",
                    "explosiafx_sourcemesh_temperature",
                ),
                (
                    item.explosiafx_sourcemesh_fuel_weight,
                    "ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_WEIGHTS_LINK",
                    "explosiafx_sourcemesh_fuel",
                ),
                (
                    item.explosiafx_sourcemesh_pressure_weight,
                    "ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_WEIGHTS_LINK",
                    "explosiafx_sourcemesh_pressure",
                ),
            )
            for weight_mode, weights_id, channel_prefix in channel_weights_ids:
                if weight_mode not in _EXPLOSIAFX_EXTERNAL_WEIGHT_MODES:
                    continue
                if weight_mode == "VERTEX_GROUP":
                    vgroup_name = getattr(item, f"{channel_prefix}_vertex_group", "")
                    vgroup = item_orig.obj.vertex_groups.get(vgroup_name) if vgroup_name else None
                    if vgroup is None:
                        weights = np.ones(vertex_count, dtype=np.float32)
                    else:
                        vgi = vgroup.index
                        # Vertex groups live on the original mesh; extract_mesh_data
                        # uses the evaluated mesh, so cap and zero-pad if topology-
                        # changing modifiers leave the counts mismatched.
                        src_verts = item_orig.obj.data.vertices
                        n = min(len(src_verts), vertex_count)
                        weights = np.ones(vertex_count, dtype=np.float32)
                        if n > 0:
                            weights[:n] = np.fromiter(
                                (
                                    next(
                                        (g.weight for g in src_verts[i].groups if g.group == vgi),
                                        0.0,
                                    )
                                    for i in range(n)
                                ),
                                dtype=np.float32,
                                count=n,
                            )
                elif weight_mode == "ATTRIBUTE":
                    attr_name = getattr(item, f"{channel_prefix}_attribute", "")
                    attr = item_orig.obj.data.attributes.get(attr_name) if attr_name else None
                    weights = np.ones(vertex_count, dtype=np.float32)
                    # Only point-domain float attributes map to a per-vertex
                    # scalar; anything else falls back to zeros.
                    if attr is not None and attr.domain == "POINT" and attr.data_type == "FLOAT":
                        n = min(len(attr.data), vertex_count)
                        if n > 0:
                            buf = np.empty(len(attr.data), dtype=np.float32)
                            attr.data.foreach_get("value", buf)
                            weights[:n] = buf[:n]
                elif weight_mode == "TEXTURE":
                    weights = _resolve_texture_weights(
                        item, item_orig.obj.data, vertex_count, channel_prefix
                    )
                elif weight_mode == "COLOR_ATTRIBUTE":
                    weights = _fill_color_attribute_weights(
                        item, item_orig.obj.data, vertex_count, channel_prefix
                    )
                else:
                    weights = np.ones(vertex_count, dtype=np.float32)

                theron.set_memory(
                    node_container,
                    get(weights_id),
                    weights.ctypes.data_as(ctypes.c_void_p),
                    weights.nbytes,
                )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_EMIT_ENUM_MAP.get(
                item.explosiafx_sourcemesh_emit_from
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_EMITFROM"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_EMIT_SURFACEINNERWIDTH"),
                item.explosiafx_sourcemesh_surface_emitwidth,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_EMIT_SURFACEOUTERWIDTH"),
                item.explosiafx_sourcemesh_surface_taperwidth,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE"),
                item.explosiafx_sourcemesh_smoke,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcemesh_smoke_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_MODE"), get(op_id_name)
                )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_EMIT_WEIGHT_ENUM_MAP.get(
                item.explosiafx_sourcemesh_smoke_weight
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_CUSTOM"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_MIXPC"),
                item.explosiafx_sourcemesh_smoke_mixpc * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_NOISEWT_STRENGTH"),
                item.explosiafx_sourcemesh_smoke_noisewt_strength * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_NOISEWT_LENSCL"),
                item.explosiafx_sourcemesh_smoke_noisewt_lenscl,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_NOISEWT_OCTAVES"),
                item.explosiafx_sourcemesh_smoke_noisewt_octaves,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_NOISEWT_PERSISTENCE"),
                item.explosiafx_sourcemesh_smoke_noisewt_persistence * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKE_NOISEWT_FREQ"),
                item.explosiafx_sourcemesh_smoke_noisewt_freq * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKEFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcemesh_smoke_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKEFRAMELIMIT_MIN"),
                item.explosiafx_sourcemesh_smoke_framelimit_min
                if item.explosiafx_sourcemesh_smoke_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_SMOKEFRAMELIMIT_MAX"),
                item.explosiafx_sourcemesh_smoke_framelimit_max
                if item.explosiafx_sourcemesh_smoke_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP"),
                item.explosiafx_sourcemesh_temperature,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcemesh_temperature_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_MODE"), get(op_id_name)
                )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_EMIT_WEIGHT_ENUM_MAP.get(
                item.explosiafx_sourcemesh_temperature_weight
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_CUSTOM"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_MIXPC"),
                item.explosiafx_sourcemesh_temperature_mixpc * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_NOISEWT_STRENGTH"),
                item.explosiafx_sourcemesh_temperature_noisewt_strength * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_NOISEWT_LENSCL"),
                item.explosiafx_sourcemesh_temperature_noisewt_lenscl,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_NOISEWT_OCTAVES"),
                item.explosiafx_sourcemesh_temperature_noisewt_octaves,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_NOISEWT_PERSISTENCE"),
                item.explosiafx_sourcemesh_temperature_noisewt_persistence * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMP_NOISEWT_FREQ"),
                item.explosiafx_sourcemesh_temperature_noisewt_freq * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMPERATUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcemesh_temperature_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMPERATUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcemesh_temperature_framelimit_min
                if item.explosiafx_sourcemesh_temperature_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_TEMPERATUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcemesh_temperature_framelimit_max
                if item.explosiafx_sourcemesh_temperature_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL"),
                item.explosiafx_sourcemesh_fuel,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcemesh_fuel_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_MODE"), get(op_id_name)
                )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_EMIT_WEIGHT_ENUM_MAP.get(
                item.explosiafx_sourcemesh_fuel_weight
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_CUSTOM"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_MIXPC"),
                item.explosiafx_sourcemesh_fuel_mixpc * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_NOISEWT_STRENGTH"),
                item.explosiafx_sourcemesh_fuel_noisewt_strength * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_NOISEWT_LENSCL"),
                item.explosiafx_sourcemesh_fuel_noisewt_lenscl,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_NOISEWT_OCTAVES"),
                item.explosiafx_sourcemesh_fuel_noisewt_octaves,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_NOISEWT_PERSISTENCE"),
                item.explosiafx_sourcemesh_fuel_noisewt_persistence * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUEL_NOISEWT_FREQ"),
                item.explosiafx_sourcemesh_fuel_noisewt_freq * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUELFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcemesh_fuel_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUELFRAMELIMIT_MIN"),
                item.explosiafx_sourcemesh_fuel_framelimit_min
                if item.explosiafx_sourcemesh_fuel_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_FUELFRAMELIMIT_MAX"),
                item.explosiafx_sourcemesh_fuel_framelimit_max
                if item.explosiafx_sourcemesh_fuel_framelimit_enabled
                else -1,
            )

            # UI range for cm units
            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE"),
                item.explosiafx_sourcemesh_pressure,
            )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_EMIT_WEIGHT_ENUM_MAP.get(
                item.explosiafx_sourcemesh_pressure_weight
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_CUSTOM"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_NOISEWT_STRENGTH"),
                item.explosiafx_sourcemesh_pressure_noisewt_strength * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_NOISEWT_LENSCL"),
                item.explosiafx_sourcemesh_pressure_noisewt_lenscl,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_NOISEWT_OCTAVES"),
                item.explosiafx_sourcemesh_pressure_noisewt_octaves,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_NOISEWT_PERSISTENCE"),
                item.explosiafx_sourcemesh_pressure_noisewt_persistence * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSURE_NOISEWT_FREQ"),
                item.explosiafx_sourcemesh_pressure_noisewt_freq * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcemesh_pressure_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcemesh_pressure_framelimit_min
                if item.explosiafx_sourcemesh_pressure_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_PRESSUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcemesh_pressure_framelimit_max
                if item.explosiafx_sourcemesh_pressure_framelimit_enabled
                else -1,
            )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_VELOCITY_TYPE_MAP.get(
                item.explosiafx_sourcemesh_velocity_from
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEMESH_VELOCITY_TYPE"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_VELOCITY_MIX"),
                item.explosiafx_sourcemesh_velocity_objpercent * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_VELOCITY_MAGNITUDE"),
                item.explosiafx_sourcemesh_velocity_perpsize,
            )

            theron.set_vector(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_VELOCITY_VEC"),
                item.explosiafx_sourcemesh_velocity_custom[0],
                item.explosiafx_sourcemesh_velocity_custom[1],
                item.explosiafx_sourcemesh_velocity_custom[2],
            )

            op_id_name = _EXPLOSIAFX_SOURCEMESH_COLOR_TYPE_MAP.get(
                item.explosiafx_sourcemesh_color_from
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_TYPE"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_STRENGTH"),
                item.explosiafx_sourcemesh_color_objpercent * pcxform,
            )

            if item.explosiafx_sourcemesh_color_from == "OBJECT":
                color_vec = item.obj.color
            elif item.explosiafx_sourcemesh_color_from == "CUSTOM":
                color_vec = item.explosiafx_sourcemesh_color_custom
            else:
                color_vec = (1.0, 1.0, 1.0)
            theron.set_vector(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_VALUE"),
                color_vec[0],
                color_vec[1],
                color_vec[2],
            )

            if item.explosiafx_sourcemesh_color_from == "ATTRIBUTE":
                attr_name = item.explosiafx_sourcemesh_color_attribute
                attr = item_orig.obj.data.color_attributes.get(attr_name) if attr_name else None
                colors = np.zeros((vertex_count, 3), dtype=np.float32)
                if (
                    attr is not None
                    and attr.domain == "POINT"
                    and attr.data_type in {"FLOAT_COLOR", "BYTE_COLOR"}
                ):
                    n = min(len(attr.data), vertex_count)
                    if n > 0:
                        buf = np.empty(len(attr.data) * 4, dtype=np.float32)
                        attr.data.foreach_get("color", buf)
                        colors[:n] = buf.reshape(-1, 4)[:n, :3]
                theron.set_memory(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEMESH_COLOR_VERTEX_LINK"),
                    colors.ctypes.data_as(ctypes.c_void_p),
                    colors.nbytes,
                )

        elif obj_kind == "CURVE":
            customradius = item.explosiafx_sourcespline_custom_radius
            radius = -1
            if customradius:
                radius = item.explosiafx_sourcespline_radius

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_RADIUS"),
                radius,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKE"),
                item.explosiafx_sourcespline_smoke,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcespline_smoke_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKE_MODE"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKE_MIXPC"),
                item.explosiafx_sourcespline_smoke_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKEFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcespline_smoke_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKEFRAMELIMIT_MIN"),
                item.explosiafx_sourcespline_smoke_framelimit_min
                if item.explosiafx_sourcespline_smoke_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_SMOKEFRAMELIMIT_MAX"),
                item.explosiafx_sourcespline_smoke_framelimit_max
                if item.explosiafx_sourcespline_smoke_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMP"),
                item.explosiafx_sourcespline_temperature,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcespline_temperature_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMP_MODE"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMP_MIXPC"),
                item.explosiafx_sourcespline_temperature_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMPERATUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcespline_temperature_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMPERATUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcespline_temperature_framelimit_min
                if item.explosiafx_sourcespline_temperature_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_TEMPERATUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcespline_temperature_framelimit_max
                if item.explosiafx_sourcespline_temperature_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUEL"),
                item.explosiafx_sourcespline_fuel,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcespline_fuel_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUEL_MODE"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUEL_MIXPC"),
                item.explosiafx_sourcespline_fuel_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUELFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcespline_fuel_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUELFRAMELIMIT_MIN"),
                item.explosiafx_sourcespline_fuel_framelimit_min
                if item.explosiafx_sourcespline_fuel_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_FUELFRAMELIMIT_MAX"),
                item.explosiafx_sourcespline_fuel_framelimit_max
                if item.explosiafx_sourcespline_fuel_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_PRESSURE"),
                item.explosiafx_sourcespline_pressure,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_PRESSUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcespline_pressure_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_PRESSUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcespline_pressure_framelimit_min
                if item.explosiafx_sourcespline_pressure_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_PRESSUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcespline_pressure_framelimit_max
                if item.explosiafx_sourcespline_pressure_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_VELOCITY_MIX"),
                item.explosiafx_sourcespline_velocity_objpercent * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_COLOR_STRENGTH"),
                item.explosiafx_sourcespline_color_objpercent * pcxform,
            )

            if item.explosiafx_sourcespline_color_from == "OBJECT":
                color_vec = item.obj.color
            elif item.explosiafx_sourcespline_color_from == "CUSTOM":
                color_vec = item.explosiafx_sourcespline_color_custom
            theron.set_vector(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCESPLINE_COLOR"),
                color_vec[0],
                color_vec[1],
                color_vec[2],
            )

            active_curves.add(item_orig.obj.name)

        elif obj_kind == "NX_EMITTER":
            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKE"),
                item.explosiafx_sourcexp_smoke,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcexp_smoke_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKE_MODE"),
                    get(op_id_name),
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKE_MIXPC"),
                item.explosiafx_sourcexp_smoke_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKEFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcexp_smoke_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKEFRAMELIMIT_MIN"),
                item.explosiafx_sourcexp_smoke_framelimit_min
                if item.explosiafx_sourcexp_smoke_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_SMOKEFRAMELIMIT_MAX"),
                item.explosiafx_sourcexp_smoke_framelimit_max
                if item.explosiafx_sourcexp_smoke_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMP"),
                item.explosiafx_sourcexp_temperature,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcexp_temperature_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMP_MODE"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMP_MIXPC"),
                item.explosiafx_sourcexp_temperature_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMPERATUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcexp_temperature_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMPERATUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcexp_temperature_framelimit_min
                if item.explosiafx_sourcexp_temperature_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_TEMPERATUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcexp_temperature_framelimit_max
                if item.explosiafx_sourcexp_temperature_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_FUEL"),
                item.explosiafx_sourcexp_fuel,
            )

            op_id_name = _EXPLOSIAFX_SOURCE_EMIT_MODE_ENUM_MAP.get(
                item.explosiafx_sourcexp_fuel_mode
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEXP_FUEL_MODE"), get(op_id_name)
                )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_FUEL_MIXPC"),
                item.explosiafx_sourcexp_fuel_mixpc * pcxform,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_FUELFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcexp_fuel_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_FUELFRAMELIMIT_MIN"),
                item.explosiafx_sourcexp_fuel_framelimit_min
                if item.explosiafx_sourcexp_fuel_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_FUELFRAMELIMIT_MAX"),
                item.explosiafx_sourcexp_fuel_framelimit_max
                if item.explosiafx_sourcexp_fuel_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_PRESSURE"),
                item.explosiafx_sourcexp_pressure,
            )

            theron.set_bool(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_PRESSUREFRAMELIMIT_ENABLE"),
                item.explosiafx_sourcexp_pressure_framelimit_enabled,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_PRESSUREFRAMELIMIT_MIN"),
                item.explosiafx_sourcexp_pressure_framelimit_min
                if item.explosiafx_sourcexp_pressure_framelimit_enabled
                else -1,
            )

            theron.set_int32(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_PRESSUREFRAMELIMIT_MAX"),
                item.explosiafx_sourcexp_pressure_framelimit_max
                if item.explosiafx_sourcexp_pressure_framelimit_enabled
                else -1,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_VELOCITY_MIX"),
                item.explosiafx_sourcexp_velocity_objpercent * pcxform,
            )

            theron.set_float(
                node_container,
                get("ID_NX_EXPLOSIAFX_SOURCEXP_COLOR_STRENGTH"),
                item.explosiafx_sourcexp_color_objpercent * pcxform,
            )

            op_id_name = _EXPLOSIAFX_SOURCEXP_COLOR_TYPE_MAP.get(
                item.explosiafx_sourcexp_color_from
            )
            if op_id_name is not None:
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_SOURCEXP_COLOR_MODE"), get(op_id_name)
                )

            if item.explosiafx_sourcexp_color_from == "CUSTOM":
                color_vec = item.explosiafx_sourcexp_color_custom
                theron.set_vector(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_SOURCEXP_COLOR_VALUE"),
                    color_vec[0],
                    color_vec[1],
                    color_vec[2],
                )

        prev_node = node

    stale = [k for k in _explosiafx_line_cache if k[0] == mod_uid and k[1] not in active_curves]
    for key in stale:
        line_handle, _vc, _sc = _explosiafx_line_cache.pop(key)
        theron.free_line_object(line_handle)


def _sync_colliderobjects_tree(obj, container, props, evaluated_props, depsgraph):
    """Sync all colliders into the theron collider node tree."""
    from ..libs import theron, theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item
    from ..pipeline_manager.identity import ensure_object_uid
    from ..utils import extract_mesh_data

    get = theron_ids.get
    items_orig = props.explosiafx_collider_objects
    items_eval = evaluated_props.explosiafx_collider_objects

    pcxform = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

    tree = theron.create_node_tree(container, get("ID_NX_EXPLOSIAFX_COLLIDER_OBJECTSTREE"))
    if tree is None:
        return

    mod_uid = ensure_object_uid(obj)
    prev_node = None

    for index, item_orig in enumerate(items_orig):
        item = resolve_evaluated_item(items_eval, index, item_orig)
        if not item.enabled:
            continue

        if item_orig.obj is None or item_orig.obj.type != "MESH":
            continue

        mesh_data = extract_mesh_data(item_orig.obj, depsgraph)
        if mesh_data is None:
            continue
        vertices, polygons, vertex_count, tri_count, world_matrix = mesh_data

        cache_key = (mod_uid, item_orig.obj.name)
        if cache_key in _explosiafx_poly_cache:
            poly_handle, prev_verts, prev_tris = _explosiafx_poly_cache[cache_key]
            if vertex_count != prev_verts or tri_count != prev_tris:
                theron.resize_polygon_object(poly_handle, vertex_count, tri_count)
                _explosiafx_poly_cache[cache_key] = (poly_handle, vertex_count, tri_count)
            theron.update_polygon_object_points(poly_handle, vertices)
        else:
            poly_handle = theron.create_polygon_object_with_data(vertices, polygons)
            if poly_handle is None:
                continue
            _explosiafx_poly_cache[cache_key] = (poly_handle, vertex_count, tri_count)
        theron.set_matrix(poly_handle, world_matrix)

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_link(node, poly_handle)

        node_container = theron.create_node_container(node)
        if node_container is None:
            prev_node = node
            continue

        theron.set_bool(
            node_container,
            get("ID_NX_EXPLOSIAFX_COLLIDER_INSIDENORMALS"),
            item.explosiafx_collider_insidenormals,
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_COLLIDER_ADDPRESSURE"),
            item.explosiafx_collider_pressure,
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_COLLIDER_VELOCITYSCALE"),
            item.explosiafx_collider_velocity_scale * pcxform,
        )


def _sync_forcelayers_tree(obj, container, props, evaluated_props, depsgraph):
    """Sync all dynamics -> force layers into the theron force layer tree."""
    del obj, depsgraph
    from ..libs import theron, theron_ids
    from ..libs.nodetree_sync import resolve_evaluated_item

    pcxform = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

    get = theron_ids.get

    layers_orig = props.explosiafx_force_layers
    layers_eval = evaluated_props.explosiafx_force_layers
    tree = theron.create_node_tree(container, get("ID_NX_EXPLOSIAFX_FORCES_TREE"))
    if tree is None:
        return

    prev_node = None

    for index, item_orig in enumerate(layers_orig):
        item = resolve_evaluated_item(layers_eval, index, item_orig)
        if not item.enabled:
            continue

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        layer_type_id = get(
            _EXPLOSIAFX_FORCE_LAYER_TYPE_MAP.get(
                item_orig.item_type, "ID_NX_EXPLOSIAFX_FORCE_TYPE_TURBULENCE"
            )
        )
        theron.set_node_id(node, layer_type_id)

        node_container = theron.create_node_container(node)
        if node_container is None:
            prev_node = node
            continue

        theron.set_int32(node_container, get("ID_NX_EXPLOSIAFX_FORCE_LAYER_TYPE"), layer_type_id)

        match item_orig.item_type:
            case "TURBULENCE":
                noisetype = get(
                    _EXPLOSIAFX_TURBULENCE_TYPE_MAP.get(
                        item.turbulence_type, "ID_NX_EXPLOSIAFX_NOISE_TYPE_SIMPLEX"
                    )
                )
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_TURBULENCE_NOISE_TYPE"), noisetype
                )
                theron.set_float(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_TURBULENCE_STRENGTH"),
                    item.strength,
                )
                theron.set_float(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_TURBULENCE_LENGTHSCALE"),
                    item.length_scale,
                )
                theron.set_float(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_TURBULENCE_FREQUENCY"),
                    item.frequency * pcxform,
                )
                theron.set_float(
                    node_container, get("ID_NX_EXPLOSIAFX_TURBULENCE_LACUNARITY"), item.lacunarity
                )
                theron.set_float(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_TURBULENCE_PERSISTENCE"),
                    item.persistence * pcxform,
                )
                theron.set_int32(
                    node_container, get("ID_NX_EXPLOSIAFX_TURBULENCE_OCTAVES"), item.octaves
                )
            case "VORTICITY":
                theron.set_float(
                    node_container, get("ID_NX_EXPLOSIAFX_VORTICITY_STRENGTH"), item.strength
                )
            case "WIND":
                theron.set_float(
                    node_container, get("ID_NX_EXPLOSIAFX_WIND_STRENGTH"), item.strength
                )
                theron.set_float(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_WIND_STRENGTH_VAR"),
                    item.variation * pcxform,
                )
                # Permute axes to make dirn control make sense
                theron.set_vector(
                    node_container,
                    get("ID_NX_EXPLOSIAFX_WIND_DIRN"),
                    item.wind_dirn[2],
                    -item.wind_dirn[0],
                    -item.wind_dirn[1],
                )

        mapping_type_id = get(
            _EXPLOSIAFX_FORCE_MAPPING_TYPE_MAP.get(
                item.mapto, "ID_NX_EXPLOSIAFX_FORCE_MAPPING_NONE"
            )
        )
        theron.set_int32(
            node_container, get("ID_NX_EXPLOSIAFX_FORCES_MAPPING_MAPTO"), mapping_type_id
        )

        theron.set_float(node_container, get("ID_NX_EXPLOSIAFX_FORCES_MAPPING_MIN"), item.mapmin)
        theron.set_float(node_container, get("ID_NX_EXPLOSIAFX_FORCES_MAPPING_MAX"), item.mapmax)

        from ..libs.resource_sync import sync_curve_specs

        sync_curve_specs(
            theron,
            get,
            node_container,
            item_orig.id_data,
            EXPLOSIAFX_FORCE_DATAMAP_CURVE_SPECS,
            source=item_orig,
            evaluated_source=item,
        )


def _sync_padvect_tree(obj, container, props, scene, depsgraph):
    """Sync all Particle Advect Emitters into the theron node tree."""
    from ..libs import theron, theron_ids

    del obj

    get = theron_ids.get
    items = props.explosiafx_padvect_objects

    pcxform = TRANSFORM_FACTORS[Transform.PERCENT_TO_DECIMAL]

    tree = theron.create_node_tree(container, get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_OBJECTSTREE"))
    if tree is None:
        return

    prev_node = None

    for item in items:
        if not item.enabled:
            continue

        if item.obj is None:
            continue

        # Support NX_EMITTER
        nx_type = item.obj.get("nexus_modifier_type")
        obj_kind = nx_type if nx_type else item.obj.type

        if obj_kind == "NX_EMITTER":
            from ..handlers.pipeline import get_nexus_obj_handle

            obj_handle = get_nexus_obj_handle(scene, item.obj)
            if obj_handle is None:
                continue

        else:
            continue

        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        theron.set_node_link(node, obj_handle)

        node_container = theron.create_node_container(node)
        if node_container is None:
            prev_node = node
            continue

        padvect_mode_id = get(
            _EXPLOSIAFX_PADVECT_MODE_MAP.get(
                item.explosiafx_padvect_mode, "ID_NX_EXPLOSIAFX_PARTICLEADVECT_VELOCITY"
            )
        )
        theron.set_int32(
            node_container, get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_MODE"), padvect_mode_id
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_STRENGTH"),
            item.explosiafx_padvect_strength * pcxform,
        )

        padvect_xfer_id = get(
            _EXPLOSIAFX_PADVECT_PROPXFERTYPE_MAP.get(
                item.explosiafx_padvect_propxfertype,
                "ID_NX_EXPLOSIAFX_PARTICLEADVECT_TRANSFER_SET",
            )
        )
        theron.set_int32(
            node_container, get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_TRANSFERTYPE"), padvect_xfer_id
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_SMOKETRANSFER"),
            item.explosiafx_padvect_smoke * pcxform,
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_FUELTRANSFER"),
            item.explosiafx_padvect_fuel * pcxform,
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_TEMPTRANSFER"),
            item.explosiafx_padvect_temperature * pcxform,
        )

        theron.set_float(
            node_container,
            get("ID_NX_EXPLOSIAFX_PARTICLEADVECT_COLORTRANSFER"),
            item.explosiafx_padvect_color * pcxform,
        )

        prev_node = node


def _sync_modifiers_tree(obj, container, props, scene, depsgraph):
    """Sync all modifiers into the theron node tree."""
    from ..handlers.pipeline import get_nexus_obj_handle
    from ..libs import theron, theron_ids

    del obj

    get = theron_ids.get
    items = props.explosiafx_modifiers_objects

    tree = theron.create_node_tree(container, get("ID_NX_EXPLOSIAFX_MODIFIERS_OBJECTTREE"))
    if tree is None:
        return

    prev_node = None

    for item in items:
        if not item.enabled:
            continue

        if item.obj is None:
            continue

        # Support adding NeXus modifiers by handle to the list of Theron object links.
        nx_type = item.obj.get("nexus_modifier_type")
        if nx_type is None:
            continue  # Not a NeXus modifier

        obj_handle = get_nexus_obj_handle(scene, item.obj)
        if obj_handle is None:
            continue

        # Create node
        node = theron.node_tree_insert(tree, None, prev_node)
        if node is None:
            continue

        # Link handle
        theron.set_node_link(node, obj_handle)

        prev_node = node


def _remove_unused_explosiafx_poly_cache(obj, container, props, scene, depsgraph):
    """Since the polygon cache is shared between sources and colliders,
    detect and remove stale entries in this centralized routine"""
    from ..libs import theron

    # Build list of still-active objects from both collider and source node trees
    active_objs: set[str] = set()

    for item in props.explosiafx_source_objects:
        if not item.enabled:
            continue

        if item.obj is None:
            continue

        active_objs.add(item.obj.name)

    for item in props.explosiafx_collider_objects:
        if not item.enabled:
            continue

        if item.obj is None:
            continue

        active_objs.add(item.obj.name)

    # Remove stale polygons
    mod_name = obj.name
    stale = [k for k in _explosiafx_poly_cache if k[0] == mod_name and k[1] not in active_objs]
    for key in stale:
        poly_handle, _vc, _tc = _explosiafx_poly_cache.pop(key)
        theron.free_polygon_object(poly_handle)


class NXExplosiaFXModifier(NexusModifier):
    object_type = "NX_EXPLOSIAFX"
    object_name = "nxExplosiaFX"
    object_label = "ExplosiaFX Modifier"
    object_description = "ExplosiaFX simulation"
    icon_name = "nx_explosiafx"
    category = "Simulation"
    menu_category = MenuCategory.SIMULATION
    gizmo_max_handles = 3

    ui_flags = UIFlags.VISIBLE_IN_EDITOR | UIFlags.RESET_BUTTON | UIFlags.HELP_BUTTON

    @classmethod
    def get_theron_type(cls, obj):
        return "TR_MODIFIER_TYPE_EXPLOSIAFX"

    @classmethod
    def get_gizmo_handles(cls, obj, props):
        from ..gizmos.resize_gizmo import HandleConfig

        return [
            HandleConfig(
                Vector((1, 0, 0)),
                "explosiafx_domain_size",
                prop_component=0,
                position_factor=0.5,
                min_value=0.1,
            ),
            HandleConfig(
                Vector((0, 1, 0)),
                "explosiafx_domain_size",
                prop_component=1,
                position_factor=0.5,
                min_value=0.1,
            ),
            HandleConfig(
                Vector((0, 0, 1)),
                "explosiafx_domain_size",
                prop_component=2,
                position_factor=0.5,
                min_value=0.1,
            ),
        ]

    @classmethod
    def on_create(cls, obj: bpy.types.Object) -> None:
        from ..properties.nx_explosiafx import add_default_force_layers

        props = obj.nexus_modifier
        add_default_force_layers(props)

    @classmethod
    def on_destroy(cls, mod_uid):
        clear_explosiafx_poly_cache(modifier_name=mod_uid)
        clear_explosiafx_line_cache(modifier_name=mod_uid)

    @classmethod
    def on_state_clear(cls, *, free_resources=True):
        if free_resources:
            clear_explosiafx_poly_cache()
            clear_explosiafx_line_cache()
        else:
            _explosiafx_poly_cache.clear()
            _explosiafx_line_cache.clear()

    @classmethod
    def get_modifier_properties(cls) -> list[str]:
        return SPEC.build_preset_properties()

    @classmethod
    def get_tabs(cls, props):
        tabs = []
        tabs.append(("DYNAMICS", "Dynamics"))
        tabs.append(("DISPLAY", "Display"))
        tabs.append(("RENDER", "Render"))
        return tabs

    @classmethod
    def draw_tab(cls, section_id, layout, props):
        col = layout.column()
        col.use_property_split = True

        if section_id == "DISPLAY":
            cls.draw_display_section(layout, props)
        elif section_id == "DYNAMICS":
            cls.draw_dynamics_section(layout, props)
        elif section_id == "RENDER":
            cls.draw_render_section(layout, props)

    @classmethod
    def draw_display_section(cls, layout, data):
        row = layout.row(align=True)
        row.prop(data, "explosiafx_display_tab", expand=True)

        tab = data.explosiafx_display_tab
        if tab == "VOLUME":
            cls._draw_displayvolume_tab(layout, data)
        elif tab == "HUD":
            cls._draw_displayhud_tab(layout, data)

    @classmethod
    def _draw_displayvolume_tab(cls, layout, data):
        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("explosiafx_display_volume_drawupres", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_volume_show_in_rendered")
        row = col.row()
        row.enabled = getattr(data, "ID_NX_EXPLOSIAFX_UPRES", 1) > 1
        row.prop(data, "explosiafx_display_volume_drawupres")

        col.separator(type="LINE")
        col.prop(data, "explosiafx_display_volume_drawmode")

        mode = data.explosiafx_display_volume_drawmode
        if mode == "SLICES":
            cls._draw_displayvolume_slices_tab(layout, data)
        elif mode == "RAYMARCHER":
            cls._draw_displayvolume_raymarcher_tab(layout, data)

    @classmethod
    def _draw_displayvolume_slices_tab(cls, layout, data):
        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("explosiafx_display_slicer_channel", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_slicer_channel")
        col.prop(data, "explosiafx_display_slicer_count")
        col.prop(data, "explosiafx_display_slicer_transparency")

        channel = data.explosiafx_display_slicer_channel

        if channel == "SPEED":
            box = layout.box()
            box.label(text="Speed Style")
            col = box.column()
            col.use_property_split = True

            obj = bpy.context.object
            if obj:
                NexusGradient(obj, "explosiafx_display_slicer_speed_color").draw_ui(
                    col, "Speed Color"
                )
                NexusGradient(obj, "explosiafx_display_slicer_speed_alpha").draw_ui(
                    col, "Speed Alpha"
                )
            col.prop(data, "explosiafx_display_slicer_speed_min")
            col.prop(data, "explosiafx_display_slicer_speed_max")

        if channel == "TEMP" or channel == "SMOKE_TEMP":
            box = layout.box()
            box.label(text="Temperature Style")
            col = box.column()
            col.use_property_split = True

            col.prop(data, "explosiafx_display_slicer_temp_color_mode")
            color_mode = data.explosiafx_display_slicer_temp_color_mode

            col.prop(data, "explosiafx_display_slicer_temp_min_opacity_clip")
            col.prop(data, "explosiafx_display_slicer_temp_max_opacity_clip")
            obj = bpy.context.object
            if obj and color_mode == "MANUAL":
                NexusGradient(obj, "explosiafx_display_slicer_temp_color").draw_ui(
                    col, "Temperature Color"
                )
            if obj:
                NexusGradient(obj, "explosiafx_display_slicer_temp_alpha").draw_ui(
                    col, "Temperature Opacity"
                )
            col.prop(data, "explosiafx_display_slicer_temp_transparency")

            if color_mode == "MANUAL":
                col.prop(data, "explosiafx_display_slicer_temp_min")
                col.prop(data, "explosiafx_display_slicer_temp_max")
            elif color_mode == "BLACKBODY":
                col.prop(data, "explosiafx_display_slicer_temp_bb_power")
                col.prop(data, "explosiafx_display_slicer_temp_bb_min")
                col.prop(data, "explosiafx_display_slicer_temp_bb_max")

        if channel == "FUEL" or channel == "SMOKE_FUEL":
            box = layout.box()
            box.label(text="Fuel Style")
            col = box.column()
            col.use_property_split = True

            col.prop(data, "explosiafx_display_slicer_fuel_min_opacity_clip")
            col.prop(data, "explosiafx_display_slicer_fuel_max_opacity_clip")
            obj = bpy.context.object
            if obj:
                NexusGradient(obj, "explosiafx_display_slicer_fuel_color").draw_ui(
                    col, "Fuel Color"
                )
                NexusGradient(obj, "explosiafx_display_slicer_fuel_alpha").draw_ui(
                    col, "Fuel Alpha"
                )
            col.prop(data, "explosiafx_display_slicer_fuel_transparency")
            col.prop(data, "explosiafx_display_slicer_fuel_min")
            col.prop(data, "explosiafx_display_slicer_fuel_max")

        if channel == "SMOKE" or channel == "SMOKE_TEMP" or channel == "SMOKE_FUEL":
            box = layout.box()
            box.label(text="Smoke Style")
            col = box.column()
            col.use_property_split = True

            col.prop(data, "explosiafx_display_slicer_smoke_min_opacity_clip")
            col.prop(data, "explosiafx_display_slicer_smoke_max_opacity_clip")
            obj = bpy.context.object
            if obj:
                NexusGradient(obj, "explosiafx_display_slicer_smoke_color").draw_ui(
                    col, "Smoke Color"
                )
                NexusGradient(obj, "explosiafx_display_slicer_smoke_alpha").draw_ui(
                    col, "Smoke Alpha"
                )
            col.prop(data, "explosiafx_display_slicer_smoke_transparency")

    @classmethod
    def _draw_displayvolume_raymarcher_tab(cls, layout, data):
        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("explosiafx_display_vrm_ray_max_steps", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_vrm_ray_max_steps")
        col.prop(data, "explosiafx_display_vrm_global_transparency")
        col.separator(type="LINE")

        col = layout.column()
        col.label(text="Smoke")
        col.use_property_split = ui_config.get(
            "explosiafx_display_vrm_smoke_extinction_coef", {}
        ).get("use_property_split", True)
        col.prop(data, "explosiafx_display_vrm_smoke_extinction_coef")
        col.prop(data, "explosiafx_display_vrm_smoke_tint_color")
        col.prop(data, "explosiafx_display_vrm_smoke_albedo")
        col.prop(data, "explosiafx_display_vrm_smoke_scatter_anisotropy")
        col.separator(type="LINE")

        col = layout.column()
        col.label(text="Flame")
        col.use_property_split = ui_config.get("explosiafx_display_vrm_flame_emit_min_t", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_vrm_flame_emit_min_t")
        col.prop(data, "explosiafx_display_vrm_flame_intensity")
        col.prop(data, "explosiafx_display_vrm_hot_gas_emit_strength")
        col.prop(data, "explosiafx_display_vrm_hot_gas_emit_type")
        row = col.row()
        row.enabled = data.explosiafx_display_vrm_hot_gas_emit_type == "MANUAL"
        row.prop(data, "explosiafx_display_vrm_hot_gas_emit_color")
        col.separator(type="LINE")

        col = layout.column()
        col.label(text="Ambient Light")
        col.use_property_split = ui_config.get("explosiafx_display_vrm_light_intensity", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_vrm_light_intensity")
        col.prop(data, "explosiafx_display_vrm_light_dirn")
        col.prop(data, "explosiafx_display_vrm_light_color")
        col.separator(type="LINE")

    @classmethod
    def _draw_displayhud_tab(cls, layout, data):
        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("explosiafx_display_draw_voxelgrid", {}).get(
            "use_property_split", True
        )
        col.prop(data, "explosiafx_display_draw_voxelgrid")
        col.prop(data, "explosiafx_display_draw_domainbox")
        row = col.row()
        row.enabled = data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE
        row.prop(data, "explosiafx_display_draw_adaptivedomain")
        col.prop(data, "explosiafx_display_draw_solidvoxels")

        col.separator(type="LINE")

        col.prop(data, "explosiafx_display_draw_velocity")
        velocity_enabled = data.explosiafx_display_draw_velocity

        obj = bpy.context.object
        if obj:
            NexusGradient(obj, "explosiafx_display_velocity_speed_color").draw_ui(
                col, "Speed Color", enabled=velocity_enabled
            )
            NexusGradient(obj, "explosiafx_display_velocity_speed_alpha").draw_ui(
                col, "Speed Alpha", enabled=velocity_enabled
            )

        row = col.row()
        row.enabled = velocity_enabled
        row.prop(data, "explosiafx_display_velocity_speed_transparency")

        row = col.row()
        row.enabled = velocity_enabled
        row.prop(data, "explosiafx_display_velocity_speed_auto_range")

        speed_range_enabled = (
            velocity_enabled and not data.explosiafx_display_velocity_speed_auto_range
        )

        row = col.row()
        row.enabled = speed_range_enabled
        row.prop(data, "explosiafx_display_velocity_speed_min")

        row = col.row()
        row.enabled = speed_range_enabled
        row.prop(data, "explosiafx_display_velocity_speed_max")

        row = col.row()
        row.enabled = velocity_enabled
        row.prop(data, "explosiafx_display_velocity_trail_length")

    @classmethod
    def draw_render_section(cls, layout, data):
        box = layout.box()
        box.label(text="Render Output (Eevee / Cycles)")
        col = box.column()
        col.use_property_split = True
        col.prop(data, "explosiafx_render_volume_mode")
        sub = col.column()
        sub.enabled = data.explosiafx_render_volume_mode != "OFF"
        sub.prop(data, "explosiafx_render_cache_dir")
        sub.prop(data, "explosiafx_render_volume_obj", text="Volume Object")

    @classmethod
    def _draw_dynamics_padvect_tab(cls, layout, data):
        from ..ui import draw_nodetree

        ui_config = get_explosiafx_ui_config()

        draw_nodetree(
            layout,
            data,
            "explosiafx_padvect_objects",
            "explosiafx_padvect_objects_index",
            label="Emitters",
            draw_item_settings=ui_config.get("explosiafx_padvect_objects", {}).get(
                "draw_item_settings"
            ),
            menu_id=ui_config.get("explosiafx_padvect_objects", {}).get("menu_id"),
            allowed_types=ui_config.get("explosiafx_padvect_objects", {}).get("allowed_types"),
        )

    @classmethod
    def _draw_dynamics_modifiers_tab(cls, layout, data):
        from ..ui import draw_nodetree

        ui_config = get_explosiafx_ui_config()

        draw_nodetree(
            layout,
            data,
            "explosiafx_modifiers_objects",
            "explosiafx_modifiers_objects_index",
            label="Modifiers",
            draw_item_settings=None,
            menu_id=ui_config.get("explosiafx_modifiers_objects", {}).get("menu_id"),
            allowed_types=ui_config.get("explosiafx_modifiers_objects", {}).get("allowed_types"),
        )

    @classmethod
    def draw_dynamics_section(cls, layout, data):
        from ..properties.nx_explosiafx import (
            draw_explosiafx_force_layer_settings,
        )
        from ..ui import draw_nodetree

        row = layout.row(align=True)
        row.prop(data, "explosiafx_dynamics_tab", expand=True)

        tab = data.explosiafx_dynamics_tab
        if tab == "FORCES":
            draw_nodetree(
                layout,
                data,
                "explosiafx_force_layers",
                "explosiafx_force_layers_index",
                label="Forces",
                draw_item_settings=draw_explosiafx_force_layer_settings,
                menu_id="explosiafx_force_layers",
            )
        elif tab == "MODIFIERS":
            cls._draw_dynamics_modifiers_tab(layout, data)
        elif tab == "PADVECT":
            cls._draw_dynamics_padvect_tab(layout, data)

    @classmethod
    def post_sync(cls, obj, container, handle, props, scene, depsgraph=None, original_props=None):
        """Sync ExplosiaFX domain size explicitly (legacy behavior)."""
        from ..libs import theron
        from ..libs.theron_ids import get as get_id

        domain = props.explosiafx_domain_size
        theron.set_vector(
            container,
            get_id("ID_NX_EXPLOSIAFX_DOMAINSIZE"),
            domain[0],
            domain[1],
            domain[2],
        )

        _remove_unused_explosiafx_poly_cache(obj, container, props, scene, depsgraph)

    @classmethod
    def get_gradient_specs(cls):
        return EFX_GRADIENT_SPECS

    @classmethod
    def draw_ui(cls, layout, data):
        row = layout.row(align=True)
        row.prop(data, "explosiafx_object_tab", expand=True)

        tab = data.explosiafx_object_tab
        if tab == "SIMULATION":
            cls._draw_simulation_tab(layout, data)
        elif tab == "SOURCES":
            cls._draw_sources_tab(layout, data)
        elif tab == "COLLIDERS":
            cls._draw_colliders_tab(layout, data)
        elif tab == "SOLVER":
            cls._draw_solver_tab(layout, data)

    @classmethod
    def _draw_simulation_tab(cls, layout, data):
        from ..libs import theron

        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_VOXELSIZE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_VOXELSIZE")
        col.prop(data, "explosiafx_domain_size")
        col.separator(type="LINE")
        col.prop(data, "ID_NX_EXPLOSIAFX_UPRES")
        col.prop(data, "ID_NX_EXPLOSIAFX_RETIME")
        col.separator(type="LINE")

        voxel_size = getattr(data, "ID_NX_EXPLOSIAFX_VOXELSIZE", 0.1)
        domain_size_raw = Vector(getattr(data, "explosiafx_domain_size", (2.0, 2.0, 2.0)))
        # Theron is the single source of truth for grid resolution. If it's not yet reachable, fall
        # back to floor(L/dx) as a coarse preview so the UI panel still shows something meaningful.
        reg = theron.get_efx_regularizeddomain(
            float(domain_size_raw.x),
            float(domain_size_raw.y),
            float(domain_size_raw.z),
            float(voxel_size),
        )
        if reg is not None:
            (nx, ny, nz) = reg[1]
        elif voxel_size > 0:
            nx = max(1, int(domain_size_raw.x / voxel_size))
            ny = max(1, int(domain_size_raw.y / voxel_size))
            nz = max(1, int(domain_size_raw.z / voxel_size))
        else:
            nx, ny, nz = 1, 1, 1
        col.label(text="Memory Stats")
        flow = col.grid_flow(columns=2, row_major=True, align=True)
        flow.use_property_split = ui_config.get("explosiafx_memory_stats", {}).get(
            "use_property_split", True
        )
        upresMult = getattr(data, "ID_NX_EXPLOSIAFX_UPRES", 1)
        flow.label(text="Voxel Grid:")
        flow.label(text="({} x {} x {})".format(nx, ny, nz))
        if upresMult > 1:
            flow.label(text="Upscaled Grid:")
            flow.label(
                text="({} x {} x {})".format(nx * upresMult, ny * upresMult, nz * upresMult)
            )
        if theron.is_initialized():
            numPropFields = 0
            if getattr(data, "ID_NX_EXPLOSIAFX_CHANNEL_SMOKE", False):
                numPropFields += 1
            if getattr(data, "ID_NX_EXPLOSIAFX_CHANNEL_TEMP", False):
                numPropFields += 1
            if getattr(data, "ID_NX_EXPLOSIAFX_CHANNEL_FUEL", False):
                numPropFields += 1
            if getattr(data, "ID_NX_EXPLOSIAFX_CHANNEL_COLOR", False):
                numPropFields += 3
            try:
                vram = theron.get_efx_vram_persistent_GiB(nx, ny, nz, upresMult, numPropFields)
                flow.label(text="Est. Persistent VRAM:")
                flow.label(text="{:.2f} GiB".format(vram))
            except Exception as e:
                print(f"nx_explosiafx: VRAM estimate error: {e}")
            try:
                vram = theron.get_efx_vram_peak_GiB(nx, ny, nz, upresMult, numPropFields)
                flow.label(text="Est. Peak VRAM:")
                flow.label(text="{:.2f} GiB".format(vram))
            except Exception as e:
                print(f"nx_explosiafx: VRAM estimate error: {e}")
        col.separator(type="LINE")

        box = layout.box()

        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_simulation_burning_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_simulation_burning_expanded",
            icon="TRIA_DOWN" if data.explosiafx_simulation_burning_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Burning")

        if data.explosiafx_simulation_burning_expanded:
            col = box.column()
            col.use_property_split = ui_config.get(
                "explosiafx_simulation_burning_burnrate", {}
            ).get("use_property_split", True)
            col.prop(data, "ID_NX_EXPLOSIAFX_NXBURNING_BURNRATE")
            col.prop(data, "ID_NX_EXPLOSIAFX_NXBURNING_TEMPPRODUCTION")
            col.prop(data, "ID_NX_EXPLOSIAFX_NXBURNING_SMOKEPRODUCTION")
            col.prop(data, "ID_NX_EXPLOSIAFX_NXBURNING_GASEXPANSION")
            col.prop(data, "ID_NX_EXPLOSIAFX_NXBURNING_IGNITIONTEMP")

        box = layout.box()

        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_simulation_ambient_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_simulation_ambient_expanded",
            icon="TRIA_DOWN" if data.explosiafx_simulation_ambient_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Ambient Conditions")

        if data.explosiafx_simulation_ambient_expanded:
            col = box.column()
            col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_AMBIENT_TEMP", {}).get(
                "use_property_split", True
            )
            col.prop(data, "ID_NX_EXPLOSIAFX_AMBIENT_TEMP")
            col.prop(data, "ID_NX_EXPLOSIAFX_AMBIENT_FUEL")

        box = layout.box()
        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_simulation_diffusion_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_simulation_diffusion_expanded",
            icon="TRIA_DOWN" if data.explosiafx_simulation_diffusion_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Diffusion")

        if data.explosiafx_simulation_diffusion_expanded:
            col = box.column()
            col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_DIFFUSION_TEMP", {}).get(
                "use_property_split", True
            )
            col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSION_SMOKE")
            col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSION_TEMP")
            col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSION_FUEL")
            col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSION_VISCOSITY")

        box = layout.box()
        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_simulation_dissipation_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_simulation_dissipation_expanded",
            icon="TRIA_DOWN" if data.explosiafx_simulation_dissipation_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Dissipation")

        if data.explosiafx_simulation_dissipation_expanded:
            col = box.column()
            col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_DISSIPATION_SMOKE", {}).get(
                "use_property_split", True
            )
            col.prop(data, "ID_NX_EXPLOSIAFX_DISSIPATION_SMOKE")
            col.prop(data, "ID_NX_EXPLOSIAFX_DISSIPATION_TEMP")
            col.prop(data, "ID_NX_EXPLOSIAFX_DISSIPATION_FUEL")
            col.prop(data, "ID_NX_EXPLOSIAFX_DISSIPATION_VELOCITY_DAMP")

        box = layout.box()
        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_simulation_buoyancy_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_simulation_buoyancy_expanded",
            icon="TRIA_DOWN" if data.explosiafx_simulation_buoyancy_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Buoyancy")

        if data.explosiafx_simulation_buoyancy_expanded:
            col = box.column()
            col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_BUOYANCY_GRAVITY", {}).get(
                "use_property_split", True
            )
            col.prop(data, "ID_NX_EXPLOSIAFX_BUOYANCY_GRAVITY")
            col.prop(data, "ID_NX_EXPLOSIAFX_BUOYANCY_SMOKE")
            col.prop(data, "ID_NX_EXPLOSIAFX_BUOYANCY_TEMP")
            col.prop(data, "ID_NX_EXPLOSIAFX_BUOYANCY_FUEL")

    @classmethod
    def _draw_sources_tab(cls, layout, data):
        from ..ui import draw_nodetree

        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_SOURCE_MOTIONGAPFILL", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_SOURCE_MOTIONGAPFILL")

        draw_nodetree(
            layout,
            data,
            "explosiafx_source_objects",
            "explosiafx_source_objects_index",
            label="Sources",
            draw_item_settings=ui_config.get("explosiafx_source_objects", {}).get(
                "draw_item_settings"
            ),
            menu_id=ui_config.get("explosiafx_source_objects", {}).get("menu_id"),
            allowed_types=ui_config.get("explosiafx_source_objects", {}).get("allowed_types"),
        )

    @classmethod
    def _draw_colliders_tab(cls, layout, data):
        from ..ui import draw_nodetree

        ui_config = get_explosiafx_ui_config()

        draw_nodetree(
            layout,
            data,
            "explosiafx_collider_objects",
            "explosiafx_collider_objects_index",
            label="Colliders",
            draw_item_settings=ui_config.get("explosiafx_collider_objects", {}).get(
                "draw_item_settings"
            ),
            menu_id=ui_config.get("explosiafx_collider_objects", {}).get("menu_id"),
            allowed_types=ui_config.get("explosiafx_collider_objects", {}).get("allowed_types"),
        )

    @classmethod
    def _draw_solver_tab(cls, layout, data):
        ui_config = get_explosiafx_ui_config()

        col = layout.column()
        col.label(text="Active Channels")

        col.use_property_split = True
        flow = col.grid_flow(
            row_major=False, columns=2, even_columns=False, even_rows=False, align=False
        )
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(data, "ID_NX_EXPLOSIAFX_CHANNEL_SMOKE")
        flow.prop(data, "ID_NX_EXPLOSIAFX_CHANNEL_FUEL")
        flow.prop(data, "ID_NX_EXPLOSIAFX_CHANNEL_TEMP")
        flow.prop(data, "ID_NX_EXPLOSIAFX_CHANNEL_COLOR")

        col.separator(type="LINE")

        col = layout.column()
        col.label(text="Pressure Solver")
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_PRESSUREACCURACY", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_PRESSUREACCURACY")
        col.prop(data, "ID_NX_EXPLOSIAFX_PRESSUREITERS")

        col = layout.column()
        col.label(text="Diffusion Solver")
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_DIFFUSIONACCURACY", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSIONACCURACY")
        col.prop(data, "ID_NX_EXPLOSIAFX_DIFFUSIONITERS")

        col = layout.column()
        col.label(text="Advection Accuracy")
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_CFLNUMBER", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_CFLNUMBER")
        col.prop(data, "ID_NX_EXPLOSIAFX_MINSUBSTEPS")
        col.prop(data, "ID_NX_EXPLOSIAFX_MAXSUBSTEPS")

        col = layout.column()
        col.label(text="Advection Solver")
        col.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_ADVECTION_SMOKE", {}).get(
            "use_property_split", True
        )
        col.prop(data, "ID_NX_EXPLOSIAFX_ADVECTION_SMOKE")
        col.prop(data, "ID_NX_EXPLOSIAFX_ADVECTION_TEMP")
        col.prop(data, "ID_NX_EXPLOSIAFX_ADVECTION_FUEL")
        col.prop(data, "ID_NX_EXPLOSIAFX_ADVECTION_VELOCITY")
        col.prop(data, "ID_NX_EXPLOSIAFX_ADVECTION_COLOR")

        box = layout.box()

        header = box.row()
        header.use_property_split = ui_config.get(
            "explosiafx_solver_adaptivebounds_expanded", {}
        ).get("use_property_split", True)
        header.prop(
            data,
            "explosiafx_solver_adaptivebounds_expanded",
            icon="TRIA_DOWN" if data.explosiafx_solver_adaptivebounds_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Adaptive Bounds")
        if data.explosiafx_solver_adaptivebounds_expanded:
            col = box.column()
            flow = col.grid_flow(columns=2, row_major=True, even_columns=True, align=True)
            flow.use_property_split = ui_config.get(
                "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE", {}
            ).get("use_property_split", True)
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE")
            adt_enabled = data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE
            extravoxels_row = flow.row()
            extravoxels_row.enabled = adt_enabled
            extravoxels_row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_EXTRAVOXELS")
            #
            col.separator(type="LINE")
            #
            col.label(text="Track channels:")
            flow = box.grid_flow(columns=2, row_major=True, even_columns=True, align=True)
            flow.use_property_split = ui_config.get(
                "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE", {}
            ).get("use_property_split", True)
            flow.enabled = adt_enabled
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE")
            #
            row = flow.row()
            row.enabled = adt_enabled and data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKSMOKE
            row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_SMOKETHRESH")
            #
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKTEMP")
            row = flow.row()
            row.enabled = adt_enabled and data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKTEMP
            row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TEMPTHRESH")
            #
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKFUEL")
            row = flow.row()
            row.enabled = adt_enabled and data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKFUEL
            row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_FUELTHRESH")
            #
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKVEL")
            row = flow.row()
            row.enabled = adt_enabled and data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKVEL
            row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_VELTHRESH")
            #
            flow.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKCOLOR")
            row = flow.row()
            row.enabled = adt_enabled and data.ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_TRACKCOLOR
            row.prop(data, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_COLORTHRESH")

        box = layout.box()

        header = box.row()
        header.use_property_split = ui_config.get("explosiafx_solver_walls_expanded", {}).get(
            "use_property_split", True
        )
        header.prop(
            data,
            "explosiafx_solver_walls_expanded",
            icon="TRIA_DOWN" if data.explosiafx_solver_walls_expanded else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        header.label(text="Domain Boundary Walls")

        if data.explosiafx_solver_walls_expanded:
            flow = box.grid_flow(columns=3, row_major=False, align=True)
            flow.use_property_split = ui_config.get("ID_NX_EXPLOSIAFX_WALLS_XPLUS", {}).get(
                "use_property_split", True
            )
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_XPLUS")
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_XMINUS")
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_YPLUS")
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_YMINUS")
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_ZPLUS")
            flow.prop(data, "ID_NX_EXPLOSIAFX_WALLS_ZMINUS")

    @classmethod
    def _draw_base_grid(
        cls,
        shader,
        mx,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []
        z = -half.z

        for i in range(1, nx):
            x = -half.x + i * voxel_size
            lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        for j in range(1, ny):
            y = -half.y + j * voxel_size
            lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def _find_back_face(cls, context, obj) -> str:
        view_matrix = context.region_data.view_matrix
        view_forward = Vector((view_matrix[2][0], view_matrix[2][1], view_matrix[2][2]))

        obj_rot = obj.matrix_world.to_3x3().normalized()
        face_normals = {
            "x_pos": obj_rot @ Vector((1, 0, 0)),
            "x_neg": obj_rot @ Vector((-1, 0, 0)),
            "y_pos": obj_rot @ Vector((0, 1, 0)),
            "y_neg": obj_rot @ Vector((0, -1, 0)),
            "z_pos": obj_rot @ Vector((0, 0, 1)),
            "z_neg": obj_rot @ Vector((0, 0, -1)),
        }

        best_face = "z_neg"
        best_dot = 2.0
        for face_id, normal in face_normals.items():
            dot = normal.dot(view_forward)
            if dot < best_dot:
                best_dot = dot
                best_face = face_id

        return best_face

    @classmethod
    def _draw_face_grid(
        cls,
        shader,
        mx,
        face_id: str,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []

        if face_id == "x_pos":
            x = half.x
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        elif face_id == "x_neg":
            x = -half.x
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        elif face_id == "y_pos":
            y = half.y
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "y_neg":
            y = -half.y
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))
            for k in range(1, nz):
                z = -half.z + k * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "z_pos":
            z = half.z
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        elif face_id == "z_neg":
            z = -half.z
            for i in range(1, nx):
                x = -half.x + i * voxel_size
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))
            for j in range(1, ny):
                y = -half.y + j * voxel_size
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def _draw_voxel_grid(
        cls,
        shader,
        mx,
        half: Vector,
        num_voxels: Tuple[int, int, int],
        voxel_size: float,
    ) -> None:
        nx, ny, nz = num_voxels
        lines = []

        # Z-direction lines — skip corner edges (x and y both at boundary)
        for i in range(nx + 1):
            x = -half.x + i * voxel_size
            x_boundary = i == 0 or i == nx
            for j in range(ny + 1):
                y = -half.y + j * voxel_size
                if x_boundary and (j == 0 or j == ny):
                    continue
                lines.append((mx @ Vector((x, y, -half.z)), mx @ Vector((x, y, half.z))))

        # Y-direction lines — skip corner edges (x and z both at boundary)
        for i in range(nx + 1):
            x = -half.x + i * voxel_size
            x_boundary = i == 0 or i == nx
            for k in range(nz + 1):
                z = -half.z + k * voxel_size
                if x_boundary and (k == 0 or k == nz):
                    continue
                lines.append((mx @ Vector((x, -half.y, z)), mx @ Vector((x, half.y, z))))

        # X-direction lines — skip corner edges (y and z both at boundary)
        for j in range(ny + 1):
            y = -half.y + j * voxel_size
            y_boundary = j == 0 or j == ny
            for k in range(nz + 1):
                z = -half.z + k * voxel_size
                if y_boundary and (k == 0 or k == nz):
                    continue
                lines.append((mx @ Vector((-half.x, y, z)), mx @ Vector((half.x, y, z))))

        shader.uniform_float("color", XP_COLOR_GRID)
        draw_lines(shader, lines)

    @classmethod
    def draw_viewport(cls, obj: bpy.types.Object, props, context) -> None:
        from ..libs import theron

        voxel_size = getattr(props, "ID_NX_EXPLOSIAFX_VOXELSIZE", 0.04)
        domain_size_raw = Vector(getattr(props, "explosiafx_domain_size", (4.0, 4.0, 4.0)))

        # Theron is the single source of truth for the regularized domain extent
        # and voxel counts. If the engine isn't reachable yet, fall back to the
        # raw domain and simplified floor(L/dx) voxel count so the box
        # and grid overlays still draw.
        reg = theron.get_efx_regularizeddomain(
            float(domain_size_raw.x),
            float(domain_size_raw.y),
            float(domain_size_raw.z),
            float(voxel_size),
        )
        if reg is not None:
            domain_size = Vector(reg[0])
            num_voxels = reg[1]
        elif voxel_size > 0:
            domain_size = domain_size_raw.copy()
            num_voxels = (
                max(1, int(domain_size_raw.x / voxel_size)),
                max(1, int(domain_size_raw.y / voxel_size)),
                max(1, int(domain_size_raw.z / voxel_size)),
            )
        else:
            domain_size = domain_size_raw.copy()
            num_voxels = (1, 1, 1)

        half = domain_size / 2.0

        mx = obj.matrix_world.copy()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(1.5)

        corners = [
            Vector((-half.x, -half.y, -half.z)),  # 0: back-left-bottom
            Vector((half.x, -half.y, -half.z)),  # 1: back-right-bottom
            Vector((half.x, half.y, -half.z)),  # 2: front-right-bottom
            Vector((-half.x, half.y, -half.z)),  # 3: front-left-bottom
            Vector((-half.x, -half.y, half.z)),  # 4: back-left-top
            Vector((half.x, -half.y, half.z)),  # 5: back-right-top
            Vector((half.x, half.y, half.z)),  # 6: front-right-top
            Vector((-half.x, half.y, half.z)),  # 7: front-left-top
        ]
        world_corners = [mx @ c for c in corners]

        draw_box = getattr(props, "explosiafx_display_draw_domainbox", True)
        if draw_box:
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

            # Write depth so the volume slicer's LESS_EQUAL test fails on line pixels.
            prev_depth_test = gpu.state.depth_test_get()
            prev_depth_mask = gpu.state.depth_mask_get()
            try:
                gpu.state.depth_test_set("LESS_EQUAL")
                gpu.state.depth_mask_set(True)
                shader.uniform_float("color", XP_COLOR_MODS_BLUE)
                draw_lines(shader, box_edges)
            finally:
                gpu.state.depth_test_set(prev_depth_test)
                gpu.state.depth_mask_set(prev_depth_mask)

            # Add corner decorators
            corner_len = min(0.25, min(half.x, half.y, half.z) * 0.5)

            corner_lines = []
            corner_dirs = [
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],  # 0
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))],  # 1
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],  # 2
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))],  # 3
                [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],  # 4
                [Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, -1))],  # 5
                [Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],  # 6
                [Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))],  # 7
            ]

            for i, corner in enumerate(corners):
                world_corner = mx @ corner
                for direction in corner_dirs[i]:
                    end_local = corner + direction * corner_len
                    end_world = mx @ end_local
                    corner_lines.append((world_corner, end_world))

            draw_thick_lines(context, corner_lines, XP_COLOR_MODS_RED, 4.0)

        draw_grid = getattr(props, "explosiafx_display_draw_voxelgrid", "NONE")
        if draw_grid != "NONE":
            if draw_grid == "BASE":
                cls._draw_base_grid(shader, mx, half, num_voxels, voxel_size)
            elif draw_grid == "BACK":
                back_face = cls._find_back_face(context, obj)
                cls._draw_face_grid(shader, mx, back_face, half, num_voxels, voxel_size)
            elif draw_grid == "BASEANDBACK":
                cls._draw_base_grid(shader, mx, half, num_voxels, voxel_size)
                back_face = cls._find_back_face(context, obj)
                if back_face != "z_neg":
                    cls._draw_face_grid(shader, mx, back_face, half, num_voxels, voxel_size)
            elif draw_grid == "VOXELS":
                cls._draw_voxel_grid(shader, mx, half, num_voxels, voxel_size)

        draw_solidvoxels = getattr(props, "explosiafx_display_draw_solidvoxels", False)
        if context.scene.frame_current <= 1:
            draw_solidvoxels = False
        if draw_solidvoxels:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    result = theron.get_efx_solidsdf_voxelvertex(modifier_handle)
                    if result is not None:
                        # dx is Theron's actual voxel size; use it (not the UI value)
                        # for any spatial positioning of returned data.
                        flat_data, resolution, dx = result
                        nx, ny, nz = resolution

                        # Do not attempt to draw the solid voxels if the simulation data is stale
                        # i.e., voxel grid spec change since theron last ran a step
                        if num_voxels[0] == nx and num_voxels[1] == ny and num_voxels[2] == nz:
                            # Collect voxel vertex coordinates that are inside colliders
                            # Use Numpy to efficiently collect the list of coordinates
                            flat = np.asarray(flat_data, dtype=np.float32).reshape(
                                nz + 1, ny + 1, nx + 1
                            )
                            iz_idx, iy_idx, ix_idx = np.where(flat < 0.0)

                            local_x = (-half.x + ix_idx * dx).astype(np.float32)
                            local_y = (-half.y + iy_idx * dx).astype(np.float32)
                            local_z = (-half.z + iz_idx * dx).astype(np.float32)

                            R = np.array(mx.to_3x3(), dtype=np.float32)
                            t = np.array(mx.translation, dtype=np.float32)
                            local_pts = np.stack([local_x, local_y, local_z], axis=1)
                            # batch_for_shader accepts numpy arrays directly
                            solid_points = local_pts @ R.T + t

                            # Batched drawing
                            if len(solid_points):
                                gpu.state.point_size_set(6.0)
                                batch = batch_for_shader(shader, "POINTS", {"pos": solid_points})
                                shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0))
                                gpu.state.depth_test_set("LESS_EQUAL")
                                batch.draw(shader)
                                gpu.state.depth_test_set("NONE")
                except Exception as exc:
                    print(f"[nxExplosiaFX] solid sdf field fetch failed: {exc}")

        draw_adaptivebounds = getattr(props, "explosiafx_display_draw_adaptivedomain", False)
        if not getattr(props, "ID_NX_EXPLOSIAFX_ADAPTIVEBOUNDS_ENABLE", True):
            draw_adaptivebounds = False
        if context.scene.frame_current <= 1:
            draw_adaptivebounds = False
        if draw_adaptivebounds:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    result = theron.get_efx_voxelisactive(modifier_handle)
                    if result is not None:
                        # dx is Theron's actual voxel size. use This (not the UI value)
                        # for any spatial positioning of returned data.
                        flat_data, resolution, dx = result
                        nx, ny, nz = resolution

                        # Do not attempt to draw the adaptive bounds voxels
                        # if the simulation data is stale i.e., voxel grid spec
                        # change since theron last ran a step
                        if num_voxels[0] == nx and num_voxels[1] == ny and num_voxels[2] == nz:
                            flat = np.asarray(flat_data, dtype=np.float32).reshape(nz, ny, nx)
                            a = flat == 1  # boolean active mask, shape (nz, ny, nx)

                            vs = np.float32(dx)
                            hx = np.float32(half.x)
                            hy = np.float32(half.y)
                            hz = np.float32(half.z)

                            # Per-face draw masks: active voxel whose neighbor in that
                            # direction is inactive (or is at the grid boundary).
                            # np.pad fills with 0 (inactive) at boundaries.
                            xm = a & ~np.pad(a, ((0, 0), (0, 0), (1, 0)))[:, :, :nx]
                            xp = a & ~np.pad(a, ((0, 0), (0, 0), (0, 1)))[:, :, 1:]
                            ym = a & ~np.pad(a, ((0, 0), (1, 0), (0, 0)))[:, :ny, :]
                            yp = a & ~np.pad(a, ((0, 0), (0, 1), (0, 0)))[:, 1:, :]
                            zm = a & ~np.pad(a, ((1, 0), (0, 0), (0, 0)))[:nz, :, :]
                            zp = a & ~np.pad(a, ((0, 1), (0, 0), (0, 0)))[1:, :, :]

                            # 4 corners per face as (xi, yi, zi) selectors into [lo, hi] arrays.
                            # Edges drawn are AB, BC, CD, DA (one square outline per face).
                            face_defs = [
                                (xm, ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1))),
                                (xp, ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
                                (ym, ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
                                (yp, ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1))),
                                (zm, ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))),
                                (zp, ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
                            ]

                            segments = []
                            for mask, corners in face_defs:
                                iz_idx, iy_idx, ix_idx = np.where(mask)
                                if len(ix_idx) == 0:
                                    continue
                                x_lo = -hx + ix_idx.astype(np.float32) * vs
                                y_lo = -hy + iy_idx.astype(np.float32) * vs
                                z_lo = -hz + iz_idx.astype(np.float32) * vs
                                # xs/ys/zs: shape (2, n) — index 0 = lo, 1 = hi
                                xs = np.stack([x_lo, x_lo + vs])
                                ys = np.stack([y_lo, y_lo + vs])
                                zs = np.stack([z_lo, z_lo + vs])
                                c = corners
                                A = np.stack([xs[c[0][0]], ys[c[0][1]], zs[c[0][2]]], axis=1)
                                B = np.stack([xs[c[1][0]], ys[c[1][1]], zs[c[1][2]]], axis=1)
                                C = np.stack([xs[c[2][0]], ys[c[2][1]], zs[c[2][2]]], axis=1)
                                D = np.stack([xs[c[3][0]], ys[c[3][1]], zs[c[3][2]]], axis=1)
                                # np.stack produces (n, 8, 3); reshape to (8n, 3) for LINES
                                segments.append(
                                    np.stack([A, B, B, C, C, D, D, A], axis=1).reshape(-1, 3)
                                )

                            if segments:
                                R = np.array(mx.to_3x3(), dtype=np.float32)
                                t = np.array(mx.translation, dtype=np.float32)
                                all_verts = np.concatenate(segments, axis=0)
                                world_verts = all_verts @ R.T + t
                                batch = batch_for_shader(shader, "LINES", {"pos": world_verts})
                                shader.uniform_float("color", (0.0, 0.71, 1.0, 0.2))
                                gpu.state.depth_test_set("LESS_EQUAL")
                                batch.draw(shader)
                                gpu.state.depth_test_set("NONE")
                except Exception as exc:
                    print(f"[nxExplosiaFX] adaptive domain field fetch failed: {exc}")

        draw_velocity = getattr(props, "explosiafx_display_draw_velocity", False)
        if context.scene.frame_current <= 1:
            draw_velocity = False
        if draw_velocity:
            import numpy as np
            from gpu_extras.batch import batch_for_shader

            from ..handlers.pipeline import get_modifier_handle
            from ..libs import theron

            modifier_handle = get_modifier_handle(context.scene, obj)

            if theron.is_initialized() and modifier_handle is not None:
                try:
                    vel_result = theron.get_efx_velocity(modifier_handle)
                    if vel_result is not None:
                        # vel_dx is Theron's actual voxel size; use it (not the UI
                        # value) for spatial positioning.
                        flat_u_data, flat_v_data, flat_w_data, vel_resolution, vel_dx = vel_result
                        nx, ny, nz = vel_resolution

                        if num_voxels[0] == nx and num_voxels[1] == ny and num_voxels[2] == nz:
                            flat_u = np.asarray(flat_u_data, dtype=np.float32).reshape(
                                nz, ny, (nx + 1)
                            )
                            flat_v = np.asarray(flat_v_data, dtype=np.float32).reshape(
                                nz, (ny + 1), nx
                            )
                            flat_w = np.asarray(flat_w_data, dtype=np.float32).reshape(
                                (nz + 1), ny, nx
                            )
                            cls._draw_velocity_trails(
                                obj,
                                props,
                                mx,
                                half,
                                vel_dx,
                                nx,
                                ny,
                                nz,
                                flat_u,
                                flat_v,
                                flat_w,
                            )
                except Exception as exc:
                    print(f"[nxExplosiaFX] liquid velocity field fetch failed: {exc}")

        gpu.state.blend_set("NONE")
        gpu.state.line_width_set(1.0)

    @staticmethod
    def _trilinear(arr, gz, gy, gx, max_iz, max_iy, max_ix):
        """Trilinear sample a (nz, ny, nx) array at fractional indices (gz, gy, gx).

        Out-of-range fractional indices are clamped to the array bounds.
        """
        gz_c = np.clip(gz, 0.0, float(max_iz))
        gy_c = np.clip(gy, 0.0, float(max_iy))
        gx_c = np.clip(gx, 0.0, float(max_ix))
        iz0 = np.floor(gz_c).astype(np.int32)
        iy0 = np.floor(gy_c).astype(np.int32)
        ix0 = np.floor(gx_c).astype(np.int32)
        iz1 = np.minimum(iz0 + 1, max_iz)
        iy1 = np.minimum(iy0 + 1, max_iy)
        ix1 = np.minimum(ix0 + 1, max_ix)
        fz = (gz_c - iz0).astype(np.float32)
        fy = (gy_c - iy0).astype(np.float32)
        fx = (gx_c - ix0).astype(np.float32)

        c000 = arr[iz0, iy0, ix0]
        c001 = arr[iz0, iy0, ix1]
        c010 = arr[iz0, iy1, ix0]
        c011 = arr[iz0, iy1, ix1]
        c100 = arr[iz1, iy0, ix0]
        c101 = arr[iz1, iy0, ix1]
        c110 = arr[iz1, iy1, ix0]
        c111 = arr[iz1, iy1, ix1]

        c00 = c000 * (1.0 - fx) + c001 * fx
        c01 = c010 * (1.0 - fx) + c011 * fx
        c10 = c100 * (1.0 - fx) + c101 * fx
        c11 = c110 * (1.0 - fx) + c111 * fx

        c0 = c00 * (1.0 - fy) + c01 * fy
        c1 = c10 * (1.0 - fy) + c11 * fy

        return c0 * (1.0 - fz) + c1 * fz

    @classmethod
    def _draw_velocity_trails(
        cls,
        obj,
        props,
        mx,
        half: Vector,
        voxel_size: float,
        nx: int,
        ny: int,
        nz: int,
        flat_u,
        flat_v,
        flat_w,
    ) -> None:
        from gpu_extras.batch import batch_for_shader

        vs = float(voxel_size)
        if vs <= 0.0:
            return

        # Trail length and segment count
        trail_length = float(getattr(props, "explosiafx_display_velocity_trail_length", 0.2))
        seg_length = vs * 0.3
        if seg_length <= 0.0 or trail_length <= 0.0:
            return
        num_segs = max(2, min(8, int(trail_length / seg_length)))
        seg_length = trail_length / float(num_segs)

        # Global transparency: 0% = LUT alpha unchanged, 100% = fully transparent.
        transparency = float(getattr(props, "explosiafx_display_velocity_speed_transparency", 0.0))
        alpha_scale = max(0.0, 1.0 - transparency / 100.0)
        if alpha_scale <= 0.0:
            return

        # Speed range: min/max of |component| over each MAC field
        # independently (not vector magnitude).
        if getattr(props, "explosiafx_display_velocity_speed_auto_range", True):
            max_speed = float(
                max(
                    np.abs(flat_u).max(),
                    np.abs(flat_v).max(),
                    np.abs(flat_w).max(),
                )
            )
            min_speed = float(
                min(
                    np.abs(flat_u).min(),
                    np.abs(flat_v).min(),
                    np.abs(flat_w).min(),
                )
            )
        else:
            min_speed = float(getattr(props, "explosiafx_display_velocity_speed_min", 0.0))
            max_speed = float(getattr(props, "explosiafx_display_velocity_speed_max", 1.0))

        speed_range = max_speed - min_speed
        inv_speed_range = 1.0 / speed_range if speed_range > 0.0 else 0.0

        # Pre-cache gradient lookups.
        color_lut = NexusGradient(obj, "explosiafx_display_velocity_speed_color").lut
        alpha_lut = NexusGradient(obj, "explosiafx_display_velocity_speed_alpha").lut
        if color_lut is None or alpha_lut is None:
            return

        seg_colors = np.zeros((num_segs, 3), dtype=np.float32)
        for s in range(num_segs):
            cidx = max(0, min(255, int((s / float(num_segs)) * 255.0)))
            seg_colors[s] = color_lut[cidx][:3]

        # Alpha is taken from the red channel of the alpha gradient.
        alpha_lut_r = np.array([alpha_lut[i][0] for i in range(256)], dtype=np.float32)

        # Every voxel participates as a trail seed.
        iz_seed, iy_seed, ix_seed = (a.ravel() for a in np.indices((nz, ny, nx)))
        if ix_seed.size == 0:
            return

        # Collocated voxel-center velocity from MAC face averages.
        u_c = 0.5 * (flat_u[iz_seed, iy_seed, ix_seed] + flat_u[iz_seed, iy_seed, ix_seed + 1])
        v_c = 0.5 * (flat_v[iz_seed, iy_seed, ix_seed] + flat_v[iz_seed, iy_seed + 1, ix_seed])
        w_c = 0.5 * (flat_w[iz_seed, iy_seed, ix_seed] + flat_w[iz_seed + 1, iy_seed, ix_seed])

        speed = np.sqrt(u_c * u_c + v_c * v_c + w_c * w_c)
        keep = speed > 1e-12
        if not np.any(keep):
            return

        ix_seed = ix_seed[keep]
        iy_seed = iy_seed[keep]
        iz_seed = iz_seed[keep]
        u_c = u_c[keep]
        v_c = v_c[keep]
        w_c = w_c[keep]
        speed = speed[keep]

        # Per-seed alpha based on the seed-cell relative speed.
        rel = np.clip((speed - min_speed) * inv_speed_range, 0.0, 1.0)
        a_idx = np.clip((rel * 255.0).astype(np.int32), 0, 255)
        seed_alpha = alpha_lut_r[a_idx] * np.float32(alpha_scale)

        # Initial start positions in object-centered coords (voxel centers).
        hx = np.float32(half.x)
        hy = np.float32(half.y)
        hz = np.float32(half.z)
        vsf = np.float32(vs)

        pos = np.empty((ix_seed.size, 3), dtype=np.float32)
        pos[:, 0] = -hx + (ix_seed.astype(np.float32) + 0.5) * vsf
        pos[:, 1] = -hy + (iy_seed.astype(np.float32) + 0.5) * vsf
        pos[:, 2] = -hz + (iz_seed.astype(np.float32) + 0.5) * vsf

        vel = np.stack([u_c, v_c, w_c], axis=1).astype(np.float32)

        half_arr = np.array([hx, hy, hz], dtype=np.float32)
        active = np.ones(ix_seed.size, dtype=bool)

        seg_starts: list = []
        seg_ends: list = []
        seg_cols: list = []

        for seg in range(num_segs):
            if not np.any(active):
                break

            s_now = np.linalg.norm(vel, axis=1)
            nonzero = s_now > 1e-12
            active = active & nonzero
            if not np.any(active):
                break

            safe_s = np.where(nonzero, s_now, 1.0).astype(np.float32)
            d = vel / safe_s[:, None]

            end = pos + d * np.float32(seg_length)

            # Clip trails whose end leaves the box; mark them to terminate.
            outside = active & np.any(np.abs(end) > half_arr, axis=1)
            if np.any(outside):
                cp = pos[outside]
                cd = d[outside]
                t_min = np.full(cp.shape[0], np.inf, dtype=np.float32)
                for axis in range(3):
                    d_axis = cd[:, axis]
                    p_axis = cp[:, axis]
                    target = np.where(d_axis > 0, half_arr[axis], -half_arr[axis])
                    with np.errstate(divide="ignore", invalid="ignore"):
                        t = (target - p_axis) / d_axis
                    t = np.where(np.isfinite(t) & (t > 0), t, np.inf)
                    t_min = np.minimum(t_min, t)
                t_clip = np.minimum(t_min, np.float32(seg_length))
                end[outside] = cp + cd * t_clip[:, None]

            draw_mask = active
            if np.any(draw_mask):
                seg_starts.append(pos[draw_mask].copy())
                seg_ends.append(end[draw_mask].copy())
                cols = np.empty((int(draw_mask.sum()), 4), dtype=np.float32)
                cols[:, :3] = seg_colors[seg]
                cols[:, 3] = seed_alpha[draw_mask]
                seg_cols.append(cols)

            # Continue only trails that drew this segment AND were not clipped.
            active = draw_mask & ~outside

            pos = end

            if seg < num_segs - 1 and np.any(active):
                # Trilinear sample of the MAC velocity at the new position.
                sp = pos + half_arr
                new_u = cls._trilinear(
                    flat_u,
                    sp[:, 2] / vsf - 0.5,
                    sp[:, 1] / vsf - 0.5,
                    sp[:, 0] / vsf,
                    nz - 1,
                    ny - 1,
                    nx,
                )
                new_v = cls._trilinear(
                    flat_v,
                    sp[:, 2] / vsf - 0.5,
                    sp[:, 1] / vsf,
                    sp[:, 0] / vsf - 0.5,
                    nz - 1,
                    ny,
                    nx - 1,
                )
                new_w = cls._trilinear(
                    flat_w,
                    sp[:, 2] / vsf,
                    sp[:, 1] / vsf - 0.5,
                    sp[:, 0] / vsf - 0.5,
                    nz,
                    ny - 1,
                    nx - 1,
                )
                vel = np.stack([new_u, new_v, new_w], axis=1).astype(np.float32)

        if not seg_starts:
            return

        starts = np.concatenate(seg_starts, axis=0)
        ends = np.concatenate(seg_ends, axis=0)
        cols = np.concatenate(seg_cols, axis=0)

        n = starts.shape[0]
        verts_local = np.empty((2 * n, 3), dtype=np.float32)
        verts_local[0::2] = starts
        verts_local[1::2] = ends
        vert_cols = np.empty((2 * n, 4), dtype=np.float32)
        vert_cols[0::2] = cols
        vert_cols[1::2] = cols

        R = np.array(mx.to_3x3(), dtype=np.float32)
        t = np.array(mx.translation, dtype=np.float32)
        world_verts = verts_local @ R.T + t

        color_shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        batch = batch_for_shader(color_shader, "LINES", {"pos": world_verts, "color": vert_cols})
        gpu.state.depth_test_set("LESS_EQUAL")
        batch.draw(color_shader)
        gpu.state.depth_test_set("NONE")
