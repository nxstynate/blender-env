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
from typing import List, Tuple

import gpu
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_line_line


def flatten_4x4(matrix) -> List[float]:
    return [matrix[i][j] for i in range(4) for j in range(4)]


def draw_lines(shader, lines: List[Tuple[Vector, Vector]]) -> None:
    if not lines:
        return
    coords = []
    for start, end in lines:
        coords.extend([start, end])
    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    batch.draw(shader)


def draw_circle(
    shader, matrix: Matrix, radius: float, plane: str = "XY", segments: int = 64
) -> None:
    coords = []
    for i in range(segments):
        angle1 = (i / segments) * math.pi * 2
        angle2 = ((i + 1) / segments) * math.pi * 2

        if plane == "XY":
            local1 = Vector((math.cos(angle1) * radius, math.sin(angle1) * radius, 0.0))
            local2 = Vector((math.cos(angle2) * radius, math.sin(angle2) * radius, 0.0))
        elif plane == "XZ":
            local1 = Vector((math.cos(angle1) * radius, 0.0, math.sin(angle1) * radius))
            local2 = Vector((math.cos(angle2) * radius, 0.0, math.sin(angle2) * radius))
        else:  # YZ
            local1 = Vector((0.0, math.cos(angle1) * radius, math.sin(angle1) * radius))
            local2 = Vector((0.0, math.cos(angle2) * radius, math.sin(angle2) * radius))

        coords.extend([matrix @ local1, matrix @ local2])

    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    batch.draw(shader)


def draw_thick_circle(
    context,
    matrix: Matrix,
    radius: float,
    color: Tuple[float, float, float, float],
    line_width: float,
    plane: str = "XY",
    segments: int = 64,
) -> None:
    lines = []
    for i in range(segments):
        angle1 = (i / segments) * math.pi * 2
        angle2 = ((i + 1) / segments) * math.pi * 2

        if plane == "XY":
            local1 = Vector((math.cos(angle1) * radius, math.sin(angle1) * radius, 0.0))
            local2 = Vector((math.cos(angle2) * radius, math.sin(angle2) * radius, 0.0))
        elif plane == "XZ":
            local1 = Vector((math.cos(angle1) * radius, 0.0, math.sin(angle1) * radius))
            local2 = Vector((math.cos(angle2) * radius, 0.0, math.sin(angle2) * radius))
        else:  # YZ
            local1 = Vector((0.0, math.cos(angle1) * radius, math.sin(angle1) * radius))
            local2 = Vector((0.0, math.cos(angle2) * radius, math.sin(angle2) * radius))

        lines.append((matrix @ local1, matrix @ local2))

    draw_thick_lines(context, lines, color, line_width)


def draw_thick_lines(
    context,
    lines: List[Tuple[Vector, Vector]],
    color: Tuple[float, float, float, float],
    line_width: float,
) -> None:
    if not lines:
        return

    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", line_width)
    shader.uniform_float("viewportSize", (context.region.width, context.region.height))

    coords = []
    for start, end in lines:
        coords.extend([start, end])

    batch = batch_for_shader(shader, "LINES", {"pos": coords})

    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(False)
    batch.draw(shader)
    gpu.state.depth_mask_set(True)
    gpu.state.depth_test_set("NONE")


def ray_axis_signed_distance(region, rv3d, mouse_co, axis_origin, axis_dir):
    """Cast a ray from *mouse_co* and return its signed distance along an axis.

    Parameters
    ----------
    region : bpy.types.Region
    rv3d : bpy.types.RegionView3D
    mouse_co : tuple[float, float]
        Screen-space mouse coordinates ``(x, y)``.
    axis_origin : mathutils.Vector
        World-space origin of the constraint axis.
    axis_dir : mathutils.Vector
        Normalised world-space direction of the constraint axis.

    Returns
    -------
    float | None
        Signed distance along *axis_dir* from *axis_origin* to the closest
        point on the axis to the view ray, or ``None`` when the axis is
        (nearly) parallel to the view direction.
    """
    ray_origin = region_2d_to_origin_3d(region, rv3d, mouse_co)
    ray_dir = region_2d_to_vector_3d(region, rv3d, mouse_co)

    result = intersect_line_line(
        ray_origin,
        ray_origin + ray_dir,
        axis_origin,
        axis_origin + axis_dir,
    )

    if result is None:
        return None

    closest_on_axis = result[1]
    return (closest_on_axis - axis_origin).dot(axis_dir)
