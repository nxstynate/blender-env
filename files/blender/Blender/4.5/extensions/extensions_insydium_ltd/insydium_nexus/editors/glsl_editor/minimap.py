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

"""Minimap widget for the GLSL Script Editor.

Provides a zoomed-out overview of the document shown alongside the code editor.
Clicking or dragging scrolls the editor to the corresponding position.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass

from .theme import GLSLEditorTheme  # noqa: E402

_MINIMAP_WIDTH = 90
_LINE_HEIGHT = 2


class MinimapWidget(QtWidgets.QWidget):
    """Minimap showing a zoomed-out document overview."""

    def __init__(self, editor, theme: GLSLEditorTheme, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._theme = theme
        self._dragging = False

        self.setFixedWidth(_MINIMAP_WIDTH)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        self._cache_pixmap: QtGui.QPixmap | None = None
        self._cache_dirty = True

        self._repaint_timer = QtCore.QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(200)
        self._repaint_timer.timeout.connect(self._regenerate_cache)

        editor.document().contentsChanged.connect(self._on_content_changed)
        editor.verticalScrollBar().valueChanged.connect(self.update)

        QtCore.QTimer.singleShot(0, self._regenerate_cache)

    def _on_content_changed(self):
        self._cache_dirty = True
        self._repaint_timer.start()

    def _regenerate_cache(self):
        """Render the document into a cached pixmap with syntax coloring."""
        doc = self._editor.document()
        line_count = doc.blockCount()
        if line_count == 0:
            self._cache_pixmap = None
            self._cache_dirty = False
            self.update()
            return

        cache_height = max(1, line_count * _LINE_HEIGHT)

        image = QtGui.QImage(
            _MINIMAP_WIDTH,
            cache_height,
            QtGui.QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(self._theme.qcolor("minimap_bg"))

        default_color = QtGui.QColor(self._theme.minimap_text)
        default_color.setAlpha(140)
        default_rgba = default_color.rgba()

        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        max_chars = _MINIMAP_WIDTH

        block = doc.begin()
        y = 0
        while block.isValid():
            text = block.text()
            if text.strip():
                layout = block.layout()
                format_ranges = layout.formats() if layout else []
                line_len = len(text)
                render_len = min(line_len, max_chars)

                colors = [default_rgba] * render_len

                for fmt_range in format_ranges:
                    fg = fmt_range.format.foreground()
                    if fg.style() == QtCore.Qt.BrushStyle.NoBrush:
                        continue
                    range_color = QtGui.QColor(fg.color())
                    range_color.setAlpha(180)
                    rgba = range_color.rgba()
                    start = fmt_range.start
                    end = min(render_len, start + fmt_range.length)
                    for ci in range(max(0, start), end):
                        colors[ci] = rgba

                run_start = -1
                run_color = 0
                for ci in range(render_len):
                    is_space = text[ci].isspace()
                    c = colors[ci] if not is_space else 0

                    if not is_space:
                        if c == run_color and run_start >= 0:
                            continue
                        if run_start >= 0:
                            painter.setBrush(QtGui.QColor.fromRgba(run_color))
                            painter.drawRect(
                                run_start,
                                y,
                                ci - run_start,
                                _LINE_HEIGHT,
                            )
                        run_start = ci
                        run_color = c
                    elif run_start >= 0:
                        painter.setBrush(QtGui.QColor.fromRgba(run_color))
                        painter.drawRect(
                            run_start,
                            y,
                            ci - run_start,
                            _LINE_HEIGHT,
                        )
                        run_start = -1

                if run_start >= 0:
                    painter.setBrush(QtGui.QColor.fromRgba(run_color))
                    painter.drawRect(
                        run_start,
                        y,
                        render_len - run_start,
                        _LINE_HEIGHT,
                    )

            y += _LINE_HEIGHT
            block = block.next()

        painter.end()
        self._cache_pixmap = QtGui.QPixmap.fromImage(image)
        self._cache_dirty = False
        self.update()

    def _visible_line_range(self) -> tuple[int, int]:
        """Return (first_visible_line, visible_line_count)."""
        first_visible = self._editor.firstVisibleBlock().blockNumber()
        visible_lines = 0
        block = self._editor.firstVisibleBlock()
        viewport_height = self._editor.viewport().height()
        while block.isValid():
            geom = self._editor.blockBoundingGeometry(block).translated(
                self._editor.contentOffset()
            )
            if geom.top() > viewport_height:
                break
            visible_lines += 1
            block = block.next()
        return first_visible, visible_lines

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)

        painter.fillRect(self.rect(), self._theme.qcolor("minimap_bg"))

        if self._cache_pixmap is None:
            border_color = self._theme.qcolor("toolbar_separator")
            painter.setPen(border_color)
            painter.drawLine(0, 0, 0, self.height())
            painter.end()
            return

        doc = self._editor.document()
        line_count = doc.blockCount()
        if line_count == 0:
            painter.end()
            return

        total_minimap_height = line_count * _LINE_HEIGHT
        widget_height = self.height()

        if total_minimap_height <= widget_height:
            painter.drawPixmap(0, 0, self._cache_pixmap)
            offset_y = 0
        else:
            scroll_bar = self._editor.verticalScrollBar()
            max_scroll = scroll_bar.maximum()
            if max_scroll > 0:
                scroll_fraction = scroll_bar.value() / max_scroll
            else:
                scroll_fraction = 0.0

            max_offset = total_minimap_height - widget_height
            offset_y = int(scroll_fraction * max_offset)

            source_rect = QtCore.QRect(0, offset_y, _MINIMAP_WIDTH, widget_height)
            painter.drawPixmap(
                0,
                0,
                self._cache_pixmap,
                source_rect.x(),
                source_rect.y(),
                source_rect.width(),
                source_rect.height(),
            )

        first_visible, visible_lines = self._visible_line_range()

        if total_minimap_height <= widget_height:
            vp_top = first_visible * _LINE_HEIGHT
        else:
            vp_top = first_visible * _LINE_HEIGHT - offset_y

        vp_height = max(10, visible_lines * _LINE_HEIGHT)

        vp_color = self._theme.qcolor("minimap_viewport")
        if not vp_color.isValid():
            vp_color = QtGui.QColor(255, 255, 255, 25)

        painter.fillRect(0, vp_top, _MINIMAP_WIDTH, vp_height, vp_color)

        border_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 1)
        painter.setPen(border_pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(1, vp_top, _MINIMAP_WIDTH - 3, vp_height - 1)

        border_color = self._theme.qcolor("toolbar_separator")
        painter.setPen(border_color)
        painter.drawLine(0, 0, 0, self.height())

        painter.end()

    def _y_to_line(self, y: int) -> int:
        """Convert a widget y-coordinate to a line number."""
        doc = self._editor.document()
        line_count = doc.blockCount()
        total_minimap_height = line_count * _LINE_HEIGHT
        widget_height = self.height()

        if total_minimap_height <= widget_height:
            return max(0, min(line_count - 1, y // max(1, _LINE_HEIGHT)))

        scroll_bar = self._editor.verticalScrollBar()
        max_offset = total_minimap_height - widget_height
        if scroll_bar.maximum() > 0:
            offset_y = int((scroll_bar.value() / scroll_bar.maximum()) * max_offset)
        else:
            offset_y = 0
        return max(0, min(line_count - 1, (y + offset_y) // max(1, _LINE_HEIGHT)))

    def _scroll_to_line(self, line: int):
        """Scroll the editor to center the given line."""
        block = self._editor.document().findBlockByNumber(line)
        if not block.isValid():
            return
        cursor = QtGui.QTextCursor(block)
        self._editor.setTextCursor(cursor)
        self._editor.centerCursor()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = True
            line = self._y_to_line(event.pos().y())
            self._scroll_to_line(line)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self._dragging:
            line = self._y_to_line(event.pos().y())
            self._scroll_to_line(line)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = False
