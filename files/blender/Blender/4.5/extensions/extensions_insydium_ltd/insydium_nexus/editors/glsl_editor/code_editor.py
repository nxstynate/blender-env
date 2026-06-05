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

"""Core GLSL code editor widget for the NeXus Script Editor.

Provides ``GLSLCodeEditor``, a ``QPlainTextEdit`` subclass with line numbers,
current-line highlight, bracket matching, auto-indent, and auto-completion.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass

from .completer import (  # noqa: E402
    CompletionContext,
    CompletionItem,
    CompletionKind,
    WorkspaceSymbols,
    analyze_context,
    build_external_var_completions,
    extract_workspace_symbols,
    find_active_signature,
    find_enclosing_scope,
    get_completions,
    get_signature_info,
)
from .completion_popup import CompletionPopup  # noqa: E402
from .highlighter import _STATE_IN_MULTILINE_COMMENT, GLSLSyntaxHighlighter  # noqa: E402
from .signature_help import SignatureHelpWidget  # noqa: E402
from .validator import Diagnostic, Severity  # noqa: E402
from .vim_mode import VimHandler, VimMode  # noqa: E402

_BRACKET_PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    ")": "(",
    "]": "[",
    "}": "{",
}
_OPEN_BRACKETS = frozenset("({[")
_CLOSE_BRACKETS = frozenset(")}]")

_AUTO_CLOSE_PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    '"': '"',
    "'": "'",
}
_CLOSE_CHARS = frozenset(_AUTO_CLOSE_PAIRS.values())

_QUOTE_AUTO_CLOSE_CONTEXT = frozenset(" \t\n([{,;=+-*/<>!&|")

_PREFERRED_FONTS = ("Source Code Pro", "Consolas", "Menlo", "Courier New")
_FONT_POINT_SIZE = 11

_FOLD_MARGIN_WIDTH = 14

_MAX_BRACKET_SCAN = 5000


# ---------------------------------------------------------------------------
# Snippet session
# ---------------------------------------------------------------------------


class _TabstopRange:
    __slots__ = ("pos", "length")

    def __init__(self, pos: int, length: int):
        self.pos = pos
        self.length = length


class SnippetSession:
    """Manages an active snippet expansion with tabstop navigation."""

    def __init__(self, editor, insert_pos: int, parsed):
        self.editor = editor
        self.start_pos = insert_pos
        self.end_pos = insert_pos + len(parsed.text)
        self._active = True
        self._updating = False

        groups: dict[int, list[_TabstopRange]] = {}
        for ts in parsed.tabstops:
            r = _TabstopRange(insert_pos + ts.offset, ts.length)
            groups.setdefault(ts.index, []).append(r)
        self.tabstop_groups = groups

        indices = sorted(k for k in groups if k != 0)
        if 0 in groups:
            indices.append(0)
        else:
            groups[0] = [_TabstopRange(self.end_pos, 0)]
            indices.append(0)
        self.visit_order = indices
        self.current_idx = 0

    def is_active(self) -> bool:
        return self._active

    def select_current(self):
        if not self._active or not self.visit_order:
            return
        tabstop_num = self.visit_order[self.current_idx]
        ranges = self.tabstop_groups[tabstop_num]
        r = ranges[0]
        cursor = self.editor.textCursor()
        cursor.setPosition(r.pos)
        cursor.setPosition(r.pos + r.length, QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

    def next_tabstop(self) -> bool:
        if not self._active:
            return False
        self.current_idx += 1
        if self.current_idx >= len(self.visit_order):
            self.finish()
            return False
        self.select_current()
        return True

    def previous_tabstop(self) -> bool:
        if not self._active or self.current_idx <= 0:
            return False
        self.current_idx -= 1
        self.select_current()
        return True

    def finish(self):
        if not self._active:
            return
        self._active = False
        if 0 in self.tabstop_groups:
            r = self.tabstop_groups[0][0]
            cursor = self.editor.textCursor()
            cursor.setPosition(r.pos + r.length)
            self.editor.setTextCursor(cursor)

    def on_contents_change(self, position: int, chars_removed: int, chars_added: int):
        if self._updating or not self._active:
            return
        delta = chars_added - chars_removed

        if position < self.start_pos or position > self.end_pos:
            self.finish()
            return

        self.end_pos += delta

        edited_group_idx = None
        edited_range = None
        current_num = (
            self.visit_order[self.current_idx] if self.current_idx < len(self.visit_order) else -1
        )

        if current_num >= 0 and current_num in self.tabstop_groups:
            for r in self.tabstop_groups[current_num]:
                if r.pos <= position <= r.pos + r.length - delta + chars_removed:
                    edited_group_idx = current_num
                    edited_range = r
                    break

        if edited_range is None:
            for idx, ranges in self.tabstop_groups.items():
                for r in ranges:
                    if r.pos > position:
                        r.pos += delta
                    elif r is not edited_range and r.pos + r.length > position:
                        r.length += delta
            return

        edited_range.length += delta

        for idx, ranges in self.tabstop_groups.items():
            for r in ranges:
                if r is edited_range:
                    continue
                if r.pos > position:
                    r.pos += delta

        mirrors = [r for r in self.tabstop_groups[edited_group_idx] if r is not edited_range]
        if not mirrors:
            return

        doc_text = self.editor.toPlainText()
        new_text = doc_text[edited_range.pos : edited_range.pos + edited_range.length]

        self._updating = True
        try:
            cursor = self.editor.textCursor()
            cursor.beginEditBlock()
            for r in sorted(mirrors, key=lambda x: x.pos, reverse=True):
                old_len = r.length
                c = self.editor.textCursor()
                c.setPosition(r.pos)
                c.setPosition(r.pos + old_len, QtGui.QTextCursor.MoveMode.KeepAnchor)
                c.insertText(new_text)
                length_delta = len(new_text) - old_len
                r.length = len(new_text)
                for idx2, ranges2 in self.tabstop_groups.items():
                    for r2 in ranges2:
                        if r2 is r:
                            continue
                        if r2.pos > r.pos:
                            r2.pos += length_delta
                self.end_pos += length_delta
            cursor.endEditBlock()
        finally:
            self._updating = False

    def get_extra_selections(self, theme):
        """Return extra selections for tabstop highlighting."""
        selections = []
        if not self._active:
            return selections

        current_num = (
            self.visit_order[self.current_idx] if self.current_idx < len(self.visit_order) else -1
        )

        for idx, ranges in self.tabstop_groups.items():
            if idx == 0:
                continue
            color_key = (
                "snippet_tabstop_active" if idx == current_num else "snippet_tabstop_inactive"
            )
            bg = theme.qcolor(color_key)
            for r in ranges:
                if r.length == 0:
                    continue
                sel = QtWidgets.QTextEdit.ExtraSelection()
                sel.format.setBackground(bg)
                c = self.editor.textCursor()
                c.setPosition(r.pos)
                c.setPosition(r.pos + r.length, QtGui.QTextCursor.MoveMode.KeepAnchor)
                sel.cursor = c
                selections.append(sel)

        return selections


# ---------------------------------------------------------------------------
# Line number gutter
# ---------------------------------------------------------------------------


class _LineNumberArea(QtWidgets.QWidget):
    """Narrow gutter widget that displays line numbers alongside the editor."""

    def __init__(self, editor: GLSLCodeEditor):
        super().__init__(editor)
        self._editor = editor
        self.setMouseTracking(True)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent):
        self._editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self._editor.fold_area_mouse_press(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        self._editor.fold_area_mouse_move(event)

    def leaveEvent(self, event):
        self._editor.fold_area_mouse_leave()


# ---------------------------------------------------------------------------
# Diagnostic tooltip
# ---------------------------------------------------------------------------


class _DiagnosticTooltip(QtWidgets.QFrame):
    """Instant diagnostic tooltip that bypasses QToolTip's internal delay."""

    def __init__(self, theme):
        super().__init__(None)
        self._theme = theme

        self.setWindowFlags(
            QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {theme.menu_bg};"
            f"  color: {theme.text};"
            f"  border: 1px solid {theme.menu_border};"
            f"  border-radius: 3px;"
            f"}}"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._label = QtWidgets.QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._label.setStyleSheet("border: none;")
        layout.addWidget(self._label)

        self.setLayout(layout)

    def show_diagnostic(self, global_pos: QtCore.QPoint, text: str):
        self._label.setText(text)
        self.adjustSize()

        target_x = global_pos.x() + 16
        target_y = global_pos.y() + 16

        screen = QtWidgets.QApplication.screenAt(global_pos)
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        widget_width = self.sizeHint().width()
        widget_height = self.sizeHint().height()

        if target_x + widget_width > screen_rect.right():
            target_x = screen_rect.right() - widget_width
        if target_x < screen_rect.left():
            target_x = screen_rect.left()
        if target_y + widget_height > screen_rect.bottom():
            target_y = global_pos.y() - widget_height - 4
        if target_y < screen_rect.top():
            target_y = screen_rect.top()

        self.move(target_x, target_y)
        self.show()

    def hide_diagnostic(self):
        self.hide()

    def is_showing(self) -> bool:
        return self.isVisible()


# ---------------------------------------------------------------------------
# Code editor
# ---------------------------------------------------------------------------


class GLSLCodeEditor(QtWidgets.QPlainTextEdit):
    """A ``QPlainTextEdit`` subclass tailored for editing GLSL source code."""

    zoom_changed = QtCore.pyqtSignal(int)
    vim_mode_changed = QtCore.pyqtSignal(object)
    vim_command_requested = QtCore.pyqtSignal()
    vim_find_requested = QtCore.pyqtSignal()
    vim_find_word_requested = QtCore.pyqtSignal(str, bool)
    vim_find_next_requested = QtCore.pyqtSignal()
    vim_find_prev_requested = QtCore.pyqtSignal()

    def __init__(self, theme, parent=None, *, user_vars=()):
        super().__init__(parent)

        self._theme = theme
        self._tab_width: int = 4
        self._zoom_level: int = 0
        self._use_spaces: bool = True
        self._find_selections: list[QtWidgets.QTextEdit.ExtraSelection] = []

        self._occurrence_selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        self._last_occurrence_word: str = ""
        self._occurrence_timer = QtCore.QTimer(self)
        self._occurrence_timer.setSingleShot(True)
        self._occurrence_timer.setInterval(150)
        self._occurrence_timer.timeout.connect(self._update_occurrence_highlights)

        self._diagnostics: list[Diagnostic] = []
        self._diagnostic_selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        self._diagnostic_line_map: dict[int, list[Diagnostic]] = {}
        self._last_tooltip_line: int = -1
        self._diagnostic_tooltip = _DiagnosticTooltip(theme)

        self._folded_blocks: dict[int, QtGui.QTextBlock] = {}
        self._fold_hover_block: int = -1
        self._fold_regions: dict[int, int] = {}
        self._fold_regions_dirty: bool = True
        self._in_fold_update: bool = False

        self._setup_font()
        self.setTabStopDistance(
            QtGui.QFontMetricsF(self.font()).horizontalAdvance(" " * self._tab_width)
        )
        self.setWordWrapMode(QtGui.QTextOption.WrapMode.NoWrap)

        self._line_number_area = _LineNumberArea(self)
        self._update_line_number_area_width()

        self._highlighter = GLSLSyntaxHighlighter(theme, self.document())

        self._completion_popup = CompletionPopup(theme, self.font(), self)
        self._completion_popup.item_accepted.connect(self._insert_completion)
        self._signature_widget = SignatureHelpWidget(theme, self)
        self._completion_context: tuple[CompletionContext, str, str] | None = None

        self._bracket_cache_key: tuple[int, int] | None = None
        self._bracket_cache_value: list[QtWidgets.QTextEdit.ExtraSelection] = []

        self._workspace_symbols: WorkspaceSymbols | None = None
        self._user_vars = user_vars
        if user_vars:
            self._external_completions, self._external_var_types = build_external_var_completions(
                user_vars
            )
        else:
            self._external_completions = ()
            self._external_var_types = {}
        self._extraction_timer = QtCore.QTimer(self)
        self._extraction_timer.setSingleShot(True)
        self._extraction_timer.setInterval(200)
        self._extraction_timer.timeout.connect(self._extract_workspace_symbols)

        self._snippet_session: SnippetSession | None = None

        self._vim_handler = VimHandler(self, parent=self)
        self._vim_handler.mode_changed.connect(self.vim_mode_changed.emit)
        self._vim_handler.find_requested.connect(self.vim_find_requested.emit)
        self._vim_handler.find_word_requested.connect(self.vim_find_word_requested.emit)
        self._vim_handler.find_next_requested.connect(self.vim_find_next_requested.emit)
        self._vim_handler.find_prev_requested.connect(self.vim_find_prev_requested.emit)

        self._scroll_animation = QtCore.QPropertyAnimation(
            self.verticalScrollBar(),
            b"value",
            self,
        )
        self._scroll_animation.setDuration(150)
        self._scroll_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        self._apply_theme()
        self.viewport().setMouseTracking(True)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        doc = self.document()
        doc.contentsChanged.connect(self._on_contents_changed)
        doc.contentsChange.connect(self._on_contents_change_snippet)

        self._update_extra_selections()

    # ------------------------------------------------------------------
    # Font setup
    # ------------------------------------------------------------------

    def _setup_font(self):
        available = set(QtGui.QFontDatabase.families())

        font = None
        for family in _PREFERRED_FONTS:
            if family in available:
                font = QtGui.QFont(family, _FONT_POINT_SIZE)
                break

        if font is None:
            font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
            font.setPointSize(_FONT_POINT_SIZE)

        font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.setFont(font)
        self.document().setDefaultFont(font)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom_in(self):
        if self._zoom_level < 10:
            self._zoom_level += 1
            self._apply_zoom()

    def zoom_out(self):
        if self._zoom_level > -5:
            self._zoom_level -= 1
            self._apply_zoom()

    def zoom_reset(self):
        self._zoom_level = 0
        self._apply_zoom()

    def _apply_zoom(self):
        font = self.font()
        font.setPointSize(_FONT_POINT_SIZE + self._zoom_level)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.setTabStopDistance(QtGui.QFontMetricsF(font).horizontalAdvance(" " * self._tab_width))
        self._update_line_number_area_width()
        self._signature_widget.update_font()
        self.viewport().update()
        percentage = round(100 * (_FONT_POINT_SIZE + self._zoom_level) / _FONT_POINT_SIZE)
        self.zoom_changed.emit(percentage)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        self._diagnostic_tooltip.hide_diagnostic()
        self._last_tooltip_line = -1

        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
            return

        if event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return

        self._handle_smooth_scroll(event)
        event.accept()

    def _handle_smooth_scroll(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y()
        pixels_per_step = self.fontMetrics().height() * 3
        scroll_amount = -int(delta / 120.0 * pixels_per_step)

        scroll_bar = self.verticalScrollBar()

        if self._scroll_animation.state() == QtCore.QAbstractAnimation.State.Running:
            target = self._scroll_animation.endValue() + scroll_amount
        else:
            target = scroll_bar.value() + scroll_amount

        target = max(scroll_bar.minimum(), min(scroll_bar.maximum(), target))

        self._scroll_animation.stop()
        self._scroll_animation.setStartValue(scroll_bar.value())
        self._scroll_animation.setEndValue(target)
        self._scroll_animation.start()

        self._completion_popup.dismiss()
        self._signature_widget.dismiss()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        self.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {self._theme.background};"
            f"  color: {self._theme.text};"
            f"  selection-background-color: {self._theme.selection};"
            f"  border: none;"
            f"}}"
        )

    # ------------------------------------------------------------------
    # Line number area
    # ------------------------------------------------------------------

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        char_width = self.fontMetrics().horizontalAdvance("9")
        padding = 20
        return char_width * digits + padding + _FOLD_MARGIN_WIDTH

    def _update_line_number_area_width(self, _new_block_count: int = 0):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QtCore.QRect, dy: int):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def line_number_area_paint_event(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self._theme.qcolor("line_number_bg"))

        self._ensure_fold_regions()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        current_block_number = self.textCursor().blockNumber()
        gutter_width = self._line_number_area.width()
        right_margin = 10 + _FOLD_MARGIN_WIDTH
        triangle_size = 8

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if block_number == current_block_number:
                    painter.setPen(self._theme.qcolor("line_number_active_fg"))
                else:
                    painter.setPen(self._theme.qcolor("line_number_fg"))
                painter.drawText(
                    0,
                    top,
                    gutter_width - right_margin,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
                    str(block_number + 1),
                )

                diag_line = block_number + 1
                if diag_line in self._diagnostic_line_map:
                    diags_on_line = self._diagnostic_line_map[diag_line]
                    has_error = any(d.severity == Severity.ERROR for d in diags_on_line)
                    if has_error:
                        dot_color = self._theme.qcolor("gutter_error")
                    else:
                        dot_color = self._theme.qcolor("gutter_warning")
                    dot_radius = 3
                    dot_x = 6
                    dot_y = top + self.fontMetrics().height() // 2
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.setBrush(dot_color)
                    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                    painter.drawEllipse(
                        QtCore.QPoint(dot_x, dot_y),
                        dot_radius,
                        dot_radius,
                    )
                    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

                if block_number in self._fold_regions:
                    fold_x = gutter_width - _FOLD_MARGIN_WIDTH + 3
                    fold_y = top + (self.fontMetrics().height() - triangle_size) // 2

                    if block_number == self._fold_hover_block:
                        color = self._theme.qcolor("fold_marker_hover")
                    else:
                        color = self._theme.qcolor("fold_marker")

                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.setBrush(color)

                    if block.blockNumber() in self._folded_blocks:
                        triangle = QtGui.QPolygon(
                            [
                                QtCore.QPoint(fold_x, fold_y),
                                QtCore.QPoint(fold_x + triangle_size, fold_y + triangle_size // 2),
                                QtCore.QPoint(fold_x, fold_y + triangle_size),
                            ]
                        )
                    else:
                        triangle = QtGui.QPolygon(
                            [
                                QtCore.QPoint(fold_x, fold_y),
                                QtCore.QPoint(fold_x + triangle_size, fold_y),
                                QtCore.QPoint(fold_x + triangle_size // 2, fold_y + triangle_size),
                            ]
                        )
                    painter.drawPolygon(triangle)

            block = block.next()
            block_number += 1
            if not block.isValid():
                break
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())

        painter.end()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(), self.line_number_area_width(), cr.height()
        )
        self._completion_popup.dismiss()
        self._signature_widget.dismiss()

    def focusOutEvent(self, event: QtGui.QFocusEvent):
        focus_widget = QtWidgets.QApplication.focusWidget()
        is_own_popup = (
            focus_widget is self._completion_popup or focus_widget is self._signature_widget
        )
        if not is_own_popup:
            self._completion_popup.dismiss()
            self._signature_widget.dismiss()
        super().focusOutEvent(event)

    # ------------------------------------------------------------------
    # Extra selections (current line, bracket match, find highlights)
    # ------------------------------------------------------------------

    def _on_cursor_position_changed(self):
        if self._snippet_session is not None and self._snippet_session.is_active():
            pos = self.textCursor().position()
            if pos < self._snippet_session.start_pos or pos > self._snippet_session.end_pos:
                self._clear_snippet_session()
        self._occurrence_timer.start()
        self._update_extra_selections()

    def _update_extra_selections(self):
        selections: list[QtWidgets.QTextEdit.ExtraSelection] = []

        current_line_sel = QtWidgets.QTextEdit.ExtraSelection()
        current_line_sel.format.setBackground(self._theme.qcolor("current_line"))
        current_line_sel.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
        current_line_sel.cursor = self.textCursor()
        current_line_sel.cursor.clearSelection()
        selections.append(current_line_sel)

        selections.extend(self._diagnostic_selections)
        selections.extend(self._occurrence_selections)
        selections.extend(self._get_bracket_selections())
        selections.extend(self._find_selections)
        if self._snippet_session is not None and self._snippet_session.is_active():
            selections.extend(self._snippet_session.get_extra_selections(self._theme))
        self.setExtraSelections(selections)

    def set_find_selections(self, selections: list[QtWidgets.QTextEdit.ExtraSelection]):
        self._find_selections = selections
        self._update_extra_selections()

    @property
    def vim_handler(self) -> VimHandler:
        return self._vim_handler

    def set_vim_mode_enabled(self, enabled: bool) -> None:
        self._vim_handler.set_enabled(enabled)

    # ------------------------------------------------------------------
    # Diagnostics (errors / warnings)
    # ------------------------------------------------------------------

    def set_diagnostics(self, diagnostics: list[Diagnostic]):
        """Apply a new set of diagnostics and refresh underlines + gutter."""
        self._diagnostics = diagnostics

        self._diagnostic_line_map.clear()
        self._diagnostic_tooltip.hide_diagnostic()
        self._last_tooltip_line = -1
        for diag in diagnostics:
            self._diagnostic_line_map.setdefault(diag.line, []).append(diag)

        self._diagnostic_selections.clear()
        doc = self.document()

        for diag in diagnostics:
            block = doc.findBlockByNumber(diag.line - 1)
            if not block.isValid():
                continue

            block_text = block.text()
            start_col = diag.column
            if start_col <= 0:
                start_col = len(block_text) - len(block_text.lstrip())

            end_col = len(block_text.rstrip())
            if end_col <= start_col:
                end_col = max(start_col + 1, len(block_text))

            cursor = QtGui.QTextCursor(block)
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.Right,
                QtGui.QTextCursor.MoveMode.MoveAnchor,
                start_col,
            )
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.Right,
                QtGui.QTextCursor.MoveMode.KeepAnchor,
                end_col - start_col,
            )

            sel = QtWidgets.QTextEdit.ExtraSelection()
            fmt = QtGui.QTextCharFormat()
            fmt.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline)
            if diag.severity == Severity.WARNING:
                fmt.setUnderlineColor(self._theme.qcolor("warning_underline"))
            else:
                fmt.setUnderlineColor(self._theme.qcolor("error_underline"))
            sel.format = fmt
            sel.cursor = cursor
            self._diagnostic_selections.append(sel)

        self._update_extra_selections()
        self._line_number_area.update()

    def diagnostics(self) -> list[Diagnostic]:
        """Return the current diagnostic list."""
        return self._diagnostics

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Show a tooltip when hovering over a line with diagnostics."""
        super().mouseMoveEvent(event)
        cursor = self.cursorForPosition(event.pos())
        line = cursor.blockNumber() + 1

        diags = self._diagnostic_line_map.get(line)
        if diags:
            if line == self._last_tooltip_line and self._diagnostic_tooltip.is_showing():
                return
            self._last_tooltip_line = line
            parts: list[str] = []
            for d in diags:
                prefix = "\u26a0" if d.severity == Severity.WARNING else "\u2716"
                parts.append(f"{prefix} {d.message}")
            self._diagnostic_tooltip.show_diagnostic(
                event.globalPosition().toPoint(),
                "\n".join(parts),
            )
        else:
            self._diagnostic_tooltip.hide_diagnostic()
            self._last_tooltip_line = -1

    def leaveEvent(self, event):
        self._diagnostic_tooltip.hide_diagnostic()
        self._last_tooltip_line = -1
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # Occurrence highlighting
    # ------------------------------------------------------------------

    def _update_occurrence_highlights(self):
        cursor = self.textCursor()
        tc = QtGui.QTextCursor(cursor)
        tc.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        word = tc.selectedText()

        if not word or word.isspace() or len(word) <= 1:
            if self._occurrence_selections:
                self._occurrence_selections.clear()
                self._last_occurrence_word = ""
                self._update_extra_selections()
            return

        if word == self._last_occurrence_word:
            return

        self._last_occurrence_word = word

        doc = self.document()
        cursor_pos = cursor.position()
        highlight_color = self._theme.qcolor("occurrence_highlight")
        find_flags = (
            QtGui.QTextDocument.FindFlag.FindWholeWords
            | QtGui.QTextDocument.FindFlag.FindCaseSensitively
        )

        selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        search_cursor = doc.find(word, 0, find_flags)
        while not search_cursor.isNull():
            match_start = search_cursor.selectionStart()
            match_end = search_cursor.selectionEnd()
            if not (match_start <= cursor_pos <= match_end):
                sel = QtWidgets.QTextEdit.ExtraSelection()
                sel.format.setBackground(highlight_color)
                sel.cursor = search_cursor
                selections.append(sel)
            search_cursor = doc.find(word, search_cursor, find_flags)

        self._occurrence_selections = selections
        self._update_extra_selections()

    # ------------------------------------------------------------------
    # Bracket matching
    # ------------------------------------------------------------------

    def _get_bracket_selections(self) -> list[QtWidgets.QTextEdit.ExtraSelection]:
        pos = self.textCursor().position()
        rev = self.document().revision()
        cache_key = (pos, rev)
        if self._bracket_cache_key == cache_key:
            return self._bracket_cache_value

        doc = self.document()

        bracket_char = None
        bracket_pos = -1

        if pos < doc.characterCount():
            char_at = doc.characterAt(pos)
            if char_at in _BRACKET_PAIRS:
                bracket_char = char_at
                bracket_pos = pos

        if bracket_char is None and pos > 0:
            char_before = doc.characterAt(pos - 1)
            if char_before in _BRACKET_PAIRS:
                bracket_char = char_before
                bracket_pos = pos - 1

        if bracket_char is None:
            self._bracket_cache_key = cache_key
            self._bracket_cache_value = []
            return []

        match_pos = self._find_matching_bracket(bracket_pos, bracket_char)

        if match_pos >= 0:
            bg_color = self._theme.qcolor("bracket_match")
        else:
            bg_color = self._theme.qcolor("bracket_mismatch")

        sel_a = QtWidgets.QTextEdit.ExtraSelection()
        sel_a.format.setBackground(bg_color)
        c = QtGui.QTextCursor(doc)
        c.setPosition(bracket_pos)
        c.movePosition(
            QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        sel_a.cursor = c

        selections = [sel_a]

        if match_pos >= 0:
            sel_b = QtWidgets.QTextEdit.ExtraSelection()
            sel_b.format.setBackground(bg_color)
            c2 = QtGui.QTextCursor(doc)
            c2.setPosition(match_pos)
            c2.movePosition(
                QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor
            )
            sel_b.cursor = c2
            selections.append(sel_b)

        self._bracket_cache_key = cache_key
        self._bracket_cache_value = selections
        return selections

    def _find_matching_bracket(self, position: int, char: str) -> int:
        doc = self.document()
        match_char = _BRACKET_PAIRS[char]
        forward = char in _OPEN_BRACKETS
        depth = 0
        length = doc.characterCount()

        if forward:
            i = position + 1
            while i < min(length, position + _MAX_BRACKET_SCAN):
                if self._is_in_comment_or_string(i):
                    i += 1
                    continue
                c = doc.characterAt(i)
                if c == char:
                    depth += 1
                elif c == match_char:
                    if depth == 0:
                        return i
                    depth -= 1
                i += 1
        else:
            i = position - 1
            while i >= max(0, position - _MAX_BRACKET_SCAN):
                if self._is_in_comment_or_string(i):
                    i -= 1
                    continue
                c = doc.characterAt(i)
                if c == char:
                    depth += 1
                elif c == match_char:
                    if depth == 0:
                        return i
                    depth -= 1
                i -= 1

        return -1

    def goto_matching_bracket(self) -> bool:
        """Jump cursor to the matching bracket. Return True if a match was found."""
        cursor = self.textCursor()
        pos = cursor.position()
        doc = self.document()

        bracket_char = None
        bracket_pos = -1

        if pos < doc.characterCount():
            char_at = doc.characterAt(pos)
            if char_at in _BRACKET_PAIRS:
                bracket_char = char_at
                bracket_pos = pos

        if bracket_char is None and pos > 0:
            char_before = doc.characterAt(pos - 1)
            if char_before in _BRACKET_PAIRS:
                bracket_char = char_before
                bracket_pos = pos - 1

        if bracket_char is None:
            return False

        match_pos = self._find_matching_bracket(bracket_pos, bracket_char)
        if match_pos < 0:
            return False

        cursor.setPosition(match_pos)
        self.setTextCursor(cursor)
        self.centerCursor()
        return True

    def _is_in_comment_or_string(self, position: int) -> bool:
        block = self.document().findBlock(position)
        if not block.isValid():
            return False

        col = position - block.position()
        text = block.text()

        prev = block.previous()
        in_block_comment = prev.isValid() and prev.userState() == _STATE_IN_MULTILINE_COMMENT
        in_string = False

        i = 0
        while i < col and i < len(text):
            ch = text[i]

            if in_block_comment:
                if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if in_string:
                if ch == '"':
                    num_backslashes = 0
                    j = i - 1
                    while j >= 0 and text[j] == "\\":
                        num_backslashes += 1
                        j -= 1
                    if num_backslashes % 2 == 0:
                        in_string = False
                i += 1
                continue

            if ch == "/" and i + 1 < len(text):
                if text[i + 1] == "/":
                    return True
                if text[i + 1] == "*":
                    in_block_comment = True
                    i += 2
                    continue

            if ch == '"':
                in_string = True

            i += 1

        return in_block_comment or in_string

    # ------------------------------------------------------------------
    # Code folding
    # ------------------------------------------------------------------

    def _on_contents_changed(self):
        """Fold invalidation, occurrence reset, and workspace symbol
        extraction restart."""
        if self._in_fold_update:
            return

        self._fold_regions_dirty = True
        if self._folded_blocks:
            self._revalidate_folds()

        self._last_occurrence_word = ""

        if self._extraction_timer is not None:
            self._extraction_timer.start()

    def _revalidate_folds(self):
        """Check fold validity and re-apply surviving folds."""
        self._in_fold_update = True
        try:
            doc = self.document()
            still_valid = {b.blockNumber(): b for b in self._folded_blocks.values() if b.isValid()}
            if not still_valid:
                self._unfold_all_blocks()
                return

            self._ensure_fold_regions()

            blocks_to_keep = {bn: b for bn, b in still_valid.items() if bn in self._fold_regions}

            if not blocks_to_keep:
                self._unfold_all_blocks()
                return

            block = doc.begin()
            while block.isValid():
                if not block.isVisible():
                    block.setVisible(True)
                block = block.next()

            for fold_block in blocks_to_keep.values():
                bn = fold_block.blockNumber()
                end_bn = self._fold_regions[bn]
                inner = doc.findBlockByNumber(bn + 1)
                while inner.isValid() and inner.blockNumber() <= end_bn:
                    inner.setVisible(False)
                    inner = inner.next()

            self._folded_blocks = blocks_to_keep
            doc.markContentsDirty(0, doc.characterCount())
            self.viewport().update()
            self._line_number_area.update()
        finally:
            self._in_fold_update = False

    def _unfold_all_blocks(self):
        """Make all blocks visible and clear fold state."""
        doc = self.document()
        block = doc.begin()
        any_hidden = False
        while block.isValid():
            if not block.isVisible():
                block.setVisible(True)
                any_hidden = True
            block = block.next()
        self._folded_blocks.clear()
        if any_hidden:
            doc.markContentsDirty(0, doc.characterCount())
            self.viewport().update()
            self._line_number_area.update()

    def _ensure_fold_regions(self):
        if not self._fold_regions_dirty:
            return
        self._fold_regions.clear()
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            text = block.text().rstrip()
            if text.endswith("{"):
                brace_pos = block.position() + len(text) - 1
                if not self._is_in_comment_or_string(brace_pos):
                    end_block_num = self._find_matching_brace_block(block)
                    if end_block_num is not None and end_block_num > block.blockNumber():
                        self._fold_regions[block.blockNumber()] = end_block_num
            block = block.next()
        self._fold_regions_dirty = False

    def _find_matching_brace_block(
        self,
        start_block: QtGui.QTextBlock,
    ) -> int | None:
        depth = 0
        block = start_block
        prev_block = block.previous()
        in_block_comment = (
            prev_block.isValid() and prev_block.userState() == _STATE_IN_MULTILINE_COMMENT
        )
        in_string = False

        while block.isValid():
            text = block.text()
            i = 0
            while i < len(text):
                ch = text[i]

                if in_block_comment:
                    if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue

                if in_string:
                    if ch == '"':
                        num_backslashes = 0
                        j = i - 1
                        while j >= 0 and text[j] == "\\":
                            num_backslashes += 1
                            j -= 1
                        if num_backslashes % 2 == 0:
                            in_string = False
                    i += 1
                    continue

                if ch == "/" and i + 1 < len(text):
                    if text[i + 1] == "/":
                        break
                    if text[i + 1] == "*":
                        in_block_comment = True
                        i += 2
                        continue

                if ch == '"':
                    in_string = True
                    i += 1
                    continue

                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return block.blockNumber()

                i += 1

            block = block.next()
            in_string = False
        return None

    def _toggle_fold(self, block_number: int):
        self._in_fold_update = True
        try:
            self._ensure_fold_regions()
            if block_number not in self._fold_regions:
                return

            end_block_number = self._fold_regions[block_number]
            doc = self.document()
            block = doc.findBlockByNumber(block_number)

            if block_number in self._folded_blocks:
                self._folded_blocks.pop(block_number, None)
                inner = doc.findBlockByNumber(block_number + 1)
                while inner.isValid() and inner.blockNumber() <= end_block_number:
                    inner.setVisible(True)
                    inner = inner.next()
            else:
                self._folded_blocks[block_number] = block
                inner = doc.findBlockByNumber(block_number + 1)
                while inner.isValid() and inner.blockNumber() <= end_block_number:
                    inner.setVisible(False)
                    inner = inner.next()

            doc.markContentsDirty(0, doc.characterCount())
            self._update_line_number_area_width()
            self.viewport().update()
            self._line_number_area.update()
        finally:
            self._in_fold_update = False

    def fold_area_mouse_press(self, event: QtGui.QMouseEvent):
        x = event.pos().x()
        fold_zone_start = self.line_number_area_width() - _FOLD_MARGIN_WIDTH
        if x < fold_zone_start:
            return

        block_num = self._block_number_at_y(event.pos().y())
        if block_num < 0:
            return

        self._ensure_fold_regions()
        if block_num in self._fold_regions:
            self._toggle_fold(block_num)

    def fold_area_mouse_move(self, event: QtGui.QMouseEvent):
        x = event.pos().x()
        fold_zone_start = self.line_number_area_width() - _FOLD_MARGIN_WIDTH

        if x < fold_zone_start:
            if self._fold_hover_block >= 0:
                self._fold_hover_block = -1
                self._line_number_area.update()
            self._line_number_area.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            return

        block_num = self._block_number_at_y(event.pos().y())
        self._ensure_fold_regions()

        if block_num >= 0 and block_num in self._fold_regions:
            if self._fold_hover_block != block_num:
                self._fold_hover_block = block_num
                self._line_number_area.update()
            self._line_number_area.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        else:
            if self._fold_hover_block >= 0:
                self._fold_hover_block = -1
                self._line_number_area.update()
            self._line_number_area.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def fold_area_mouse_leave(self):
        if self._fold_hover_block >= 0:
            self._fold_hover_block = -1
            self._line_number_area.update()

    def _block_number_at_y(self, y: int) -> int:
        block = self.firstVisibleBlock()
        while block.isValid():
            geom = self.blockBoundingGeometry(block).translated(
                self.contentOffset(),
            )
            if geom.top() <= y <= geom.bottom():
                return block.blockNumber()
            if geom.top() > y:
                break
            block = block.next()
        return -1

    # ------------------------------------------------------------------
    # Indent guides
    # ------------------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)
        self._paint_indent_guides(event)
        self._paint_fold_indicators(event)

    def _paint_indent_guides(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self.viewport())

        guide_color = self._theme.qcolor("indent_guide")
        active_color = self._theme.qcolor("indent_guide_active")
        pen_normal = QtGui.QPen(guide_color, 1, QtCore.Qt.PenStyle.SolidLine)
        pen_active = QtGui.QPen(active_color, 1, QtCore.Qt.PenStyle.SolidLine)

        char_width = self.fontMetrics().horizontalAdvance(" ")
        indent_width = char_width * self._tab_width

        cursor_block = self.textCursor().block()
        cursor_indent = len(self._leading_whitespace(cursor_block.text())) // max(
            1, self._tab_width
        )

        block = self.firstVisibleBlock()
        while block.isValid():
            geom = self.blockBoundingGeometry(block).translated(self.contentOffset())
            if geom.top() > event.rect().bottom():
                break
            if block.isVisible() and geom.bottom() >= event.rect().top():
                text = block.text()
                if text.strip():
                    indent_level = len(self._leading_whitespace(text)) // max(1, self._tab_width)
                    for level in range(1, indent_level + 1):
                        x = round(level * indent_width + self.contentOffset().x())
                        painter.setPen(pen_active if level == cursor_indent else pen_normal)
                        painter.drawLine(x, round(geom.top()), x, round(geom.bottom()))
            block = block.next()

        painter.end()

    def _paint_fold_indicators(self, event: QtGui.QPaintEvent):
        if not self._folded_blocks:
            return

        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self.font())

        indicator_text = " ... "
        fm = self.fontMetrics()
        indicator_width = fm.horizontalAdvance(indicator_text)

        bg_color = QtGui.QColor(self._theme.fold_line)
        bg_color.setAlpha(200)
        text_color = QtGui.QColor(self._theme.fold_indicator_text)

        block = self.firstVisibleBlock()
        while block.isValid():
            geo = self.blockBoundingGeometry(block).translated(self.contentOffset())
            if geo.top() > event.rect().bottom():
                break
            if block.isVisible() and block.blockNumber() in self._folded_blocks:
                x = fm.horizontalAdvance(block.text()) + self.contentOffset().x()
                rect = QtCore.QRectF(x, geo.top(), indicator_width, geo.height())
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(bg_color)
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(text_color)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, indicator_text)
            block = block.next()

        painter.end()

    # ------------------------------------------------------------------
    # Auto-indent and key handling
    # ------------------------------------------------------------------

    def event(self, e: QtCore.QEvent) -> bool:
        if (
            e.type() == QtCore.QEvent.Type.ShortcutOverride
            and self._vim_handler.enabled
            and e.key() == QtCore.Qt.Key.Key_Escape
        ):
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self._completion_popup.is_visible():
            key = event.key()
            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Tab):
                self._completion_popup.accept_current()
                return
            if key == QtCore.Qt.Key.Key_Escape:
                self._completion_popup.dismiss()
                return
            if key == QtCore.Qt.Key.Key_Down:
                self._completion_popup.select_next()
                return
            if key == QtCore.Qt.Key.Key_Up:
                self._completion_popup.select_previous()
                return
            if key == QtCore.Qt.Key.Key_PageDown:
                self._completion_popup.select_page_down()
                return
            if key == QtCore.Qt.Key.Key_PageUp:
                self._completion_popup.select_page_up()
                return

        if self._vim_handler.enabled and self._vim_handler.mode != VimMode.INSERT:
            if self._vim_handler.handle_key(event):
                return

        modifiers = event.modifiers()

        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._handle_auto_indent()
            return

        if event.key() == QtCore.Qt.Key.Key_Backspace and self._handle_auto_close_backspace():
            self._update_completion()
            return

        text = event.text()

        if text and text in _CLOSE_CHARS and self._handle_overtype(text):
            if text == "}":
                self._handle_closing_brace()
            self._update_completion()
            return

        if event.key() == QtCore.Qt.Key.Key_BraceRight:
            super().keyPressEvent(event)
            self._handle_closing_brace()
            self._update_completion()
            return

        if text and text in _AUTO_CLOSE_PAIRS and self._handle_auto_close(text):
            self._update_completion()
            return

        if event.key() == QtCore.Qt.Key.Key_Tab and not modifiers:
            if self._snippet_session is not None and self._snippet_session.is_active():
                if not self._snippet_session.next_tabstop():
                    self._clear_snippet_session()
                self._update_extra_selections()
                return
            if self._try_snippet_expand():
                return
            self._handle_tab()
            return

        if event.key() == QtCore.Qt.Key.Key_Backtab:
            if self._snippet_session is not None and self._snippet_session.is_active():
                self._snippet_session.previous_tabstop()
                self._update_extra_selections()
                return
            self._handle_shift_tab()
            return

        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self._snippet_session is not None and self._snippet_session.is_active():
                self._clear_snippet_session()
                if self._vim_handler.enabled and self._vim_handler.mode == VimMode.INSERT:
                    self._vim_handler.escape_from_insert()
                return
            self._signature_widget.dismiss()
            if self._vim_handler.enabled and self._vim_handler.mode == VimMode.INSERT:
                self._vim_handler.escape_from_insert()
                return
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)

        if text == ".":
            self._update_completion()
        elif text == "(":
            self._completion_popup.dismiss()
            self._update_signature_help()
        elif text == ")":
            self._signature_widget.dismiss()
            self._update_completion()
        elif text == ",":
            self._update_signature_help()
        elif text:
            self._update_completion()
            if self._signature_widget.is_visible():
                self._update_signature_help()

    def _handle_auto_indent(self):
        cursor = self.textCursor()
        line_text = cursor.block().text()
        indent = self._leading_whitespace(line_text)
        col = cursor.position() - cursor.block().position()
        text_before_cursor = line_text[:col]

        stripped = self._strip_line_comments(text_before_cursor.rstrip())

        char_after = ""
        if cursor.position() < self.document().characterCount():
            char_after = self.document().characterAt(cursor.position())

        if stripped.endswith("{") and char_after == "}":
            inner_indent = indent + self._indent_string()
            cursor.insertText("\n" + inner_indent + "\n" + indent)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfLine)
            self.setTextCursor(cursor)
            return

        if stripped.endswith("{"):
            indent += self._indent_string()

        cursor.insertText("\n" + indent)
        self.setTextCursor(cursor)

    def _handle_closing_brace(self):
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()

        if line_text.strip() != "}":
            return

        brace_col = line_text.index("}")
        brace_pos = block.position() + brace_col

        match_pos = self._find_matching_bracket(brace_pos, "}")

        if match_pos < 0:
            current_indent = self._leading_whitespace(line_text)
            indent_str = self._indent_string()
            if len(current_indent) >= len(indent_str):
                new_indent = current_indent[: len(current_indent) - len(indent_str)]
            else:
                new_indent = ""
        else:
            match_block = self.document().findBlock(match_pos)
            new_indent = self._leading_whitespace(match_block.text())

        current_indent = self._leading_whitespace(line_text)
        if new_indent == current_indent:
            return

        cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.EndOfBlock, QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(new_indent + "}")
        self.setTextCursor(cursor)

    def _handle_tab(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._indent_selection(cursor)
        else:
            cursor.insertText(self._indent_string())

    def _handle_shift_tab(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._unindent_selection(cursor)
        else:
            self._unindent_current_line(cursor)

    def _indent_selection(self, cursor: QtGui.QTextCursor):
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        indent_str = self._indent_string()

        cursor.beginEditBlock()
        doc = self.document()
        block = doc.findBlock(start)
        while block.isValid() and block.position() <= end:
            c = QtGui.QTextCursor(block)
            c.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            c.insertText(indent_str)
            end += len(indent_str)
            block = block.next()
        cursor.endEditBlock()

    def _unindent_selection(self, cursor: QtGui.QTextCursor):
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        cursor.beginEditBlock()
        doc = self.document()
        block = doc.findBlock(start)
        while block.isValid() and block.position() <= end:
            removed = self._remove_one_indent_level(block)
            end -= removed
            block = block.next()
        cursor.endEditBlock()

    def _unindent_current_line(self, cursor: QtGui.QTextCursor):
        cursor.beginEditBlock()
        self._remove_one_indent_level(cursor.block())
        cursor.endEditBlock()

    def _remove_one_indent_level(self, block: QtGui.QTextBlock) -> int:
        text = block.text()
        if not text or not text[0].isspace():
            return 0

        remove_count = 0
        if self._use_spaces:
            for i in range(min(self._tab_width, len(text))):
                if text[i] == " ":
                    remove_count += 1
                else:
                    break
        else:
            if text[0] == "\t":
                remove_count = 1

        if remove_count > 0:
            c = QtGui.QTextCursor(block)
            c.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            for _ in range(remove_count):
                c.deleteChar()

        return remove_count

    # ------------------------------------------------------------------
    # Auto-close pairs
    # ------------------------------------------------------------------

    def _should_auto_close_quote(self, quote_char: str) -> bool:
        cursor = self.textCursor()
        pos = cursor.position()
        if pos == 0 or pos == cursor.block().position():
            return True
        char_before = self.document().characterAt(pos - 1)
        return char_before in _QUOTE_AUTO_CLOSE_CONTEXT or char_before == ""

    def _handle_auto_close(self, char: str) -> bool:
        is_quote = char in ('"', "'")
        if is_quote and not self._should_auto_close_quote(char):
            return False

        closing = _AUTO_CLOSE_PAIRS[char]
        cursor = self.textCursor()

        if cursor.hasSelection():
            selected = cursor.selectedText()
            cursor.beginEditBlock()
            cursor.insertText(char + selected + closing)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return True

        cursor.beginEditBlock()
        cursor.insertText(char + closing)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _handle_overtype(self, char: str) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        if pos >= self.document().characterCount():
            return False
        char_at = self.document().characterAt(pos)
        if char_at != char:
            return False
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
        self.setTextCursor(cursor)
        return True

    def _handle_auto_close_backspace(self) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        if pos == 0 or pos >= self.document().characterCount():
            return False
        char_before = self.document().characterAt(pos - 1)
        char_after = self.document().characterAt(pos)
        if char_before in _AUTO_CLOSE_PAIRS and _AUTO_CLOSE_PAIRS[char_before] == char_after:
            cursor.beginEditBlock()
            cursor.deleteChar()
            cursor.deletePreviousChar()
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return True
        return False

    # ------------------------------------------------------------------
    # Toggle comment
    # ------------------------------------------------------------------

    def toggle_comment(self):
        cursor = self.textCursor()
        doc = self.document()

        if cursor.hasSelection():
            start_block = doc.findBlock(cursor.selectionStart())
            end_block = doc.findBlock(cursor.selectionEnd())
            if cursor.selectionEnd() == end_block.position() and end_block != start_block:
                end_block = end_block.previous()
        else:
            start_block = cursor.block()
            end_block = start_block

        blocks = []
        block = start_block
        while block.isValid():
            blocks.append(block)
            if block == end_block:
                break
            block = block.next()

        non_empty_blocks = [b for b in blocks if b.text().strip()]
        if not non_empty_blocks:
            return

        all_commented = all(b.text().lstrip().startswith("//") for b in non_empty_blocks)

        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()

        cursor.beginEditBlock()

        if all_commented:
            for block in blocks:
                text = block.text()
                if not text.strip():
                    continue
                indent = self._leading_whitespace(text)
                rest = text[len(indent) :]
                if rest.startswith("// "):
                    new_text = indent + rest[3:]
                elif rest.startswith("//"):
                    new_text = indent + rest[2:]
                else:
                    continue
                diff = len(text) - len(new_text)
                c = QtGui.QTextCursor(block)
                c.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
                c.movePosition(
                    QtGui.QTextCursor.MoveOperation.EndOfBlock,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                )
                c.insertText(new_text)
                if block.position() <= sel_start:
                    sel_start = max(block.position(), sel_start - diff)
                if block.position() <= sel_end:
                    sel_end = max(block.position(), sel_end - diff)
        else:
            min_indent = min(len(self._leading_whitespace(b.text())) for b in non_empty_blocks)
            prefix = "// "
            for block in blocks:
                text = block.text()
                if not text.strip():
                    continue
                c = QtGui.QTextCursor(block)
                c.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
                c.movePosition(QtGui.QTextCursor.MoveOperation.Right, n=min_indent)
                c.insertText(prefix)
                if block.position() <= sel_start:
                    sel_start += len(prefix)
                if block.position() < sel_end:
                    sel_end += len(prefix)

        cursor.endEditBlock()

        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Duplicate line
    # ------------------------------------------------------------------

    def duplicate_line(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()

        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            doc = self.document()

            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)
            if end == end_block.position() and end_block != start_block:
                end_block = end_block.previous()

            first_pos = start_block.position()
            last_pos = end_block.position() + end_block.length() - 1
            cursor.setPosition(first_pos)
            cursor.setPosition(last_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()

            cursor.setPosition(last_pos)
            cursor.insertText("\n" + text.replace("\u2029", "\n"))
        else:
            block = cursor.block()
            text = block.text()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n" + text)

        cursor.endEditBlock()
        self.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Move line up/down
    # ------------------------------------------------------------------

    def move_line_up(self):
        cursor = self.textCursor()
        doc = self.document()

        if cursor.hasSelection():
            start_block = doc.findBlock(cursor.selectionStart())
            end_block = doc.findBlock(cursor.selectionEnd())
            if cursor.selectionEnd() == end_block.position() and end_block != start_block:
                end_block = end_block.previous()
        else:
            start_block = cursor.block()
            end_block = start_block

        if start_block.blockNumber() == 0:
            return

        prev_block = start_block.previous()

        cursor.beginEditBlock()

        first_pos = start_block.position()
        last_pos = end_block.position() + end_block.length() - 1

        c = QtGui.QTextCursor(doc)
        c.setPosition(first_pos)
        c.setPosition(last_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
        selected_text = c.selectedText()

        prev_text = prev_block.text()

        c.setPosition(prev_block.position())
        c.setPosition(last_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
        c.insertText(selected_text + "\n" + prev_text)

        new_start = prev_block.position()
        new_cursor = self.textCursor()
        new_cursor.setPosition(new_start)
        new_end = new_start + len(selected_text.replace("\u2029", "\n"))
        new_cursor.setPosition(new_end, QtGui.QTextCursor.MoveMode.KeepAnchor)

        cursor.endEditBlock()
        self.setTextCursor(new_cursor)

    def move_line_down(self):
        cursor = self.textCursor()
        doc = self.document()

        if cursor.hasSelection():
            start_block = doc.findBlock(cursor.selectionStart())
            end_block = doc.findBlock(cursor.selectionEnd())
            if cursor.selectionEnd() == end_block.position() and end_block != start_block:
                end_block = end_block.previous()
        else:
            start_block = cursor.block()
            end_block = start_block

        next_block = end_block.next()
        if not next_block.isValid():
            return

        cursor.beginEditBlock()

        first_pos = start_block.position()
        last_pos = end_block.position() + end_block.length() - 1

        c = QtGui.QTextCursor(doc)
        c.setPosition(first_pos)
        c.setPosition(last_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
        selected_text = c.selectedText()

        next_text = next_block.text()
        next_end = next_block.position() + next_block.length() - 1

        c.setPosition(first_pos)
        c.setPosition(next_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        c.insertText(next_text + "\n" + selected_text)

        new_start = first_pos + len(next_text) + 1
        new_cursor = self.textCursor()
        new_cursor.setPosition(new_start)
        new_end = new_start + len(selected_text.replace("\u2029", "\n"))
        new_cursor.setPosition(new_end, QtGui.QTextCursor.MoveMode.KeepAnchor)

        cursor.endEditBlock()
        self.setTextCursor(new_cursor)

    # ------------------------------------------------------------------
    # Workspace symbol extraction
    # ------------------------------------------------------------------

    def set_user_vars(self, user_vars):
        """Update external variable definitions and re-extract symbols."""
        self._user_vars = user_vars
        if user_vars:
            self._external_completions, self._external_var_types = build_external_var_completions(
                user_vars
            )
        else:
            self._external_completions = ()
            self._external_var_types = {}
        self._extract_workspace_symbols()

    def _extract_workspace_symbols(self):
        ws = extract_workspace_symbols(self.toPlainText())
        if self._external_completions:
            ws = WorkspaceSymbols(
                completions=ws.completions + self._external_completions,
                signatures=ws.signatures,
                variable_types={**self._external_var_types, **ws.variable_types},
                function_scopes=ws.function_scopes,
                scoped_completions=ws.scoped_completions,
                scoped_variable_types=ws.scoped_variable_types,
            )
        self._workspace_symbols = ws

    # ------------------------------------------------------------------
    # Completion and signature help
    # ------------------------------------------------------------------

    def _update_completion(self):
        cursor = self.textCursor()
        pos = cursor.position()

        in_comment_or_string = False
        if pos > 0:
            in_comment_or_string = self._is_in_comment_or_string(pos - 1)

        block = cursor.block()
        line_text = block.text()
        col = pos - block.position()
        cursor_line = block.blockNumber()

        ws = self._workspace_symbols

        scoped_var_types = None
        if ws is not None and ws.function_scopes:
            scope = find_enclosing_scope(ws.function_scopes, cursor_line)
            if scope is not None and scope.name in ws.scoped_variable_types:
                scoped_var_types = ws.scoped_variable_types[scope.name]

        context, qualifier, prefix = analyze_context(
            line_text,
            col,
            in_comment_or_string,
            user_variable_types=ws.variable_types if ws else None,
            scoped_variable_types=scoped_var_types,
        )
        self._completion_context = (context, qualifier, prefix)

        if context == CompletionContext.GLOBAL and len(prefix) < 2:
            self._completion_popup.dismiss()
            return

        if context == CompletionContext.NONE:
            self._completion_popup.dismiss()
            return

        precomputed = (context, qualifier, prefix)
        items = get_completions(
            line_text,
            col,
            in_comment_or_string,
            workspace=ws,
            cursor_line=cursor_line,
            _precomputed=precomputed,
        )

        if not items:
            self._completion_popup.dismiss()
            return

        cursor_rect = self.cursorRect()
        self._completion_popup.show_items(items, cursor_rect)

    def _insert_completion(self, completion_item: CompletionItem):
        if self._completion_context is None:
            return

        context, qualifier, prefix = self._completion_context

        if completion_item.kind == CompletionKind.SNIPPET:
            from .snippets import get_snippet_by_trigger, parse_snippet_body

            snippet = get_snippet_by_trigger(completion_item.label)
            if snippet is not None:
                cursor = self.textCursor()
                block = cursor.block()
                indent = self._leading_whitespace(block.text())
                parsed = parse_snippet_body(
                    snippet.body,
                    indent,
                    self._indent_string(),
                )

                replace_len = len(prefix)
                cursor.beginEditBlock()
                if replace_len > 0:
                    cursor.movePosition(
                        QtGui.QTextCursor.MoveOperation.Left,
                        QtGui.QTextCursor.MoveMode.KeepAnchor,
                        replace_len,
                    )
                insert_pos = cursor.selectionStart()
                cursor.removeSelectedText()
                cursor.insertText(parsed.text)
                cursor.endEditBlock()

                self._snippet_session = SnippetSession(self, insert_pos, parsed)
                self._snippet_session.select_current()
                self._update_extra_selections()
                return

        cursor = self.textCursor()

        replace_len = len(prefix)

        if replace_len > 0:
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.Left,
                QtGui.QTextCursor.MoveMode.KeepAnchor,
                replace_len,
            )

        cursor.insertText(completion_item.insert_text)
        self.setTextCursor(cursor)

        if completion_item.insert_text.endswith("("):
            self._update_signature_help()

    def _update_signature_help(self):
        cursor = self.textCursor()
        pos = cursor.position()
        full_text = self.toPlainText()

        func_name, active_param = find_active_signature(full_text, pos)
        if func_name is None:
            self._signature_widget.dismiss()
            return

        workspace = self._workspace_symbols
        info = get_signature_info(
            func_name,
            user_signatures=workspace.signatures if workspace else None,
        )
        if info is None:
            self._signature_widget.dismiss()
            return

        cursor_rect = self.cursorRect()

        if self._signature_widget.is_visible():
            self._signature_widget.update_active_param(active_param)
        else:
            self._signature_widget.show_signature(info, active_param, cursor_rect)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _indent_string(self) -> str:
        if self._use_spaces:
            return " " * self._tab_width
        return "\t"

    @staticmethod
    def _leading_whitespace(text: str) -> str:
        stripped = text.lstrip()
        return text[: len(text) - len(stripped)]

    @staticmethod
    def _strip_line_comments(text: str) -> str:
        """Strip // and /* */ comments from a single line for indent analysis."""
        result = []
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                result.append(ch)
                if ch == '"':
                    num_backslashes = 0
                    j = i - 1
                    while j >= 0 and text[j] == "\\":
                        num_backslashes += 1
                        j -= 1
                    if num_backslashes % 2 == 0:
                        in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
                result.append(ch)
                i += 1
                continue
            if ch == "/" and i + 1 < len(text):
                if text[i + 1] == "/":
                    break
                if text[i + 1] == "*":
                    end = text.find("*/", i + 2)
                    if end >= 0:
                        i = end + 2
                        continue
                    else:
                        break
            result.append(ch)
            i += 1
        return "".join(result).rstrip()

    # ------------------------------------------------------------------
    # Snippet expansion
    # ------------------------------------------------------------------

    def _try_snippet_expand(self) -> bool:
        from .snippets import get_snippet_by_trigger, parse_snippet_body

        cursor = self.textCursor()
        block = cursor.block()
        text = block.text()
        col = cursor.positionInBlock()

        end = col
        start = end
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        if start == end:
            return False

        word = text[start:end]
        snippet = get_snippet_by_trigger(word)
        if snippet is None:
            return False

        indent = self._leading_whitespace(text)
        parsed = parse_snippet_body(snippet.body, indent, self._indent_string())

        cursor.beginEditBlock()
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        insert_pos = cursor.selectionStart()
        cursor.removeSelectedText()
        cursor.insertText(parsed.text)
        cursor.endEditBlock()

        self._snippet_session = SnippetSession(self, insert_pos, parsed)
        self._snippet_session.select_current()
        self._update_extra_selections()
        return True

    def _clear_snippet_session(self):
        self._snippet_session = None
        self._update_extra_selections()

    def _on_contents_change_snippet(self, position, chars_removed, chars_added):
        if self._snippet_session is not None and self._snippet_session.is_active():
            self._snippet_session.on_contents_change(
                position,
                chars_removed,
                chars_added,
            )
