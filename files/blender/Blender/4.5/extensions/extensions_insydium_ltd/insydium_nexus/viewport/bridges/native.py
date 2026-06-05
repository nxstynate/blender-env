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

"""Shared Python-side bridge for Vulkan and Metal DLL backends."""

from __future__ import annotations

import ctypes
import os
import sys
from abc import abstractmethod
from ctypes import c_float, c_int, c_size_t, c_uint32, c_void_p

from ..core.buffer_state import BufferTracker
from .base import BridgeBase

SENTINEL_MAGIC: float = 7919.0  # Particle magic # write / detect in R channel
VOLUME_SENTINEL_MAGIC: float = 7907.0  # Different value for volumes; write / detect in G channel
GENERATOR_SENTINEL_MAGIC: float = 7913.0  # NX_GENERATOR magic; write / detect in B channel
TRAIL_SENTINEL_MAGIC: float = 7901.0  # Trail sentinel, A channel.


class NativeBridge(BridgeBase):
    """Python ctypes wrapper around the ``nexus_*`` C API."""

    def __init__(self) -> None:
        self._lib: ctypes.CDLL | None = None
        self._available: bool = False
        self._loaded: bool = False
        self._tracker = BufferTracker()
        self._sentinel_shader = None
        self._sentinel_batch = None
        self._active_trail_pipeline: int | None = None
        self._active_trail_bundle_uid: int = 0
        self._active_trail_history_key: tuple[int, int] | None = None
        self._active_trail_topology_key: tuple[int, int] | None = None
        self._active_trail_color_key: tuple[int, int] | None = None
        self._active_trail_thickness_key: tuple[int, int] | None = None
        self._active_trail_radius_key: tuple[int, int] | None = None
        self._active_trail_live_endpoint_key: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_dll_candidates(self) -> list[str]:
        """Return absolute paths to try when loading the native library."""

    @abstractmethod
    def _platform_ok(self) -> bool:
        """Return True if the current OS matches this bridge."""

    @abstractmethod
    def _gpu_backend_ok(self) -> bool:
        """Return True if Blender's GPU backend matches."""

    def _on_loaded(self, lib: ctypes.CDLL) -> None:
        """Hook called after successful ``nexus_init`` (e.g. log callback)."""

    # ------------------------------------------------------------------
    # BridgeBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._platform_ok() and self._gpu_backend_ok()

    def load(self) -> bool:
        if self._available and self._lib is not None:
            return True
        if self._loaded:
            return self._available
        self._loaded = True

        if not self._platform_ok() or not self._gpu_backend_ok():
            return False

        for path in self._get_dll_candidates():
            if not os.path.isfile(path):
                continue
            try:
                lib = ctypes.CDLL(path)
                self._setup_argtypes(lib)
                if lib.nexus_init() == 0:
                    self._lib = lib
                    self._available = True
                    self._on_loaded(lib)
                    return True
                lib = None
            except (OSError, AttributeError):
                pass
        return False

    def shutdown(self) -> None:
        if self._lib is not None and self._available:
            try:
                if hasattr(self._lib, "nexus_shutdown"):
                    self._lib.nexus_shutdown()
            except Exception:
                pass

        self._available = False
        self._tracker.reset()

        native_handle = None
        if self._lib is not None:
            native_handle = getattr(self._lib, "_handle", None)
            self._lib = None

        self._loaded = False

        if native_handle is not None:
            try:
                import _ctypes

                if sys.platform == "win32":
                    _ctypes.FreeLibrary(native_handle)
                else:
                    _ctypes.dlclose(native_handle)
            except ImportError:
                print("theron: _ctypes not available, viewport library not explicitly closed")
            except Exception as e:
                print(f"theron: Failed to unload viewport library: {e}")

    # ------------------------------------------------------------------
    # ctypes setup
    # ------------------------------------------------------------------

    @staticmethod
    def _setup_argtypes(lib: ctypes.CDLL) -> None:
        lib.nexus_init.restype = c_int
        lib.nexus_init.argtypes = []

        lib.nexus_stage_frame.restype = None
        lib.nexus_stage_frame.argtypes = [
            ctypes.POINTER(c_float),
            ctypes.POINTER(c_float),
            c_uint32,
            c_uint32,
        ]

        _optional = [
            ("nexus_use_external_buffer", [c_void_p, c_size_t, c_uint32]),
            (
                "nexus_stage_volume_params",
                [c_float, c_float, c_float, ctypes.POINTER(c_float)],
            ),
            (
                "nexus_stage_particle_params",
                [ctypes.POINTER(c_float), c_float],
            ),
            (
                "nexus_stage_display_shape",
                [c_int, c_int, c_int, c_float, c_float, c_int],
            ),
            (
                "nexus_use_external_buffers_quad",
                [c_void_p, c_size_t, c_void_p, c_size_t, c_uint32],
            ),
            (
                "nexus_use_external_buffers_line",
                [c_void_p, c_size_t, c_void_p, c_size_t, c_void_p, c_size_t, c_uint32],
            ),
            ("nexus_stage_color_mode", [c_int]),
            ("nexus_stage_ssf_params", [ctypes.POINTER(c_float)]),
            ("nexus_stage_ssf_emitter_sizes", [ctypes.POINTER(c_float), c_uint32]),
            ("nexus_stage_ssf_enabled", [c_int]),
            (
                "nexus_use_external_buffers_indirect",
                [
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_void_p,
                    c_size_t,
                    c_uint32,
                    c_uint32,
                ],
            ),
            ("nexus_stage_indirect_mode", [c_uint32]),
            ("nexus_stage_emitter_settings", [ctypes.POINTER(c_float), c_uint32]),
            (
                "nexus_stage_emitter_constraint_palette",
                [ctypes.POINTER(c_float), c_uint32],
            ),
            ("nexus_stage_constraint_overlay_enabled", [c_int]),
            (
                "nexus_use_external_constraint_buffer",
                [c_void_p, c_size_t],
            ),
            (
                "nexus_use_external_id_lut_buffer",
                [c_void_p, c_size_t, c_uint32],
            ),
            (
                "nexus_use_external_particle_id_buffer",
                [c_void_p, c_size_t],
            ),
            (
                "nexus_stage_trail_params",
                [ctypes.POINTER(c_float), c_int, c_int, c_int, c_int],
            ),
            (
                "nexus_stage_trail_frame",
                [ctypes.POINTER(c_float), ctypes.POINTER(c_float), c_uint32, c_uint32],
            ),
            ("nexus_use_external_trail_history_buffer", [c_void_p, c_size_t]),
            ("nexus_use_external_trail_topology_buffer", [c_void_p, c_size_t]),
            ("nexus_use_external_trail_color_buffer", [c_void_p, c_size_t]),
            ("nexus_use_external_trail_thickness_buffer", [c_void_p, c_size_t]),
            ("nexus_use_external_trail_radius_buffer", [c_void_p, c_size_t]),
            ("nexus_use_external_trail_live_endpoint_buffer", [c_void_p, c_size_t]),
            ("nexus_release_trail_scratch_buffers", []),
            ("nexus_release_all_trail_externals", []),
            (
                "nexus_stage_trail_palette",
                [ctypes.POINTER(c_float), c_uint32, c_int],
            ),
        ]
        for name, argtypes in _optional:
            if hasattr(lib, name):
                fn = getattr(lib, name)
                fn.argtypes = argtypes
                fn.restype = None

    # ------------------------------------------------------------------
    # Sentinel batch (shared Vulkan / Metal)
    # ------------------------------------------------------------------

    def _ensure_sentinel_batch(self) -> bool:
        if self._sentinel_batch is not None:
            return True
        try:
            import gpu
            from gpu_extras.batch import batch_for_shader
        except ImportError:
            return False
        try:
            self._sentinel_shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            self._sentinel_batch = batch_for_shader(
                self._sentinel_shader, "POINTS", {"pos": [(0.0, 0.0, 0.0)]}
            )
            return True
        except Exception:
            return False

    def draw_sentinel(self) -> bool:
        """Issue the 1-vertex sentinel draw."""
        if not self._ensure_sentinel_batch():
            return False
        try:
            self._sentinel_shader.bind()
            self._sentinel_shader.uniform_float("color", (SENTINEL_MAGIC, 0.0, 0.0, 0.0))
            self._sentinel_batch.draw(self._sentinel_shader)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Staging helpers (called by particle mode renderers)
    # ------------------------------------------------------------------

    def stage_frame(self, vm_flat: list, pm_flat: list, w: int, h: int) -> None:
        vm = (c_float * 16)(*vm_flat)
        pm = (c_float * 16)(*pm_flat)
        self._lib.nexus_stage_frame(vm, pm, c_uint32(w), c_uint32(h))

    def stage_particle_params(self, color: tuple, size: float) -> None:
        if hasattr(self._lib, "nexus_stage_particle_params"):
            arr = (c_float * 4)(*color)
            self._lib.nexus_stage_particle_params(arr, c_float(size))

    def stage_display_shape(
        self,
        shape_id: int,
        is_circle: int,
        use_radius: int,
        size_a: float,
        size_b: float,
        line_length_mode: int = 0,
    ) -> None:
        if hasattr(self._lib, "nexus_stage_display_shape"):
            self._lib.nexus_stage_display_shape(
                c_int(shape_id),
                c_int(is_circle),
                c_int(use_radius),
                c_float(size_a),
                c_float(size_b),
                c_int(line_length_mode),
            )

    def stage_color_mode(self, use_color: bool) -> None:
        if hasattr(self._lib, "nexus_stage_color_mode"):
            self._lib.nexus_stage_color_mode(c_int(1 if use_color else 0))

    # ------------------------------------------------------------------
    # Buffer configuration
    # ------------------------------------------------------------------

    def configure_points(self, handle: int, size: int, count: int) -> None:
        if hasattr(self._lib, "nexus_use_external_buffer"):
            self._lib.nexus_use_external_buffer(c_void_p(handle), c_size_t(size), c_uint32(count))

    def configure_quad(
        self,
        pos_handle: int,
        pos_size: int,
        rad_handle: int | None,
        rad_size: int,
        count: int,
    ) -> None:
        if hasattr(self._lib, "nexus_use_external_buffers_quad"):
            self._lib.nexus_use_external_buffers_quad(
                c_void_p(pos_handle),
                c_size_t(pos_size),
                c_void_p(rad_handle) if rad_handle else None,
                c_size_t(rad_size),
                c_uint32(count),
            )

    def configure_line(
        self,
        pos_handle: int,
        pos_size: int,
        vel_handle: int,
        vel_size: int,
        rad_handle: int | None,
        rad_size: int,
        count: int,
    ) -> None:
        if hasattr(self._lib, "nexus_use_external_buffers_line"):
            self._lib.nexus_use_external_buffers_line(
                c_void_p(pos_handle),
                c_size_t(pos_size),
                c_void_p(vel_handle),
                c_size_t(vel_size),
                c_void_p(rad_handle) if rad_handle else None,
                c_size_t(rad_size),
                c_uint32(count),
            )

    def configure_indirect_points(
        self,
        pos_handle: int,
        pos_size: int,
        prefix_handle: int,
        prefix_size: int,
        binned_handle: int,
        binned_size: int,
        emitter_index_handle: int,
        emitter_index_size: int,
        radius_handle: int | None,
        radius_size: int,
        velocity_handle: int | None,
        velocity_size: int,
        rotation_handle: int | None,
        rotation_size: int,
        color_handle: int | None,
        color_size: int,
        mode_index: int,
        count: int,
    ) -> None:
        if hasattr(self._lib, "nexus_use_external_buffers_indirect"):
            self._lib.nexus_use_external_buffers_indirect(
                c_void_p(pos_handle),
                c_size_t(pos_size),
                c_void_p(prefix_handle),
                c_size_t(prefix_size),
                c_void_p(binned_handle),
                c_size_t(binned_size),
                c_void_p(emitter_index_handle),
                c_size_t(emitter_index_size),
                c_void_p(radius_handle) if radius_handle else None,
                c_size_t(radius_size),
                c_void_p(velocity_handle) if velocity_handle else None,
                c_size_t(velocity_size),
                c_void_p(rotation_handle) if rotation_handle else None,
                c_size_t(rotation_size),
                c_void_p(color_handle) if color_handle else None,
                c_size_t(color_size),
                c_uint32(mode_index),
                c_uint32(count),
            )

    def stage_indirect_mode(self, mode_index: int) -> None:
        if hasattr(self._lib, "nexus_stage_indirect_mode"):
            self._lib.nexus_stage_indirect_mode(c_uint32(mode_index))

    # ------------------------------------------------------------------
    # SSF staging (Metal + Vulkan)
    # ------------------------------------------------------------------

    _SSF_PARAM_COUNT = 16

    def stage_ssf_enabled(self, enabled: bool) -> None:
        if hasattr(self._lib, "nexus_stage_ssf_enabled"):
            self._lib.nexus_stage_ssf_enabled(c_int(1 if enabled else 0))

    def stage_ssf_params(
        self,
        *,
        fluid_color: tuple[float, float, float],
        background: tuple[float, float, float],
        absorption: float,
        fresnel_power: float,
        min_alpha: float,
        anisotropy_scale: float,
        anisotropy_max_stretch: float,
        use_anisotropy: bool,
        blur_iterations: int,
        blur_radius: int,
        blur_depth_falloff: float,
        thickness_blur_iterations: int,
    ) -> None:
        if not hasattr(self._lib, "nexus_stage_ssf_params"):
            return
        packed = (
            float(fluid_color[0]),
            float(fluid_color[1]),
            float(fluid_color[2]),
            float(background[0]),
            float(background[1]),
            float(background[2]),
            float(absorption),
            float(fresnel_power),
            float(min_alpha),
            float(anisotropy_scale),
            float(anisotropy_max_stretch),
            1.0 if use_anisotropy else 0.0,
            float(int(blur_iterations)),
            float(int(blur_radius)),
            float(blur_depth_falloff),
            float(int(thickness_blur_iterations)),
        )
        arr = (c_float * self._SSF_PARAM_COUNT)(*packed)
        self._lib.nexus_stage_ssf_params(arr)

    def stage_ssf_emitter_sizes(self, sizes: tuple[float, ...]) -> None:
        if not hasattr(self._lib, "nexus_stage_ssf_emitter_sizes"):
            return
        capped = tuple(float(s) for s in sizes[:64])
        count = len(capped)
        if count == 0:
            self._lib.nexus_stage_ssf_emitter_sizes(None, c_uint32(0))
            return
        arr = (c_float * count)(*capped)
        self._lib.nexus_stage_ssf_emitter_sizes(arr, c_uint32(count))

    def stage_emitter_settings(
        self,
        sizes: tuple[float, ...],
        colors: tuple[tuple[float, float, float, float], ...],
        rotation_modes: tuple[int, ...],
        up_vectors: tuple[tuple[float, float, float], ...],
        line_length_modes: tuple[int, ...],
        line_fixed_lengths: tuple[float, ...],
        line_min_lengths: tuple[float, ...] = (),
        line_max_lengths: tuple[float, ...] = (),
        *,
        default_size: float,
        default_color: tuple[float, float, float, float],
    ) -> None:
        if not hasattr(self._lib, "nexus_stage_emitter_settings"):
            return
        count = max(
            len(sizes),
            len(colors),
            len(rotation_modes),
            len(up_vectors),
            len(line_length_modes),
            len(line_fixed_lengths),
            len(line_min_lengths),
            len(line_max_lengths),
            1,
        )

        def up_code_of(vec: tuple[float, float, float]) -> float:
            mapping = {
                (1.0, 0.0, 0.0): 0.0,
                (-1.0, 0.0, 0.0): 1.0,
                (0.0, 1.0, 0.0): 2.0,
                (0.0, -1.0, 0.0): 3.0,
                (0.0, 0.0, 1.0): 4.0,
                (0.0, 0.0, -1.0): 5.0,
            }
            key = tuple(float(x) for x in vec[:3])
            return mapping.get(key, 2.0)

        packed: list[float] = []
        for i in range(count):
            color = colors[i] if i < len(colors) else default_color
            size = sizes[i] if i < len(sizes) else default_size
            rotation_mode = float(rotation_modes[i]) if i < len(rotation_modes) else 0.0
            up_code = up_code_of(up_vectors[i]) if i < len(up_vectors) else 2.0
            line_mode = float(line_length_modes[i]) if i < len(line_length_modes) else 0.0
            fixed_length = float(line_fixed_lengths[i]) if i < len(line_fixed_lengths) else 0.1
            min_length = float(line_min_lengths[i]) if i < len(line_min_lengths) else 0.0
            max_length = float(line_max_lengths[i]) if i < len(line_max_lengths) else 0.0
            packed.extend((float(color[0]), float(color[1]), float(color[2]), float(color[3])))
            packed.extend((float(size), rotation_mode, up_code, line_mode))
            packed.extend((fixed_length, min_length, max_length, 0.0))
        arr = (c_float * len(packed))(*packed)
        self._lib.nexus_stage_emitter_settings(arr, c_uint32(count))

    # ------------------------------------------------------------------
    # Constraint overlay staging
    # ------------------------------------------------------------------

    # 4 colours * vec4 + 1 enable/pad vec4 = 20 floats per emitter.
    # Slot order matches sim's CONSTRAINT_TYPE_* enum (BIRTH/DIST/CUSTOM/VISCOSITY).
    _CONSTRAINT_PALETTE_FLOATS = 20

    def stage_constraint_overlay_enabled(self, enabled: bool) -> None:
        if hasattr(self._lib, "nexus_stage_constraint_overlay_enabled"):
            self._lib.nexus_stage_constraint_overlay_enabled(c_int(1 if enabled else 0))

    def stage_emitter_constraint_palette(
        self,
        palettes: tuple[tuple[tuple[float, float, float, float], ...], ...],
        enables: tuple[bool, ...],
    ) -> None:
        """Upload per-emitter 4-colour constraint palette + enable flag.

        ``palettes`` is one tuple of 4 RGBA tuples per emitter (one per
        renderable constraint type). Missing entries are zero-filled.
        ``enables`` is the per-emitter ``display_constraints`` toggle.
        """
        if not hasattr(self._lib, "nexus_stage_emitter_constraint_palette"):
            return
        count = max(len(palettes), len(enables), 1)
        packed: list[float] = []
        for i in range(count):
            colors = palettes[i] if i < len(palettes) else ()
            for slot in range(4):
                rgba = colors[slot] if slot < len(colors) else (0.0, 0.0, 0.0, 0.0)
                packed.extend(float(c) for c in rgba)
            enable = 1.0 if (i < len(enables) and enables[i]) else 0.0
            packed.extend((enable, 0.0, 0.0, 0.0))
        arr = (c_float * len(packed))(*packed)
        self._lib.nexus_stage_emitter_constraint_palette(arr, c_uint32(count))

    def configure_constraints(
        self,
        constraint_handle: int | None,
        constraint_size: int,
        lut_handle: int | None,
        lut_size_bytes: int,
        lut_capacity: int,
        particle_id_handle: int | None,
        particle_id_size: int,
    ) -> None:
        """Pass the constraint-overlay external buffers to the native library."""
        if hasattr(self._lib, "nexus_use_external_constraint_buffer"):
            self._lib.nexus_use_external_constraint_buffer(
                c_void_p(constraint_handle) if constraint_handle else None,
                c_size_t(constraint_size),
            )
        if hasattr(self._lib, "nexus_use_external_id_lut_buffer"):
            self._lib.nexus_use_external_id_lut_buffer(
                c_void_p(lut_handle) if lut_handle else None,
                c_size_t(lut_size_bytes),
                c_uint32(lut_capacity),
            )
        if hasattr(self._lib, "nexus_use_external_particle_id_buffer"):
            self._lib.nexus_use_external_particle_id_buffer(
                c_void_p(particle_id_handle) if particle_id_handle else None,
                c_size_t(particle_id_size),
            )

    # ------------------------------------------------------------------
    # Trail staging
    # ------------------------------------------------------------------

    def trail_hook_ready(self) -> bool:
        """True when the native backend has trail staging functions."""
        required = (
            "nexus_stage_trail_params",
            "nexus_stage_trail_frame",
            "nexus_stage_trail_palette",
            "nexus_use_external_trail_history_buffer",
            "nexus_use_external_trail_topology_buffer",
            "nexus_use_external_trail_color_buffer",
            "nexus_use_external_trail_thickness_buffer",
            "nexus_use_external_trail_radius_buffer",
        )
        return self._lib is not None and all(hasattr(self._lib, name) for name in required)

    def stage_trail_params(
        self,
        default_color: tuple,
        slots_per_particle: int,
        history_capacity: int,
        segment_count: int,
        max_points_per_segment: int,
    ) -> None:
        if not hasattr(self._lib, "nexus_stage_trail_params"):
            return
        arr = (c_float * 4)(*default_color)
        self._lib.nexus_stage_trail_params(
            arr,
            c_int(slots_per_particle),
            c_int(history_capacity),
            c_int(segment_count),
            c_int(max_points_per_segment),
        )

    def stage_trail_frame(self, vm_flat: list, pm_flat: list, w: int, h: int) -> None:
        if not hasattr(self._lib, "nexus_stage_trail_frame"):
            return
        vm = (c_float * 16)(*vm_flat)
        pm = (c_float * 16)(*pm_flat)
        self._lib.nexus_stage_trail_frame(vm, pm, c_uint32(w), c_uint32(h))

    def configure_trail_bundle(
        self,
        *,
        pipeline: int,
        bundle_uid: int,
        history: tuple[int, ...] | None,
        topology: tuple[int, ...] | None,
        color: tuple[int, ...] | None,
        thickness: tuple[int, ...] | None,
        radius: tuple[int, ...] | None,
        live_endpoint: tuple[int, ...] | None,
    ) -> bool:
        """Import trail buffers when the active Theron bundle changes."""
        if history is None or topology is None:
            return False
        if not self.trail_hook_ready():
            return False
        history_key = self._trail_export_key(history)
        topology_key = self._trail_export_key(topology)
        color_key = self._trail_export_key(color)
        thickness_key = self._trail_export_key(thickness)
        radius_key = self._trail_export_key(radius)
        live_endpoint_key = self._trail_export_key(live_endpoint)
        if history_key != self._active_trail_history_key:
            self.configure_trail_history(history)
            self._active_trail_history_key = history_key
        if topology_key != self._active_trail_topology_key:
            self.configure_trail_topology(topology)
            self._active_trail_topology_key = topology_key
        if color_key != self._active_trail_color_key:
            self.configure_trail_color(color)
            self._active_trail_color_key = color_key
        if thickness_key != self._active_trail_thickness_key:
            self.configure_trail_thickness(thickness)
            self._active_trail_thickness_key = thickness_key
        if radius_key != self._active_trail_radius_key:
            self.configure_trail_radius(radius)
            self._active_trail_radius_key = radius_key
        if live_endpoint_key != self._active_trail_live_endpoint_key:
            self.configure_trail_live_endpoint(live_endpoint)
            self._active_trail_live_endpoint_key = live_endpoint_key
        self._active_trail_pipeline = pipeline
        self._active_trail_bundle_uid = int(bundle_uid)
        return True

    def reset_trail_bundle_cache(self, pipeline: int | None = None) -> None:
        if pipeline is None:
            if self._active_trail_pipeline is None and self._active_trail_bundle_uid == 0:
                return
        else:
            if self._active_trail_pipeline != pipeline:
                return
        self._active_trail_pipeline = None
        self._active_trail_bundle_uid = 0
        self._active_trail_history_key = None
        self._active_trail_topology_key = None
        self._active_trail_color_key = None
        self._active_trail_thickness_key = None
        self._active_trail_radius_key = None
        self._active_trail_live_endpoint_key = None
        self.release_all_trail_externals()
        self.release_trail_scratch_buffers()

    def release_trail_scratch_buffers(self) -> None:
        if hasattr(self._lib, "nexus_release_trail_scratch_buffers"):
            self._lib.nexus_release_trail_scratch_buffers()

    def release_all_trail_externals(self) -> None:
        if hasattr(self._lib, "nexus_release_all_trail_externals"):
            self._lib.nexus_release_all_trail_externals()

    @staticmethod
    def _trail_export_key(export: tuple[int, ...] | None) -> tuple[int, int] | None:
        if not export:
            return None
        size = int(export[1]) if len(export) > 1 else 0
        uid = int(export[2]) if len(export) > 2 else 0
        return (size, uid)

    @staticmethod
    def _trail_export_handle_size(export: tuple[int, ...] | None) -> tuple[int, int]:
        if not export:
            return (0, 0)
        handle = int(export[0]) if len(export) > 0 else 0
        size = int(export[1]) if len(export) > 1 else 0
        return (handle, size)

    def configure_trail_history(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_history_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_history_buffer(c_void_p(handle), c_size_t(size))

    def configure_trail_topology(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_topology_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_topology_buffer(c_void_p(handle), c_size_t(size))

    def configure_trail_color(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_color_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_color_buffer(c_void_p(handle), c_size_t(size))

    def configure_trail_thickness(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_thickness_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_thickness_buffer(c_void_p(handle), c_size_t(size))

    def configure_trail_radius(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_radius_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_radius_buffer(c_void_p(handle), c_size_t(size))

    def configure_trail_live_endpoint(self, export: tuple[int, ...] | None) -> None:
        if hasattr(self._lib, "nexus_use_external_trail_live_endpoint_buffer"):
            handle, size = self._trail_export_handle_size(export)
            self._lib.nexus_use_external_trail_live_endpoint_buffer(
                c_void_p(handle), c_size_t(size)
            )

    def stage_trail_palette(
        self,
        source_colors: tuple,
        source_color_modes: tuple,
        source_thickness_modes: tuple,
        source_thickness_values: tuple,
        source_no_data_flags: tuple,
        source_trail_color_modes: tuple,
        source_thickness_variations: tuple = (),
        source_spline_max_values: tuple = (),
        source_enabled_flags: tuple = (),
    ) -> None:
        if not hasattr(self._lib, "nexus_stage_trail_palette"):
            return

        count = len(source_colors)
        if count == 0:
            return

        _THICKNESS_MODE_MAP = {
            "NONE": 0,
            "VALUE": 1,
            "SPLINE": 2,
            "RADIUS_CURRENT": 3,
            "RADIUS_VARIABLE": 4,
        }
        _COLOR_MODE_MAP = {"STANDARD": 0, "GRADIENT": 1}
        _TRAIL_COLOR_MODE_MAP = {"PARTICLE": 0, "PER_VERTEX": 1}

        packed: list[float] = []
        has_thickness = False
        for i in range(count):
            color = source_colors[i] if i < len(source_colors) else (0.0, 0.0, 0.0, 1.0)
            packed.extend(float(c) for c in color)

            enabled = 1.0 if (i < len(source_enabled_flags) and source_enabled_flags[i]) else 0.0
            color_mode = (
                float(_COLOR_MODE_MAP.get(source_color_modes[i], 0))
                if i < len(source_color_modes)
                else 0.0
            )
            trail_color_mode = (
                float(_TRAIL_COLOR_MODE_MAP.get(source_trail_color_modes[i], 0))
                if i < len(source_trail_color_modes)
                else 0.0
            )
            no_data = 1.0 if (i < len(source_no_data_flags) and source_no_data_flags[i]) else 0.0
            packed.extend((enabled, color_mode, trail_color_mode, no_data))

            thickness_mode_str = (
                source_thickness_modes[i] if i < len(source_thickness_modes) else "NONE"
            )
            thickness_mode = float(_THICKNESS_MODE_MAP.get(thickness_mode_str, 0))
            thickness_value = (
                float(source_thickness_values[i]) if i < len(source_thickness_values) else 0.01
            )
            thickness_variation = (
                float(source_thickness_variations[i])
                if i < len(source_thickness_variations)
                else 0.0
            )
            spline_max = (
                float(source_spline_max_values[i]) if i < len(source_spline_max_values) else 0.01
            )
            packed.extend((thickness_mode, thickness_value, thickness_variation, spline_max))

            if enabled > 0.5 and no_data < 0.5 and int(thickness_mode) != 0:
                has_thickness = True

        arr = (c_float * len(packed))(*packed)
        self._lib.nexus_stage_trail_palette(
            arr,
            c_uint32(count),
            c_int(1 if has_thickness else 0),
        )

    def draw_trail_sentinel(self) -> bool:
        """Issue the 1-vertex sentinel draw for trail recording."""
        if not self._ensure_sentinel_batch():
            return False
        try:
            self._sentinel_shader.bind()
            self._sentinel_shader.uniform_float("color", (0.0, 0.0, 0.0, TRAIL_SENTINEL_MAGIC))
            self._sentinel_batch.draw(self._sentinel_shader)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Staging helpers for volume renderers (e.g., nxExplosiaFX)
    # ------------------------------------------------------------------

    def volume_hook_ready(self) -> bool:
        """Return True when the volume staging function is available."""
        return self._lib is not None and hasattr(self._lib, "nexus_stage_volume_params")

    def stage_volume_params(
        self,
        domain_size: tuple[float, float, float],
        world_matrix: list[float],
    ) -> None:
        if hasattr(self._lib, "nexus_stage_volume_params"):
            mx = (c_float * 16)(*world_matrix)
            self._lib.nexus_stage_volume_params(
                c_float(domain_size[0]),
                c_float(domain_size[1]),
                c_float(domain_size[2]),
                mx,
            )

    def draw_volume_sentinel(self) -> bool:
        """Issue the 1-vertex sentinel draw for volume rendering."""
        if not self._ensure_sentinel_batch():
            return False
        try:
            self._sentinel_shader.bind()
            self._sentinel_shader.uniform_float("color", (0.0, VOLUME_SENTINEL_MAGIC, 0.0, 0.0))
            self._sentinel_batch.draw(self._sentinel_shader)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Tracker access
    # ------------------------------------------------------------------

    @property
    def tracker(self) -> BufferTracker:
        return self._tracker

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _get_addon_dir() -> str:
        """Parent of the ``viewport`` package (i.e. the addon root)."""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @staticmethod
    def _get_blender_gpu_backend() -> str:
        try:
            from ..registry import get_blender_gpu_backend

            return get_blender_gpu_backend()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # NX_GENERATOR staging
    # ------------------------------------------------------------------

    def generator_hook_ready(self) -> bool:
        """Return True when the native lib supports generator rendering."""
        return (
            self._lib is not None
            and hasattr(self._lib, "nexus_use_external_buffers_generator")
            and hasattr(self._lib, "nexus_stage_generator_frame")
        )

    def configure_generator_externals(
        self,
        pos_handle: int | None,
        pos_size: int,
        pid_handle: int | None,
        pid_size: int,
        color_handle: int | None,
        color_size: int,
        radius_handle: int | None,
        radius_size: int,
        scale_handle: int | None,
        scale_size: int,
        rotation_handle: int | None,
        rotation_size: int,
        emitter_idx_handle: int | None,
        emitter_idx_size: int,
    ) -> None:
        if not hasattr(self._lib, "nexus_use_external_buffers_generator"):
            return
        if (
            not hasattr(self._lib.nexus_use_external_buffers_generator, "argtypes")
            or self._lib.nexus_use_external_buffers_generator.argtypes is None
        ):
            self._lib.nexus_use_external_buffers_generator.argtypes = [
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
                c_void_p,
                c_size_t,
            ]
            self._lib.nexus_use_external_buffers_generator.restype = None
        self._lib.nexus_use_external_buffers_generator(
            c_void_p(pos_handle) if pos_handle else None,
            c_size_t(pos_size),
            c_void_p(pid_handle) if pid_handle else None,
            c_size_t(pid_size),
            c_void_p(color_handle) if color_handle else None,
            c_size_t(color_size),
            c_void_p(radius_handle) if radius_handle else None,
            c_size_t(radius_size),
            c_void_p(scale_handle) if scale_handle else None,
            c_size_t(scale_size),
            c_void_p(rotation_handle) if rotation_handle else None,
            c_size_t(rotation_size),
            c_void_p(emitter_idx_handle) if emitter_idx_handle else None,
            c_size_t(emitter_idx_size),
        )

    def stage_generator_frame(
        self,
        camera_pos: tuple[float, float, float],
        particle_count: int,
        num_layers: int,
        emitter_mask: int,
        layers_obj,  # ctypes array of GeneratorLayerGpu structs
        vertex_ptr,  # ctypes POINTER(c_float) into a contiguous float buffer
        vertex_count_floats: int,
        index_ptr,  # ctypes POINTER(c_uint32) into a contiguous uint32 buffer
        index_count: int,
        mesh_revision: int,
    ) -> None:
        if not hasattr(self._lib, "nexus_stage_generator_frame"):
            return
        from ctypes import POINTER, c_uint32, c_uint64

        if (
            not hasattr(self._lib.nexus_stage_generator_frame, "argtypes")
            or self._lib.nexus_stage_generator_frame.argtypes is None
        ):
            self._lib.nexus_stage_generator_frame.argtypes = [
                POINTER(c_float),
                c_uint32,
                c_uint32,
                c_uint32,
                POINTER(c_float),
                POINTER(c_float),
                c_uint32,
                POINTER(c_uint32),
                c_uint32,
                c_uint64,
            ]
            self._lib.nexus_stage_generator_frame.restype = None

        cam = (c_float * 3)(float(camera_pos[0]), float(camera_pos[1]), float(camera_pos[2]))
        layers_ptr = ctypes.cast(layers_obj, POINTER(c_float)) if layers_obj is not None else None

        self._lib.nexus_stage_generator_frame(
            ctypes.cast(cam, POINTER(c_float)),
            c_uint32(int(particle_count)),
            c_uint32(int(num_layers)),
            c_uint32(int(emitter_mask) & 0xFFFFFFFF),
            layers_ptr,
            vertex_ptr,
            c_uint32(int(vertex_count_floats)),
            index_ptr,
            c_uint32(int(index_count)),
            c_uint64(int(mesh_revision) & 0xFFFFFFFFFFFFFFFF),
        )

    def draw_generator_sentinel(self) -> bool:
        """Issue the 1-vertex sentinel draw for generator rendering."""
        if not self._ensure_sentinel_batch():
            return False
        try:
            self._sentinel_shader.bind()
            self._sentinel_shader.uniform_float("color", (0.0, 0.0, GENERATOR_SENTINEL_MAGIC, 0.0))
            self._sentinel_batch.draw(self._sentinel_shader)
            return True
        except Exception:
            return False
