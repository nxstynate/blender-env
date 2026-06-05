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

"""Signature help tooltip widget for the GLSL Script Editor.

Displays function parameter information when the user types ``(``, similar
to VSCode's parameter hints.  The active parameter is highlighted in bold
with a distinct color.  The widget never steals focus from the editor.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass

from .completer import SignatureInfo  # noqa: E402
from .theme import GLSLEditorTheme  # noqa: E402

_MAX_WIDTH = 500
_PADDING = 8
_GAP = 2
_DESC_FONT_SHRINK = 1


class SignatureHelpWidget(QtWidgets.QFrame):
    def __init__(self, theme: GLSLEditorTheme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._info: SignatureInfo | None = None
        self._active_param: int = -1

        self.setWindowFlags(
            QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {theme.signature_bg};"
            f"  border: 1px solid {theme.signature_border};"
            f"  border-radius: 4px;"
            f"}}"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(_PADDING, _PADDING, _PADDING, _PADDING)
        layout.setSpacing(4)

        self._signature_label = QtWidgets.QLabel(self)
        self._signature_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._signature_label.setWordWrap(True)
        self._signature_label.setStyleSheet("border: none;")
        layout.addWidget(self._signature_label)

        self._description_label = QtWidgets.QLabel(self)
        self._description_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet(f"color: {theme.signature_fg}; border: none;")
        layout.addWidget(self._description_label)

        self._param_description_label = QtWidgets.QLabel(self)
        self._param_description_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._param_description_label.setWordWrap(True)
        self._param_description_label.setStyleSheet("border: none;")
        layout.addWidget(self._param_description_label)

        self.setLayout(layout)

        self._apply_fonts()

    def update_font(self):
        self._apply_fonts()

    def _apply_fonts(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "font"):
            mono_font = QtGui.QFont(parent.font())
        else:
            mono_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        self._signature_label.setFont(mono_font)

        desc_font = QtGui.QFont(mono_font)
        desc_font.setPointSize(max(8, mono_font.pointSize() - _DESC_FONT_SHRINK))
        self._description_label.setFont(desc_font)
        self._param_description_label.setFont(desc_font)

    def _build_signature_html(self, info: SignatureInfo, active_param: int) -> str:
        parts: list[str] = []

        parts.append(
            f'<span style="color:{self._theme.signature_type_fg}">'
            f"{_html_escape(info.return_type)}</span> "
        )

        func_name = info.label.split("(")[0]
        if " " in func_name:
            func_name = func_name.split()[-1]
        parts.append(
            f'<span style="color:{self._theme.signature_fg}">{_html_escape(func_name)}</span>('
        )

        for i, (name, type_str, _desc) in enumerate(info.parameters):
            if i > 0:
                parts.append(f'<span style="color:{self._theme.signature_fg}">, </span>')

            param_text = f"{type_str} {name}"

            if i == active_param:
                parts.append(
                    f'<b style="color:{self._theme.signature_active_param}">'
                    f"{_html_escape(param_text)}</b>"
                )
            else:
                parts.append(
                    f'<span style="color:{self._theme.signature_fg}">'
                    f"{_html_escape(param_text)}</span>"
                )

        parts.append(f'<span style="color:{self._theme.signature_fg}">)</span>')

        return "".join(parts)

    def show_signature(
        self,
        info: SignatureInfo,
        active_param: int,
        cursor_rect: QtCore.QRect,
    ):
        self._info = info
        self._active_param = active_param

        self._signature_label.setText(self._build_signature_html(info, active_param))

        if info.description:
            self._description_label.setText(info.description)
            self._description_label.show()
        else:
            self._description_label.hide()

        self._update_param_description(info, active_param)

        self.adjustSize()

        width = min(self.sizeHint().width(), _MAX_WIDTH)
        self.setFixedWidth(width)
        self.adjustSize()

        self._position_near_cursor(cursor_rect)
        self.show()

    def update_active_param(self, active_param: int):
        if self._info is None:
            return

        self._active_param = active_param
        self._signature_label.setText(self._build_signature_html(self._info, active_param))
        self._update_param_description(self._info, active_param)
        self.adjustSize()

    def dismiss(self):
        self._info = None
        self._active_param = -1
        self.hide()

    def is_visible(self) -> bool:
        return self.isVisible()

    def _update_param_description(self, info: SignatureInfo, active_param: int):
        if 0 <= active_param < len(info.parameters):
            name, _type_str, desc = info.parameters[active_param]
            if desc:
                self._param_description_label.setText(
                    f'<b style="color:{self._theme.signature_active_param}">'
                    f"{_html_escape(name)}</b>"
                    f'<span style="color:{self._theme.signature_fg}">'
                    f": {_html_escape(desc)}</span>"
                )
                self._param_description_label.show()
                return

        self._param_description_label.hide()

    def _position_near_cursor(self, cursor_rect: QtCore.QRect):
        parent = self.parent()
        if parent is None:
            return

        global_top_left = parent.mapToGlobal(cursor_rect.topLeft())
        global_bottom_left = parent.mapToGlobal(cursor_rect.bottomLeft())

        screen = QtWidgets.QApplication.screenAt(global_top_left)
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        widget_height = self.sizeHint().height()
        widget_width = self.width()

        above_y = global_top_left.y() - widget_height - _GAP
        if above_y >= screen_geometry.top():
            target_y = above_y
        else:
            target_y = global_bottom_left.y() + _GAP

        target_x = global_top_left.x()
        if target_x + widget_width > screen_geometry.right():
            target_x = screen_geometry.right() - widget_width
        if target_x < screen_geometry.left():
            target_x = screen_geometry.left()

        self.move(target_x, target_y)


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
