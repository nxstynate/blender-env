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

"""Particle display-mode discovery and backend registration.

Creates bridge singletons, instantiates per-mode renderers, and
registers composite backends with the viewport registry.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.particle_renderer import ParticleRenderer


from .arrow.basic import ArrowBasicRenderer, ArrowFilledBasicRenderer
from .arrow.native import ArrowFilledNativeRenderer, ArrowNativeRenderer
from .arrow.opengl import ArrowFilledOpenGLRenderer, ArrowOpenGLRenderer
from .axis.basic import AxisBasicRenderer
from .axis.native import AxisNativeRenderer
from .axis.opengl import AxisOpenGLRenderer
from .box.basic import Box3DBasicRenderer, Box3DFilledBasicRenderer
from .box.native import Box3DFilledNativeRenderer, Box3DNativeRenderer
from .box.opengl import Box3DFilledOpenGLRenderer, Box3DOpenGLRenderer
from .circle.basic import CircleBasicRenderer
from .circle.native import CircleNativeRenderer
from .circle.opengl import CircleOpenGLRenderer
from .circlefilled.basic import CircleFilledBasicRenderer
from .circlefilled.native import CircleFilledNativeRenderer
from .circlefilled.opengl import CircleFilledOpenGLRenderer
from .direction.basic import DirectionBasicRenderer
from .direction.native import DirectionNativeRenderer
from .direction.opengl import DirectionOpenGLRenderer
from .point.basic import PointBasicRenderer
from .point.native import PointNativeRenderer
from .point.opengl import PointOpenGLRenderer
from .pyramid.basic import PyramidBasicRenderer, PyramidFilledBasicRenderer
from .pyramid.native import PyramidFilledNativeRenderer, PyramidNativeRenderer
from .pyramid.opengl import PyramidFilledOpenGLRenderer, PyramidOpenGLRenderer
from .sphere.basic import SphereBasicRenderer
from .sphere.native import SphereNativeRenderer
from .sphere.opengl import SphereOpenGLRenderer
from .square.basic import SquareBasicRenderer
from .square.native import SquareNativeRenderer
from .square.opengl import SquareOpenGLRenderer
from .ssf.native import SSFNativeStager
from .ssf.opengl import SSFOpenGLRenderer

# ------------------------------------------------------------------
# Helper: create a draw function that dispatches by display_shape
# ------------------------------------------------------------------


def _make_dispatch(
    modes: dict[str, ParticleRenderer],
    bridge=None,
):
    """Return ``(draw_fn, shutdown_fn)`` for a backend with per-mode renderers."""

    def draw(context, pipeline, scene, params) -> bool:
        mode = modes.get(params.display_shape)
        if mode is None:
            return False
        return mode.draw(context, pipeline, scene, params)

    def shutdown():
        for r in modes.values():
            r.shutdown()
        if bridge is not None:
            bridge.shutdown()

    return draw, shutdown


_ALL_INDIRECT_SHAPES = (
    "POINTS",
    "SQUARE",
    "BOX3D",
    "BOX3D_FILLED",
    "CIRCLE",
    "CIRCLE_FILLED",
    "PYRAMID",
    "PYRAMID_FILLED",
    "DIRECTION",
    "ARROW",
    "ARROW_FILLED",
    "AXIS",
    "SPHERE",
    "SSF",
)


def _make_opengl_dispatch(
    modes: dict[str, ParticleRenderer],
    bridge=None,
):
    """OpenGL-specific dispatch with binned-indirect multi-shape fanout."""
    base_draw, base_shutdown = _make_dispatch(modes, bridge)

    def draw(context, pipeline, scene, params) -> bool:
        from ..core.particle_renderer import ParticleRenderer as _PR

        has_binned_indirect = _PR.fetch_draw_mode_buffers(pipeline) is not None
        if not has_binned_indirect:
            return base_draw(context, pipeline, scene, params)

        drew_any = False
        for shape in _ALL_INDIRECT_SHAPES:
            drew_any = (
                base_draw(
                    context,
                    pipeline,
                    scene,
                    replace(params, display_shape=shape),
                )
                or drew_any
            )
        return drew_any

    return draw, base_shutdown


def _make_native_indirect_dispatch(
    modes: dict[str, ParticleRenderer],
    bridge=None,
):
    """Vulkan/Metal dispatch: one POINTS call when binned-indirect is active."""
    base_draw, base_shutdown = _make_dispatch(modes, bridge)
    ssf = SSFNativeStager(bridge) if bridge is not None else None

    def draw(context, pipeline, scene, params) -> bool:
        from ..core.particle_renderer import ParticleRenderer as _PR

        has_binned_indirect = _PR.fetch_draw_mode_buffers(pipeline) is not None
        if not has_binned_indirect:
            return base_draw(context, pipeline, scene, params)

        if ssf is not None:
            ssf.stage(params)

        return base_draw(context, pipeline, scene, replace(params, display_shape="POINTS"))

    return draw, base_shutdown


def _make_basic_indirect_dispatch(
    modes: dict[str, ParticleRenderer],
):
    """Basic dispatch that mirrors OpenGL indirect fanout using host buffers.

    When the pipeline exposes per-particle emitter ids we sub-bin the already
    shape-binned indices once more by emitter id so each ``base_draw`` call
    sees a buffer whose particles share a single emitter. That lets us apply
    per-emitter overrides (point size, rotation mode, line length mode / fixed
    length, up-vector) exactly the way the Vulkan/Metal/OpenGL SSBO path does,
    without every renderer having to learn how to look up per-particle
    settings.
    """
    import numpy as np

    base_draw, base_shutdown = _make_dispatch(modes)
    rot_mode_map = {0: "NONE", 1: "UP_VECTOR", 2: "TANGENTIAL"}

    def _emitter_override(params, emitter_idx: int):
        """Return ``params`` with per-emitter fields replaced (or unchanged)."""
        if emitter_idx < 0:
            return params
        rot_modes = params.emitter_rotation_modes
        up_vecs = params.emitter_rotation_up_vectors
        line_modes = params.emitter_line_length_modes
        line_fixed = params.emitter_line_fixed_lengths
        line_min = params.emitter_line_min_lengths
        line_max = params.emitter_line_max_lengths
        point_sizes = params.emitter_point_sizes
        out = params
        if emitter_idx < len(rot_modes):
            out = replace(
                out,
                rotation_mode=rot_mode_map.get(int(rot_modes[emitter_idx]), "NONE"),
            )
        if emitter_idx < len(up_vecs):
            out = replace(
                out,
                rotation_up_vector=tuple(float(v) for v in up_vecs[emitter_idx]),
            )
        if emitter_idx < len(line_modes):
            out = replace(out, line_length_mode=int(line_modes[emitter_idx]))
        if emitter_idx < len(line_fixed):
            out = replace(out, line_fixed_length=float(line_fixed[emitter_idx]))
        if emitter_idx < len(line_min):
            out = replace(out, line_min_length=float(line_min[emitter_idx]))
        if emitter_idx < len(line_max):
            out = replace(out, line_max_length=float(line_max[emitter_idx]))
        if emitter_idx < len(point_sizes):
            out = replace(out, size=float(point_sizes[emitter_idx]))
        return out

    def _shape_for_single_emitter(params, shape: str) -> int:
        """Map ``shape`` to a single emitter id via emitter_display_shapes."""
        emitter_shapes = params.emitter_display_shapes
        if not emitter_shapes:
            return -1
        matches = [i for i, shp in enumerate(emitter_shapes) if str(shp) == shape]
        return matches[0] if len(matches) == 1 else -1

    def draw(context, pipeline, scene, params) -> bool:
        from ..core.particle_renderer import ParticleRenderer as _PR

        host_buffers = _PR.fetch_draw_mode_host_buffers(pipeline)
        if host_buffers is None:
            host_buffers = _PR.build_draw_mode_bins_cpu(pipeline, scene.session_uid, params.count)
        if host_buffers is None:
            return base_draw(context, pipeline, scene, params)

        if not _PR.ensure_cpu_ready(scene, context):
            return True

        base = _PR.read_cpu_base(pipeline, scene.session_uid)
        if base is None:
            return True
        positions, colors, count = base
        if count <= 0:
            return True
        velocities_result = _PR.read_cpu_velocities(pipeline, scene.session_uid)
        radii_result = _PR.read_cpu_radii(pipeline, scene.session_uid)
        needs_rotations = str(getattr(params, "rotation_mode", "NONE")) == "UP_VECTOR" or any(
            int(mode) == 1 for mode in params.emitter_rotation_modes
        )
        rotations_result = (
            _PR.read_cpu_rotations(pipeline, scene.session_uid) if needs_rotations else None
        )
        velocities = velocities_result[0] if velocities_result is not None else None
        radii = radii_result[0] if radii_result is not None else None
        rotations = rotations_result[0] if rotations_result is not None else None

        emit_idx_result = _PR.read_cpu_emitter_indices(pipeline, scene.session_uid)
        emit_idx_array = emit_idx_result[0] if emit_idx_result is not None else None
        # Per-emitter overrides are only meaningful if at least one emitter
        # has something to override; otherwise skip the emitter sub-binning.
        has_emitter_overrides = bool(
            params.emitter_point_sizes
            or params.emitter_rotation_modes
            or params.emitter_rotation_up_vectors
            or params.emitter_line_length_modes
            or params.emitter_line_fixed_lengths
            or params.emitter_line_min_lengths
            or params.emitter_line_max_lengths
        )

        prefix, binned = host_buffers
        binned_np = np.asarray(binned)
        drew_any = False

        def _issue(shape: str, sub_indices: np.ndarray, emitter_idx: int) -> bool:
            if sub_indices.size == 0:
                return False
            shape_params = _emitter_override(params, emitter_idx)
            return bool(
                base_draw(
                    context,
                    pipeline,
                    scene,
                    replace(
                        shape_params,
                        display_shape=shape,
                        cpu_ready=True,
                        cpu_positions=positions,
                        cpu_colors=colors,
                        cpu_velocities=velocities,
                        cpu_radii=radii,
                        cpu_rotations=rotations,
                        cpu_emitter_indices=emit_idx_array,
                        cpu_count=count,
                        indirect_binned_indices=sub_indices,
                        indirect_start=0,
                        indirect_end=int(sub_indices.size),
                    ),
                )
            )

        for shape in _ALL_INDIRECT_SHAPES:
            start, end = _PR.mode_bin_range(prefix, shape)
            if end <= start:
                continue
            subset = binned_np[start:end]
            if subset.dtype != np.uint32:
                subset = subset.astype(np.uint32, copy=False)

            if not has_emitter_overrides:
                drew_any = _issue(shape, subset, -1) or drew_any
                continue

            if emit_idx_array is None:
                # No CPU emitter ids available — fall back to shape→emitter
                # mapping (only reliable when exactly one emitter uses a shape).
                drew_any = (
                    _issue(shape, subset, _shape_for_single_emitter(params, shape)) or drew_any
                )
                continue

            per_em = emit_idx_array[subset]
            uniq = np.unique(per_em)
            if uniq.size <= 1:
                em_id = int(uniq[0]) if uniq.size == 1 else -1
                drew_any = _issue(shape, subset, em_id) or drew_any
                continue

            order = np.argsort(per_em, kind="stable")
            sorted_em = per_em[order]
            sorted_sub = subset[order]
            starts = np.searchsorted(sorted_em, uniq, side="left")
            ends = np.searchsorted(sorted_em, uniq, side="right")
            for em_val, s, e in zip(uniq, starts, ends):
                drew_any = _issue(shape, sorted_sub[int(s) : int(e)], int(em_val)) or drew_any

        if not drew_any and params.count > 0:
            return base_draw(context, pipeline, scene, params)
        return drew_any

    return draw, base_shutdown


# ------------------------------------------------------------------
# Bridge singletons  (lazily evaluated, but created early enough for
# registration to hook ``is_available``)
# ------------------------------------------------------------------

from ..bridges import get_metal_bridge, get_opengl_bridge, get_vulkan_bridge  # noqa: E402

_vulkan_bridge = get_vulkan_bridge()
_metal_bridge = get_metal_bridge()
_opengl_bridge = get_opengl_bridge()


def _native_modes(bridge):
    return {
        "POINTS": PointNativeRenderer(bridge),
        "CIRCLE": CircleNativeRenderer(bridge),
        "CIRCLE_FILLED": CircleFilledNativeRenderer(bridge),
        "SQUARE": SquareNativeRenderer(bridge),
        "BOX3D": Box3DNativeRenderer(bridge),
        "BOX3D_FILLED": Box3DFilledNativeRenderer(bridge),
        "PYRAMID": PyramidNativeRenderer(bridge),
        "PYRAMID_FILLED": PyramidFilledNativeRenderer(bridge),
        "DIRECTION": DirectionNativeRenderer(bridge),
        "ARROW": ArrowNativeRenderer(bridge, filled=False),
        "ARROW_FILLED": ArrowFilledNativeRenderer(bridge),
        "AXIS": AxisNativeRenderer(bridge),
        "SPHERE": SphereNativeRenderer(bridge),
    }


def _opengl_modes(bridge):
    return {
        "POINTS": PointOpenGLRenderer(bridge),
        "CIRCLE": CircleOpenGLRenderer(bridge),
        "CIRCLE_FILLED": CircleFilledOpenGLRenderer(bridge),
        "SQUARE": SquareOpenGLRenderer(bridge),
        "BOX3D": Box3DOpenGLRenderer(bridge),
        "BOX3D_FILLED": Box3DFilledOpenGLRenderer(bridge),
        "PYRAMID": PyramidOpenGLRenderer(bridge),
        "PYRAMID_FILLED": PyramidFilledOpenGLRenderer(bridge),
        "DIRECTION": DirectionOpenGLRenderer(bridge),
        "ARROW": ArrowOpenGLRenderer(bridge),
        "ARROW_FILLED": ArrowFilledOpenGLRenderer(bridge),
        "AXIS": AxisOpenGLRenderer(bridge),
        "SPHERE": SphereOpenGLRenderer(bridge),
        "SSF": SSFOpenGLRenderer(bridge),
    }


def _basic_modes():
    return {
        "POINTS": PointBasicRenderer(),
        "CIRCLE": CircleBasicRenderer(),
        "CIRCLE_FILLED": CircleFilledBasicRenderer(),
        "SQUARE": SquareBasicRenderer(),
        "BOX3D": Box3DBasicRenderer(),
        "BOX3D_FILLED": Box3DFilledBasicRenderer(),
        "PYRAMID": PyramidBasicRenderer(),
        "PYRAMID_FILLED": PyramidFilledBasicRenderer(),
        "DIRECTION": DirectionBasicRenderer(),
        "ARROW": ArrowBasicRenderer(filled=False),
        "ARROW_FILLED": ArrowFilledBasicRenderer(),
        "AXIS": AxisBasicRenderer(),
        "SPHERE": SphereBasicRenderer(),
    }


# ------------------------------------------------------------------
# Build dispatch closures
# ------------------------------------------------------------------

_vulkan_modes_map = _native_modes(_vulkan_bridge)
_metal_modes_map = _native_modes(_metal_bridge)
_opengl_modes_map = _opengl_modes(_opengl_bridge)
_basic_modes_map = _basic_modes()

vulkan_draw, vulkan_shutdown = _make_native_indirect_dispatch(_vulkan_modes_map, _vulkan_bridge)
metal_draw, metal_shutdown = _make_native_indirect_dispatch(_metal_modes_map, _metal_bridge)
opengl_draw, opengl_shutdown = _make_opengl_dispatch(_opengl_modes_map, _opengl_bridge)
basic_draw, basic_shutdown = _make_basic_indirect_dispatch(_basic_modes_map)


# ------------------------------------------------------------------
# Public: register with the viewport registry
# ------------------------------------------------------------------


def register_all_backends() -> None:
    """Register Vulkan, Metal, OpenGL, and Basic backends."""
    from ..registry import ViewportBackend, register_backend

    register_backend(
        ViewportBackend(
            id="VULKAN",
            label="Vulkan",
            description="Zero-copy Vulkan particle draw via funchook.",
            priority=25,
            is_available=_vulkan_bridge.is_available,
            draw=vulkan_draw,
        )
    )
    register_backend(
        ViewportBackend(
            id="METAL",
            label="Metal",
            description="Zero-copy Metal particle draw via method swizzle.",
            priority=20,
            is_available=_metal_bridge.is_available,
            draw=metal_draw,
        )
    )
    register_backend(
        ViewportBackend(
            id="OPENGL",
            label="OpenGL",
            description="Zero-copy Vulkan→OpenGL particle draw via external memory.",
            priority=10,
            is_available=_opengl_bridge.is_available,
            draw=opengl_draw,
        )
    )
    register_backend(
        ViewportBackend(
            id="BASIC",
            label="Basic",
            description="CPU-read + GPU batch upload fallback (all platforms).",
            priority=0,
            is_available=lambda: True,
            draw=basic_draw,
        )
    )


def shutdown_all() -> None:
    """Shut down every mode renderer and bridge."""
    vulkan_shutdown()
    metal_shutdown()
    opengl_shutdown()
    basic_shutdown()


def clear_basic_shaders() -> None:
    """Release cached Blender GPU shaders for the basic backend."""
    for mode in _basic_modes_map.values():
        mode.shutdown()
