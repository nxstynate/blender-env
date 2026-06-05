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

import datetime
import os
import sys

from ..libs import theron

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
    _HAS_PYQT = True
except ImportError:
    _HAS_PYQT = False

try:
    from PyQt6 import QtMultimedia  # noqa: E402

    _HAVE_MULTIMEDIA = True
except ImportError:
    _HAVE_MULTIMEDIA = False



_win = None

_SPLASH_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "icons",
    "images",
    "splash",
    "nexus_splash_01.mp4",
)

# Native video dimensions
_SPLASH_W = 800
_SPLASH_H = 600
_CORNER_RADIUS = 14


def has_open_window():
    return _win is not None


def _gather_about_info():
    from .. import version

    try:
        # Don't include full version string with git commit
        addon_ver = version.get_blender_version_str().split("+")[0]
    except Exception:
        addon_ver = "unknown"

    try:
        core_ver = theron.get_version_str() or "unknown"
    except Exception:
        core_ver = "unknown"

    try:
        ts = theron.get_build_date()
        build_date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        build_date = ""

    name = ""
    email = ""
    try:
        from ..utils import get_blender_addon

        prefs = get_blender_addon().preferences
        name = (prefs.license_name or "").strip()
        email = (prefs.license_email or "").strip()
    except Exception:
        pass

    return {
        "addon_ver": addon_ver,
        "core_ver": core_ver,
        "build_date": build_date,
        "name": name,
        "email": email,
        "year": datetime.datetime.now().year,
    }


if _HAS_PYQT:
    class _AboutView(QtWidgets.QGraphicsView):
        """Hosts the scene. Click anywhere to close. Rounded clip + no chrome."""

        def __init__(self, scene, on_close):
            super().__init__(scene)
            self._on_close = on_close
            self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
            self.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
            self.setStyleSheet("background: transparent;")
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
            self.viewport().setAutoFillBackground(False)

        def mousePressEvent(self, event):
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._on_close()
                return
            super().mousePressEvent(event)

    class _AboutWindow(QtWidgets.QWidget):
        """Frameless rounded-corner window. Players are torn down on close via a
        two-stage async sequence so QMediaPlayer's backend thread can flush
        before its referenced sinks/audio outputs are destroyed."""

        def __init__(self):
            super().__init__()
            self._player = None
            self._audio = None
            self._sink = None
            self._closing = False

        def paintEvent(self, event):
            # Paint a rounded black background so the corners are alpha-clipped.
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0))
            rect = QtCore.QRectF(0, 0, self.width(), self.height())
            painter.drawRoundedRect(rect, _CORNER_RADIUS, _CORNER_RADIUS)

        def resizeEvent(self, event):
            # Hard alpha mask via QBitmap so the window outline really is rounded
            # (some compositors ignore translucent-painted corners alone).
            bmp = QtGui.QBitmap(self.size())
            bmp.fill(QtCore.Qt.GlobalColor.color0)
            p = QtGui.QPainter(bmp)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            p.setBrush(QtCore.Qt.GlobalColor.color1)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.drawRoundedRect(
                QtCore.QRectF(0, 0, self.width(), self.height()),
                _CORNER_RADIUS,
                _CORNER_RADIUS,
            )
            p.end()
            self.setMask(bmp)

        def begin_close(self):
            if self._closing:
                return
            self._closing = True

            # Hide immediately so the user sees no UI lag
            self.hide()

            # Stop playback first
            if self._player is not None:
                try:
                    self._player.stop()
                except Exception:
                    pass

            # Disconnect sink signal so no more frames are pushed during teardown
            if self._sink is not None:
                try:
                    self._sink.videoFrameChanged.disconnect()
                except Exception:
                    pass

            # Defer the real teardown so MF backend thread can flush
            QtCore.QTimer.singleShot(120, self._finish_close)

        def _finish_close(self):
            if self._player is not None:
                try:
                    self._player.setVideoOutput(None)
                except Exception:
                    pass
                try:
                    self._player.setAudioOutput(None)
                except Exception:
                    pass
                try:
                    self._player.setSource(QtCore.QUrl())
                except Exception:
                    pass
                try:
                    self._player.deleteLater()
                except Exception:
                    pass
                self._player = None

            if self._audio is not None:
                try:
                    self._audio.deleteLater()
                except Exception:
                    pass
                self._audio = None

            if self._sink is not None:
                try:
                    self._sink.deleteLater()
                except Exception:
                    pass
                self._sink = None

            global _win
            _win = None
            # Defer the actual close one more tick so deleteLater queue drains
            QtCore.QTimer.singleShot(60, self.close)

        def closeEvent(self, event):
            # If close was triggered externally (e.g. Blender shutting down)
            # and we haven't started teardown yet, do the safe path.
            if not self._closing:
                event.ignore()
                self.begin_close()
                return
            event.accept()


def _close_window():
    if _win is None:
        return
    _win.begin_close()


def _make_text_item(text, font_size, color, bold=False, opacity=1.0):
    item = QtWidgets.QGraphicsSimpleTextItem(text)
    weight = 600 if bold else 400
    font = QtGui.QFont("Segoe UI", font_size)
    font.setWeight(QtGui.QFont.Weight(weight))
    item.setFont(font)
    item.setBrush(QtGui.QBrush(QtGui.QColor(color)))
    item.setOpacity(opacity)
    return item


def open_about_dialog():
    if not _HAS_PYQT:
        return
    global _win

    if _win is not None:
        _win.raise_()
        _win.activateWindow()
        return

    _win = _AboutWindow()
    _win.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
    _win.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
    _win.setWindowFlags(
        QtCore.Qt.WindowType.Window
        | QtCore.Qt.WindowType.WindowStaysOnTopHint
        | QtCore.Qt.WindowType.FramelessWindowHint
    )
    _win.setWindowTitle("About INSYDIUM NeXus")

    icon_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "icons",
        "images",
        "brand",
        "insydium_black.png",
    )
    if os.path.isfile(icon_path):
        _win.setWindowIcon(QtGui.QIcon(icon_path))

    _win.setFixedSize(_SPLASH_W, _SPLASH_H)

    screen = QtWidgets.QApplication.primaryScreen()
    if screen is not None:
        geom = screen.availableGeometry()
        _win.move(
            geom.x() + (geom.width() - _SPLASH_W) // 2,
            geom.y() + (geom.height() - _SPLASH_H) // 2,
        )

    # Scene exactly matches video pixels — no letterbox.
    scene = QtWidgets.QGraphicsScene(0, 0, _SPLASH_W, _SPLASH_H)
    scene.setBackgroundBrush(QtCore.Qt.GlobalColor.transparent)

    # Pixmap item is what actually draws video frames.
    pixmap_item = QtWidgets.QGraphicsPixmapItem()
    pixmap_item.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
    scene.addItem(pixmap_item)

    if _HAVE_MULTIMEDIA and os.path.isfile(_SPLASH_PATH):
        sink = QtMultimedia.QVideoSink()

        def on_frame(frame):
            if not frame.isValid():
                return
            img = frame.toImage()
            if img.isNull():
                return
            pm = QtGui.QPixmap.fromImage(img)
            if (pm.width(), pm.height()) != (_SPLASH_W, _SPLASH_H):
                pm = pm.scaled(
                    _SPLASH_W,
                    _SPLASH_H,
                    QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            pixmap_item.setPixmap(pm)

        sink.videoFrameChanged.connect(on_frame)

        player = QtMultimedia.QMediaPlayer(_win)
        audio = QtMultimedia.QAudioOutput(_win)
        audio.setMuted(True)
        player.setAudioOutput(audio)
        player.setVideoSink(sink)
        player.setLoops(QtMultimedia.QMediaPlayer.Loops.Infinite)
        player.setSource(QtCore.QUrl.fromLocalFile(_SPLASH_PATH))
        player.play()

        _win._player = player
        _win._audio = audio
        _win._sink = sink

    # Overlay text — positioned at the very bottom of the video frame so it
    # sits in the dark/grey strip the splash artwork already provides. No
    # added black border below.
    info = _gather_about_info()

    title_text = f"INSYDIUM NeXus {info['addon_ver']}"

    core_text = f"NeXus Core Build {info['core_ver']}"
    if info["build_date"]:
        core_text += f"   ({info['build_date']})"

    user_text = ""
    if info["name"] and info["email"]:
        user_text = f"{info['name']} <{info['email']}>"
    elif info["name"]:
        user_text = info["name"]
    elif info["email"]:
        user_text = f"<{info['email']}>"

    copyright_text = f"Copyright © {info['year']} INSYDIUM LTD   ·   https://insydium.ltd"

    # Stack of lines anchored to bottom-left of the video, sitting on the
    # built-in dark strip. ~70px tall area at the bottom.
    margin_x = 22
    line_h = 13
    # Bottom line baseline ≈ _SPLASH_H - 10
    lines = []
    if copyright_text:
        lines.append((copyright_text, 7, "#aaaaaa", False, 0.6))
    if user_text:
        lines.append((user_text, 8, "#cccccc", False, 0.8))
    if core_text:
        lines.append((core_text, 8, "#dddddd", False, 0.85))
    if title_text:
        lines.append((title_text, 10, "#ffffff", True, 1.0))

    # Build bottom-up
    y = _SPLASH_H - 14
    for text, fs, color, bold, opacity in lines:
        item = _make_text_item(text, fs, color, bold=bold, opacity=opacity)
        rect = item.boundingRect()
        y -= rect.height()
        item.setPos(margin_x, y)
        scene.addItem(item)

    # Close hint — top-right
    hint_item = _make_text_item("click to close", font_size=7, color="#ffffff", opacity=0.5)
    hint_rect = hint_item.boundingRect()
    hint_item.setPos(_SPLASH_W - hint_rect.width() - 14, 8)
    scene.addItem(hint_item)

    view = _AboutView(scene, _close_window)
    view.setGeometry(0, 0, _SPLASH_W, _SPLASH_H)

    layout = QtWidgets.QVBoxLayout(_win)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(view)

    _win.show()
    _win.raise_()
    _win.activateWindow()
