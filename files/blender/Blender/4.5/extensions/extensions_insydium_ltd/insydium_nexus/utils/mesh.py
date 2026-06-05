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

from typing import Optional

import bpy
import numpy as np


def extract_mesh_data(
    mesh_obj: bpy.types.Object,
    depsgraph: Optional[bpy.types.Depsgraph],
) -> Optional[tuple]:
    """Extract local-space vertices, polygons and world matrix from a mesh object.

    Returns (vertices, polygons, vertex_count, poly_count, world_matrix) or None.
    Vertices are in the object's local space; world_matrix is its mathutils.Matrix.
    Triangles use d=c convention, quads have all four unique indices. N-gons are
    tessellated into triangles.
    """
    try:
        eval_mesh_obj = mesh_obj.evaluated_get(depsgraph) if depsgraph else mesh_obj
        mesh = eval_mesh_obj.to_mesh()
        if mesh is None:
            return None

        try:
            vertex_count = len(mesh.vertices)
            poly_count_raw = len(mesh.polygons)

            if vertex_count == 0 or poly_count_raw == 0:
                return None

            local_co = np.empty(vertex_count * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", local_co)
            local_co = local_co.reshape(vertex_count, 3).astype(np.float64)

            world_matrix = mesh_obj.matrix_world

            loop_totals = np.empty(poly_count_raw, dtype=np.int32)
            loop_starts = np.empty(poly_count_raw, dtype=np.int32)
            mesh.polygons.foreach_get("loop_total", loop_totals)
            mesh.polygons.foreach_get("loop_start", loop_starts)

            loop_count = len(mesh.loops)
            loop_verts = np.empty(loop_count, dtype=np.int32)
            mesh.loops.foreach_get("vertex_index", loop_verts)

            # Fast path: uniform meshes (all-tri or all-quad) skip
            # masking and offset assembly entirely.
            min_lt = int(loop_totals.min())
            max_lt = int(loop_totals.max())

            if min_lt == max_lt == 3:
                # All tris — single vectorised gather.
                idx = loop_starts[:, np.newaxis] + np.arange(3, dtype=np.int32)
                raw = loop_verts[idx.ravel()].reshape(poly_count_raw, 3)
                polygons = np.empty((poly_count_raw, 4), dtype=np.int32)
                polygons[:, 0] = raw[:, 0]
                polygons[:, 1] = raw[:, 1]
                polygons[:, 2] = raw[:, 2]
                polygons[:, 3] = raw[:, 2]
                return (local_co, polygons, vertex_count, poly_count_raw, world_matrix)

            if min_lt == max_lt == 4:
                # All quads — single vectorised gather.
                idx = loop_starts[:, np.newaxis] + np.arange(4, dtype=np.int32)
                raw = loop_verts[idx.ravel()].reshape(poly_count_raw, 4)
                polygons = np.empty((poly_count_raw, 4), dtype=np.int32)
                polygons[:, 0] = raw[:, 0]
                polygons[:, 1] = raw[:, 1]
                polygons[:, 2] = raw[:, 2]
                polygons[:, 3] = raw[:, 3]
                return (local_co, polygons, vertex_count, poly_count_raw, world_matrix)

            # Mixed mesh — do classification
            tri_mask = loop_totals == 3
            quad_mask = loop_totals == 4

            tri_starts = loop_starts[tri_mask]
            tri_count = len(tri_starts)

            quad_starts = loop_starts[quad_mask]
            quad_count = len(quad_starts)

            # N-gons: tessellate when max_lt >= 5.
            ngon_tri_count = 0
            ngon_polys = np.empty((0, 4), dtype=np.int32)
            if max_lt >= 5:
                mesh.calc_loop_triangles()
                lt_count = len(mesh.loop_triangles)

                lt_poly_indices = np.empty(lt_count, dtype=np.int32)
                mesh.loop_triangles.foreach_get("polygon_index", lt_poly_indices)
                lt_vertices = np.empty(lt_count * 3, dtype=np.int32)
                mesh.loop_triangles.foreach_get("vertices", lt_vertices)
                lt_vertices = lt_vertices.reshape(lt_count, 3)

                # Boolean lookup
                is_ngon = np.zeros(poly_count_raw, dtype=np.bool_)
                is_ngon[loop_totals >= 5] = True
                lt_mask = is_ngon[lt_poly_indices]

                ngon_tris = lt_vertices[lt_mask]
                ngon_tri_count = len(ngon_tris)
                if ngon_tri_count > 0:
                    ngon_polys = np.empty((ngon_tri_count, 4), dtype=np.int32)
                    ngon_polys[:, 0] = ngon_tris[:, 0]
                    ngon_polys[:, 1] = ngon_tris[:, 1]
                    ngon_polys[:, 2] = ngon_tris[:, 2]
                    ngon_polys[:, 3] = ngon_tris[:, 2]

            total_poly_count = tri_count + quad_count + ngon_tri_count
            if total_poly_count == 0:
                return None

            polygons = np.empty((total_poly_count, 4), dtype=np.int32)
            offset = 0

            # Tris
            if tri_count > 0:
                idx = tri_starts[:, np.newaxis] + np.arange(3, dtype=np.int32)
                raw = loop_verts[idx.ravel()].reshape(tri_count, 3)
                polygons[offset : offset + tri_count, 0] = raw[:, 0]
                polygons[offset : offset + tri_count, 1] = raw[:, 1]
                polygons[offset : offset + tri_count, 2] = raw[:, 2]
                polygons[offset : offset + tri_count, 3] = raw[:, 2]
                offset += tri_count

            # Quads
            if quad_count > 0:
                idx = quad_starts[:, np.newaxis] + np.arange(4, dtype=np.int32)
                raw = loop_verts[idx.ravel()].reshape(quad_count, 4)
                polygons[offset : offset + quad_count, 0] = raw[:, 0]
                polygons[offset : offset + quad_count, 1] = raw[:, 1]
                polygons[offset : offset + quad_count, 2] = raw[:, 2]
                polygons[offset : offset + quad_count, 3] = raw[:, 3]
                offset += quad_count

            # N-gon tessellated tris.
            if ngon_tri_count > 0:
                polygons[offset : offset + ngon_tri_count] = ngon_polys

            return (local_co, polygons, vertex_count, total_poly_count, world_matrix)

        finally:
            eval_mesh_obj.to_mesh_clear()

    except Exception as e:
        print(f"nexus: mesh extract error for '{mesh_obj.name}': {e}")
        return None


def extract_mesh_loop_data(
    mesh_obj: bpy.types.Object,
    depsgraph: Optional[bpy.types.Depsgraph],
) -> Optional[tuple]:
    """Returns (loop_positions, corner_normals, smooth_normals, tri_idx,
    loop_count, tri_count) or None. Corners are not deduplicated so per-polygon
    smooth/flat flags are preserved in the corner normals."""
    try:
        eval_obj = mesh_obj.evaluated_get(depsgraph) if depsgraph else mesh_obj
        mesh = eval_obj.to_mesh()
        if mesh is None:
            return None
        try:
            vc = len(mesh.vertices)
            if vc == 0 or len(mesh.polygons) == 0:
                return None

            mesh.calc_loop_triangles()
            tri_count = len(mesh.loop_triangles)
            if tri_count == 0:
                return None
            loop_count = tri_count * 3

            vertex_co = np.empty(vc * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", vertex_co)
            vertex_co = vertex_co.reshape(vc, 3)

            vertex_normals = np.empty(vc * 3, dtype=np.float32)
            mesh.vertex_normals.foreach_get("vector", vertex_normals)
            vertex_normals = vertex_normals.reshape(vc, 3)

            mesh_loop_count = len(mesh.loops)
            loop_verts = np.empty(mesh_loop_count, dtype=np.int32)
            mesh.loops.foreach_get("vertex_index", loop_verts)

            corner_normals = np.empty(mesh_loop_count * 3, dtype=np.float32)
            mesh.corner_normals.foreach_get("vector", corner_normals)
            corner_normals = corner_normals.reshape(mesh_loop_count, 3)

            tri_loop_indices = np.empty(loop_count, dtype=np.int32)
            mesh.loop_triangles.foreach_get("loops", tri_loop_indices)
            tri_vertex_indices = loop_verts[tri_loop_indices]

            loop_positions = np.ascontiguousarray(vertex_co[tri_vertex_indices], dtype=np.float32)
            loop_corner_normals = np.ascontiguousarray(
                corner_normals[tri_loop_indices], dtype=np.float32
            )
            loop_smooth_normals = np.ascontiguousarray(
                vertex_normals[tri_vertex_indices], dtype=np.float32
            )
            tri_idx = np.arange(loop_count, dtype=np.uint32)

            return (
                loop_positions,
                loop_corner_normals,
                loop_smooth_normals,
                tri_idx,
                loop_count,
                tri_count,
            )
        finally:
            eval_obj.to_mesh_clear()
    except Exception as e:
        print(f"nexus: mesh loop extract error for '{mesh_obj.name}': {e}")
        return None


def extract_line_data(
    curve_obj: bpy.types.Object,
    depsgraph: Optional[bpy.types.Depsgraph],
) -> Optional[tuple]:
    """Extract local-space vertices, segment data and world matrix from a curve object.

    Returns (vertices, segments, vertex_count, seg_count, world_matrix) or None.
    Vertices are in the curve's local space; world_matrix is its mathutils.Matrix.
    segments is a (M, 2) int32 array: [point_count, is_closed] per spline.
    """
    try:
        eval_obj = curve_obj.evaluated_get(depsgraph) if depsgraph else curve_obj

        # Convert to a mesh as this will handle all spline types automatically and sample them
        # using their preview resolution option
        mesh = eval_obj.to_mesh()
        if mesh is None:
            return None

        # TODO: optimise this, see where we can use direct data access with ctypes

        # Grab vertices from the mesh
        vertex_count = len(mesh.vertices)

        local_co = np.empty(vertex_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", local_co)
        local_co = local_co.reshape(vertex_count, 3).astype(np.float64)

        world_matrix = curve_obj.matrix_world

        # Use edge data to determine the line segments - makes the assumption that the vertices are
        # stored consecutively and grouped by segment. Seems to be correct...
        edge_set: set[tuple[int, int]] = set()
        for e in mesh.edges:
            a, b = e.vertices
            edge_set.add((min(a, b), max(a, b)))

        segments = []

        count = 0
        is_closed = False
        start = 0
        i = 1

        def _create_segment():
            nonlocal count, is_closed, start

            count = i - start
            is_closed = (start, i - 1) in edge_set

            segments.append((count, is_closed))
            start = i

        while i < vertex_count:
            is_connected = (i - 1, i) in edge_set

            # Reached the end of the chain
            if not is_connected:
                _create_segment()
            i += 1

        # Final segment
        _create_segment()

        return (local_co, np.array(segments), vertex_count, len(segments), world_matrix)

    except Exception as e:
        print(f"nexus: line extract error for '{curve_obj.name}': {e}")
        return None
