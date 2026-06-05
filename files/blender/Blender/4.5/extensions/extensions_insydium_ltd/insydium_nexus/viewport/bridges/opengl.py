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

"""Unified Windows + Linux OpenGL zero-copy bridge.

Handles PyOpenGL discovery, GL_EXT_memory_object extension resolution
(Win32 handle on Windows, DMA-BUF fd on Linux), buffer import/free,
shader compilation, and GL state save/restore.

Platform-specific differences are confined to ``_resolve_*_extensions``
and ``_import_memory``.  Everything else is shared.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from ..core.buffer_state import _buffer_identity
from .base import BridgeBase

# ---------------------------------------------------------------------------
# PyOpenGL bootstrap (vendor dir + user site on Linux)
# ---------------------------------------------------------------------------
_PYOPENGL_AVAILABLE = False
_GL = None  # module reference

try:
    if sys.platform == "linux":
        import site

        _user_site = getattr(site, "getusersitepackages", lambda: None)()
        if _user_site and _user_site not in sys.path:
            sys.path.insert(0, _user_site)

    vendor_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "vendor")
    if vendor_dir not in sys.path:
        sys.path.append(vendor_dir)

    import OpenGL.GL as _GL_mod  # noqa: N812

    _GL = _GL_mod
    _PYOPENGL_AVAILABLE = True

    if vendor_dir in sys.path:
        sys.path.remove(vendor_dir)
except Exception:
    _PYOPENGL_AVAILABLE = False


def _pyopengl_ok() -> bool:
    return _PYOPENGL_AVAILABLE and _GL is not None


def _duplicate_win32_handle(handle: int) -> int | None:
    """Private duplicate of a Win32 NT handle, or None on failure.

    Decouples the bridge's HANDLE lifetime from Theron's: the dup is closed
    in :meth:`OpenGLBridge.free_buffer`; Theron's original is tracked in
    ``libs.theron._track_win32_source_handle``.
    """
    if sys.platform != "win32":
        return None
    import ctypes as _ct

    DUPLICATE_SAME_ACCESS = 0x00000002
    out = _ct.c_void_p()
    proc = _ct.windll.kernel32.GetCurrentProcess()
    ok = _ct.windll.kernel32.DuplicateHandle(
        _ct.c_void_p(proc),
        _ct.c_void_p(int(handle)),
        _ct.c_void_p(proc),
        _ct.byref(out),
        0,
        False,
        DUPLICATE_SAME_ACCESS,
    )
    if not ok or out.value is None:
        return None
    return int(out.value)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HANDLE_TYPE_OPAQUE_WIN32_EXT = 0x9587
HANDLE_TYPE_OPAQUE_FD_EXT = 0x9586
DEDICATED_MEMORY_OBJECT_EXT = 0x9581

GL_CURRENT_PROGRAM = 0x8B8D
GL_VERTEX_ARRAY_BINDING = 0x85B5
GL_ARRAY_BUFFER_BINDING = 0x8894
GL_ACTIVE_TEXTURE = 0x84E0
GL_TEXTURE_BINDING_2D = 0x8069
GL_SAMPLER_BINDING = 0x8919
GL_ELEMENT_ARRAY_BUFFER_BINDING = 0x8895
GL_CURRENT_VERTEX_ATTRIB = 0x8626
GL_POLYGON_MODE = 0x0B40
GL_VIEWPORT = 0x0BA2
GL_SCISSOR_BOX = 0x0C10
GL_BLEND_SRC_RGB = 0x80C9
GL_BLEND_DST_RGB = 0x80C8
GL_BLEND_SRC_ALPHA = 0x80CB
GL_BLEND_DST_ALPHA = 0x80CA
GL_BLEND_EQUATION_RGB = 0x8009
GL_BLEND_EQUATION_ALPHA = 0x883D
GL_FRONT_AND_BACK = 0x0408
GL_DRAW_FRAMEBUFFER_BINDING = 0x8CA6
GL_READ_FRAMEBUFFER_BINDING = 0x8CAA
GL_DRAW_INDIRECT_BUFFER_BINDING = 0x8F43
GL_BLEND = 0x0BE2
GL_CULL_FACE = 0x0B44
GL_DEPTH_TEST = 0x0B71
GL_SCISSOR_TEST = 0x0C11
GL_STENCIL_TEST = 0x0B90
GL_PRIMITIVE_RESTART = 0x8F9D
GL_RASTERIZER_DISCARD = 0x8C89
GL_DEPTH_WRITEMASK = 0x0B72
GL_COLOR_WRITEMASK = 0x0C23
GL_CULL_FACE_MODE = 0x0B45
GL_FRONT_FACE = 0x0B46
GL_DEPTH_FUNC = 0x0B74
GL_DEPTH_CLEAR_VALUE = 0x0B73
GL_STENCIL_FUNC = 0x0B92
GL_STENCIL_REF = 0x0B97
GL_STENCIL_VALUE_MASK = 0x0B93
GL_STENCIL_WRITEMASK = 0x0B98
GL_STENCIL_FAIL = 0x0B94
GL_STENCIL_PASS_DEPTH_FAIL = 0x0B95
GL_STENCIL_PASS_DEPTH_PASS = 0x0B96
GL_PROGRAM_POINT_SIZE = 0x8642
GL_COLOR_CLEAR_VALUE = 0x0C22


class OpenGLBridge(BridgeBase):
    """Unified OpenGL zero-copy bridge for Windows (Win32 handle) and Linux (fd)."""

    def __init__(self) -> None:
        self._loaded = False
        self._available = False

        # Extension function pointers (set by _resolve_extensions)
        self._create_memory_objects: Any = None
        self._memory_object_parameteriv: Any = None
        self._import_memory: Any = None
        self._named_buffer_storage_mem: Any = None
        self._delete_memory_objects: Any = None
        self._handle_type: int = 0

    # ------------------------------------------------------------------
    # BridgeBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if not _pyopengl_ok():
            return False
        if sys.platform not in ("win32", "linux"):
            return False
        backend = self._get_blender_gpu_backend()
        if backend and "OPENGL" not in backend and "GL" not in backend:
            return False
        return True

    def load(self) -> bool:
        if self._available:
            return True
        if self._loaded:
            return self._available
        self._loaded = True
        if not self.is_available():
            return False
        self._available = self._resolve_extensions()
        return self._available

    def shutdown(self) -> None:
        self._available = False

    # ------------------------------------------------------------------
    # Extension resolution
    # ------------------------------------------------------------------

    def _resolve_extensions(self) -> bool:
        if self._import_memory is not None:
            return True
        if sys.platform == "win32":
            return self._resolve_win32_extensions()
        if sys.platform == "linux":
            return self._resolve_linux_extensions()
        return False

    def _resolve_win32_extensions(self) -> bool:
        import ctypes as _ct

        try:
            opengl32 = _ct.windll.opengl32
        except Exception:
            return False

        wgl = opengl32.wglGetProcAddress
        wgl.argtypes = [_ct.c_char_p]
        wgl.restype = _ct.c_void_p

        def _proc(name: str):
            p = wgl(name.encode("ascii"))
            if not p:
                p = wgl((name + "ARB").encode("ascii"))
            return p

        def _void_ii_p(name: str):
            a = _proc(name)
            return _ct.CFUNCTYPE(None, _ct.c_int, _ct.POINTER(_ct.c_uint))(a) if a else None

        def _void_iuiep(name: str):
            a = _proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint64, _ct.c_uint, _ct.c_void_p)(a)
                if a
                else None
            )

        def _void_iuu(name: str):
            a = _proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint64, _ct.c_uint, _ct.c_uint64)(a)
                if a
                else None
            )

        def _void_iuip(name: str):
            a = _proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint, _ct.POINTER(_ct.c_int))(a)
                if a
                else None
            )

        self._create_memory_objects = _void_ii_p("glCreateMemoryObjectsEXT")
        self._memory_object_parameteriv = _void_iuip("glMemoryObjectParameterivEXT")
        self._import_memory = _void_iuiep("glImportMemoryWin32HandleEXT")
        self._named_buffer_storage_mem = _void_iuu("glNamedBufferStorageMemEXT")
        self._delete_memory_objects = _void_ii_p("glDeleteMemoryObjectsEXT")
        self._handle_type = HANDLE_TYPE_OPAQUE_WIN32_EXT

        return self._import_memory is not None and self._named_buffer_storage_mem is not None

    def _resolve_linux_extensions(self) -> bool:
        import ctypes as _ct

        get_proc = self._linux_get_proc_address()
        if get_proc is None:
            return False

        def _void_ii_p(name: str):
            a = get_proc(name)
            return _ct.CFUNCTYPE(None, _ct.c_int, _ct.POINTER(_ct.c_uint))(a) if a else None

        def _void_iuiui(name: str):
            a = get_proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint64, _ct.c_uint, _ct.c_int)(a)
                if a
                else None
            )

        def _void_iuu(name: str):
            a = get_proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint64, _ct.c_uint, _ct.c_uint64)(a)
                if a
                else None
            )

        def _void_iuip(name: str):
            a = get_proc(name)
            return (
                _ct.CFUNCTYPE(None, _ct.c_uint, _ct.c_uint, _ct.POINTER(_ct.c_int))(a)
                if a
                else None
            )

        self._create_memory_objects = _void_ii_p("glCreateMemoryObjectsEXT")
        self._memory_object_parameteriv = _void_iuip("glMemoryObjectParameterivEXT")
        self._import_memory = _void_iuiui("glImportMemoryFdEXT")
        self._named_buffer_storage_mem = _void_iuu("glNamedBufferStorageMemEXT")
        self._delete_memory_objects = _void_ii_p("glDeleteMemoryObjectsEXT")
        self._handle_type = HANDLE_TYPE_OPAQUE_FD_EXT

        return self._import_memory is not None and self._named_buffer_storage_mem is not None

    @staticmethod
    def _linux_get_proc_address():
        """Resolve glXGetProcAddress or eglGetProcAddress on Linux."""
        import ctypes as _ct

        for lib_name in ("libGL.so.1", "libGL.so"):
            try:
                libgl = _ct.CDLL(lib_name)
                glx = getattr(libgl, "glXGetProcAddress", None) or getattr(
                    libgl, "glXGetProcAddressARB", None
                )
                if glx is not None:
                    glx.argtypes = [_ct.POINTER(_ct.c_ubyte)]
                    glx.restype = _ct.c_void_p

                    def _get(name: str, _glx=glx):
                        b = name.encode("ascii") + b"\0"
                        return _glx(_ct.cast(b, _ct.POINTER(_ct.c_ubyte)))

                    return _get
            except OSError:
                continue

        try:
            libegl = _ct.CDLL("libEGL.so.1")
            egl = libegl.eglGetProcAddress
            egl.argtypes = [_ct.POINTER(_ct.c_ubyte)]
            egl.restype = _ct.c_void_p

            def _get(name: str, _egl=egl):
                b = name.encode("ascii") + b"\0"
                return _egl(_ct.cast(b, _ct.POINTER(_ct.c_ubyte)))

            return _get
        except (OSError, AttributeError):
            pass
        return None

    # ------------------------------------------------------------------
    # Buffer import / free
    # ------------------------------------------------------------------

    @staticmethod
    def buffer_identity(handle: int | None, uid: int = 0) -> Any:
        """Stable identity for an external buffer handle."""
        return _buffer_identity(handle, uid)

    def import_buffer(self, handle: int, size: int) -> tuple[int, int, int | None] | None:
        """Import an external handle (DMA-BUF fd / Win32) into a GL buffer.

        Returns ``(vbo, mem_object, keep_handle)`` on success or ``None``.
        ``keep_handle`` is the Win32 duplicate to pass back to
        :meth:`free_buffer`; ``None`` on Linux (``glImportMemoryFdEXT``
        consumes the fd).
        """
        if not handle or size <= 0 or not self._available:
            return None
        if sys.platform != "win32" and int(handle) <= 0:
            return None

        import ctypes as _ct

        fd_consumed = False
        win32_dup: int | None = None

        try:
            _GL.glGetError()

            mem_arr = (_ct.c_uint * 1)()
            self._create_memory_objects(1, mem_arr)
            mem = int(mem_arr[0])
            if mem == 0:
                return None

            if self._memory_object_parameteriv is not None:
                dedicated = (_ct.c_int * 1)(1)
                self._memory_object_parameteriv(mem, DEDICATED_MEMORY_OBJECT_EXT, dedicated)

            if sys.platform == "win32":
                win32_dup = _duplicate_win32_handle(int(handle))
                if win32_dup is None:
                    return None
                self._import_memory(mem, size, self._handle_type, _ct.c_void_p(win32_dup))
            else:
                self._import_memory(mem, size, self._handle_type, int(handle))
                fd_consumed = True

            buf_gen = _GL.glGenBuffers(1)
            buf = int(buf_gen[0]) if hasattr(buf_gen, "__len__") else int(buf_gen)
            _GL.glBindBuffer(_GL.GL_ARRAY_BUFFER, buf)
            _GL.glBindBuffer(_GL.GL_ARRAY_BUFFER, 0)
            self._named_buffer_storage_mem(buf, size, mem, 0)
            return (buf, mem, win32_dup)

        except Exception as e:
            print(f"nexus OpenGL: import_buffer failed — {e}")
            if sys.platform == "win32":
                if win32_dup is not None:
                    try:
                        _ct.windll.kernel32.CloseHandle(_ct.c_void_p(win32_dup))
                    except Exception:
                        pass
            elif not fd_consumed:
                try:
                    os.close(int(handle))
                except OSError:
                    pass
            return None

    def free_buffer(self, vbo: int | None, mem: int | None, handle: int | None = None) -> None:
        """Free an imported VBO + memory object; close ``handle`` (the Win32
        duplicate from :meth:`import_buffer`) after the memory object."""
        if vbo is not None:
            try:
                _GL.glDeleteBuffers(1, [vbo])
            except Exception:
                pass
        if mem is not None and self._delete_memory_objects is not None:
            try:
                import ctypes as _ct

                self._delete_memory_objects(1, (_ct.c_uint * 1)(mem))
            except Exception:
                pass
        if handle is not None and sys.platform == "win32":
            try:
                import ctypes as _ct

                _ct.windll.kernel32.CloseHandle(_ct.c_void_p(int(handle)))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Shader compilation
    # ------------------------------------------------------------------

    @staticmethod
    def compile_program(vs_src: str, fs_src: str) -> int | None:
        """Compile + link a GLSL program.  Returns the program id or None."""
        if not _pyopengl_ok():
            return None

        def _compile(stage, src):
            sh = _GL.glCreateShader(stage)
            _GL.glShaderSource(sh, src)
            _GL.glCompileShader(sh)
            if not _GL.glGetShaderiv(sh, _GL.GL_COMPILE_STATUS):
                _GL.glDeleteShader(sh)
                return None
            return sh

        vs = _compile(_GL.GL_VERTEX_SHADER, vs_src)
        fs = _compile(_GL.GL_FRAGMENT_SHADER, fs_src)
        if vs is None or fs is None:
            if vs:
                _GL.glDeleteShader(vs)
            if fs:
                _GL.glDeleteShader(fs)
            return None

        prog = _GL.glCreateProgram()
        _GL.glAttachShader(prog, vs)
        _GL.glAttachShader(prog, fs)
        _GL.glLinkProgram(prog)
        _GL.glDeleteShader(vs)
        _GL.glDeleteShader(fs)

        if not _GL.glGetProgramiv(prog, _GL.GL_LINK_STATUS):
            _GL.glDeleteProgram(prog)
            return None
        return prog

    # ------------------------------------------------------------------
    # GL state save / restore
    # ------------------------------------------------------------------

    @staticmethod
    def save_state() -> dict | None:
        if not _pyopengl_ok():
            return None

        def _int(name: int) -> int:
            val = _GL.glGetIntegerv(name)
            if isinstance(val, (list, tuple)):
                return int(val[0]) if val else 0
            if hasattr(val, "__len__") and not isinstance(val, (bytes, str)):
                try:
                    return int(val[0])
                except Exception:
                    pass
            return int(val)

        def _ivec(name: int, n: int) -> tuple[int, ...]:
            val = _GL.glGetIntegerv(name)
            if isinstance(val, (list, tuple)):
                seq = list(val)
            else:
                try:
                    seq = [int(v) for v in val]
                except Exception:
                    seq = [int(val)]
            if len(seq) < n:
                seq.extend([0] * (n - len(seq)))
            return tuple(int(v) for v in seq[:n])

        def _bvec(name: int, n: int) -> tuple[bool, ...]:
            val = _GL.glGetBooleanv(name)
            if isinstance(val, (list, tuple)):
                seq = list(val)
            else:
                try:
                    seq = [bool(v) for v in val]
                except Exception:
                    seq = [bool(val)]
            if len(seq) < n:
                seq.extend([False] * (n - len(seq)))
            return tuple(bool(v) for v in seq[:n])

        def _float(name: int) -> float:
            val = _GL.glGetFloatv(name)
            if isinstance(val, (list, tuple)):
                return float(val[0]) if val else 0.0
            if hasattr(val, "__len__") and not isinstance(val, (bytes, str)):
                try:
                    return float(val[0])
                except Exception:
                    pass
            return float(val)

        def _fvec(name: int, n: int) -> tuple[float, ...]:
            val = _GL.glGetFloatv(name)
            if isinstance(val, (list, tuple)):
                seq = list(val)
            else:
                try:
                    seq = [float(v) for v in val]
                except Exception:
                    seq = [float(val)]
            if len(seq) < n:
                seq.extend([0.0] * (n - len(seq)))
            return tuple(float(v) for v in seq[:n])

        try:
            return {
                "program": _int(GL_CURRENT_PROGRAM),
                "active_texture": _int(GL_ACTIVE_TEXTURE),
                "texture_2d": _int(GL_TEXTURE_BINDING_2D),
                "sampler": _int(GL_SAMPLER_BINDING),
                "vao": _int(GL_VERTEX_ARRAY_BINDING),
                "array_buffer": _int(GL_ARRAY_BUFFER_BINDING),
                "element_array_buffer": _int(GL_ELEMENT_ARRAY_BUFFER_BINDING),
                "draw_indirect_buffer": _int(GL_DRAW_INDIRECT_BUFFER_BINDING),
                "draw_framebuffer": _int(GL_DRAW_FRAMEBUFFER_BINDING),
                "read_framebuffer": _int(GL_READ_FRAMEBUFFER_BINDING),
                "blend_src_rgb": _int(GL_BLEND_SRC_RGB),
                "blend_dst_rgb": _int(GL_BLEND_DST_RGB),
                "blend_src_alpha": _int(GL_BLEND_SRC_ALPHA),
                "blend_dst_alpha": _int(GL_BLEND_DST_ALPHA),
                "blend_equation_rgb": _int(GL_BLEND_EQUATION_RGB),
                "blend_equation_alpha": _int(GL_BLEND_EQUATION_ALPHA),
                "viewport": _ivec(GL_VIEWPORT, 4),
                "scissor_box": _ivec(GL_SCISSOR_BOX, 4),
                "polygon_mode": _ivec(GL_POLYGON_MODE, 2),
                "depth_mask": bool(_GL.glGetBooleanv(GL_DEPTH_WRITEMASK)),
                "color_mask": _bvec(GL_COLOR_WRITEMASK, 4),
                "color_clear_value": _fvec(GL_COLOR_CLEAR_VALUE, 4),
                "cull_face_mode": _int(GL_CULL_FACE_MODE),
                "front_face": _int(GL_FRONT_FACE),
                "depth_func": _int(GL_DEPTH_FUNC),
                "depth_clear_value": _float(GL_DEPTH_CLEAR_VALUE),
                "stencil_func": _int(GL_STENCIL_FUNC),
                "stencil_ref": _int(GL_STENCIL_REF),
                "stencil_value_mask": _int(GL_STENCIL_VALUE_MASK),
                "stencil_write_mask": _int(GL_STENCIL_WRITEMASK),
                "stencil_fail": _int(GL_STENCIL_FAIL),
                "stencil_depth_fail": _int(GL_STENCIL_PASS_DEPTH_FAIL),
                "stencil_depth_pass": _int(GL_STENCIL_PASS_DEPTH_PASS),
                "blend_enabled": bool(_GL.glIsEnabled(GL_BLEND)),
                "cull_enabled": bool(_GL.glIsEnabled(GL_CULL_FACE)),
                "depth_enabled": bool(_GL.glIsEnabled(GL_DEPTH_TEST)),
                "scissor_enabled": bool(_GL.glIsEnabled(GL_SCISSOR_TEST)),
                "stencil_enabled": bool(_GL.glIsEnabled(GL_STENCIL_TEST)),
                "primitive_restart_enabled": bool(_GL.glIsEnabled(GL_PRIMITIVE_RESTART)),
                "rasterizer_discard_enabled": bool(_GL.glIsEnabled(GL_RASTERIZER_DISCARD)),
                "program_point_size_enabled": bool(_GL.glIsEnabled(GL_PROGRAM_POINT_SIZE)),
            }
        except Exception:
            return None

    @staticmethod
    def save_state_for_particle_draw() -> dict | None:
        """Save GL state, then enable depth test + writes for self-occlusion.

        ``POST_VIEW`` draw handlers often run with ``GL_DEPTH_TEST`` disabled and
        ``GL_DEPTH_WRITEMASK`` cleared in the current GL context, while the viewport
        depth buffer already holds opaque geometry. Particle draws must test that
        depth or they paint as a screen-space overlay, and must write depth or
        nearer particles fail to occlude farther ones in the same draw. Pair with
        :meth:`restore_state` after drawing. SSF keeps using :meth:`save_state`
        because it manages depth and FBO state internally.
        """
        saved = OpenGLBridge.save_state()
        if saved is None:
            return None
        try:
            _GL.glEnable(GL_DEPTH_TEST)
            _GL.glDepthFunc(_GL.GL_LEQUAL)
            _GL.glDepthMask(True)
        except Exception:
            pass
        return saved

    @staticmethod
    def restore_state(saved: dict | None) -> None:
        if saved is None or not _pyopengl_ok():
            return
        try:

            def _set_enabled(cap: int, enabled: bool) -> None:
                if enabled:
                    _GL.glEnable(cap)
                else:
                    _GL.glDisable(cap)

            _set_enabled(GL_BLEND, bool(saved.get("blend_enabled", False)))
            _set_enabled(GL_CULL_FACE, bool(saved.get("cull_enabled", False)))
            _set_enabled(GL_DEPTH_TEST, bool(saved.get("depth_enabled", False)))
            _set_enabled(GL_SCISSOR_TEST, bool(saved.get("scissor_enabled", False)))
            _set_enabled(GL_STENCIL_TEST, bool(saved.get("stencil_enabled", False)))
            _set_enabled(GL_PRIMITIVE_RESTART, bool(saved.get("primitive_restart_enabled", False)))
            _set_enabled(
                GL_RASTERIZER_DISCARD,
                bool(saved.get("rasterizer_discard_enabled", False)),
            )
            _set_enabled(
                GL_PROGRAM_POINT_SIZE,
                bool(saved.get("program_point_size_enabled", False)),
            )

            _GL.glBlendEquationSeparate(
                int(saved.get("blend_equation_rgb", _GL.GL_FUNC_ADD)),
                int(saved.get("blend_equation_alpha", _GL.GL_FUNC_ADD)),
            )
            _GL.glBlendFuncSeparate(
                int(saved.get("blend_src_rgb", _GL.GL_ONE)),
                int(saved.get("blend_dst_rgb", _GL.GL_ZERO)),
                int(saved.get("blend_src_alpha", _GL.GL_ONE)),
                int(saved.get("blend_dst_alpha", _GL.GL_ZERO)),
            )
            _GL.glDepthMask(bool(saved.get("depth_mask", True)))
            _GL.glClearDepth(float(saved.get("depth_clear_value", 1.0)))
            color_clear = saved.get("color_clear_value", (0.0, 0.0, 0.0, 0.0))
            _GL.glClearColor(*[float(v) for v in color_clear[:4]])
            color_mask = saved.get("color_mask", (True, True, True, True))
            _GL.glColorMask(*[bool(v) for v in color_mask[:4]])
            _GL.glDepthFunc(int(saved.get("depth_func", _GL.GL_LESS)))
            _GL.glStencilFunc(
                int(saved.get("stencil_func", _GL.GL_ALWAYS)),
                int(saved.get("stencil_ref", 0)),
                int(saved.get("stencil_value_mask", 0xFFFFFFFF)),
            )
            _GL.glStencilMask(int(saved.get("stencil_write_mask", 0xFFFFFFFF)))
            _GL.glStencilOp(
                int(saved.get("stencil_fail", _GL.GL_KEEP)),
                int(saved.get("stencil_depth_fail", _GL.GL_KEEP)),
                int(saved.get("stencil_depth_pass", _GL.GL_KEEP)),
            )
            _GL.glCullFace(int(saved.get("cull_face_mode", _GL.GL_BACK)))
            _GL.glFrontFace(int(saved.get("front_face", _GL.GL_CCW)))

            _GL.glPolygonMode(
                GL_FRONT_AND_BACK, int(saved.get("polygon_mode", (0, _GL.GL_FILL))[0])
            )
            viewport = saved.get("viewport", (0, 0, 0, 0))
            _GL.glViewport(*[int(v) for v in viewport[:4]])
            scissor_box = saved.get("scissor_box", (0, 0, 0, 0))
            _GL.glScissor(*[int(v) for v in scissor_box[:4]])

            _GL.glActiveTexture(int(saved.get("active_texture", _GL.GL_TEXTURE0)))
            _GL.glBindTexture(_GL.GL_TEXTURE_2D, int(saved.get("texture_2d", 0)))
            try:
                _GL.glBindSampler(0, int(saved.get("sampler", 0)))
            except Exception:
                pass

            _GL.glBindFramebuffer(_GL.GL_DRAW_FRAMEBUFFER, int(saved.get("draw_framebuffer", 0)))
            _GL.glBindFramebuffer(_GL.GL_READ_FRAMEBUFFER, int(saved.get("read_framebuffer", 0)))
            _GL.glBindBuffer(_GL.GL_ARRAY_BUFFER, int(saved.get("array_buffer", 0)))
            _GL.glBindBuffer(
                _GL.GL_ELEMENT_ARRAY_BUFFER,
                int(saved.get("element_array_buffer", 0)),
            )
            _GL.glBindBuffer(
                _GL.GL_DRAW_INDIRECT_BUFFER,
                int(saved.get("draw_indirect_buffer", 0)),
            )
            _GL.glBindVertexArray(int(saved.get("vao", 0)))
            program = int(saved.get("program", 0))
            if program == 0 or _GL.glIsProgram(program):
                _GL.glUseProgram(program)
        except Exception:
            return

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _get_blender_gpu_backend() -> str:
        try:
            from ..registry import get_blender_gpu_backend

            return get_blender_gpu_backend()
        except Exception:
            return ""
