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

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import mathutils


class CacheKind(Enum):
    POLY = "poly"
    LINE = "line"
    POLY_CONTAINER = "poly_container"
    CAMERA = "camera"
    TRAIL_SOURCE = "trail_source"


@dataclass(frozen=True)
class CacheSpec:
    kind: CacheKind
    collection_attr: str
    cache_dict: dict = field(repr=False, hash=False, compare=False)


def _free_entry(kind: CacheKind, entry: tuple) -> None:
    from . import theron

    if kind == CacheKind.POLY:
        theron.free_polygon_object(entry[0])
    elif kind == CacheKind.LINE:
        theron.free_line_object(entry[0])
    elif kind == CacheKind.POLY_CONTAINER:
        theron.free_polygon_object(entry[0])
        theron.free_container(entry[1])
    elif kind == CacheKind.CAMERA:
        theron.free_object(entry[0])
    elif kind == CacheKind.TRAIL_SOURCE:
        pipeline_handle, source_id = entry[0], entry[1]
        if pipeline_handle:
            theron.remove_trail_source(pipeline_handle, source_id)


def clear_cache(spec: CacheSpec, mod_name: str | None = None) -> None:
    if mod_name is None:
        for entry in spec.cache_dict.values():
            _free_entry(spec.kind, entry)
        spec.cache_dict.clear()
    else:
        for key in [k for k in spec.cache_dict if k[0] == mod_name]:
            _free_entry(spec.kind, spec.cache_dict.pop(key))


def ensure_poly_entry(
    spec: CacheSpec,
    mod_name: str,
    target_name: str,
    vertices,
    polygons,
    vc: int,
    pc: int,
    matrix=None,
) -> int | None:
    from . import theron

    cache_key = (mod_name, target_name)
    if cache_key in spec.cache_dict:
        poly_handle, prev_vc, prev_pc = spec.cache_dict[cache_key]
        if vc != prev_vc or pc != prev_pc:
            theron.resize_polygon_object(poly_handle, vc, pc)
            spec.cache_dict[cache_key] = (poly_handle, vc, pc)
        theron.update_polygon_object_points(poly_handle, vertices)
        if matrix is not None:
            theron.set_matrix(poly_handle, matrix)
        return poly_handle

    poly_handle = theron.create_polygon_object_with_data(vertices, polygons)
    if poly_handle is None:
        return None
    if matrix is not None:
        theron.set_matrix(poly_handle, matrix)
    spec.cache_dict[cache_key] = (poly_handle, vc, pc)
    return poly_handle


def ensure_line_entry(
    spec: CacheSpec,
    mod_name: str,
    target_name: str,
    vertices,
    segments,
    vc: int,
    sc: int,
    matrix=None,
) -> int | None:
    from . import theron

    cache_key = (mod_name, target_name)
    if cache_key in spec.cache_dict:
        prev_handle, prev_vc, prev_sc = spec.cache_dict[cache_key]
        if vc != prev_vc or sc != prev_sc:
            theron.free_line_object(prev_handle)
            line_handle = theron.create_line_object_with_data(vertices, segments)
            if line_handle is None:
                del spec.cache_dict[cache_key]
                return None
            if matrix is not None:
                theron.set_matrix(line_handle, matrix)
            spec.cache_dict[cache_key] = (line_handle, vc, sc)
            return line_handle
        theron.update_line_object_points(prev_handle, vertices)
        if matrix is not None:
            theron.set_matrix(prev_handle, matrix)
        return prev_handle

    line_handle = theron.create_line_object_with_data(vertices, segments)
    if line_handle is None:
        return None
    if matrix is not None:
        theron.set_matrix(line_handle, matrix)
    spec.cache_dict[cache_key] = (line_handle, vc, sc)
    return line_handle


def ensure_poly_container_entry(
    spec: CacheSpec,
    mod_name: str,
    target_name: str,
    vertices,
    polygons,
    vc: int,
    pc: int,
    *,
    on_new=None,
    matrix=None,
) -> tuple[int | None, int | None]:
    from . import theron

    cache_key = (mod_name, target_name)
    if cache_key in spec.cache_dict:
        poly_handle, container_handle, prev_vc, prev_pc = spec.cache_dict[cache_key]
        if vc != prev_vc or pc != prev_pc:
            theron.resize_polygon_object(poly_handle, vc, pc)
            spec.cache_dict[cache_key] = (poly_handle, container_handle, vc, pc)
        theron.update_polygon_object_points(poly_handle, vertices)
        if matrix is not None:
            theron.set_matrix(poly_handle, matrix)
        return poly_handle, container_handle

    poly_handle = theron.create_polygon_object_with_data(vertices, polygons)
    if poly_handle is None:
        return None, None
    if matrix is not None:
        theron.set_matrix(poly_handle, matrix)
    container_handle = theron.create_container()
    if container_handle is None:
        theron.free_polygon_object(poly_handle)
        return None, None
    if on_new is not None and not on_new(poly_handle, container_handle):
        theron.free_polygon_object(poly_handle)
        theron.free_container(container_handle)
        return None, None
    spec.cache_dict[cache_key] = (poly_handle, container_handle, vc, pc)
    return poly_handle, container_handle


def ensure_camera_entry(
    spec: CacheSpec,
    mod_name: str,
    cam_obj,
) -> int | None:
    from . import theron

    if cam_obj is None or cam_obj.type != "CAMERA" or cam_obj.data is None:
        return None

    cache_key = (mod_name, cam_obj.name)
    handle = spec.cache_dict.get(cache_key, (None,))[0]
    if handle is None:
        handle = theron.create_camera()
        if handle is None:
            return None
        spec.cache_dict[cache_key] = (handle,)

    # Awkwardly, Blender's camera points in -Z, rather than the +Y forwards direction. We rotate
    # the matrix before pushing to Theron to compensate.
    transformed = cam_obj.matrix_world @ mathutils.Matrix(
        [
            [0, 0, 1, 0],
            [-1, 0, 0, 0],
            [0, -1, 0, 0],
            [0, 0, 0, 1],
        ]
    )
    theron.set_matrix(handle, transformed)
    _push_camera_intrinsics(handle, cam_obj)
    return handle


def _push_camera_intrinsics(handle: int, cam_obj) -> None:
    from . import theron

    cam_data = cam_obj.data
    cam_type = cam_data.type

    if cam_type == "ORTHO":
        theron.set_camera_projection(handle, theron.CameraProjection.ORTHOGRAPHIC)
        half_x, half_y = _ortho_half_extents(cam_data)
        theron.set_camera_ortho_scale(handle, half_x, half_y)
        return

    projection = (
        theron.CameraProjection.PANORAMIC
        if cam_type == "PANO"
        else theron.CameraProjection.PERSPECTIVE
    )
    theron.set_camera_projection(handle, projection)
    fov_x, fov_y = _perspective_fovs(cam_data)
    theron.set_camera_fov(handle, fov_x, fov_y)


def _perspective_fovs(cam_data) -> tuple[float, float]:
    import math

    import bpy

    scene = bpy.context.scene
    corners = cam_data.view_frame(scene=scene)
    max_x = max(abs(c.x) for c in corners)
    max_y = max(abs(c.y) for c in corners)
    depth = max(abs(corners[0].z), 1e-9)
    return 2.0 * math.atan(max_x / depth), 2.0 * math.atan(max_y / depth)


def _ortho_half_extents(cam_data) -> tuple[float, float]:
    import bpy

    scene = bpy.context.scene
    render = scene.render
    aspect_x = render.resolution_x * render.pixel_aspect_x
    aspect_y = render.resolution_y * render.pixel_aspect_y
    if aspect_y <= 0.0:
        aspect = 1.0
    else:
        aspect = aspect_x / aspect_y

    ortho_scale = cam_data.ortho_scale
    sensor_fit = cam_data.sensor_fit

    if sensor_fit == "VERTICAL" or (sensor_fit == "AUTO" and aspect < 1.0):
        half_y = ortho_scale * 0.5
        half_x = half_y * aspect
    else:
        half_x = ortho_scale * 0.5
        if aspect > 0.0:
            half_y = half_x / aspect
        else:
            half_y = half_x

    return half_x, half_y


def evict_stale_entries_for(
    spec: CacheSpec,
    mod_name: str,
    active_names: set[str],
    *,
    entry_filter=None,
) -> None:
    stale = [
        key
        for key, entry in spec.cache_dict.items()
        if key[0] == mod_name
        and key[1] not in active_names
        and (entry_filter is None or entry_filter(key, entry))
    ]
    for key in stale:
        _free_entry(spec.kind, spec.cache_dict.pop(key))


def install_cache_hooks(cls) -> None:
    if "on_destroy" not in cls.__dict__:

        @classmethod
        def on_destroy(cls, mod_uid):
            for spec in cls.cache_specs:
                clear_cache(spec, mod_name=mod_uid)

        cls.on_destroy = on_destroy

    if "on_state_clear" not in cls.__dict__:

        @classmethod
        def on_state_clear(cls, *, free_resources=True):
            for spec in cls.cache_specs:
                if free_resources:
                    clear_cache(spec)
                else:
                    spec.cache_dict.clear()

        cls.on_state_clear = on_state_clear
