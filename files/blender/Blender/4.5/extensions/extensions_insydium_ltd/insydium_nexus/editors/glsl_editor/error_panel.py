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

"""Error / Problems panel for the GLSL Script Editor.

Displays a scrollable list of GLSL validation diagnostics.  Clicking a
row emits ``line_clicked`` with the 1-based line number so the parent
editor can navigate to the relevant source location.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtWidgets  # noqa: E402
except ImportError:
    pass

from .theme import GLSLEditorTheme  # noqa: E402
from .validator import Diagnostic, Severity  # noqa: E402


class ErrorPanel(QtWidgets.QWidget):
    """Scrollable list of GLSL compiler diagnostics."""

    line_clicked = QtCore.pyqtSignal(int)
    close_requested = QtCore.pyqtSignal()

    def __init__(self, theme: GLSLEditorTheme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._diagnostics: list[Diagnostic] = []
        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setObjectName("errorPanel")
        self.setMinimumHeight(80)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Header row ---
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(8, 4, 4, 4)

        label = QtWidgets.QLabel("PROBLEMS")
        label.setStyleSheet(
            f"font-size: 11px; font-weight: bold; "
            f"color: {self._theme.line_number_fg}; background: transparent;"
        )
        header.addWidget(label)
        header.addStretch()

        btn_close = QtWidgets.QPushButton("\u2715")
        btn_close.setFixedSize(20, 20)
        btn_close.setFlat(True)
        btn_close.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"color: {self._theme.line_number_fg}; background: transparent; border: none;"
        )
        btn_close.clicked.connect(self.close_requested.emit)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # -- Separator ---
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {self._theme.toolbar_separator};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # -- Stacked content: empty state / list ---
        self._stack = QtWidgets.QStackedWidget()

        self._lbl_empty = QtWidgets.QLabel("No problems have been detected.")
        self._lbl_empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet(
            f"color: {self._theme.line_number_fg}; font-size: 12px; background: transparent;"
        )
        self._stack.addWidget(self._lbl_empty)

        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._list_widget.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self._list_widget.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._list_widget.setMouseTracking(True)
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        self._stack.addWidget(self._list_widget)

        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack)

    # ------------------------------------------------------------------
    # Row widget construction
    # ------------------------------------------------------------------

    def _create_row_widget(self, diag: Diagnostic) -> QtWidgets.QWidget:
        """Build a styled row widget for a single diagnostic."""
        if diag.severity == Severity.ERROR:
            dot_color = self._theme.error_underline
        else:
            dot_color = self._theme.warning_underline

        row = QtWidgets.QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(8, 0, 8, 0)
        row_layout.setSpacing(6)

        # Severity dot
        lbl_dot = QtWidgets.QLabel("\u25cf")
        lbl_dot.setFixedWidth(14)
        lbl_dot.setStyleSheet(f"color: {dot_color}; font-size: 10px; background: transparent;")
        lbl_dot.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_dot.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row_layout.addWidget(lbl_dot)

        # Location
        if diag.column > 0:
            loc_text = f"Ln {diag.line}, Col {diag.column}"
        else:
            loc_text = f"Ln {diag.line}"
        lbl_loc = QtWidgets.QLabel(loc_text)
        lbl_loc.setMinimumWidth(80)
        lbl_loc.setStyleSheet(
            f"color: {self._theme.error_panel_location_fg}; font-size: 12px; "
            f"background: transparent;"
        )
        lbl_loc.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row_layout.addWidget(lbl_loc)

        # Message
        lbl_msg = QtWidgets.QLabel(diag.message)
        lbl_msg.setStyleSheet(
            f"color: {self._theme.text}; font-size: 12px; background: transparent;"
        )
        lbl_msg.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row_layout.addWidget(lbl_msg, stretch=1)

        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_diagnostics(self, diagnostics: list[Diagnostic]):
        """Replace the displayed diagnostics list."""
        self._diagnostics = list(diagnostics)
        self._list_widget.clear()

        if not self._diagnostics:
            self._stack.setCurrentIndex(0)
            return

        self._stack.setCurrentIndex(1)
        for diag in self._diagnostics:
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(0, 26))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, diag.line)
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, self._create_row_widget(diag))

    def toggle(self):
        """Toggle panel visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def has_diagnostics(self) -> bool:
        """Return whether any diagnostics are present."""
        return bool(self._diagnostics)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item):
        line = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.line_clicked.emit(line)
