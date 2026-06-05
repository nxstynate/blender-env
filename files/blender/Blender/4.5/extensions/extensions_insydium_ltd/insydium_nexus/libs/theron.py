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
import os
import subprocess
import sys
from typing import Dict, List, NamedTuple, Optional, Tuple

import bpy
import numpy as np

from ..version import get_blender_version_str
from .theron_bindings import *


class MappingParamInfo(NamedTuple):
    param: int
    group: int
    name: str


class MappingLayerInfo(NamedTuple):
    id: int
    name: str


def _show_error_qt(title: str, msg: str) -> bool:
    """Show a modal error dialog via PyQt6."""
    try:
        from PyQt6 import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])

        QtWidgets.QMessageBox.critical(None, title, msg)
        return True
    except Exception:
        return False


def _show_error_dialog(title: str, msg: str) -> None:
    """Show a native modal error dialog on the current platform."""
    try:
        if sys.platform == "win32":
            MB_ICONERROR = 0x10
            MB_TOPMOST = 0x40000

            ctypes.windll.user32.MessageBoxW(
                0,
                msg,
                title,
                MB_ICONERROR | MB_TOPMOST,
            )
        elif sys.platform == "darwin":
            safe_msg = msg.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display dialog "{safe_msg}" with title "{safe_title}" '
                    f'buttons {{"OK"}} default button "OK" with icon stop',
                ],
                timeout=120,
            )
        else:
            commands = [
                ["zenity", "--error", f"--title={title}", f"--text={msg}"],
                ["kdialog", "--error", msg, "--title", title],
                ["yad", "--error", f"--title={title}", f"--text={msg}"],
            ]

            for cmd in commands:
                try:
                    subprocess.run(cmd, timeout=120)
                    return
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

            if _show_error_qt(title, msg):
                return

            print(f"nexus: {title}\n{msg}")

    except Exception as e:
        print(f"theron: could not show dialog '{title}': {e}")


def _stop_playback() -> None:
    """Stop timeline playback if it is currently running."""
    try:
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            if screen.is_animation_playing:
                with bpy.context.temp_override(window=window, screen=screen):
                    bpy.ops.screen.animation_cancel(restore_frame=False)
                break
    except Exception as e:
        print(f"theron: could not stop playback: {e}")


def _check_result(result: int, func_name: str) -> bool:
    if result == TrResult.TR_RESULT_SUCCESS:
        return True
    try:
        name = TrResult(result).name
    except ValueError:
        name = f"UNKNOWN({result})"
    print(f"theron: {func_name} failed: {name}")
    if result == TrResult.TR_RESULT_GPU_ERROR:
        _show_error_dialog(
            "INSYDIUM NeXus",
            "A GPU crash occurred during simulation!",
        )
        reload_lib()
        _stop_playback()
    if result == TrResult.TR_RESULT_DEVICE_MEMORY_ALLOC:
        _show_error_dialog(
            "INSYDIUM NeXus",
            "NeXus ran out of GPU memory!\n\n"
            "Try reducing the simulation size, or raise the VRAM limit "
            "in NeXus preferences if you have available memory.",
        )
        reload_lib()
        _stop_playback()

    return False


# Win32 source-HANDLE refcount

_WIN32_HANDLE_OWNERS: Dict[int, set] = {}
_WIN32_SLOT_HANDLE: Dict[Tuple, int] = {}


def _track_win32_source_handle(slot_key: Tuple, handle: int) -> None:
    """Close *slot_key*'s previous source HANDLE once no slot still owns it."""
    if sys.platform != "win32":
        return
    prev = _WIN32_SLOT_HANDLE.get(slot_key)
    if prev == handle:
        return
    if prev is not None:
        owners = _WIN32_HANDLE_OWNERS.get(prev)
        if owners is not None:
            owners.discard(slot_key)
            if not owners:
                _WIN32_HANDLE_OWNERS.pop(prev, None)
                try:
                    ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(prev))
                except Exception:
                    pass
    if handle:
        _WIN32_HANDLE_OWNERS.setdefault(handle, set()).add(slot_key)
        _WIN32_SLOT_HANDLE[slot_key] = handle
    else:
        _WIN32_SLOT_HANDLE.pop(slot_key, None)


# Linux source-fd refcount

_LINUX_FD_OWNERS: Dict[int, set] = {}
_LINUX_SLOT_FD: Dict[Tuple, int] = {}


def _track_linux_source_fd(slot_key: Tuple, fd: int) -> None:
    """Close *slot_key*'s previous fd once no slot still owns it."""
    if sys.platform in ("win32", "darwin"):
        return
    prev = _LINUX_SLOT_FD.get(slot_key)
    if prev == fd:
        return
    if prev is not None:
        owners = _LINUX_FD_OWNERS.get(prev)
        if owners is not None:
            owners.discard(slot_key)
            if not owners:
                _LINUX_FD_OWNERS.pop(prev, None)
                try:
                    os.close(prev)
                except OSError:
                    pass
    if fd > 0:
        _LINUX_FD_OWNERS.setdefault(fd, set()).add(slot_key)
        _LINUX_SLOT_FD[slot_key] = fd
    else:
        _LINUX_SLOT_FD.pop(slot_key, None)


NOISE_TYPE_NAMES = {
    TrNoiseType.TR_NOISE_TYPE_SIMPLEX: "Simplex",
    TrNoiseType.TR_NOISE_TYPE_FBM: "FBM",
    TrNoiseType.TR_NOISE_TYPE_TURBULENCE: "Turbulence",
    TrNoiseType.TR_NOISE_TYPE_WAVY_TURBULENCE: "Wavy Turbulence",
    TrNoiseType.TR_NOISE_TYPE_VORONOISE: "Voronoise",
    TrNoiseType.TR_NOISE_TYPE_CUBIC: "Cubic",
}

PARTICLE_PROPERTY_NAMES = {
    TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION: "Position",
    TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY: "Velocity",
    TrParticleProperty.TR_PARTICLE_PROPERTY_ORIGIN_POS: "Origin Position",
    TrParticleProperty.TR_PARTICLE_PROPERTY_COLOR: "Color",
    TrParticleProperty.TR_PARTICLE_PROPERTY_SCALE: "Scale",
    TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION: "Rotation",
    TrParticleProperty.TR_PARTICLE_PROPERTY_FLUID_SURFACE: "Fluid Surface",
    TrParticleProperty.TR_PARTICLE_PROPERTY_UVW: "UVW",
    TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION_UP: "Rotation Up",
    TrParticleProperty.TR_PARTICLE_PROPERTY_MASS: "Mass",
    TrParticleProperty.TR_PARTICLE_PROPERTY_DELTA: "Delta",
    TrParticleProperty.TR_PARTICLE_PROPERTY_TIME: "Time",
    TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS: "Radius",
    TrParticleProperty.TR_PARTICLE_PROPERTY_GROUP: "Group",
    TrParticleProperty.TR_PARTICLE_PROPERTY_ID: "ID",
    TrParticleProperty.TR_PARTICLE_PROPERTY_FLAGS: "Flags",
    TrParticleProperty.TR_PARTICLE_PROPERTY_DISTANCE: "Distance",
    TrParticleProperty.TR_PARTICLE_PROPERTY_FRICTION: "Friction",
    TrParticleProperty.TR_PARTICLE_PROPERTY_BOUNCE: "Bounce",
    TrParticleProperty.TR_PARTICLE_PROPERTY_EMITTER_INDEX: "Emitter Index",
    TrParticleProperty.TR_PARTICLE_PROPERTY_GRANULAR: "Granular",
    TrParticleProperty.TR_PARTICLE_PROPERTY_LIFE: "Life",
    TrParticleProperty.TR_PARTICLE_PROPERTY_VERTEX_WEIGHT: "Vertex Weight",
    TrParticleProperty.TR_PARTICLE_PROPERTY_DENSITY: "Density",
    TrParticleProperty.TR_PARTICLE_PROPERTY_NB_DIST: "Nb Dist",
    TrParticleProperty.TR_PARTICLE_PROPERTY_MOD_TIME: "Mod Time",
    TrParticleProperty.TR_PARTICLE_PROPERTY_CUSTOM_DATA: "Custom Data",
    TrParticleProperty.TR_PARTICLE_PROPERTY_VERTEX_INDEX: "Vertex Index",
    TrParticleProperty.TR_PARTICLE_PROPERTY_FOAM: "Foam",
    TrParticleProperty.TR_PARTICLE_PROPERTY_DISPLAY: "Display",
    TrParticleProperty.TR_PARTICLE_PROPERTY_SUBFRAME_DELTA: "Subframe Delta",
    TrParticleProperty.TR_PARTICLE_PROPERTY_SMOKE: "Smoke",
    TrParticleProperty.TR_PARTICLE_PROPERTY_TEMPERATURE: "Temperature",
    TrParticleProperty.TR_PARTICLE_PROPERTY_FUEL: "Fuel",
}

_vec4 = np.dtype((np.float32, 4))

PARTICLE_PROPERTY_TYPES = {
    TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_ORIGIN_POS: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_COLOR: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_SCALE: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_FLUID_SURFACE: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_UVW: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION_UP: _vec4,
    TrParticleProperty.TR_PARTICLE_PROPERTY_MASS: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_DELTA: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_TIME: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_GROUP: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_ID: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_FLAGS: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_DISTANCE: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_FRICTION: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_BOUNCE: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_EMITTER_INDEX: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_GRANULAR: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_LIFE: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_VERTEX_WEIGHT: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_DENSITY: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_NB_DIST: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_MOD_TIME: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_CUSTOM_DATA: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_VERTEX_INDEX: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_FOAM: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_DISPLAY: np.int32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_SUBFRAME_DELTA: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_SMOKE: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_TEMPERATURE: np.float32,
    TrParticleProperty.TR_PARTICLE_PROPERTY_FUEL: np.float32,
}

EFX_CHANNEL_NAMES = {
    TrEFXChannel.TR_EFX_CHANNEL_SMOKE: "Smoke",
    TrEFXChannel.TR_EFX_CHANNEL_TEMPERATURE: "Temperature",
    TrEFXChannel.TR_EFX_CHANNEL_FUEL: "Fuel",
    TrEFXChannel.TR_EFX_CHANNEL_COLOR_R: "Color (Red)",
    TrEFXChannel.TR_EFX_CHANNEL_COLOR_G: "Color (Green)",
    TrEFXChannel.TR_EFX_CHANNEL_COLOR_B: "Color (Blue)",
}


_lib: Optional[ctypes.CDLL] = None
_initialized: bool = False
_shutting_down: bool = False
_gpu_error_pending: bool = False
_gpu_oom_pending: bool = False

_pipeline_ptrs: Dict[int, ctypes.c_void_p] = {}
_live_pipelines: set = set()

_dll_dir_handle: Optional[object] = None
_preloaded_dlls: Dict[str, ctypes.CDLL] = {}

_license_message: str = "Please enter a valid license to use INSYDIUM NeXus"


def get_license_message() -> str:
    return _license_message


def _require_lib(func_name: str) -> bool:
    """Check if the library is available for a normal (non-shutdown) C call."""
    if _shutting_down:
        return False
    if not _initialized or _lib is None:
        print(f"theron: {func_name} called but library is not initialized")
        return False
    return True


def _has_particle_property(pipeline_ptr: ctypes.c_void_p, prop: int) -> bool:
    """Check if a particle property is available on the pipeline.

    Returns True when the binding is missing so callers fall back to the
    regular fetch path (which logs once via ``_check_result``).
    """
    if _lib is None or not hasattr(_lib, "trParticleHasProperty"):
        return True
    try:
        has_prop = ctypes.c_bool(False)
        rc = _lib.trParticleHasProperty(pipeline_ptr, ctypes.c_int(prop), ctypes.byref(has_prop))
        return rc == TrResult.TR_RESULT_SUCCESS and bool(has_prop.value)
    except Exception:
        return False


def begin_shutdown() -> None:
    """Signal that shutdown has started."""
    global _shutting_down
    _shutting_down = True


def is_shutting_down() -> bool:
    return _shutting_down


def _get_library_path() -> str:
    libs_dir = os.path.dirname(__file__)

    if sys.platform == "darwin":
        lib_name = "libnexus.dylib"
    elif sys.platform == "win32":
        lib_name = "nexus.dll"
    else:
        lib_name = "libnexus.so"

    return os.path.join(libs_dir, lib_name)


def _read_license_prefs() -> tuple:
    """Return (serial, name, email) from addon preferences, or empty strings."""
    try:
        addon_id = __package__.rsplit(".", 1)[0]
        entry = bpy.context.preferences.addons.get(addon_id)
        if entry is None:
            return ("", "", "")
        p = entry.preferences
        return (p.license_key, p.license_name, p.license_email)
    except Exception:
        return ("", "", "")


def _read_vram_limit_bytes() -> int:
    """Return the vram_limit_gb pref converted to bytes (0 = unlimited)."""
    try:
        addon_id = __package__.rsplit(".", 1)[0]
        entry = bpy.context.preferences.addons.get(addon_id)
        if entry is None:
            return 0
        gb = entry.preferences.vram_limit_gb
        return int(gb * 1_000_000_000) if gb > 0.0 else 0
    except Exception:
        return 0


def init() -> bool:
    """Initialize the theron library.

    Loads the native library, sets up function signatures, and initializes resources.

    Returns:
        True if initialization succeeded, False otherwise.
    """

    global _lib, _initialized, _license_message

    if _initialized:
        return True

    # Don't make any licensing attempt unless online access is enabled
    if not bpy.app.online_access:
        _license_message = (
            'Please enable "Allow Online Access" in the Blender preferences for online licensing'
        )
        return False

    serial, name, email = _read_license_prefs()
    if not serial:
        _license_message = "Please enter a valid license to use INSYDIUM NeXus"
        return False

    lib_path = _get_library_path()

    try:
        _lib = ctypes.CDLL(lib_path)
        setup_function_signatures(_lib)

        if (
            _lib.trSetLicenseInfo(
                serial.encode(), ("nexus_blender").encode(), name.encode(), email.encode()
            )
            != TrResult.TR_RESULT_SUCCESS
        ):
            _license_message = "Failed to pass license info to library"
            _lib = None
            return False

        result = _lib.trInitialise()
        if result == TrResult.TR_RESULT_LICENSE_NO_NET:
            _license_message = "License server unreachable! Please check your internet connection."
            _lib = None
            return False
        if result == TrResult.TR_RESULT_LICENSE_FAIL:
            _license_message = "License check failed! Verify your license is valid"
            _lib = None
            return False
        if result != TrResult.TR_RESULT_SUCCESS:
            _license_message = f"Initialisation failed (error code: {result})"
            _lib = None
            return False

        # Select the first device - needs to be changed to match Blender viewport GPU
        _lib.trSelectDevice(0)

        _initialized = True

        vram_bytes = _read_vram_limit_bytes()
        if vram_bytes > 0:
            _lib.trSetVRAMLimit(ctypes.c_uint64(vram_bytes))

        # Setup shader compilation dir
        data_dir = bpy.utils.user_resource("DATAFILES", path="insydium_nexus", create=True)
        set_compiled_shader_cache_dir(data_dir)
        ensure_compiled_shaders_async()

        _license_message = ""
        return True

    except OSError as e:
        _license_message = f"Failed to load library: {e}"
        _lib = None
        _initialized = False
        return False
    except Exception as e:
        _license_message = f"Unexpected error during initialisation: {e}"
        _lib = None
        _initialized = False
        return False


def shutdown() -> None:
    """Shutdown the theron library and release resources."""

    global _lib, _initialized, _shutting_down, _license_message

    _license_message = ""
    _pipeline_ptrs.clear()

    native_handle = None

    if _lib is not None:
        remaining = list(_live_pipelines)
        _live_pipelines.clear()
        for pipeline in remaining:
            try:
                _lib.trDestroyModifierPipeline(ctypes.c_void_p(pipeline))
            except Exception as e:
                print(f"theron: Error destroying pipeline {pipeline} during cleanup: {e}")

    if _initialized and _lib is not None:
        try:
            _lib.trShutdown()
        except Exception as e:
            print(f"theron: Error during force cleanup: {e}")

        native_handle = getattr(_lib, "_handle", None)

    _lib = None
    _initialized = False
    _shutting_down = False

    if native_handle is not None:
        try:
            import _ctypes

            if sys.platform == "win32":
                _ctypes.FreeLibrary(native_handle)
            else:
                _ctypes.dlclose(native_handle)
        except ImportError:
            print("theron: _ctypes not available, native library handle not explicitly closed")
        except Exception as e:
            print(f"theron: Failed to unload native library handle: {e}")


def reload_lib() -> bool:
    """
    Does a full shutdown and reload of the simulation library, useful for a GPU crash, allowing the
    pipeline to be recreated and continue without application restart.
    """

    from ..handlers import pipeline

    shutdown()
    pipeline._clear_all_state()
    return init()


def is_initialized() -> bool:
    """Check if the library is initialized and ready for use."""
    return _initialized


def get_version_str() -> str:
    """Get the theron library version string.

    Returns:
        The Theron version string.
    """

    if not _require_lib("get_version_str"):
        return ""

    try:
        result = _lib.trGetVersionStr()
        return result.decode("utf-8")
    except Exception as e:
        print(f"theron: get_version_str error: {e}")
        return ""


def get_build_type() -> str:
    """Get the theron build type."""

    if not _require_lib("get_build_type"):
        return ""

    try:
        result = _lib.trGetBuildType()
        return result.decode("utf-8")
    except Exception as e:
        print(f"theron: get_build_type error: {e}")
        return ""


def get_build_date() -> str:
    """Get the unix time of the theron build."""

    if not _require_lib("get_build_date"):
        return ""

    try:
        return _lib.trGetBuildDate()
    except Exception as e:
        print(f"theron: get_build_date error: {e}")
        return ""


def submit_bug_report(name, email, subject, message, filename) -> int:

    if not _require_lib("submit_bug_report"):
        return -1

    try:
        application = "Blender " + bpy.app.version_string
        try:
            from ..viewport.registry import get_blender_gpu_backend

            backend = get_blender_gpu_backend()
            if backend:
                application += f"\nBackend: {backend}"
        except Exception:
            pass

        report_id = ctypes.c_int(-1)
        result = _lib.trSubmitBugReport(
            application.encode("utf-8"),
            ("NeXus Blender add-on v" + get_blender_version_str()).encode("utf-8"),
            name.encode("utf-8"),
            email.encode("utf-8"),
            subject.encode("utf-8"),
            message.encode("utf-8"),
            filename.encode("utf-8"),
            ctypes.byref(report_id),
        )

        if _check_result(result, "trSubmitBugReport"):
            return report_id.value
        return -1
    except Exception as e:
        print(f"theron: submit_bug_report error: {e}")
        return -1


def matrix_to_tr_matrix(matrix) -> TrDMatrix:
    """Convert a Blender 4x4 matrix to TrDMatrix."""

    tr_mat = TrDMatrix()
    tr_mat.off = TrDVec3(float(matrix[0][3]), float(matrix[1][3]), float(matrix[2][3]))
    tr_mat.v1 = TrDVec3(float(matrix[0][0]), float(matrix[1][0]), float(matrix[2][0]))
    tr_mat.v2 = TrDVec3(float(matrix[0][1]), float(matrix[1][1]), float(matrix[2][1]))
    tr_mat.v3 = TrDVec3(float(matrix[0][2]), float(matrix[1][2]), float(matrix[2][2]))
    return tr_mat


def create_prefs(
    octaves: int = 4,
    scale: float = 1.0,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    frequency: float = 1.0,
    amplitude: float = 1.0,
    absolute: bool = False,
) -> TrNoisePrefs:
    """Create a NoisePrefs structure with the specified parameters.

    Args:
        octaves: Number of noise octaves for fractal noise types.
        scale: Overall scale factor for the noise pattern.
        persistence: Amplitude multiplier between octaves (0.0-1.0).
        lacunarity: Frequency multiplier between octaves (typically 2.0).
        frequency: Base frequency of the noise.
        amplitude: Base amplitude of the noise output.
        absolute: If True, use absolute value of noise (for turbulence effects).

    Returns:
        A NoisePrefs structure ready for use with eval functions.
    """
    prefs = TrNoisePrefs()

    if not _shutting_down and _initialized and _lib is not None:
        _lib.trNoisePrefsInit(ctypes.byref(prefs))

    prefs.octaves = octaves
    prefs.scale = scale
    prefs.persistence = persistence
    prefs.lacunarity = lacunarity
    prefs.frequency = frequency
    prefs.amplitude = amplitude
    prefs.absolute = 1 if absolute else 0

    return prefs


def eval_1d(
    positions: List[Tuple[float, float, float]],
    noise_type: int,
    prefs: TrNoisePrefs,
    time: float = 0.0,
) -> List[float]:
    """Evaluate 1D noise at the given positions.

    Args:
        positions: List of (x, y, z) tuples representing sample positions.
        noise_type: One of the NOISE_* constants specifying the noise algorithm.
        prefs: NoisePrefs structure containing noise parameters.
        time: Time value for animated noise (default 0.0).

    Returns:
        List of float noise values, one per input position.
        Returns empty list if library is not initialized or on error.
    """
    if not _require_lib("eval_1d"):
        return []

    count = len(positions)
    if count == 0:
        return []

    try:
        pos_array = (TrVec3 * count)()
        for i, (x, y, z) in enumerate(positions):
            pos_array[i] = TrVec3(x, y, z)

        output_array = (ctypes.c_float * count)()

        result = _lib.trNoiseEval1D(
            pos_array,
            output_array,
            count,
            noise_type,
            ctypes.byref(prefs),
            time,
        )

        if result != 0:
            print(f"theron: eval_1d failed (error code: {result})")
            return []

        return [output_array[i] for i in range(count)]

    except Exception as e:
        print(f"theron: eval_1d error: {e}")
        return []


def eval_2d(
    positions: List[Tuple[float, float, float]],
    noise_type: int,
    prefs: TrNoisePrefs,
    time: float = 0.0,
) -> List[Tuple[float, float]]:
    """Evaluate 2D noise at the given positions.

    Args:
        positions: List of (x, y, z) tuples representing sample positions.
        noise_type: One of the NOISE_* constants specifying the noise algorithm.
        prefs: NoisePrefs structure containing noise parameters.
        time: Time value for animated noise (default 0.0).

    Returns:
        List of (x, y) tuples containing 2D noise values.
        Returns empty list if library is not initialized or on error.
    """
    if not _require_lib("eval_2d"):
        return []

    count = len(positions)
    if count == 0:
        return []

    try:
        pos_array = (TrVec3 * count)()
        for i, (x, y, z) in enumerate(positions):
            pos_array[i] = TrVec3(x, y, z)

        output_array = (TrVec2 * count)()

        result = _lib.trNoiseEval2D(
            pos_array,
            output_array,
            count,
            noise_type,
            ctypes.byref(prefs),
            time,
        )

        if result != 0:
            print(f"theron: eval_2d failed (error code: {result})")
            return []

        return [(output_array[i].x, output_array[i].y) for i in range(count)]

    except Exception as e:
        print(f"theron: eval_2d error: {e}")
        return []


def eval_3d(
    positions: List[Tuple[float, float, float]],
    noise_type: int,
    prefs: TrNoisePrefs,
    time: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """Evaluate 3D noise at the given positions.

    Args:
        positions: List of (x, y, z) tuples representing sample positions.
        noise_type: One of the NOISE_* constants specifying the noise algorithm.
        prefs: NoisePrefs structure containing noise parameters.
        time: Time value for animated noise (default 0.0).

    Returns:
        List of (x, y, z) tuples containing 3D noise values.
        Returns empty list if library is not initialized or on error.
    """
    if not _require_lib("eval_3d"):
        return []

    count = len(positions)
    if count == 0:
        return []

    try:
        pos_array = (TrVec3 * count)()
        for i, (x, y, z) in enumerate(positions):
            pos_array[i] = TrVec3(x, y, z)

        output_array = (TrVec3 * count)()

        result = _lib.trNoiseEval3D(
            pos_array,
            output_array,
            count,
            noise_type,
            ctypes.byref(prefs),
            time,
        )

        if result != 0:
            print(f"theron: eval_3d failed (error code: {result})")
            return []

        return [(output_array[i].x, output_array[i].y, output_array[i].z) for i in range(count)]

    except Exception as e:
        print(f"theron: eval_3d error: {e}")
        return []


def generate_noise_preview(
    resolution: int,
    noise_type: int,
    noise_channel: int,
    seed: int,
    prefs: TrNoisePrefs,
    low_clip: float,
    high_clip: float,
    brightness: float,
    contrast: float,
    gradient_lut: Optional[List[Tuple[float, float, float, float]]] = None,
) -> Optional[List[float]]:
    """Generate a 2D noise preview texture on the GPU.

    Evaluates noise over a 2D grid and returns RGBA float pixel data.

    Args:
        resolution: Square image resolution
        noise_type: One of the TrNoiseType constants.
        noise_channel: 0 = gradient-mapped, 1 = direct RGB.
        seed: Noise seed for spatial offset.
        prefs: NoisePrefs structure containing noise parameters.
        low_clip: Low clip threshold [0..1].
        high_clip: High clip threshold [0..1].
        brightness: Brightness offset.
        contrast: Contrast multiplier.
        gradient_lut: List of (r, g, b, a) float tuples for gradient mapping,
                      or None for direct RGB / greyscale fallback.

    Returns:
        Flat list of floats (resolution*resolution*4 RGBA values),
        or None on error.
    """
    if not _require_lib("generate_noise_preview"):
        return None

    if resolution == 0:
        return None

    try:
        pixel_count = resolution * resolution
        output_array = (ctypes.c_float * (pixel_count * 4))()

        grad_ptr = None
        grad_res = 0
        if gradient_lut is not None and len(gradient_lut) > 0:
            grad_res = len(gradient_lut)
            grad_array = (ctypes.c_float * (grad_res * 4))()
            for i, (r, g, b, a) in enumerate(gradient_lut):
                base = i * 4
                grad_array[base] = r
                grad_array[base + 1] = g
                grad_array[base + 2] = b
                grad_array[base + 3] = a
            grad_ptr = grad_array

        result = _lib.trGenerateNoisePreview(
            output_array,
            resolution,
            noise_type,
            noise_channel,
            seed,
            ctypes.byref(prefs),
            low_clip,
            high_clip,
            brightness,
            contrast,
            grad_ptr,
            grad_res,
        )

        if result != 0:
            print(f"theron: generate_noise_preview failed (error code: {result})")
            return None

        return list(output_array)

    except Exception as e:
        print(f"theron: generate_noise_preview error: {e}")
        return None


def create_pipeline() -> Optional[int]:
    """Create a new modifier pipeline for particle simulation.

    Returns:
        Pipeline handle as integer, or None if creation failed.
    """
    if not _require_lib("create_pipeline"):
        return None

    try:
        out = ctypes.c_void_p()
        upDir = TrVec3(0, 0, 1)
        forwardDir = TrVec3(0, 1, 0)
        result = _lib.trCreateModifierPipeline(
            ctypes.byref(out),
            TrHandedness.TR_HANDEDNESS_RIGHT,
            ctypes.byref(upDir),
            ctypes.byref(forwardDir),
            1.0,
        )
        if _check_result(result, "trCreateModifierPipeline") and out.value:
            _live_pipelines.add(out.value)
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_pipeline error: {e}")
        return None


def set_particle_copy_mode(pipeline: int, mode: int) -> None:
    """Set the particle copy mode for a pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        mode: TrParticleCopyMode value.
    """
    if not _require_lib("set_particle_copy_mode"):
        return

    try:
        result = _lib.trSetParticleCopyMode(ctypes.c_void_p(pipeline), mode)
        _check_result(result, "trSetParticleCopyMode")
    except Exception as e:
        print(f"theron: set_particle_copy_mode error: {e}")


def destroy_pipeline(pipeline: int) -> None:
    """Destroy a modifier pipeline and free its resources.

    This function only checks _lib (not _shutting_down or _initialized)
    so it can still run during shutdown while the native library is loaded.

    Args:
        pipeline: Pipeline handle from create_pipeline().
    """
    if _lib is None:
        return

    _live_pipelines.discard(pipeline)
    try:
        result = _lib.trDestroyModifierPipeline(ctypes.c_void_p(pipeline))
        _check_result(result, "trDestroyModifierPipeline")
    except Exception as e:
        print(f"theron: destroy_pipeline error: {e}")


def execute_frame(pipeline: int, frame: int) -> None:
    """Execute one frame of particle simulation.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        frame: Frame number to simulate.
    """
    if not _require_lib("execute_frame"):
        return

    try:
        result = _lib.trExecuteFrame(ctypes.c_void_p(pipeline), frame)
        _check_result(result, "trExecuteFrame")
    except Exception as e:
        print(f"theron: execute_frame error: {e}")


def set_fps(pipeline: int, fps: float) -> None:
    """Sets the FPS for the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        fps: Frames per second value.
    """
    if not _require_lib("set_fps"):
        return

    try:
        result = _lib.trSetFps(ctypes.c_void_p(pipeline), fps)
        _check_result(result, "trSetFps")
    except Exception as e:
        print(f"theron: set_fps error: {e}")


def set_substeps(pipeline: int, substeps: int) -> None:
    """Sets the number of substeps for the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        substeps: Number of substeps to simulate.
    """
    if not _require_lib("set_substeps"):
        return

    try:
        result = _lib.trSetSubsteps(ctypes.c_void_p(pipeline), substeps)
        _check_result(result, "trSetSubsteps")
    except Exception as e:
        print(f"theron: set_substeps error: {e}")


def set_min_max_time(
    pipeline: int,
    min_num: int,
    min_den: int,
    max_num: int,
    max_den: int,
) -> None:
    """Sets the timeline bounds for the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        min_num: Numerator for minimum time (e.g. frame_start * 1000).
        min_den: Denominator for minimum time (e.g. fps * 1000).
        max_num: Numerator for maximum time (e.g. frame_end * 1000).
        max_den: Denominator for maximum time (e.g. fps * 1000).
    """
    if not _require_lib("set_min_max_time"):
        return

    try:
        result = _lib.trSetMinMaxTime(
            ctypes.c_void_p(pipeline),
            TrTime(min_num, min_den),
            TrTime(max_num, max_den),
        )
        _check_result(result, "trSetMinMaxTime")
    except Exception as e:
        print(f"theron: set_min_max_time error: {e}")


def add_modifier(pipeline: int, modifier_type: int) -> Optional[int]:
    """Add a modifier to the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        modifier_type: One of the TR_MODIFIER_TYPE_* constants.

    Returns:
        Modifier handle, or None if creation failed.
    """
    if not _require_lib("add_modifier"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trAddModifier(ctypes.c_void_p(pipeline), modifier_type, ctypes.byref(out))
        if _check_result(result, "trAddModifier") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: add_modifier error: {e}")
        return None


def get_modifier_container(modifier: int) -> Optional[int]:
    """Get the data container for a modifier.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        Container handle, or None if not available.
    """
    if not _require_lib("get_modifier_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetModifierContainer(ctypes.c_void_p(modifier), ctypes.byref(out))
        if _check_result(result, "trGetModifierContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_modifier_container error: {e}")
        return None


def free_modifier(modifier: int) -> None:
    """Free a modifier and its resources.

    Args:
        modifier: Modifier handle from add_modifier().
    """
    if not _require_lib("free_modifier"):
        return

    try:
        result = _lib.trFreeModifier(ctypes.c_void_p(modifier))
        _check_result(result, "trFreeModifier")
    except Exception as e:
        print(f"theron: free_modifier error: {e}")


def free_object(obj: int) -> None:
    """Free a theron object

    Args:
        modifier: Object handle
    """
    if not _require_lib("free_object"):
        return

    try:
        result = _lib.trFreeObject(ctypes.c_void_p(obj))
        _check_result(result, "trFreeObject")
    except Exception as e:
        print(f"theron: free_object error: {e}")


def modifier_set_matrix(modifier: int, matrix) -> None:
    """Set the world transformation matrix for a modifier.

    Args:
        modifier: Modifier handle from add_modifier().
        matrix: 4x4 transformation matrix (mathutils.Matrix or nested list).
    """
    if not _require_lib("modifier_set_matrix"):
        return

    try:
        tr_mat = matrix_to_tr_matrix(matrix)
        result = _lib.trModifierSetMg(ctypes.c_void_p(modifier), ctypes.byref(tr_mat))
        _check_result(result, "trModifierSetMg")
    except Exception as e:
        print(f"theron: modifier_set_matrix error: {e}")


def modifier_move(modifier: int, prev: int | None) -> None:
    """Move a modifier to a new position in the pipeline execution order.

    Args:
        modifier: Modifier handle to move.
        prev: Handle of the modifier to insert after, or None to insert at
              the start of the pipeline.
    """
    if not _require_lib("modifier_move"):
        return

    try:
        result = _lib.trModifierMove(ctypes.c_void_p(modifier), ctypes.c_void_p(prev))
        _check_result(result, "trModifierMove")
    except Exception as e:
        print(f"theron: modifier_move error: {e}")


def create_emitter(pipeline: int) -> Optional[int]:
    """Create an emitter in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        Emitter handle, or None if creation failed.
    """
    if not _require_lib("create_emitter"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateEmitter(ctypes.c_void_p(pipeline), ctypes.byref(out))
        if _check_result(result, "trCreateEmitter") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_emitter error: {e}")
        return None


def get_emitter_count(pipeline: int) -> int:
    """Return the number of emitters currently registered in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        Number of emitters, or 0 on error.
    """
    if not _require_lib("get_emitter_count"):
        return 0

    try:
        count = ctypes.c_size_t(0)
        result = _lib.trGetEmitterCount(ctypes.c_void_p(pipeline), ctypes.byref(count))
        if _check_result(result, "trGetEmitterCount"):
            return int(count.value)
        return 0
    except Exception as e:
        print(f"theron: get_emitter_count error: {e}")
        return 0


def get_emitter(pipeline: int, index: int) -> Optional[int]:
    """Return the emitter handle at the given index.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        index: Zero-based emitter index (0 to get_emitter_count()-1).

    Returns:
        Emitter handle, or None on error.
    """
    if not _require_lib("get_emitter"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetEmitter(
            ctypes.c_void_p(pipeline), ctypes.c_size_t(index), ctypes.byref(out)
        )
        if _check_result(result, "trGetEmitter") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_emitter error: {e}")
        return None


def get_emitter_container(emitter: int) -> Optional[int]:
    """Get the data container for an emitter.

    Args:
        emitter: Emitter handle from create_emitter().

    Returns:
        Container handle as integer, or None if not available.
    """
    if not _require_lib("get_emitter_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetEmitterContainer(ctypes.c_void_p(emitter), ctypes.byref(out))
        if _check_result(result, "trGetEmitterContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_emitter_container error: {e}")
        return None


def get_emitter_object_index(pipeline: int, emitter: int) -> Optional[int]:
    """Return Theron's current index for an emitter object."""
    if not _require_lib("get_emitter_object_index"):
        return None
    if not hasattr(_lib, "trGetEmitterObjectIndex"):
        return None

    try:
        out = ctypes.c_int32(-1)
        result = _lib.trGetEmitterObjectIndex(
            ctypes.c_void_p(pipeline),
            ctypes.c_void_p(emitter),
            ctypes.byref(out),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return None
        if _check_result(result, "trGetEmitterObjectIndex"):
            return int(out.value)
        return None
    except Exception as e:
        print(f"theron: get_emitter_object_index error: {e}")
        return None


def emitter_set_matrix(emitter: int, matrix) -> None:
    """Set the world transformation matrix for an emitter.

    Args:
        emitter: Emitter handle from create_emitter().
        matrix: transform
    """
    if not _require_lib("emitter_set_matrix"):
        return

    try:
        tr_mat = matrix_to_tr_matrix(matrix)
        result = _lib.trEmitterSetMg(ctypes.c_void_p(emitter), ctypes.byref(tr_mat))
        _check_result(result, "trEmitterSetMg")
    except Exception as e:
        print(f"theron: emitter_set_matrix error: {e}")


def free_emitter(emitter: int) -> None:
    """Free an emitter and its resources.

    Args:
        emitter: Emitter handle from create_emitter().
    """
    if not _require_lib("free_emitter"):
        return

    try:
        result = _lib.trFreeEmitter(ctypes.c_void_p(emitter))
        _check_result(result, "trFreeEmitter")
    except Exception as e:
        print(f"theron: free_emitter error: {e}")


def get_emitter_particle_count(emitter: int) -> int:
    """Get the number of particles owned by an emitter.

    Args:
        emitter: Emitter handle from create_emitter().

    Returns:
        Number of particles, or 0 if not available.
    """
    if not _require_lib("get_emitter_particle_count"):
        return 0

    try:
        out = ctypes.c_uint64()
        result = _lib.trGetEmitterParticleCount(ctypes.c_void_p(emitter), ctypes.byref(out))
        if _check_result(result, "trGetEmitterParticleCount"):
            return out.value
        return 0
    except Exception as e:
        print(f"theron: get_emitter_particle_count error: {e}")
        return 0


def create_cache_instance(pipeline: int) -> Optional[int]:
    """Create a cache instance in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        Cache instance handle, or None if creation failed.
    """
    if not _require_lib("create_cache_instance"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateCacheInstance(ctypes.c_void_p(pipeline), ctypes.byref(out))
        if _check_result(result, "trCreateCacheInstance") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_cache_instance error: {e}")
        return None


def get_cache_status(pipeline: int, cache: int) -> Optional[tuple[int, bool, int, int, int]]:
    """Get the current status of a cache instance.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        cache: Cache instance handle from create_cache_instance().

    Returns:
        Tuple of (cached_frames, job_complete, mem_size, disk_size, uncompressed_size),
        or None on failure. Size values are in bytes.
    """
    if not _require_lib("get_cache_status"):
        return None

    try:
        cached_frames = ctypes.c_int64()
        job_complete = ctypes.c_bool()
        mem_size = ctypes.c_size_t()
        disk_size = ctypes.c_size_t()
        uncompressed_size = ctypes.c_size_t()
        result = _lib.trGetCacheStatus(
            ctypes.c_void_p(pipeline),
            ctypes.c_void_p(cache),
            ctypes.byref(cached_frames),
            ctypes.byref(job_complete),
            ctypes.byref(mem_size),
            ctypes.byref(disk_size),
            ctypes.byref(uncompressed_size),
        )
        if _check_result(result, "trGetCacheStatus"):
            return (
                cached_frames.value,
                job_complete.value,
                mem_size.value,
                disk_size.value,
                uncompressed_size.value,
            )
        return None
    except Exception as e:
        print(f"theron: get_cache_status error: {e}")
        return None


def clear_cache(cache: int) -> bool:
    """Clear all cached frames from a cache instance.

    Args:
        cache: Cache instance handle from create_cache_instance().

    Returns:
        True if the cache was cleared successfully, False otherwise.
    """
    if not _require_lib("clear_cache"):
        return False

    try:
        result = _lib.trClearCache(ctypes.c_void_p(cache))
        return _check_result(result, "trClearCache")
    except Exception as e:
        print(f"theron: clear_cache error: {e}")
        return False


def build_full_cache_async(pipeline: int, cache: int) -> bool:
    """Start an asynchronous full-cache build.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        cache: Cache instance handle from create_cache_instance().

    Returns:
        True if the build was started successfully, False otherwise.
    """
    if not _require_lib("build_full_cache_async"):
        return False

    try:
        result = _lib.trBuildFullCache_Async(ctypes.c_void_p(pipeline), ctypes.c_void_p(cache))
        return _check_result(result, "trBuildFullCache_Async")
    except Exception as e:
        print(f"theron: build_full_cache_async error: {e}")
        return False


def cancel_cache_build(pipeline: int) -> bool:
    """Cancel an in-progress async cache build and block until the build thread exits.

    Safe to call when no build is running.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        True if successful, False otherwise.
    """
    if not _require_lib("cancel_cache_build"):
        return False

    try:
        result = _lib.trCancelCacheBuild(ctypes.c_void_p(pipeline))
        return _check_result(result, "trCancelCacheBuild")
    except Exception as e:
        print(f"theron: cancel_cache_build error: {e}")
        return False


def create_particle_group(pipeline: int) -> Optional[int]:
    """Create a particle group in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        Particle group handle, or None if creation failed.
    """
    if not _require_lib("create_particle_group"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateParticleGroup(ctypes.c_void_p(pipeline), ctypes.byref(out))
        if _check_result(result, "trCreateParticleGroup") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_particle_group error: {e}")
        return None


def add_emitter_to_group(group: int, emitter: int) -> None:
    """Add an emitter to a particle group.

    Args:
        group: Particle group handle from create_particle_group().
        emitter: Emitter handle from create_emitter().
    """
    if not _require_lib("add_emitter_to_group"):
        return

    try:
        result = _lib.trAddEmitterToGroup(ctypes.c_void_p(group), ctypes.c_void_p(emitter))
        _check_result(result, "trAddEmitterToGroup")
    except Exception as e:
        print(f"theron: add_emitter_to_group error: {e}")


def remove_emitter_from_group(group: int, emitter: int) -> None:
    """Remove an emitter from a particle group.

    Args:
        group: Particle group handle from create_particle_group().
        emitter: Emitter handle from create_emitter().
    """
    if not _require_lib("remove_emitter_from_group"):
        return

    try:
        result = _lib.trRemoveEmitterFromGroup(ctypes.c_void_p(group), ctypes.c_void_p(emitter))
        _check_result(result, "trRemoveEmitterFromGroup")
    except Exception as e:
        print(f"theron: remove_emitter_from_group error: {e}")


def free_particle_group(group: int) -> None:
    """Free a particle group and its resources.

    Args:
        group: Particle group handle from create_particle_group().
    """
    if not _require_lib("free_particle_group"):
        return

    try:
        result = _lib.trFreeParticleGroup(ctypes.c_void_p(group))
        _check_result(result, "trFreeParticleGroup")
    except Exception as e:
        print(f"theron: free_particle_group error: {e}")


def create_falloff() -> Optional[int]:
    """Create a falloff object.

    Returns:
        Falloff handle, or None if creation failed.
    """
    if not _require_lib("create_falloff"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateFalloff(ctypes.byref(out))
        if _check_result(result, "trCreateFalloff") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_falloff error: {e}")
        return None


def free_falloff(falloff: int) -> None:
    """Free a falloff object and its resources.

    Args:
        falloff: Falloff handle from create_falloff().
    """
    if not _require_lib("free_falloff"):
        return

    try:
        result = _lib.trFreeFalloff(ctypes.c_void_p(falloff))
        _check_result(result, "trFreeFalloff")
    except Exception as e:
        print(f"theron: free_falloff error: {e}")


def create_camera() -> Optional[int]:
    """Create a Theron CameraObject.

    Returns:
        Camera handle, or None if creation failed.
    """
    if not _require_lib("create_camera"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateCamera(ctypes.byref(out))
        if _check_result(result, "trCreateCamera") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_camera error: {e}")
        return None


def set_camera_fov(camera: int, fov_x: float, fov_y: float) -> None:
    """Set horizontal and vertical FOV on a Theron CameraObject.

    Args:
        camera: Camera handle from create_camera().
        fov_x: Horizontal field of view in radians.
        fov_y: Vertical field of view in radians.
    """
    if not _require_lib("set_camera_fov"):
        return

    try:
        result = _lib.trSetCameraFov(
            ctypes.c_void_p(camera),
            ctypes.c_double(fov_x),
            ctypes.c_double(fov_y),
        )
        _check_result(result, "trSetCameraFov")
    except Exception as e:
        print(f"theron: set_camera_fov error: {e}")


class CameraProjection:
    PERSPECTIVE = 0
    ORTHOGRAPHIC = 1
    PANORAMIC = 2


def set_camera_projection(camera: int, projection: int) -> None:
    """Set the projection type of a Theron CameraObject.

    Args:
        camera: Handle from create_camera().
        projection: CameraProjection.PERSPECTIVE | ORTHOGRAPHIC | PANORAMIC.
    """
    if not _require_lib("set_camera_projection"):
        return

    try:
        result = _lib.trSetCameraProjection(
            ctypes.c_void_p(camera),
            ctypes.c_int(projection),
        )
        _check_result(result, "trSetCameraProjection")
    except Exception as e:
        print(f"theron: set_camera_projection error: {e}")


def set_camera_ortho_scale(camera: int, half_x: float, half_y: float) -> None:
    """Set orthographic half-widths (camera-local, world units) on a CameraObject.

    Args:
        camera: Handle from create_camera().
        half_x: Half-width along camera local X.
        half_y: Half-width along camera local Y.
    """
    if not _require_lib("set_camera_ortho_scale"):
        return

    try:
        result = _lib.trSetCameraOrthoScale(
            ctypes.c_void_p(camera),
            ctypes.c_double(half_x),
            ctypes.c_double(half_y),
        )
        _check_result(result, "trSetCameraOrthoScale")
    except Exception as e:
        print(f"theron: set_camera_ortho_scale error: {e}")


def get_object_container(object: int) -> Optional[int]:
    """Get the data container for an object."""

    if not _require_lib("get_object_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetContainer(ctypes.c_void_p(object), ctypes.byref(out))
        if _check_result(result, "trGetContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_object_container error: {e}")
        return None


def set_matrix(object: int, matrix) -> None:
    """Set the world transformation matrix for a base object.

    Args:
        object: Object handle (trBaseObject).
        matrix: 4x4 transformation matrix (mathutils.Matrix or nested list).
    """
    if not _require_lib("set_matrix"):
        return

    try:
        tr_mat = matrix_to_tr_matrix(matrix)
        result = _lib.trSetMg(ctypes.c_void_p(object), ctypes.byref(tr_mat))
        _check_result(result, "trSetMg")
    except Exception as e:
        print(f"theron: set_matrix error: {e}")


def set_int32(container: int, param_id: int, value: int) -> None:
    """Set an integer parameter on a container.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant (e.g., ID_NX_GRAVITY_MODE).
        value: Integer value to set.
    """
    if not _require_lib("set_int32"):
        return

    try:
        result = _lib.trSetInt32(ctypes.c_void_p(container), param_id, value)
        _check_result(result, "trSetInt32")
    except Exception as e:
        print(f"theron: set_int32 error: {e}")


def set_float(container: int, param_id: int, value: float) -> None:
    """Set a float parameter on a container.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant (e.g., ID_NX_GRAVITY_STRENGTH).
        value: Float value to set.
    """
    if not _require_lib("set_float"):
        return

    try:
        result = _lib.trSetFloat(ctypes.c_void_p(container), param_id, value)
        _check_result(result, "trSetFloat")
    except Exception as e:
        print(f"theron: set_float error: {e}")


def set_bool(container: int, param_id: int, value: bool) -> None:
    """Set a bool parameter on a container.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant (e.g., ID_NX_GRAVITY_ENABLED).
        value: Bool value to set.
    """
    if not _require_lib("set_bool"):
        return

    try:
        result = _lib.trSetBool(ctypes.c_void_p(container), param_id, value)
        _check_result(result, "trSetBool")
    except Exception as e:
        print(f"theron: set_bool error: {e}")


def get_bool(container: int, param_id: int) -> bool:
    """Get a bool parameter from a container.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant.

    Returns:
        Bool value, or False if unavailable.
    """
    if not _require_lib("get_bool"):
        return False

    try:
        value = ctypes.c_bool(False)
        result = _lib.trGetBool(ctypes.c_void_p(container), param_id, ctypes.byref(value))
        if _check_result(result, "trGetBool"):
            return bool(value.value)
        return False
    except Exception as e:
        print(f"theron: get_bool error: {e}")
        return False


def set_time(container: int, param_id: int, numerator: int, denominator: int) -> None:
    """Set a Time parameter on a container.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant for a BaseTime parameter.
        numerator: Numerator of the time fraction.
        denominator: Denominator of the time fraction.
    """
    if not _require_lib("set_time"):
        return

    try:
        result = _lib.trSetTime(
            ctypes.c_void_p(container), param_id, TrTime(numerator, denominator)
        )
        _check_result(result, "trSetTime")
    except Exception as e:
        print(f"theron: set_time error: {e}")


def set_link(container: int, param_id: int, link_object: Optional[int]) -> None:
    """Set a link parameter on a container to reference a base object.

    Args:
        container: Container handle from get_modifier_container() or get_emitter_container().
        param_id: Parameter ID constant for a link parameter.
        link_object: Object handle (trBaseObject) to link to, or None to clear the link.
    """
    if not _require_lib("set_link"):
        return

    try:
        result = _lib.trSetLink(ctypes.c_void_p(container), param_id, ctypes.c_void_p(link_object))
        _check_result(result, "trSetLink")
    except Exception as e:
        print(f"theron: set_link error: {e}")


def set_string(container: int, param_id: int, value: str) -> None:
    """Set a string parameter on a container.

    Args:
        container: Container handle
        param_id: Parameter ID constant (e.g., ID_NX_GRAVITY_MODE).
        value: String to set.
    """
    if not _require_lib("set_string"):
        return

    try:
        result = _lib.trSetString(
            ctypes.c_void_p(container), param_id, ctypes.c_char_p(value.encode("utf-8"))
        )
        _check_result(result, "trSetString")
    except Exception as e:
        print(f"theron: set_string error: {e}")


def get_particle_count(pipeline: int) -> int:
    """Get the number of particles in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        Number of particles, or 0 if not available.
    """
    if not _require_lib("get_particle_count"):
        return 0

    try:
        out = ctypes.c_uint64()
        result = _lib.trGetParticleCount(ctypes.c_void_p(pipeline), ctypes.byref(out))
        if _check_result(result, "trGetParticleCount"):
            return out.value
        return 0
    except Exception as e:
        print(f"theron: get_particle_count error: {e}")
        return 0


def get_particle_position(pipeline: int, index: int) -> Optional[Tuple[float, float, float]]:
    """Get the position of a single particle.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        index: Particle index (0 to particle_count-1).

    Returns:
        Tuple of (x, y, z) position, or None if not available.
    """
    if not _require_lib("get_particle_position"):
        return None

    try:
        out = TrVec3()
        result = _lib.trGetParticlePosition(
            ctypes.c_void_p(pipeline), ctypes.c_uint64(index), ctypes.byref(out)
        )
        if _check_result(result, "trGetParticlePosition"):
            return (out.x, out.y, out.z)
        return None
    except Exception as e:
        print(f"theron: get_particle_position error: {e}")
        return None


def get_all_particle_positions(pipeline: int) -> List[Tuple[float, float, float]]:
    """Get positions of all particles in the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        List of (x, y, z) tuples for each particle position.
        Returns empty list if not available.
    """
    if not _require_lib("get_all_particle_positions"):
        return []

    try:
        count_out = ctypes.c_uint64()
        result = _lib.trGetParticleCount(ctypes.c_void_p(pipeline), ctypes.byref(count_out))
        if not _check_result(result, "trGetParticleCount"):
            return []
        count = count_out.value
        if count == 0:
            return []

        buffer = (TrVec3 * count)()
        pipeline_ptr = ctypes.c_void_p(pipeline)
        get_pos = _lib.trGetParticlePosition
        for i in range(count):
            get_pos(pipeline_ptr, ctypes.c_uint64(i), ctypes.byref(buffer[i]))

        return [(buffer[i].x, buffer[i].y, buffer[i].z) for i in range(count)]
    except Exception as e:
        print(f"theron: get_all_particle_positions error: {e}")
        return []


def get_all_particle_positions_fast(pipeline: int) -> List[Tuple[float, float, float]]:
    """Get positions of all particles optimized for GPU rendering.

    Returns positions in Blender native coordinates (Z-up, right-handed, meters).

    Args:
        pipeline: Pipeline handle from create_pipeline().

    Returns:
        List of (x, y, z) tuples in Blender coordinates, ready for batch_for_shader.
        Returns empty list if not available.
    """
    if not _require_lib("get_all_particle_positions_fast"):
        return []

    try:
        count_out = ctypes.c_uint64()
        result = _lib.trGetParticleCount(ctypes.c_void_p(pipeline), ctypes.byref(count_out))
        if not _check_result(result, "trGetParticleCount"):
            return []
        count = count_out.value
        if count == 0:
            return []

        buffer = (TrVec3 * count)()
        pipeline_ptr = ctypes.c_void_p(pipeline)
        get_pos = _lib.trGetParticlePosition
        for i in range(count):
            get_pos(pipeline_ptr, ctypes.c_uint64(i), ctypes.byref(buffer[i]))

        raw_array = np.ctypeslib.as_array(buffer)
        positions = raw_array.view(dtype=np.float32).reshape(count, 3)

        return [tuple(row) for row in positions]
    except Exception as e:
        print(f"theron: get_all_particle_positions_fast error: {e}")
        return []


def _view_vec3(arr: np.ndarray, count: int) -> np.ndarray:
    # Vector properties are stored as vec4 in Theron for alignment;
    # the last lane is padding, so slice it off.
    return arr.reshape(count, 4)[:, :3]


def _view_scalar(arr: np.ndarray, count: int) -> np.ndarray:
    return arr


def _view_uint32(arr: np.ndarray, count: int) -> np.ndarray:
    return arr.view(np.uint32)


# (element dtype, elements per particle, NumPy view builder) for each property
# that ``get_particle_property_for_gpu`` knows how to fetch on the CPU side.
# Vector properties read 4 float32s (vec4 storage) and slice down to (N, 3).
_PROPERTY_FETCH_SPEC = {
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION): (np.float32, 4, _view_vec3),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_COLOR): (np.float32, 4, _view_vec3),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY): (np.float32, 4, _view_vec3),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_ROTATION): (np.float32, 4, _view_vec3),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_RADIUS): (np.float32, 1, _view_scalar),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_EMITTER_INDEX): (np.int32, 1, _view_uint32),
    int(TrParticleProperty.TR_PARTICLE_PROPERTY_ID): (np.int32, 1, _view_uint32),
}


def get_particle_property_for_gpu(
    pipeline: int,
    prop: int,
    scene_key: int = 0,
) -> Optional[Tuple[np.ndarray, int]]:
    """Read all per-particle values for ``prop`` as a NumPy view + count.

    Returns ``None`` silently when the property isn't present on the pipeline,
    so basic-mode fallbacks (e.g. rotation) don't spam the console. Shape and
    dtype follow the property kind: vec3 → (N, 3) float32, scalar float →
    (N,) float32, scalar int → (N,) uint32.
    """
    prop_int = int(prop)
    spec = _PROPERTY_FETCH_SPEC.get(prop_int)
    if spec is None:
        return None
    element_dtype, stride, view_fn = spec
    dtype = np.dtype(element_dtype)
    func_name = f"get_particle_property_for_gpu[{prop_int}]"

    if not _require_lib(func_name):
        return None
    if not hasattr(_lib, "trGetParticlePropertyData"):
        return None

    try:
        pipeline_ptr = _pipeline_ptrs.get(scene_key)
        if pipeline_ptr is None or pipeline_ptr.value != pipeline:
            pipeline_ptr = ctypes.c_void_p(pipeline)
            _pipeline_ptrs[scene_key] = pipeline_ptr

        if not _has_particle_property(pipeline_ptr, prop_int):
            return None

        count_out = ctypes.c_uint64()
        rc = _lib.trGetParticleCount(pipeline_ptr, ctypes.byref(count_out))
        if not _check_result(rc, "trGetParticleCount"):
            return None
        count = int(count_out.value)
        if count == 0:
            return None

        data_ptr = ctypes.c_void_p()
        rc = _lib.trGetParticlePropertyData(
            pipeline_ptr, ctypes.c_int(prop_int), ctypes.byref(data_ptr)
        )
        if not _check_result(rc, "trGetParticlePropertyData"):
            return None
        if not data_ptr.value:
            return None

        n_elements = count * stride
        buf = (ctypes.c_char * (n_elements * dtype.itemsize)).from_address(data_ptr.value)
        arr = np.frombuffer(buf, dtype=dtype, count=n_elements)
        arr.flags.writeable = False
        return (view_fn(arr, count), count)
    except Exception as e:
        print(f"theron: {func_name} error: {e}")
        return None


def get_particle_data_buffer_export(
    pipeline: int,
    prop: int = TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION,
) -> Optional[Tuple[int, int, int]]:
    """Get (handle_or_fd, size_bytes, uid) for the GPU data buffer of a particle property.

    On Windows this is a Win32 HANDLE suitable for GL_EXT_external_objects_win32 import.
    On other platforms it is a POSIX file descriptor where supported.
    ``uid`` is a stable identity key assigned at export time.
    Returns None if the export API is unavailable or the buffer cannot be exported.
    """
    if not _require_lib("get_particle_data_buffer_export"):
        return None

    if not hasattr(_lib, "trGetParticleDataBufferExport"):
        return None

    try:
        out = TrBufferExport()
        result = _lib.trGetParticleDataBufferExport(
            ctypes.c_void_p(pipeline),
            ctypes.c_int(prop),
            ctypes.byref(out),
        )
        if not _check_result(result, "trGetParticleDataBufferExport"):
            return None

        if sys.platform == "win32":
            handle = int(out.handle)
        elif sys.platform == "darwin":
            handle = int(out.mtlBuffer)
        else:
            handle = int(out.fileDescriptor)

        size = int(out.size)
        uid = int(out.uid) if out.uid else 0

        if handle <= 0 or size == 0:
            return None

        _track_win32_source_handle((int(pipeline), "data", int(prop)), handle)
        return (handle, size, uid)
    except Exception as e:
        print(f"theron: get_particle_data_buffer_export error: {e}")
        return None


def get_particle_draw_mode_buffer_exports(
    pipeline: int,
) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    """Get GPU exports for draw-mode prefix sums and binned particle indices.

    Returns:
        ``((prefix_handle, prefix_size, prefix_uid), (binned_handle, binned_size, binned_uid))``
        or None.
    """
    if not _require_lib("get_particle_draw_mode_buffer_exports"):
        return None

    if not hasattr(_lib, "trGetParticleDrawModeBufferExports"):
        return None

    def _safe_int(value) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    try:
        prefix_out = TrBufferExport()
        binned_out = TrBufferExport()
        result = _lib.trGetParticleDrawModeBufferExports(
            ctypes.c_void_p(pipeline),
            ctypes.byref(prefix_out),
            ctypes.byref(binned_out),
        )
        if not _check_result(result, "trGetParticleDrawModeBufferExports"):
            return None

        if sys.platform == "win32":
            prefix_handle = _safe_int(getattr(prefix_out, "handle", None))
            binned_handle = _safe_int(getattr(binned_out, "handle", None))
        elif sys.platform == "darwin":
            prefix_handle = _safe_int(getattr(prefix_out, "mtlBuffer", None))
            binned_handle = _safe_int(getattr(binned_out, "mtlBuffer", None))
        else:
            prefix_handle = _safe_int(getattr(prefix_out, "fileDescriptor", None))
            binned_handle = _safe_int(getattr(binned_out, "fileDescriptor", None))

        prefix_size = _safe_int(getattr(prefix_out, "size", 0))
        binned_size = _safe_int(getattr(binned_out, "size", 0))
        prefix_uid = int(prefix_out.uid) if getattr(prefix_out, "uid", 0) else 0
        binned_uid = int(binned_out.uid) if getattr(binned_out, "uid", 0) else 0
        if prefix_handle <= 0 or binned_handle <= 0 or prefix_size == 0 or binned_size == 0:
            return None

        _track_win32_source_handle((int(pipeline), "draw_prefix"), prefix_handle)
        _track_win32_source_handle((int(pipeline), "draw_binned"), binned_handle)
        return (
            (prefix_handle, prefix_size, prefix_uid),
            (binned_handle, binned_size, binned_uid),
        )
    except Exception as e:
        print(f"theron: get_particle_draw_mode_buffer_exports error: {e}")
        return None


def get_particle_id_lut_buffer_export(
    pipeline: int,
) -> Optional[Tuple[int, int, int, int]]:
    """Get the GPU export for the centralised particle ID → index hash table.

    Returns ``(handle, size_bytes, uid, lut_size)`` or None when unavailable.
    The LUT is a flat ``int[lut_size]`` of particle indices; empty slots hold
    ``-1``. Lookup uses :func:`particle_id_to_hash` + linear probing
    """
    if not _require_lib("get_particle_id_lut_buffer_export"):
        return None
    if not hasattr(_lib, "trGetParticleIDLUTBufferExport"):
        return None

    try:
        out = TrBufferExport()
        lut_size = ctypes.c_uint64(0)
        result = _lib.trGetParticleIDLUTBufferExport(
            ctypes.c_void_p(pipeline),
            ctypes.byref(out),
            ctypes.byref(lut_size),
        )
        if not _check_result(result, "trGetParticleIDLUTBufferExport"):
            return None

        if sys.platform == "win32":
            handle = int(getattr(out, "handle", 0))
        elif sys.platform == "darwin":
            handle = int(getattr(out, "mtlBuffer", 0))
        else:
            handle = int(getattr(out, "fileDescriptor", 0))

        size = int(getattr(out, "size", 0))
        uid = int(out.uid) if getattr(out, "uid", 0) else 0
        capacity = int(lut_size.value)
        if handle <= 0 or size == 0 or capacity == 0:
            return None
        _track_win32_source_handle((int(pipeline), "id_lut"), handle)
        return (handle, size, uid, capacity)
    except Exception as e:
        print(f"theron: get_particle_id_lut_buffer_export error: {e}")
        return None


def get_particle_constraints_buffer_export(
    pipeline: int,
) -> Optional[Tuple[int, int, int]]:
    """Get the GPU export for the per-particle constraint array.

    Returns ``(handle, size_bytes, uid)`` or None when unavailable. The buffer
    layout is ``ParticleConstraintsBuffer { int _capacity; int _count;
    ParticleConstraint constraints[]; }``
    """
    if not _require_lib("get_particle_constraints_buffer_export"):
        return None
    if not hasattr(_lib, "trGetParticleConstraintsBufferExport"):
        return None

    try:
        out = TrBufferExport()
        result = _lib.trGetParticleConstraintsBufferExport(
            ctypes.c_void_p(pipeline),
            ctypes.byref(out),
        )
        if not _check_result(result, "trGetParticleConstraintsBufferExport"):
            return None

        if sys.platform == "win32":
            handle = int(getattr(out, "handle", 0))
        elif sys.platform == "darwin":
            handle = int(getattr(out, "mtlBuffer", 0))
        else:
            handle = int(getattr(out, "fileDescriptor", 0))

        size = int(getattr(out, "size", 0))
        uid = int(out.uid) if getattr(out, "uid", 0) else 0
        if handle <= 0 or size == 0:
            return None
        _track_win32_source_handle((int(pipeline), "constraints"), handle)
        return (handle, size, uid)
    except Exception as e:
        print(f"theron: get_particle_constraints_buffer_export error: {e}")
        return None


def particle_id_to_hash(particle_id: int, lut_size: int) -> int:
    """Reference Python implementation of the sim-side ParticleIDToHash.

    Mirrors the GLSL hash function so the OpenGL Python and Basic backends
    walk the LUT identically to the GPU shader. Pure 32-bit unsigned
    arithmetic — uses ``& 0xFFFFFFFF`` to emulate uint truncation.
    """
    if lut_size <= 0:
        return 0
    state = (particle_id * 747796405 + 2891336453) & 0xFFFFFFFF
    word = (((state >> ((state >> 28) + 4)) ^ state) * 277803737) & 0xFFFFFFFF
    return ((word >> 22) ^ word) % int(lut_size)


def get_particle_display_modes(
    pipeline: int,
    scene_key: int = 0,
) -> Optional[np.ndarray]:
    """Return per-particle display-mode ids as a uint32 NumPy view.

    Uses the whole-array DLL accessor and returns None when unavailable or
    when the pipeline has zero particles.

    The returned array length equals ``trGetParticleCount(pipeline)`` and
    its values are one of the ``DRAW_MODE_BIN_INDEX`` bin ids (0..13) as
    defined in :class:`viewport.core.particle_renderer.ParticleRenderer`.
    """
    if not _require_lib("get_particle_display_modes"):
        return None

    try:
        pipeline_ptr = _pipeline_ptrs.get(scene_key)
        if pipeline_ptr is None or pipeline_ptr.value != pipeline:
            pipeline_ptr = ctypes.c_void_p(pipeline)
            _pipeline_ptrs[scene_key] = pipeline_ptr

        count_out = ctypes.c_uint64()
        rc = _lib.trGetParticleCount(pipeline_ptr, ctypes.byref(count_out))
        if not _check_result(rc, "trGetParticleCount"):
            return None
        count = int(count_out.value)
        if count == 0:
            return None

        if not hasattr(_lib, "trGetParticleDisplayModes"):
            return None

        ptr = ctypes.POINTER(ctypes.c_uint32)()
        n_out = ctypes.c_uint64(0)
        rc = _lib.trGetParticleDisplayModes(pipeline_ptr, ctypes.byref(ptr), ctypes.byref(n_out))
        if not (_check_result(rc, "trGetParticleDisplayModes") and ptr):
            return None
        effective = min(int(n_out.value) or count, count)
        if effective <= 0:
            return None
        return np.ctypeslib.as_array(ptr, shape=(effective,)).copy()
    except Exception as e:
        print(f"theron: get_particle_display_modes error: {e}")
        return None


def get_particle_draw_mode_host_buffers(
    pipeline: int,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Get CPU-visible draw-mode prefix + binned index arrays.

    Returns:
        ``(prefix_u32, binned_u32)`` NumPy views backed by Theron host memory,
        or None when unavailable.
    """
    if not _require_lib("get_particle_draw_mode_host_buffers"):
        return None

    if not hasattr(_lib, "trGetParticleDrawModeHostBuffers"):
        return None

    try:
        prefix_ptr = ctypes.POINTER(ctypes.c_int32)()
        binned_ptr = ctypes.POINTER(ctypes.c_uint32)()
        result = _lib.trGetParticleDrawModeHostBuffers(
            ctypes.c_void_p(pipeline),
            ctypes.byref(prefix_ptr),
            ctypes.byref(binned_ptr),
        )
        if not _check_result(result, "trGetParticleDrawModeHostBuffers"):
            return None

        if not prefix_ptr or not binned_ptr:
            return None

        # Prefix has one cumulative counter per draw mode (currently 14 bins).
        prefix = np.ctypeslib.as_array(prefix_ptr, shape=(14,)).view(np.uint32)

        count = get_particle_count(pipeline)
        if count <= 0:
            return None
        binned = np.ctypeslib.as_array(binned_ptr, shape=(int(count),))
        return (prefix, binned)
    except Exception as e:
        print(f"theron: get_particle_draw_mode_host_buffers error: {e}")
        return None


def create_node_tree(container: int, param_id: int) -> Optional[int]:
    """Create a NodeTree on a container at the given parameter ID."""
    if not _require_lib("create_node_tree"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateNodeTree(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(out)
        )
        if _check_result(result, "trCreateNodeTree") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_node_tree error: {e}")
        return None


def create_gradient(container: int, param_id: int) -> Optional[int]:
    """Create a Gradient on a container at the given parameter ID."""
    if not _require_lib("create_gradient"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateGradient(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(out)
        )
        if _check_result(result, "trCreateGradient") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_gradient error: {e}")
        return None


def resize_gradient(gradient: int, knot_count: int) -> bool:
    """Resize a gradient to hold the given number of knots."""
    if not _require_lib("resize_gradient"):
        return False

    try:
        result = _lib.trResizeGradient(ctypes.c_void_p(gradient), ctypes.c_int32(knot_count))
        return _check_result(result, "trResizeGradient")
    except Exception as e:
        print(f"theron: resize_gradient error: {e}")
        return False


def set_compiled_shader_cache_dir(path: str) -> bool:
    """Set the directory used to cache compiled shaders.

    Args:
        path: Absolute path to the shader cache directory.

    Returns:
        True if the path was accepted, False otherwise.
    """
    if not _require_lib("set_compiled_shader_cache_dir"):
        return False

    try:
        result = _lib.trSetCompiledShaderCacheDir(ctypes.c_char_p(path.encode("utf-8")))
        return _check_result(result, "trSetCompiledShaderCacheDir")
    except Exception as e:
        print(f"theron: set_compiled_shader_cache_dir error: {e}")
        return False


def ensure_compiled_shaders_async() -> bool:
    """Start an asynchronous shader cache build.

    Returns:
        True if the build was started successfully, False otherwise.
    """
    if not _require_lib("ensure_compiled_shaders_async"):
        return False

    try:
        result = _lib.trEnsureCompiledShaders_Async()
        return _check_result(result, "trEnsureCompiledShaders_Async")
    except Exception as e:
        print(f"theron: ensure_compiled_shaders_async error: {e}")
        return False


def check_shader_cache_status() -> Optional[Tuple[int, int]]:
    """Check the status of the async shader cache build.

    Returns:
        Tuple of (compiled, total_to_compile), or None on failure.
    """
    if not _require_lib("check_shader_cache_status"):
        return None

    try:
        compiled = ctypes.c_size_t(0)
        total = ctypes.c_size_t(0)
        result = _lib.trCheckShaderCacheStatus(ctypes.byref(compiled), ctypes.byref(total))
        if _check_result(result, "trCheckShaderCacheStatus"):
            return (int(compiled.value), int(total.value))
        return None
    except Exception as e:
        print(f"theron: check_shader_cache_status error: {e}")
        return None


def set_gradient_knot(
    gradient: int,
    knot_idx: int,
    r: float,
    g: float,
    b: float,
    position: float,
    interpolation: int = TrGradientKnotInterpolation.TR_GRADIENT_KNOT_INTERPOLATION_LINEAR,
) -> None:
    """Set a gradient knot's color, position, and interpolation."""
    if not _require_lib("set_gradient_knot"):
        return

    try:
        knot = TrGradientKnot()
        knot.col = TrDVec3(r, g, b)
        knot.pos = ctypes.c_double(position)
        knot.interpolation = ctypes.c_int(interpolation)
        result = _lib.trSetGradientKnot(
            ctypes.c_void_p(gradient), ctypes.c_int32(knot_idx), ctypes.byref(knot)
        )
        _check_result(result, "trSetGradientKnot")
    except Exception as e:
        print(f"theron: set_gradient_knot error: {e}")


def set_gradient_color_mode(
    gradient: int,
    color_mode: int,
    hue_interpolation: int = 0,
) -> bool:
    """Set a gradient's color interpolation mode and hue direction."""
    if not _require_lib("set_gradient_color_mode"):
        return False

    try:
        result = _lib.trSetGradientColorMode(
            ctypes.c_void_p(gradient),
            ctypes.c_int(color_mode),
            ctypes.c_int(hue_interpolation),
        )
        return _check_result(result, "trSetGradientColorMode")
    except Exception as e:
        print(f"theron: set_gradient_color_mode error: {e}")
        return False


def set_container(container: int, param_id: int, sub_container: int) -> bool:
    """Set a sub-container on a container at the given parameter ID."""
    if not _require_lib("set_container"):
        return False

    try:
        result = _lib.trSetContainer(
            ctypes.c_void_p(container),
            ctypes.c_int32(param_id),
            ctypes.c_void_p(sub_container),
        )
        return _check_result(result, "trSetContainer")
    except Exception as e:
        print(f"theron: set_container error: {e}")
        return False


def create_spline(container: int, param_id: int) -> Optional[int]:
    """Create a Spline on a container at the given parameter ID."""
    if not _require_lib("create_spline"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateSpline(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(out)
        )
        if _check_result(result, "trCreateSpline") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_spline error: {e}")
        return None


def resize_spline(spline: int, knot_count: int) -> bool:
    """Resize a spline to hold the given number of knots."""
    if not _require_lib("resize_spline"):
        return False

    try:
        result = _lib.trResizeSpline(ctypes.c_void_p(spline), ctypes.c_int32(knot_count))
        return _check_result(result, "trResizeSpline")
    except Exception as e:
        print(f"theron: resize_spline error: {e}")
        return False


def set_spline_knot(
    spline: int,
    knot_idx: int,
    pos_x: float,
    pos_y: float,
    handle_type: str = "AUTO",
) -> None:
    """Set a spline knot's position and interpolation."""
    if not _require_lib("set_spline_knot"):
        return

    try:
        knot = TrSpline2DKnot()
        knot.pos = TrDVec2(pos_x, pos_y)

        # Blender doesn't give explicit tangent controls - the cubic mode will generate these
        knot.vTangentLeft = TrDVec2(0.0, 0.0)
        knot.vTangentRight = TrDVec2(0.0, 0.0)

        if handle_type == "AUTO":
            knot.interpolation = TrSplineKnotInterpolation.TR_SPLINE_KNOT_INTERPOLATION_CARDINAL
        elif handle_type == "AUTO_CLAMPED":
            knot.interpolation = TrSplineKnotInterpolation.TR_SPLINE_KNOT_INTERPOLATION_CARDINAL
        else:  # VECTOR / default to linear for unknown type
            knot.interpolation = TrSplineKnotInterpolation.TR_SPLINE_KNOT_INTERPOLATION_LINEAR

        result = _lib.trSetSplineKnot(
            ctypes.c_void_p(spline), ctypes.c_int32(knot_idx), ctypes.byref(knot)
        )
        _check_result(result, "trSetSplineKnot")
    except Exception as e:
        print(f"theron: set_spline_knot error: {e}")


def get_particle_property_data(
    pipeline: int,
    prop: int = TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION,
) -> Optional[ctypes.c_void_p]:
    """Get a direct pointer to the particle property data array.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        prop: One of the TrParticleProperty constants.

    Returns:
        Ctypes pointer to the buffer. The pointer is valid until the next call to execute_frame().
    """
    if not _require_lib("get_particle_property_data"):
        return None

    if not hasattr(_lib, "trGetParticlePropertyData"):
        return None

    try:
        data_ptr = ctypes.c_void_p()
        result = _lib.trGetParticlePropertyData(
            ctypes.c_void_p(pipeline),
            ctypes.c_int(prop),
            ctypes.byref(data_ptr),
        )
        if not _check_result(result, "trGetParticlePropertyData"):
            return None

        return data_ptr
    except Exception as e:
        print(f"theron: get_particle_property_data error: {e}")
        return None


def get_emitter_particle_data(
    emitter: int,
    prop: int = TrParticleProperty.TR_PARTICLE_PROPERTY_POSITION,
) -> Optional[ctypes.c_void_p]:
    """Get a direct pointer to an emitter's particle property data array.

    Args:
        emitter: Emitter handle from create_emitter().
        prop: One of the TrParticleProperty constants.

    Returns:
        Ctypes pointer to the buffer. The pointer is valid until the next call to execute_frame().
    """
    if not _require_lib("get_emitter_particle_data"):
        return None

    if not hasattr(_lib, "trGetEmitterParticleData"):
        return None

    try:
        data_ptr = ctypes.c_void_p()
        result = _lib.trGetEmitterParticleData(
            ctypes.c_void_p(emitter),
            ctypes.c_int(prop),
            ctypes.byref(data_ptr),
        )
        if not _check_result(result, "trGetEmitterParticleData"):
            return None

        return data_ptr
    except Exception as e:
        print(f"theron: get_emitter_particle_data error: {e}")
        return None


def node_tree_clear(node_tree: int) -> None:
    """Clear all nodes from a NodeTree."""
    if not _require_lib("node_tree_clear"):
        return

    try:
        result = _lib.trNodeTreeClear(ctypes.c_void_p(node_tree))
        _check_result(result, "trNodeTreeClear")
    except Exception as e:
        print(f"theron: node_tree_clear error: {e}")


def node_tree_insert(node_tree: int, parent: Optional[int], prev: Optional[int]) -> Optional[int]:
    """Insert a new node into a NodeTree."""
    if not _require_lib("node_tree_insert"):
        return None

    try:
        out = ctypes.c_void_p()
        parent_ptr = ctypes.c_void_p(parent) if parent else ctypes.c_void_p(0)
        prev_ptr = ctypes.c_void_p(prev) if prev else ctypes.c_void_p(0)
        result = _lib.trNodeTreeInsert(
            ctypes.c_void_p(node_tree), parent_ptr, prev_ptr, ctypes.byref(out)
        )
        if _check_result(result, "trNodeTreeInsert") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: node_tree_insert error: {e}")
        return None


def set_node_id(node: int, node_id: int) -> None:
    """Set the type ID for a NodeTree node."""
    if not _require_lib("set_node_id"):
        return

    try:
        result = _lib.trSetNodeId(ctypes.c_void_p(node), ctypes.c_int32(node_id))
        _check_result(result, "trSetNodeId")
    except Exception as e:
        print(f"theron: set_node_id error: {e}")


def set_node_link(node: int, linked_object: int) -> None:
    """Link a NodeTree node to a base object (e.g., emitter handle)."""
    if not _require_lib("set_node_link"):
        return

    try:
        result = _lib.trSetNodeLink(ctypes.c_void_p(node), ctypes.c_void_p(linked_object))
        _check_result(result, "trSetNodeLink")
    except Exception as e:
        print(f"theron: set_node_link error: {e}")


def set_node_enabled(node: int, enabled: bool) -> None:
    """Set the enabled state for a NodeTree node."""
    if not _require_lib("set_node_enabled"):
        return

    try:
        result = _lib.trSetNodeEnabled(ctypes.c_void_p(node), ctypes.c_bool(enabled))
        _check_result(result, "trSetNodeEnabled")
    except Exception as e:
        print(f"theron: set_node_enabled error: {e}")


def set_node_icon_flags(node: int, flags: int) -> None:
    """Set the per-node icon flags"""
    if not _require_lib("set_node_icon_flags"):
        return

    try:
        result = _lib.trSetNodeIconFlags(ctypes.c_void_p(node), ctypes.c_uint32(flags))
        _check_result(result, "trSetNodeIconFlags")
    except Exception as e:
        print(f"theron: set_node_icon_flags error: {e}")


def create_node_container(node: int) -> Optional[int]:
    """Create a data container on a NodeTree node."""
    if not _require_lib("create_node_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateNodeContainer(ctypes.c_void_p(node), ctypes.byref(out))
        if _check_result(result, "trCreateNodeContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_node_container error: {e}")
        return None


def get_node_container(node: int) -> Optional[int]:
    """Get the existing data container from a NodeTree node."""
    if not _require_lib("get_node_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetNodeContainer(ctypes.c_void_p(node), ctypes.byref(out))
        if _check_result(result, "trGetNodeContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_node_container error: {e}")
        return None


def get_node_tree(container: int, param_id: int) -> Optional[int]:
    """Get an existing NodeTree from a container without creating one."""
    if not _require_lib("get_node_tree"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetNodeTree(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(out)
        )
        if _check_result(result, "trGetNodeTree") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_node_tree error: {e}")
        return None


def node_tree_get_first(node_tree: int) -> Optional[int]:
    """Return the first root-level node in a NodeTree, or None if empty."""
    if not _require_lib("node_tree_get_first"):
        return None

    try:
        out = ctypes.c_void_p()
        _lib.trNodeTreeGetFirst(ctypes.c_void_p(node_tree), ctypes.byref(out))
        return out.value or None
    except Exception as e:
        print(f"theron: node_tree_get_first error: {e}")
        return None


def node_tree_get_next(node_tree: int, node: int) -> Optional[int]:
    """Return the next sibling node after ``node``, or None at end-of-list."""
    if not _require_lib("node_tree_get_next"):
        return None

    try:
        out = ctypes.c_void_p()
        _lib.trNodeTreeGetNext(
            ctypes.c_void_p(node_tree), ctypes.c_void_p(node), ctypes.byref(out)
        )
        return out.value or None
    except Exception as e:
        print(f"theron: node_tree_get_next error: {e}")
        return None


def get_node_link(node: int) -> Optional[int]:
    """Return the object handle linked to a NodeTree node, or None."""
    if not _require_lib("get_node_link"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trGetNodeLink(ctypes.c_void_p(node), ctypes.byref(out))
        if _check_result(result, "trGetNodeLink") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: get_node_link error: {e}")
        return None


def get_vector(container: int, param_id: int) -> Optional[Tuple[float, float, float]]:
    """Get a vector parameter from a container."""
    if not _require_lib("get_vector"):
        return None

    try:
        vec = TrDVec3()
        result = _lib.trGetVector(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(vec)
        )
        if _check_result(result, "trGetVector"):
            return (vec.x, vec.y, vec.z)

        return None
    except Exception as e:
        print(f"theron: get_vector error: {e}")
        return None


def set_vector(container: int, param_id: int, x: float, y: float, z: float) -> None:
    """Set a vector parameter on a container."""
    if not _require_lib("set_vector"):
        return

    try:
        vec = TrDVec3(x, y, z)
        result = _lib.trSetVector(
            ctypes.c_void_p(container), ctypes.c_int32(param_id), ctypes.byref(vec)
        )
        _check_result(result, "trSetVector")
    except Exception as e:
        print(f"theron: set_vector error: {e}")


def get_memory(container: int, param_id: int) -> Optional[Tuple[int, int]]:
    """Get a memory block from a container by parameter ID."""
    if not _require_lib("get_memory"):
        return None

    try:
        out_ptr = ctypes.c_void_p()
        out_size = ctypes.c_int64()
        result = _lib.trGetMemory(
            ctypes.c_void_p(container),
            ctypes.c_int32(param_id),
            ctypes.byref(out_ptr),
            ctypes.byref(out_size),
        )
        if _check_result(result, "trGetMemory") and out_ptr.value:
            return (out_ptr.value, out_size.value)
        return None
    except Exception as e:
        print(f"theron: get_memory error: {e}")
        return None


def set_memory(container: int, param_id: int, data, size: int) -> None:
    """Set a memory block on a container by parameter ID.

    Args:
        container: Container handle.
        param_id: Parameter ID for the memory block.
        data: A ctypes array or pointer to the data.
        size: Size of the data in bytes.
    """
    if not _require_lib("set_memory"):
        return

    try:
        data_ptr = ctypes.cast(data, ctypes.c_void_p)
        result = _lib.trSetMemory(
            ctypes.c_void_p(container),
            ctypes.c_int32(param_id),
            data_ptr,
            ctypes.c_int64(size),
        )
        _check_result(result, "trSetMemory")
    except Exception as e:
        print(f"theron: set_memory error: {e}")


def create_container() -> Optional[int]:
    """Create a standalone data container for setting parameters.

    Returns:
        Container handle as integer, or None if creation failed.
    """
    if not _require_lib("create_container"):
        return None

    try:
        out = ctypes.c_void_p()
        result = _lib.trCreateContainer(ctypes.byref(out))
        if _check_result(result, "trCreateContainer") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_container error: {e}")
        return None


def free_container(container: int) -> None:
    """Free a standalone data container.

    Args:
        container: Container handle from create_container().
    """
    if not _require_lib("free_container"):
        return

    try:
        result = _lib.trFreeContainer(ctypes.c_void_p(container))
        _check_result(result, "trFreeContainer")
    except Exception as e:
        print(f"theron: free_container error: {e}")


def create_polygon_object_with_data(
    vertices: np.ndarray,
    polygons: np.ndarray,
) -> Optional[int]:
    """Create a polygon object from vertex and polygon arrays.

    Args:
        vertices: NumPy array of shape (N, 3), dtype float64, in the object's local
            space. Push the world transform separately via set_matrix().
        polygons: NumPy array of shape (M, 4), dtype int32, polygon vertex indices.

    Returns:
        Polygon object handle as integer, or None if creation failed.
    """
    if not _require_lib("create_polygon_object_with_data"):
        return None

    try:
        vertex_count = vertices.shape[0]
        poly_count = polygons.shape[0]

        verts_c = vertices.astype(np.float64, copy=False)
        verts_array = verts_c.ctypes.data_as(ctypes.POINTER(TrDVec3))

        polys_c = polygons.astype(np.int32, copy=False)
        polys_array = polys_c.ctypes.data_as(ctypes.POINTER(TrPolygon))

        out = ctypes.c_void_p()
        result = _lib.trCreatePolygonObjectWithData(
            ctypes.c_int32(vertex_count),
            verts_array,
            ctypes.c_int32(poly_count),
            polys_array,
            ctypes.byref(out),
        )
        if _check_result(result, "trCreatePolygonObjectWithData") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_polygon_object_with_data error: {e}")
        return None


def get_polygon_object_points(polygon_obj: int):
    """Get a writable pointer to the polygon object's vertex data.

    Args:
        polygon_obj: Polygon object handle.

    Returns:
        Pointer to TrDVec3 array, or None on failure.
    """
    if not _require_lib("get_polygon_object_points"):
        return None

    try:
        out = ctypes.POINTER(TrDVec3)()
        result = _lib.trGetPolygonObjectPoints(
            ctypes.c_void_p(polygon_obj),
            ctypes.byref(out),
        )
        if _check_result(result, "trGetPolygonObjectPoints"):
            return out
        return None
    except Exception as e:
        print(f"theron: get_polygon_object_points error: {e}")
        return None


def resize_polygon_object(polygon_obj: int, vertex_count: int, poly_count: int) -> bool:
    """Resize a polygon object's vertex and polygon arrays.

    Args:
        polygon_obj: Polygon object handle.
        vertex_count: New number of vertices.
        poly_count: New number of polygons.

    Returns:
        True on success, False on failure.
    """
    if not _require_lib("resize_polygon_object"):
        return False

    try:
        result = _lib.trResizePolygonObject(
            ctypes.c_void_p(polygon_obj),
            ctypes.c_int32(vertex_count),
            ctypes.c_int32(poly_count),
        )
        return _check_result(result, "trResizePolygonObject")
    except Exception as e:
        print(f"theron: resize_polygon_object error: {e}")
        return False


def update_polygon_object_points(polygon_obj: int, vertices: np.ndarray) -> bool:
    """Update a polygon object's vertex positions in-place from a numpy array.

    Args:
        polygon_obj: Polygon object handle.
        vertices: NumPy array of shape (N, 3), dtype float64.

    Returns:
        True on success, False on failure.
    """
    points = get_polygon_object_points(polygon_obj)
    if points is None:
        return False

    try:
        vertex_count = vertices.shape[0]
        dst = (ctypes.c_double * (vertex_count * 3)).from_address(
            ctypes.addressof(points.contents)
        )
        src = vertices.astype(np.float64, copy=False)
        ctypes.memmove(dst, src.ctypes.data, vertex_count * 3 * 8)
        return True
    except Exception as e:
        print(f"theron: update_polygon_object_points error: {e}")
        return False


def free_polygon_object(polygon_obj: int) -> None:
    """Free a polygon object and its resources.

    Args:
        polygon_obj: Polygon object handle from create_polygon_object_with_data().
    """
    if not _require_lib("free_polygon_object"):
        return

    try:
        result = _lib.trFreePolygonObject(ctypes.c_void_p(polygon_obj))
        _check_result(result, "trFreePolygonObject")
    except Exception as e:
        print(f"theron: free_polygon_object error: {e}")


def create_line_object_with_data(
    vertices: np.ndarray,
    segments: np.ndarray,
) -> Optional[int]:
    """Create a line object from vertex and segment arrays.

    Args:
        vertices: NumPy array of shape (N, 3), dtype float64, in the curve's local
            space. Push the world transform separately via set_matrix().
        segments: NumPy array of shape (M, 2), dtype int32, segment count and closed bool.

    Returns:
        Line object handle as integer, or None if creation failed.
    """
    if not _require_lib("create_polygon_object_with_data"):
        return None

    try:
        vertex_count = vertices.shape[0]
        seg_count = segments.shape[0]

        verts_c = vertices.astype(np.float64, copy=False)
        verts_array = verts_c.ctypes.data_as(ctypes.POINTER(TrDVec3))

        segs_c = segments.astype(np.int32, copy=False)
        segs_array = segs_c.ctypes.data_as(ctypes.POINTER(TrSegment))

        out = ctypes.c_void_p()
        result = _lib.trCreateLineObjectWithData(
            ctypes.c_int32(vertex_count),
            verts_array,
            ctypes.c_int32(seg_count),
            segs_array,
            ctypes.byref(out),
        )
        if _check_result(result, "trCreateLineObjectWithData") and out.value:
            return out.value
        return None
    except Exception as e:
        print(f"theron: create_line_object_with_data error: {e}")
        return None


def free_line_object(line_obj: int) -> None:
    """Free a line object.

    Args:
        line_obj: Line object handle.
    """
    if not _require_lib("free_line_object"):
        return

    try:
        result = _lib.trFreeLineObject(ctypes.c_void_p(line_obj))
        _check_result(result, "trFreeLineObject")
    except Exception as e:
        print(f"theron: free_line_object error: {e}")


def get_line_object_points(line_obj: int):
    """Get a writable pointer to the line object's vertex data."""
    if not _require_lib("get_line_object_points"):
        return None

    try:
        out = ctypes.POINTER(TrDVec3)()
        result = _lib.trGetLineObjectPoints(
            ctypes.c_void_p(line_obj),
            ctypes.byref(out),
        )
        if _check_result(result, "trGetLineObjectPoints"):
            return out
        return None
    except Exception as e:
        print(f"theron: get_line_object_points error: {e}")
        return None


def update_line_object_points(line_obj: int, vertices: np.ndarray) -> bool:
    """Update a line object's vertex positions in-place from a numpy array."""
    points = get_line_object_points(line_obj)
    if points is None:
        return False

    try:
        vertex_count = vertices.shape[0]
        dst = (ctypes.c_double * (vertex_count * 3)).from_address(
            ctypes.addressof(points.contents)
        )
        src = vertices.astype(np.float64, copy=False)
        ctypes.memmove(dst, src.ctypes.data, vertex_count * 3 * 8)
        return True
    except Exception as e:
        print(f"theron: update_line_object_points error: {e}")
        return False


def add_collider_mesh(pipeline: int, polygon_obj: int, opts_container: int) -> bool:
    """Add a collider mesh to the pipeline.

    Args:
        pipeline: Pipeline handle from create_pipeline().
        polygon_obj: Polygon object handle from create_polygon_object_with_data().
        opts_container: Container handle with collider options.

    Returns:
        True if the collider was added successfully, False otherwise.
    """
    if not _require_lib("add_collider_mesh"):
        return False

    try:
        result = _lib.trAddColliderMesh(
            ctypes.c_void_p(pipeline),
            ctypes.c_void_p(polygon_obj),
            ctypes.c_void_p(opts_container),
        )
        return _check_result(result, "trAddColliderMesh")
    except Exception as e:
        print(f"theron: add_collider_mesh error: {e}")
        return False


def clear_position_buffer(scene_key: int) -> None:
    """Drop the cached pipeline pointer for a scene."""
    _pipeline_ptrs.pop(scene_key, None)


def clear_all_position_buffers() -> None:
    """Drop all cached pipeline pointers."""
    _pipeline_ptrs.clear()


def get_efx_regularizeddomain(
    Lx: float, Ly: float, Lz: float, dx: float
) -> Optional[Tuple[Tuple[float, float, float], Tuple[int, int, int], float]]:
    """For the provided domain specification, adjust according to back-end regularization rules.

    Args:
        Lx, Ly, Lz: Domain extent (meters).
        dx: Voxel grid size (meters).

    Returns:
        ((Lx, Ly, Lz), (nx, ny, nz), dx) — the regularized domain extent, grid
        resolution, and voxel size after Theron's adjustment rules are applied.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_regularizeddomain"):
        return None

    try:
        c_Lx = ctypes.c_float(Lx)
        c_Ly = ctypes.c_float(Ly)
        c_Lz = ctypes.c_float(Lz)
        c_nx = ctypes.c_int()
        c_ny = ctypes.c_int()
        c_nz = ctypes.c_int()
        c_dx = ctypes.c_float(dx)
        result = _lib.trGetEFXRegularizedDomain(
            ctypes.byref(c_Lx),
            ctypes.byref(c_Ly),
            ctypes.byref(c_Lz),
            ctypes.byref(c_nx),
            ctypes.byref(c_ny),
            ctypes.byref(c_nz),
            ctypes.byref(c_dx),
        )
        if not _check_result(result, "trGetEFXRegularizedDomain"):
            return None
        return (
            (c_Lx.value, c_Ly.value, c_Lz.value),
            (c_nx.value, c_ny.value, c_nz.value),
            c_dx.value,
        )
    except Exception as e:
        print(f"theron: get_efx_regularizeddomain error: {e}")
        return None


def get_efx_vram_persistent_GiB(
    nx: int, ny: int, nz: int, upresMult: int, activeChannels: int
) -> float:
    """Estimate persistent VRAM (in GiB) for an ExplosiaFX grid of the given spec.

    Args:
        nx, ny, nz: Voxel grid resolution.
        upresMult: Upscale multiplier (1 = no upres).
        activeChannels: Number of active scalar channels (smoke, temp, fuel, color, ...).

    Returns:
        Estimated persistent VRAM in GiB. Returns 0.0 if the library is unavailable
        or if the call fails
    """
    if not _require_lib("get_efx_vram_persistent_GiB"):
        return 0.0

    try:
        vram = ctypes.c_float()
        result = _lib.trGetEFXVRAMPersistent_GiB(
            ctypes.byref(vram),
            ctypes.c_int32(nx),
            ctypes.c_int32(ny),
            ctypes.c_int32(nz),
            ctypes.c_int32(upresMult),
            ctypes.c_int32(activeChannels),
        )
        if not _check_result(result, "trGetEFXVRAMPersistent_GiB"):
            return 0.0
        return vram.value
    except Exception as e:
        print(f"theron: get_efx_vram_persistent_GiB error: {e}")
        return 0.0


def get_efx_vram_peak_GiB(nx: int, ny: int, nz: int, upresMult: int, activeChannels: int) -> float:
    """Estimate peak VRAM (in GiB) for an ExplosiaFX grid of the given spec.

    Args:
        nx, ny, nz: Voxel grid resolution.
        upresMult: Upscale multiplier (1 = no upres).
        activeChannels: Number of active scalar channels (smoke, temp, fuel, color, ...).

    Returns:
        Estimated peak VRAM in GiB. Returns 0.0 if the library is unavailable or if the
        call fails
    """
    if not _require_lib("get_efx_vram_peak_GiB"):
        return 0.0

    try:
        vram = ctypes.c_float()
        result = _lib.trGetEFXVRAMPeak_GiB(
            ctypes.byref(vram),
            ctypes.c_int32(nx),
            ctypes.c_int32(ny),
            ctypes.c_int32(nz),
            ctypes.c_int32(upresMult),
            ctypes.c_int32(activeChannels),
        )
        if not _check_result(result, "trGetEFXVRAMPeak_GiB"):
            return 0.0
        return vram.value
    except Exception as e:
        print(f"theron: get_efx_vram_peak_GiB error: {e}")
        return 0.0


def get_efx_voxelsize(
    modifier: int,
) -> Optional[float]:
    """Return the internal voxel size for an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        dx — the simulation's actual voxel size in meters. dx is the Theron-side voxel size,
        which may differ from the user-set value after any clamping and regularization is applied.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_voxelsize"):
        return None

    try:
        dx = ctypes.c_float()
        result = _lib.trGetEFXVoxelSize(
            ctypes.c_void_p(modifier),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXVoxelSize"):
            return None
        return dx.value
    except Exception as e:
        print(f"theron: get_efx_voxelsize error: {e}")
        return None


def get_efx_gridsize(
    modifier: int,
) -> Optional[Tuple[int, int, int]]:
    """Return the base voxel grid size for an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (nx, ny, nz) — the base resolution voxel grid used internally in Theron.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_gridsize"):
        return None

    try:
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        result = _lib.trGetEFXGridSize(
            ctypes.c_void_p(modifier),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
        )
        if not _check_result(result, "trGetEFXGridSize"):
            return None
        return nx.value, ny.value, nz.value
    except Exception as e:
        print(f"theron: get_efx_gridsize error: {e}")
        return None


def get_efx_field(
    modifier: int,
    channel: int = TrEFXChannel.TR_EFX_CHANNEL_SMOKE,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the density field for the chosen channel of an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().
        channel: the channel requested (See TrEFXChannel list in EFX_CHANNEL_NAMES)

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. dx is the Theron-side voxel size,
        which may differ from the user-set value after any clamping and regularization is applied.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_field"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXChannel(
            ctypes.c_void_p(modifier),
            ctypes.c_int(channel),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXChannel"):
            return None
        count = nx.value * ny.value * nz.value
        if count == 0:
            return None
        arr = (ctypes.c_float * count).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_field error: {e}")
        return None


def get_efx_field_upres(
    modifier: int,
    channel: int = TrEFXChannel.TR_EFX_CHANNEL_SMOKE,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the upscaled density field for the chosen channel of an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().
        channel: the channel requested (See TrEFXChannel list in EFX_CHANNEL_NAMES)

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_field_upres"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXChannelUpres(
            ctypes.c_void_p(modifier),
            ctypes.c_int(channel),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXChannelUpres"):
            return None
        count = nx.value * ny.value * nz.value
        if count == 0:
            return None
        arr = (ctypes.c_float * count).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_field_upres error: {e}")
        return None


def get_efx_speed(modifier: int) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the speed field of an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_speed"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXSpeed(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXSpeed"):
            return None
        count = nx.value * ny.value * nz.value
        if count == 0:
            return None
        arr = (ctypes.c_float * count).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_speed error: {e}")
        return None


def get_efx_smoke_field(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the smoke density field for an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_smoke_field"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXChannelsSmoke(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXChannelsSmoke"):
            return None
        count = nx.value * ny.value * nz.value
        if count == 0:
            return None
        arr = (ctypes.c_float * count).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_smoke_field error: {e}")
        return None


def get_efx_temperature_field(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the temperature field for an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_temperature_field"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXChannelsTemperature(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXChannelsTemperature"):
            return None
        count = nx.value * ny.value * nz.value
        if count == 0:
            return None
        arr = (ctypes.c_float * count).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_temperature_field error: {e}")
        return None


def get_efx_solidsdf_voxelvertex(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the voxel vertex centered solid SDF for an ExplosiaFX modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_solidsdf_voxelvertex"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXSolidSDFVoxelVertex(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXSolidSDFVoxelVertex"):
            return None
        voxelcnt = nx.value * ny.value * nz.value
        if voxelcnt == 0:
            return None
        vertcount = (nx.value + 1) * (ny.value + 1) * (nz.value + 1)
        # Guard against nullptr
        addr = ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        if addr is None:
            return None
        arr = (ctypes.c_float * vertcount).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_solidsdf_voxelvertex error: {e}")
        return None


def get_efx_voxelisactive(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return a marker for if a voxel is inside the adaptive domain.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_voxelisactive"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_int)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXVoxelIsActive(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXVoxelIsActive"):
            return None
        voxelcnt = nx.value * ny.value * nz.value
        if voxelcnt == 0:
            return None
        # Guard against nullptr
        addr = ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        if addr is None:
            return None
        arr = (ctypes.c_int * voxelcnt).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_voxelisactive error: {e}")
        return None


def get_efx_velocity(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, ctypes.Array, ctypes.Array, Tuple[int, int, int], float]]:
    """Return the fluid velocity sampled on MAC nodes for an nxExplosiaFX instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (u_ctypes_array, v_ctypes_array, w_ctypes_array, (nx, ny, nz), dx) — zero-copy
        views over Theron's C++ memory plus the simulation's actual voxel size in
        meters. See get_efx_field for notes on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_efx_velocity"):
        return None

    try:
        u_ptr = ctypes.POINTER(ctypes.c_float)()
        v_ptr = ctypes.POINTER(ctypes.c_float)()
        w_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetEFXVelocity(
            ctypes.c_void_p(modifier),
            ctypes.byref(u_ptr),
            ctypes.byref(v_ptr),
            ctypes.byref(w_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetEFXVelocity"):
            return None
        MACu_cnt = (nx.value + 1) * ny.value * nz.value
        MACv_cnt = nx.value * (ny.value + 1) * nz.value
        MACw_cnt = nx.value * ny.value * (nz.value + 1)
        # Guard against nullptr
        addr_u = ctypes.cast(u_ptr, ctypes.c_void_p).value
        addr_v = ctypes.cast(v_ptr, ctypes.c_void_p).value
        addr_w = ctypes.cast(w_ptr, ctypes.c_void_p).value
        if addr_u is None or addr_v is None or addr_w is None:
            return None
        arr_u = (ctypes.c_float * MACu_cnt).from_address(ctypes.cast(u_ptr, ctypes.c_void_p).value)
        arr_v = (ctypes.c_float * MACv_cnt).from_address(ctypes.cast(v_ptr, ctypes.c_void_p).value)
        arr_w = (ctypes.c_float * MACw_cnt).from_address(ctypes.cast(w_ptr, ctypes.c_void_p).value)
        return arr_u, arr_v, arr_w, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_efx_velocity error: {e}")
        return None


def get_flipfluids_solidsdf_voxelcenter(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the voxel-center solid SDF for a FLIP Fluids modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_flipfluids_solidsdf_voxelcenter"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetFLIPFluidsSolidSDF(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetFLIPFluidsSolidSDF"):
            return None
        voxelcnt = nx.value * ny.value * nz.value
        # Guard against nullptr
        addr = ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        if addr is None:
            return None
        arr = (ctypes.c_float * voxelcnt).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_flipfluids_solidsdf_voxelcenter error: {e}")
        return None


def get_flipfluids_liquidphi(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, Tuple[int, int, int], float]]:
    """Return the voxel-center liquid phi for a FLIP Fluids modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (flat_ctypes_array, (nx, ny, nz), dx) — a zero-copy view over Theron's C++ memory
        plus the simulation's actual voxel size in meters. See get_efx_field for notes
        on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_flipfluids_liquidphi"):
        return None

    try:
        flatfield_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetFLIPFluidsLiquidPhi(
            ctypes.c_void_p(modifier),
            ctypes.byref(flatfield_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetFLIPFluidsLiquidPhi"):
            return None
        voxelcnt = nx.value * ny.value * nz.value
        # Guard against nullptr
        addr = ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        if addr is None:
            return None
        arr = (ctypes.c_float * voxelcnt).from_address(
            ctypes.cast(flatfield_ptr, ctypes.c_void_p).value
        )
        return arr, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_flipfluids_liquidphi error: {e}")
        return None


def get_flipfluids_liquidvelocity(
    modifier: int,
) -> Optional[Tuple[ctypes.Array, ctypes.Array, ctypes.Array, Tuple[int, int, int], float]]:
    """Return the liquid velocity sampled on MAC nodes for a FLIP Fluids modifier instance.

    Args:
        modifier: Modifier handle from add_modifier().

    Returns:
        (u_ctypes_array, v_ctypes_array, w_ctypes_array, (nx, ny, nz), dx) — zero-copy
        views over Theron's C++ memory plus the simulation's actual voxel size in
        meters. See get_efx_field for notes on dx vs the UI voxel size.
        Returns None if unavailable.
    """
    if not _require_lib("get_flipfluids_liquidvelocity"):
        return None

    try:
        u_ptr = ctypes.POINTER(ctypes.c_float)()
        v_ptr = ctypes.POINTER(ctypes.c_float)()
        w_ptr = ctypes.POINTER(ctypes.c_float)()
        nx, ny, nz = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        dx = ctypes.c_float()
        result = _lib.trGetFLIPFluidsVelocity(
            ctypes.c_void_p(modifier),
            ctypes.byref(u_ptr),
            ctypes.byref(v_ptr),
            ctypes.byref(w_ptr),
            ctypes.byref(nx),
            ctypes.byref(ny),
            ctypes.byref(nz),
            ctypes.byref(dx),
        )
        if not _check_result(result, "trGetFLIPFluidsVelocity"):
            return None
        MACu_cnt = (nx.value + 1) * ny.value * nz.value
        MACv_cnt = nx.value * (ny.value + 1) * nz.value
        MACw_cnt = nx.value * ny.value * (nz.value + 1)
        # Guard against nullptr
        addr_u = ctypes.cast(u_ptr, ctypes.c_void_p).value
        addr_v = ctypes.cast(v_ptr, ctypes.c_void_p).value
        addr_w = ctypes.cast(w_ptr, ctypes.c_void_p).value
        if addr_u is None or addr_v is None or addr_w is None:
            return None
        arr_u = (ctypes.c_float * MACu_cnt).from_address(ctypes.cast(u_ptr, ctypes.c_void_p).value)
        arr_v = (ctypes.c_float * MACv_cnt).from_address(ctypes.cast(v_ptr, ctypes.c_void_p).value)
        arr_w = (ctypes.c_float * MACw_cnt).from_address(ctypes.cast(w_ptr, ctypes.c_void_p).value)
        return arr_u, arr_v, arr_w, (nx.value, ny.value, nz.value), dx.value
    except Exception as e:
        print(f"theron: get_flipfluids_liquidvelocity error: {e}")
        return None


def get_flipfluids_regularizeddomain(
    Lx: float, Ly: float, Lz: float, dx: float
) -> Optional[Tuple[Tuple[float, float, float], Tuple[int, int, int], float]]:
    """For the provided domain specification, adjust according to back-end regularization rules.

    Args:
        Lx, Ly, Lz: Domain extent (meters).
        dx: Voxel grid size (meters).

    Returns:
        ((Lx, Ly, Lz), (nx, ny, nz), dx) — the regularized domain extent, grid
        resolution, and voxel size after Theron's adjustment rules are applied.
        Returns None if unavailable.
    """
    if not _require_lib("get_flipfluids_regularizeddomain"):
        return None

    try:
        c_Lx = ctypes.c_float(Lx)
        c_Ly = ctypes.c_float(Ly)
        c_Lz = ctypes.c_float(Lz)
        c_nx = ctypes.c_int()
        c_ny = ctypes.c_int()
        c_nz = ctypes.c_int()
        c_dx = ctypes.c_float(dx)
        result = _lib.trGetFLIPFluidsRegularizedDomain(
            ctypes.byref(c_Lx),
            ctypes.byref(c_Ly),
            ctypes.byref(c_Lz),
            ctypes.byref(c_nx),
            ctypes.byref(c_ny),
            ctypes.byref(c_nz),
            ctypes.byref(c_dx),
        )
        if not _check_result(result, "trGetFLIPFluidsRegularizedDomain"):
            return None
        return (
            (c_Lx.value, c_Ly.value, c_Lz.value),
            (c_nx.value, c_ny.value, c_nz.value),
            c_dx.value,
        )
    except Exception as e:
        print(f"theron: get_flipfluids_regularizeddomain error: {e}")
        return None


def get_available_vram() -> int:
    """Get the available (free) VRAM on the GPU in bytes.

    Returns:
        Available VRAM in bytes, or 0 if not available.
    """
    if not _require_lib("get_available_vram"):
        return 0

    try:
        out = ctypes.c_uint64()
        result = _lib.trGetAvailableVRAM(ctypes.byref(out))
        if _check_result(result, "trGetAvailableVRAM"):
            return out.value
        return 0
    except Exception as e:
        print(f"theron: get_available_vram error: {e}")
        return 0


def get_total_vram() -> int:
    """Get the total VRAM on the GPU in bytes.

    Returns:
        Total VRAM in bytes, or 0 if not available.
    """
    if not _require_lib("get_total_vram"):
        return 0

    try:
        out = ctypes.c_uint64()
        result = _lib.trGetTotalVRAM(ctypes.byref(out))
        if _check_result(result, "trGetTotalVRAM"):
            return out.value
        return 0
    except Exception as e:
        print(f"theron: get_total_vram error: {e}")
        return 0


def get_allocated_vram() -> int:
    """Get the total VRAM allocated by NeXus on the GPU in bytes.

    Returns:
        Allocated VRAM in bytes, or 0 if not available.
    """
    if not _require_lib("get_allocated_vram"):
        return 0

    try:
        out = ctypes.c_uint64()
        result = _lib.trGetAllocatedVRAM(ctypes.byref(out))
        if _check_result(result, "trGetAllocatedVRAM"):
            return out.value
        return 0
    except Exception as e:
        print(f"theron: get_allocated_vram error: {e}")
        return 0


def set_vram_limit(bytes: int) -> bool:
    """Set the maximum VRAM NeXus may use.

    Args:
        bytes: Byte limit, or 0 to remove the limit.

    Returns:
        True if the call succeeded.
    """
    if not _require_lib("set_vram_limit"):
        return False

    try:
        result = _lib.trSetVRAMLimit(ctypes.c_uint64(bytes))
        return _check_result(result, "trSetVRAMLimit")
    except Exception as e:
        print(f"theron: set_vram_limit error: {e}")
        return False


def get_device_name(index: int) -> str:
    """Get the name of the GPU.

    Returns:
        The GPU name, or an empty string if not available.
    """
    if not _require_lib("get_device_name"):
        return ""

    try:
        name_size = ctypes.c_size_t(0)
        result = _lib.trGetGPUName(index, None, ctypes.byref(name_size))
        if not _check_result(result, "trGetGPUName"):
            return ""

        buf = ctypes.create_string_buffer(name_size.value)
        result = _lib.trGetGPUName(index, buf, ctypes.byref(name_size))
        if not _check_result(result, "trGetGPUName"):
            return ""

        return buf.value.decode("utf-8")
    except Exception as e:
        print(f"theron: get_device_name error: {e}")
        return ""


def get_current_device_name() -> str:
    """Get the name of the currently active GPU.

    Returns:
        The GPU name, or an empty string if not available.
    """
    if not _require_lib("get_current_device_name"):
        return ""

    try:
        name_size = ctypes.c_size_t(0)
        result = _lib.trGetCurrentDeviceName(None, ctypes.byref(name_size))
        if not _check_result(result, "trGetCurrentDeviceName"):
            return ""

        buf = ctypes.create_string_buffer(name_size.value)
        result = _lib.trGetCurrentDeviceName(buf, ctypes.byref(name_size))
        if not _check_result(result, "trGetCurrentDeviceName"):
            return ""

        return buf.value.decode("utf-8")
    except Exception as e:
        print(f"theron: get_current_device_name error: {e}")
        return ""


def get_available_devices() -> List[str]:
    """Get the names of all available GPU devices.

    Returns:
        List of device names
    """
    if not _require_lib("get_available_devices"):
        return []

    try:
        count = ctypes.c_size_t(0)
        result = _lib.trGetAvailableGPUCount(ctypes.byref(count))
        if not _check_result(result, "trGetAvailableGPUCount"):
            return []

        devices = []
        for i in range(count.value):
            devices.append(get_device_name(i))

        return devices
    except Exception as e:
        print(f"theron: get_available_devices error: {e}")
        return []


def validate_glsl_source(source: str) -> Tuple[bool, str]:
    """Validate GLSL source via Theron's linked glslang.

    Uses the CPU-only glslang compiler bundled in Theron to check GLSL
    syntax and semantics. Does not require trNoiseInit() or a GPU context,
    so it can be called before any pipeline is created.

    Args:
        source: GLSL source code to validate.

    Returns:
        Tuple of (is_valid, error_log). error_log is empty on success.
    """
    if _shutting_down:
        return (False, "library is shutting down")

    if not _require_lib("validate_glsl_source"):
        return (False, "library not loaded")

    try:
        source_bytes = source.encode("utf-8")
        log_ptr = ctypes.POINTER(ctypes.c_char)()

        result = _lib.trValidateGlsl(source_bytes, ctypes.byref(log_ptr))

        error_log = ""
        if log_ptr:
            raw = ctypes.cast(log_ptr, ctypes.c_char_p)
            error_log = raw.value.decode("utf-8", errors="replace")
            _lib.trFreeString(raw)

        if result == TrResult.TR_RESULT_SUCCESS:
            return (True, "")
        return (False, error_log)

    except Exception as e:
        print(f"theron: validate_glsl_source error: {e}")
        return (False, str(e))


# -----------------------------------------------------------------------------
# Mapping metadata queries.
#
# The static-per-type arrays (_mapParams, _groupNames, _mapTo, _mapToGroups) are populated when
# the modifier's Init() runs on the C side. The ABI lets us read them through any live modifier
# handle of that type -- Blender callers cache by modifier type string (see mapping_metadata.py).
# -----------------------------------------------------------------------------


def get_mapping_params(modifier_handle: int) -> List[MappingParamInfo]:
    if not _require_lib("get_mapping_params"):
        return []
    count = ctypes.c_int32(0)
    result = _lib.trGetMappingParamCount(ctypes.c_void_p(modifier_handle), ctypes.byref(count))
    if not _check_result(result, "trGetMappingParamCount"):
        return []

    out: List[MappingParamInfo] = []
    info = TrMappingParamInfo()
    for i in range(count.value):
        result = _lib.trGetMappingParam(
            ctypes.c_void_p(modifier_handle), ctypes.c_int32(i), ctypes.byref(info)
        )
        if not _check_result(result, "trGetMappingParam"):
            continue
        # Theron might only carry IDs and group indexes. Labels are used from here if available.
        # If not, labels resolve from the modifier's SyncSpecs
        # (see libs/mapping_metadata.resolve_label for logic).
        if info.name:
            raw = ctypes.cast(info.name, ctypes.c_char_p).value
            name = raw.decode("utf-8", errors="replace") if raw else ""
            out.append(MappingParamInfo(param=int(info.param), group=int(info.group), name=name))
        else:
            out.append(MappingParamInfo(param=int(info.param), group=int(info.group), name=""))
    return out


def get_mapping_groups(modifier_handle: int) -> List[str]:
    if not _require_lib("get_mapping_groups"):
        return []
    count = ctypes.c_int32(0)
    result = _lib.trGetMappingGroupCount(ctypes.c_void_p(modifier_handle), ctypes.byref(count))
    if not _check_result(result, "trGetMappingGroupCount"):
        return []

    out: List[str] = []
    # Binding expects POINTER(POINTER(c_char)); c_char_p is a distinct ctypes type and can't
    # be byref'd into that slot. Use a raw char* and cast when reading.
    name_ptr = ctypes.POINTER(ctypes.c_char)()
    for i in range(count.value):
        result = _lib.trGetMappingGroup(
            ctypes.c_void_p(modifier_handle), ctypes.c_int32(i), ctypes.byref(name_ptr)
        )
        if not _check_result(result, "trGetMappingGroup"):
            continue
        if name_ptr:
            raw = ctypes.cast(name_ptr, ctypes.c_char_p).value
            out.append(raw.decode("utf-8", errors="replace") if raw else "")
        else:
            out.append("")
    return out


def get_mapping_to(modifier_handle: int) -> List[MappingParamInfo]:
    if not _require_lib("get_mapping_to"):
        return []
    count = ctypes.c_int32(0)
    result = _lib.trGetMappingToCount(ctypes.c_void_p(modifier_handle), ctypes.byref(count))
    if not _check_result(result, "trGetMappingToCount"):
        return []

    out: List[MappingParamInfo] = []
    info = TrMappingParamInfo()
    for i in range(count.value):
        result = _lib.trGetMappingTo(
            ctypes.c_void_p(modifier_handle), ctypes.c_int32(i), ctypes.byref(info)
        )
        if not _check_result(result, "trGetMappingTo"):
            continue
        # Theron might only carry IDs and group indexes. Labels are used from here if available.
        # If not, labels resolve from the modifier's SyncSpecs
        # (see libs/mapping_metadata.resolve_label for logic).
        if info.name:
            raw = ctypes.cast(info.name, ctypes.c_char_p).value
            name = raw.decode("utf-8", errors="replace") if raw else ""
            out.append(MappingParamInfo(param=int(info.param), group=int(info.group), name=name))
        else:
            out.append(MappingParamInfo(param=int(info.param), group=int(info.group), name=""))
    return out


def get_mapping_to_groups(modifier_handle: int) -> List[str]:
    if not _require_lib("get_mapping_to_groups"):
        return []
    count = ctypes.c_int32(0)
    result = _lib.trGetMappingToGroupCount(ctypes.c_void_p(modifier_handle), ctypes.byref(count))
    if not _check_result(result, "trGetMappingToGroupCount"):
        return []

    out: List[str] = []
    name_ptr = ctypes.POINTER(ctypes.c_char)()
    for i in range(count.value):
        result = _lib.trGetMappingToGroup(
            ctypes.c_void_p(modifier_handle), ctypes.c_int32(i), ctypes.byref(name_ptr)
        )
        if not _check_result(result, "trGetMappingToGroup"):
            continue
        if name_ptr:
            raw = ctypes.cast(name_ptr, ctypes.c_char_p).value
            out.append(raw.decode("utf-8", errors="replace") if raw else "")
        else:
            out.append("")
    return out


def get_mapping_layers(modifier_handle: int) -> List[MappingLayerInfo]:
    # Count call rebuilds a thread-local buffer on the C side; subsequent indexed getters read
    # from that buffer. Do the Count + indexed reads back-to-back without other Layer calls in
    # between so the buffer isn't invalidated.
    if not _require_lib("get_mapping_layers"):
        return []
    count = ctypes.c_int32(0)
    result = _lib.trGetMappingLayerCount(ctypes.c_void_p(modifier_handle), ctypes.byref(count))
    if not _check_result(result, "trGetMappingLayerCount"):
        return []

    out: List[MappingLayerInfo] = []
    info = TrMappingLayerInfo()
    for i in range(count.value):
        result = _lib.trGetMappingLayer(
            ctypes.c_void_p(modifier_handle), ctypes.c_int32(i), ctypes.byref(info)
        )
        if not _check_result(result, "trGetMappingLayer"):
            continue
        # Layer display name comes from the modifier's Blender-side layer item (its `.name`
        # or its `item_type` enum label), not Theron -- see panels.blender_layer_labels.
        out.append(MappingLayerInfo(id=int(info.id), name=""))
    return out


class TrailSplineReadback(NamedTuple):
    ranges: np.ndarray
    points: np.ndarray
    colors: np.ndarray


class TrailBufferBundle(NamedTuple):
    history: Optional[Tuple[int, int, int]]
    topology: Optional[Tuple[int, int, int]]
    color: Optional[Tuple[int, int, int]]
    thickness: Optional[Tuple[int, int, int]]
    source_local_indices: Optional[Tuple[int, int, int]]
    live_endpoint: Optional[Tuple[int, int, int]]
    slots_per_particle: int
    history_particle_capacity: int
    source_count: int
    source_local_stride: int
    bundle_uid: int


class TrailSourceInfo(NamedTuple):
    source_id: int
    source_index: int
    emitter_index: int
    enabled: bool


_TRAIL_SPLINE_RANGE_DTYPE = np.dtype(
    [
        ("firstPoint", np.int32),
        ("pointCount", np.int32),
        ("sourceId", np.uint32),
        ("flags", np.int32),
    ]
)


def _ensure_trail_desc_struct_size(desc: "TrTrailSourceDesc") -> None:
    if hasattr(desc, "structSize"):
        desc.structSize = ctypes.sizeof(TrTrailSourceDesc)


def add_trail_source(pipeline: int, desc: TrTrailSourceDesc) -> Optional[int]:
    """Add a trail source to the pipeline. Returns the source ID or None."""
    if not _require_lib("add_trail_source"):
        return None
    if not hasattr(_lib, "trAddTrailSource"):
        return None

    try:
        _ensure_trail_desc_struct_size(desc)
        out_id = ctypes.c_uint32()
        result = _lib.trAddTrailSource(
            ctypes.c_void_p(pipeline),
            ctypes.byref(desc),
            ctypes.byref(out_id),
        )
        if _check_result(result, "trAddTrailSource"):
            return int(out_id.value)
        return None
    except Exception as e:
        print(f"theron: add_trail_source error: {e}")
        return None


def remove_trail_source(pipeline: int, source_id: int) -> bool:
    """Remove a trail source from the pipeline.

    Returns False on TR_RESULT_OUT_OF_RANGE (unknown ID) and other failures.
    """
    if not _require_lib("remove_trail_source"):
        return False
    if not hasattr(_lib, "trRemoveTrailSource"):
        return False

    try:
        result = _lib.trRemoveTrailSource(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trRemoveTrailSource")
    except Exception as e:
        print(f"theron: remove_trail_source error: {e}")
        return False


def update_trail_source(pipeline: int, source_id: int, desc: TrTrailSourceDesc) -> bool:
    """Update an existing trail source descriptor.

    Returns False on TR_RESULT_OUT_OF_RANGE (unknown ID). Caller should re-add.
    """
    if not _require_lib("update_trail_source"):
        return False
    if not hasattr(_lib, "trUpdateTrailSource"):
        return False

    try:
        _ensure_trail_desc_struct_size(desc)
        result = _lib.trUpdateTrailSource(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
            ctypes.byref(desc),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trUpdateTrailSource")
    except Exception as e:
        print(f"theron: update_trail_source error: {e}")
        return False


def clear_trail_sources(pipeline: int) -> bool:
    """Remove every registered trail source in a single call."""
    if not _require_lib("clear_trail_sources"):
        return False
    if not hasattr(_lib, "trClearTrailSources"):
        return False

    try:
        result = _lib.trClearTrailSources(ctypes.c_void_p(pipeline))
        return _check_result(result, "trClearTrailSources")
    except Exception as e:
        print(f"theron: clear_trail_sources error: {e}")
        return False


def get_trail_source_count(pipeline: int) -> Optional[int]:
    """Return the number of trail sources, or None if the call could not be made."""
    if not _require_lib("get_trail_source_count"):
        return None
    if not hasattr(_lib, "trGetTrailSourceCount"):
        return None

    try:
        count = ctypes.c_uint32()
        result = _lib.trGetTrailSourceCount(
            ctypes.c_void_p(pipeline),
            ctypes.byref(count),
        )
        if _check_result(result, "trGetTrailSourceCount"):
            return int(count.value)
        return None
    except Exception as e:
        print(f"theron: get_trail_source_count error: {e}")
        return None


def get_trail_source_infos(pipeline: int) -> Optional[tuple[TrailSourceInfo, ...]]:
    """Return trail source metadata in Theron's buffer/palette order."""
    if not _require_lib("get_trail_source_infos"):
        return None
    if not hasattr(_lib, "trGetTrailSourceInfos"):
        return None

    try:
        count = ctypes.c_uint32()
        result = _lib.trGetTrailSourceInfos(
            ctypes.c_void_p(pipeline),
            None,
            ctypes.c_uint32(0),
            ctypes.byref(count),
        )
        if not _check_result(result, "trGetTrailSourceInfos"):
            return None
        if count.value == 0:
            return ()

        infos = (TrTrailSourceInfo * count.value)()
        result = _lib.trGetTrailSourceInfos(
            ctypes.c_void_p(pipeline),
            infos,
            ctypes.c_uint32(count.value),
            ctypes.byref(count),
        )
        if not _check_result(result, "trGetTrailSourceInfos"):
            return None
        write_count = min(len(infos), int(count.value))
        return tuple(
            TrailSourceInfo(
                source_id=int(info.sourceId),
                source_index=int(info.sourceIndex),
                emitter_index=int(info.emitterIndex),
                enabled=bool(info.enabled),
            )
            for info in infos[:write_count]
        )
    except Exception as e:
        print(f"theron: get_trail_source_infos error: {e}")
        return None


def set_trail_slots_per_particle(pipeline: int, slots: int) -> bool:
    """Set the number of trail history slots per particle."""
    if not _require_lib("set_trail_slots_per_particle"):
        return False
    if not hasattr(_lib, "trSetTrailSlotsPerParticle"):
        return False

    try:
        result = _lib.trSetTrailSlotsPerParticle(
            ctypes.c_void_p(pipeline),
            ctypes.c_int32(slots),
        )
        return _check_result(result, "trSetTrailSlotsPerParticle")
    except Exception as e:
        print(f"theron: set_trail_slots_per_particle error: {e}")
        return False


def _extract_buffer_export(
    export: "TrBufferExport", slot_key: Tuple
) -> Optional[Tuple[int, int, int]]:
    if sys.platform == "win32":
        raw = export.handle
    elif sys.platform == "darwin":
        raw = export.mtlBuffer
    else:
        raw = export.fileDescriptor
    handle = int(raw) if raw is not None else 0
    size = int(export.size) if export.size else 0
    uid = int(export.uid) if export.uid else 0
    _track_win32_source_handle(slot_key, handle if handle > 0 and size > 0 else 0)
    _track_linux_source_fd(slot_key, handle if handle > 0 and size > 0 else 0)
    if handle == 0 or size == 0:
        return None
    return (handle, size, uid)


def get_trail_buffer_exports(pipeline: int) -> Optional["TrailBufferBundle"]:
    """Bundled trail buffer-export query. Returns None on error."""
    if not _require_lib("get_trail_buffer_exports"):
        return None
    if not hasattr(_lib, "trGetTrailBufferExports"):
        return None

    try:
        out = TrTrailBufferBundle()
        out.structSize = ctypes.sizeof(TrTrailBufferBundle)
        result = _lib.trGetTrailBufferExports(ctypes.c_void_p(pipeline), ctypes.byref(out))
        if not _check_result(result, "trGetTrailBufferExports"):
            return None
        pk = int(pipeline)
        return TrailBufferBundle(
            history=_extract_buffer_export(out.history, (pk, "trail_history")),
            topology=_extract_buffer_export(out.topology, (pk, "trail_topology")),
            color=_extract_buffer_export(out.color, (pk, "trail_color")),
            thickness=_extract_buffer_export(out.thickness, (pk, "trail_thickness")),
            source_local_indices=_extract_buffer_export(
                out.sourceLocalIndices, (pk, "trail_source_local_indices")
            ),
            live_endpoint=_extract_buffer_export(out.liveEndpoint, (pk, "trail_live_endpoint")),
            slots_per_particle=int(out.slotsPerParticle),
            history_particle_capacity=int(out.historyParticleCapacity),
            source_count=int(out.sourceCount),
            source_local_stride=int(out.sourceLocalStride),
            bundle_uid=int(out.uid),
        )
    except Exception as e:
        print(f"theron: get_trail_buffer_exports error: {e}")
        return None


def get_trail_spline_data_size(
    pipeline: int,
) -> Optional[Tuple[int, int, int]]:
    """Return (range_count, point_count, color_count) for the pending readback."""
    if not _require_lib("get_trail_spline_data_size"):
        return None
    if not hasattr(_lib, "trGetTrailSplineDataSize"):
        return None

    try:
        ranges = ctypes.c_int32(0)
        points = ctypes.c_int32(0)
        colors = ctypes.c_int32(0)
        result = _lib.trGetTrailSplineDataSize(
            ctypes.c_void_p(pipeline),
            ctypes.byref(ranges),
            ctypes.byref(points),
            ctypes.byref(colors),
        )
        if not _check_result(result, "trGetTrailSplineDataSize"):
            return None
        return (int(ranges.value), int(points.value), int(colors.value))
    except Exception as e:
        print(f"theron: get_trail_spline_data_size error: {e}")
        return None


def read_trail_spline_data(pipeline: int) -> Optional[TrailSplineReadback]:
    """Read CPU-side trail spline data into caller-owned NumPy arrays.

    Returns a TrailSplineReadback whose ``ranges`` is a structured NumPy array
    with firstPoint/pointCount/sourceId/flags fields; ``points`` and ``colors``
    are (N, 4) float32 arrays. ``colors`` is empty when no source uses Gradient
    or Per-Vertex colour.
    """
    if not _require_lib("read_trail_spline_data"):
        return None
    if not hasattr(_lib, "trReadTrailSplineData"):
        return None

    sizes = get_trail_spline_data_size(pipeline)
    if sizes is None:
        return None
    range_cap, point_cap, color_cap = sizes
    if range_cap <= 0 or point_cap <= 0:
        return None

    try:
        ranges = np.empty(range_cap, dtype=_TRAIL_SPLINE_RANGE_DTYPE)
        points = np.empty((point_cap, 4), dtype=np.float32)
        colors = (
            np.empty((color_cap, 4), dtype=np.float32)
            if color_cap > 0
            else np.empty((0, 4), dtype=np.float32)
        )
        out_range = ctypes.c_int32(0)
        out_point = ctypes.c_int32(0)
        out_color = ctypes.c_int32(0)
        result = _lib.trReadTrailSplineData(
            ctypes.c_void_p(pipeline),
            ranges.ctypes.data_as(ctypes.POINTER(TrTrailSplineRange)),
            points.ctypes.data_as(ctypes.POINTER(TrVec4)),
            (
                colors.ctypes.data_as(ctypes.POINTER(TrVec4))
                if color_cap > 0
                else ctypes.POINTER(TrVec4)()
            ),
            ctypes.c_int32(range_cap),
            ctypes.c_int32(point_cap),
            ctypes.c_int32(color_cap),
            ctypes.byref(out_range),
            ctypes.byref(out_point),
            ctypes.byref(out_color),
        )
        if not _check_result(result, "trReadTrailSplineData"):
            return None
        if out_range.value <= 0 or out_point.value <= 0:
            return None
        return TrailSplineReadback(
            ranges=ranges[: int(out_range.value)],
            points=points[: int(out_point.value)],
            colors=colors[: int(out_color.value)],
        )
    except Exception as e:
        print(f"theron: read_trail_spline_data error: {e}")
        return None


def set_trail_source_gradient(pipeline: int, source_id: int, gradient: int) -> bool:
    """Bind a gradient resource to a trail source.

    Returns False on TR_RESULT_OUT_OF_RANGE (unknown ID).
    """
    if not _require_lib("set_trail_source_gradient"):
        return False
    if not hasattr(_lib, "trSetTrailSourceGradient"):
        return False

    try:
        result = _lib.trSetTrailSourceGradient(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
            ctypes.c_void_p(gradient),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trSetTrailSourceGradient")
    except Exception as e:
        print(f"theron: set_trail_source_gradient error: {e}")
        return False


def clear_trail_source_gradient(pipeline: int, source_id: int) -> bool:
    """Clear any gradient resource bound to a trail source."""
    if not _require_lib("clear_trail_source_gradient"):
        return False
    if not hasattr(_lib, "trClearTrailSourceGradient"):
        return False

    try:
        result = _lib.trClearTrailSourceGradient(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trClearTrailSourceGradient")
    except Exception as e:
        print(f"theron: clear_trail_source_gradient error: {e}")
        return False


def set_trail_source_curve(pipeline: int, source_id: int, spline: int) -> bool:
    """Bind a spline/curve resource to a trail source.

    Returns False on TR_RESULT_OUT_OF_RANGE (unknown ID).
    """
    if not _require_lib("set_trail_source_curve"):
        return False
    if not hasattr(_lib, "trSetTrailSourceCurve"):
        return False

    try:
        result = _lib.trSetTrailSourceCurve(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
            ctypes.c_void_p(spline),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trSetTrailSourceCurve")
    except Exception as e:
        print(f"theron: set_trail_source_curve error: {e}")
        return False


def clear_trail_source_curve(pipeline: int, source_id: int) -> bool:
    """Clear any thickness curve resource bound to a trail source."""
    if not _require_lib("clear_trail_source_curve"):
        return False
    if not hasattr(_lib, "trClearTrailSourceCurve"):
        return False

    try:
        result = _lib.trClearTrailSourceCurve(
            ctypes.c_void_p(pipeline),
            ctypes.c_uint32(source_id),
        )
        if result == TrResult.TR_RESULT_OUT_OF_RANGE:
            return False
        return _check_result(result, "trClearTrailSourceCurve")
    except Exception as e:
        print(f"theron: clear_trail_source_curve error: {e}")
        return False
