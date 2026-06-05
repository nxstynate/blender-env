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

"""Vim command-line overlay for the GLSL Script Editor."""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtWidgets  # noqa: E402
except ImportError:
    pass


class VimCommandOverlay(QtWidgets.QFrame):
    """Bottom-of-editor overlay that appears when the user presses : in NORMAL mode."""

    command_accepted = QtCore.pyqtSignal(str)
    dismissed = QtCore.pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setFixedHeight(28)
        self._theme = theme

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self._prefix = QtWidgets.QLabel(":")
        self._input = QtWidgets.QLineEdit()
        layout.addWidget(self._prefix)
        layout.addWidget(self._input)

        self._input.returnPressed.connect(self._on_accept)

        self._base_stylesheet = (
            f"VimCommandOverlay {{"
            f"  background-color: {theme.background};"
            f"  border-top: 1px solid {theme.toolbar_separator};"
            f"}}"
            f" QLabel {{"
            f"  color: {theme.text};"
            f'  font-family: "Source Code Pro", "Consolas", "Menlo", monospace;'
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"}}"
            f" QLineEdit {{"
            f"  color: {theme.text};"
            f'  font-family: "Source Code Pro", "Consolas", "Menlo", monospace;'
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
        )
        self.setStyleSheet(self._base_stylesheet)
        self.hide()

    def show_command(self):
        self._input.clear()
        self.show()
        self.raise_()
        self._input.setFocus()

    def _on_accept(self):
        text = self._input.text().strip()
        if text:
            self.command_accepted.emit(text)
        self.hide()
        self.dismissed.emit()

    def flash_error(self):
        self.setStyleSheet(
            f"VimCommandOverlay {{"
            f"  background-color: {self._theme.background};"
            f"  border: 1px solid #f44747;"
            f"}}"
            f" QLabel {{"
            f"  color: {self._theme.text};"
            f'  font-family: "Source Code Pro", "Consolas", "Menlo", monospace;'
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"}}"
            f" QLineEdit {{"
            f"  color: {self._theme.text};"
            f'  font-family: "Source Code Pro", "Consolas", "Menlo", monospace;'
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
        )
        QtCore.QTimer.singleShot(500, self._reset_style)

    def _reset_style(self):
        self.setStyleSheet(self._base_stylesheet)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.hide()
            self.dismissed.emit()
            return
        if event.key() == QtCore.Qt.Key.Key_Backspace and not self._input.text():
            self.hide()
            self.dismissed.emit()
            return
        super().keyPressEvent(event)
