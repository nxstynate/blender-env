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

import os
import sys
import time

import bpy

from ..libs import theron
from ..libs.theron_sync import sync_properties
from ..handlers import pipeline as pipeline_handler

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
    _HAS_PYQT = True
except ImportError:
    _HAS_PYQT = False


_win = None


def _cache_handle(context) -> int | None:
    obj = context.object
    if obj is None or obj.get("nexus_modifier_type") != "NX_CACHE":
        return None
    return pipeline_handler.get_modifier_handle(context.scene, obj)


class NEXUS_OT_cache_source_toggle_lock(bpy.types.Operator):
    bl_idname = "nexus.cache_source_toggle_lock"
    bl_label = "Toggle Lock"
    bl_description = "Lock or unlock this cache source"

    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        if obj is None or obj.get("nexus_modifier_type") != "NX_CACHE":
            return {"CANCELLED"}
        sources = obj.nexus_modifier.cache_sources
        if 0 <= self.index < len(sources):
            sources[self.index].locked = not sources[self.index].locked
        return {"FINISHED"}


if _HAS_PYQT:
    class _CacheProgressDialog(QtWidgets.QDialog):
        def __init__(self, pipeline: int, cache: int, total: int):
            super().__init__()
            self._pipeline = pipeline
            self._cache = cache
            self._total = total
            self._start = time.monotonic()
            self._building = True
            self._setup_ui()
            self._poll_timer = QtCore.QTimer(self)
            self._poll_timer.timeout.connect(self._poll)
            self._poll_timer.start(100)

        def _setup_ui(self):
            self.setWindowTitle("Building Cache")
            self.setFixedWidth(500)

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(24, 18, 24, 16)
            layout.setSpacing(8)
            layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)

            self._frame_label = QtWidgets.QLabel("Starting...")
            layout.addWidget(self._frame_label)

            self._bar = QtWidgets.QProgressBar()
            self._bar.setRange(0, 1000)
            self._bar.setValue(0)
            self._bar.setTextVisible(False)
            self._bar.setFixedHeight(8)
            self._bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    border-radius: 3px;
                    background: #3a3a3a;
                }
                QProgressBar::chunk {
                    border-radius: 3px;
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3d8ef0, stop:1 #5cb8ff
                    );
                }
            """)
            layout.addWidget(self._bar)

            time_row = QtWidgets.QHBoxLayout()
            self._eta_label = QtWidgets.QLabel("Estimating time remaining...")
            time_row.addWidget(self._eta_label)
            time_row.addStretch()
            self._elapsed_label = QtWidgets.QLabel("Elapsed: 00:00")
            time_row.addWidget(self._elapsed_label)
            layout.addLayout(time_row)

            layout.addSpacing(8)

            btn_row = QtWidgets.QHBoxLayout()
            btn_row.addStretch()
            self._ok_btn = QtWidgets.QPushButton("OK")
            self._ok_btn.setEnabled(False)
            self._ok_btn.clicked.connect(self.close)
            btn_row.addWidget(self._ok_btn)
            self._cancel_btn = QtWidgets.QPushButton("Cancel")
            self._cancel_btn.clicked.connect(self._on_cancel)
            btn_row.addWidget(self._cancel_btn)
            layout.addLayout(btn_row)

        def _poll(self):
            elapsed = time.monotonic() - self._start
            m, s = divmod(int(elapsed), 60)
            self._elapsed_label.setText(f"Elapsed: {m:02d}:{s:02d}")

            status = theron.get_cache_status(self._pipeline, self._cache)
            if status is None:
                return

            frame, job_complete, _mem, _disk, _uncompressed = status
            total = self._total

            if total > 0:
                self._bar.setValue(int(frame / total * 1000))
                self._frame_label.setText(f"Caching frame {frame} of {total}")

                if frame > 0 and not job_complete:
                    eta = elapsed / frame * (total - frame)
                    m_eta, s_eta = divmod(int(eta), 60)
                    self._eta_label.setText(f"Estimated time remaining: {m_eta:02d}:{s_eta:02d}")

            if job_complete:
                self._building = False
                self._poll_timer.stop()
                self._bar.setValue(1000)
                self._frame_label.setText(f"{total} frames cached succsessfully")
                self._eta_label.setText("Complete")
                self._cancel_btn.setEnabled(False)
                self._ok_btn.setEnabled(True)

        def _on_cancel(self):
            if self._building:
                self._building = False
                theron.cancel_cache_build(self._pipeline)
            self.close()

        def closeEvent(self, event):
            global _win
            self._poll_timer.stop()
            if self._building:
                self._building = False
                theron.cancel_cache_build(self._pipeline)
            _win = None
            event.accept()


def open_caching_dialog(pipeline: int, cache: int, total: int):
    if not _HAS_PYQT:
        return
    global _win

    if _win is not None:
        try:
            _win.raise_()
            _win.activateWindow()
            return
        except RuntimeError:
            pass

    _win = _CacheProgressDialog(pipeline, cache, total)
    _win.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    _win.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
    _win.setWindowFlags(
        QtCore.Qt.WindowType.Dialog
        | QtCore.Qt.WindowType.WindowTitleHint
        | QtCore.Qt.WindowType.WindowCloseButtonHint
        | QtCore.Qt.WindowType.WindowStaysOnTopHint
    )
    icon_path = os.path.join(
        os.path.dirname(__file__), "..", "icons", "images", "brand", "insydium_black.png"
    )
    _win.setWindowIcon(QtGui.QIcon(icon_path))

    # _win.adjustSize()
    cursor = QtGui.QCursor.pos()
    screen = QtWidgets.QApplication.screenAt(cursor) or QtWidgets.QApplication.primaryScreen()
    sg = screen.availableGeometry()
    wg = _win.frameGeometry()
    x = max(sg.left(), min(cursor.x() + 16, sg.right() - wg.width()))
    y = max(sg.top(), min(cursor.y() + 16, sg.bottom() - wg.height()))
    _win.move(x, y)

    _win.show()


def has_open_window():
    return _win is not None


def _directory_has_contents(path: str) -> bool:
    if not path:
        return False
    abs_path = bpy.path.abspath(path)
    if not os.path.isdir(abs_path):
        return False
    try:
        with os.scandir(abs_path) as it:
            return next(it, None) is not None
    except OSError:
        return False


def confirm_overwrite_cache(directory: str) -> bool:
    """Return True to proceed, False if the user cancels."""
    if not _HAS_PYQT:
        return True

    if not _directory_has_contents(directory):
        return True

    abs_path = bpy.path.abspath(directory)

    msg = QtWidgets.QMessageBox()
    msg.setWindowTitle("Overwrite Cache?")
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg.setText("The cache directory already contains files.")
    msg.setInformativeText(
        f"Building the cache will overwrite existing files in:\n{abs_path}\n\n"
        "Do you want to proceed?"
    )
    proceed_btn = msg.addButton("Proceed", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    msg.addButton("Cancel", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    msg.setDefaultButton(proceed_btn)
    icon_path = os.path.join(
        os.path.dirname(__file__), "..", "icons", "images", "brand", "insydium_black.png"
    )
    msg.setWindowIcon(QtGui.QIcon(icon_path))
    msg.setWindowFlags(msg.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)
    msg.exec()

    return msg.clickedButton() == proceed_btn


class NEXUS_OT_cache_empty(bpy.types.Operator):
    bl_idname = "nexus.cache_empty"
    bl_label = "Empty Cache"
    bl_description = "Delete all cached frames"

    @classmethod
    def poll(cls, context):
        return _cache_handle(context) is not None

    def execute(self, context):
        handle = _cache_handle(context)
        if handle is None:
            return {"CANCELLED"}

        container = theron.get_object_container(handle)
        if container is not None:
            sync_properties(
                container, context.object.nexus_modifier, "NX_CACHE", scene=context.scene
            )

        theron.clear_cache(handle)

        pipeline_handler._resync_current_frame(context.scene, context.evaluated_depsgraph_get())

        return {"FINISHED"}


OPERATOR_CLASSES = (
    NEXUS_OT_cache_source_toggle_lock,
    NEXUS_OT_cache_empty,
)
