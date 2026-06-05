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

"""Keyboard shortcut reference dialog for the GLSL Script Editor.

Displays all available keyboard shortcuts in a filterable, grouped layout
styled to match the editor theme.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass

SHORTCUT_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "File",
        [
            ("Ctrl+S", "Save"),
        ],
    ),
    (
        "Edit",
        [
            ("Ctrl+Z", "Undo"),
            ("Ctrl+Shift+Z", "Redo"),
            ("Ctrl+D", "Duplicate Line"),
            ("Ctrl+/", "Toggle Comment"),
            ("Alt+Up", "Move Line Up"),
            ("Alt+Down", "Move Line Down"),
        ],
    ),
    (
        "Navigation",
        [
            ("Ctrl+G", "Go to Line"),
            ("Ctrl+F", "Find"),
            ("Ctrl+H", "Find & Replace"),
            ("F3", "Find Next"),
            ("Shift+F3", "Find Previous"),
            ("Enter", "Find Next (in Find field)"),
            ("Shift+Enter", "Find Previous (in Find field)"),
            ("Ctrl+Shift+\\", "Go to Matching Bracket"),
            ("Escape", "Close Find Bar"),
        ],
    ),
    (
        "Code",
        [
            ("Ctrl+Shift+[", "Fold Block"),
            ("Ctrl+Shift+]", "Unfold Block"),
            ("Tab", "Indent"),
            ("Shift+Tab", "Unindent"),
        ],
    ),
    (
        "Snippets",
        [
            ("Tab", "Expand snippet / Next tabstop"),
            ("Shift+Tab", "Previous tabstop"),
            ("Escape", "Cancel snippet mode"),
        ],
    ),
    (
        "View",
        [
            ("Ctrl+=", "Zoom In"),
            ("Ctrl+-", "Zoom Out"),
            ("Ctrl+0", "Reset Zoom"),
            ("Ctrl+Scroll", "Zoom In/Out"),
            ("Alt+Z", "Toggle Word Wrap"),
            ("Ctrl+Shift+M", "Toggle Minimap"),
        ],
    ),
    (
        "Vim-Lite",
        [
            ("Escape", "Return to Normal mode"),
            ("i / a", "Insert before / after cursor"),
            ("I / A", "Insert at line start / end"),
            ("o / O", "Open line below / above"),
            ("v / V", "Visual / Visual Line mode"),
            (":", "Command line"),
            ("h / j / k / l", "Move left / down / up / right"),
            ("w / b / e", "Word forward / back / end"),
            ("0 / $ / ^", "Line start / end / first char"),
            ("gg / G", "First / last line"),
            ("{ / }", "Paragraph up / down"),
            ("f / F / t / T", "Find char forward / back (to / till)"),
            ("d{motion}", "Delete with motion"),
            ("c{motion}", "Change with motion"),
            ("y{motion}", "Yank with motion"),
            ("dd / cc / yy", "Delete / change / yank line"),
            ("x / X", "Delete char forward / back"),
            ("p / P", "Paste after / before"),
            ("u / Ctrl+R", "Undo / Redo"),
            ("J", "Join lines"),
            ("~", "Toggle case"),
            ("/ / ?", "Search forward / backward"),
            ("n / N", "Next / previous match"),
            ("* / #", "Search word under cursor"),
            (":w / :q / :wq", "Save / close / save+close"),
            (":q!", "Close without saving"),
        ],
    ),
]


class ShortcutReferenceDialog(QtWidgets.QDialog):
    """Modal dialog listing all keyboard shortcuts grouped by category."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._theme = theme

        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(350, 400)
        self.resize(420, 520)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

        self._build_ui()
        self._apply_stylesheet()
        self._populate()

        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._filter_edit = QtWidgets.QLineEdit()
        self._filter_edit.setPlaceholderText("Filter shortcuts...")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._filter_edit)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._content_widget = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)

        self._scroll_area.setWidget(self._content_widget)
        layout.addWidget(self._scroll_area)

    def _populate(self):
        self._group_widgets: list[
            tuple[QtWidgets.QLabel, list[tuple[QtWidgets.QWidget, str, str]]]
        ] = []

        for group_name, shortcuts in SHORTCUT_GROUPS:
            header = QtWidgets.QLabel(group_name)
            header.setProperty("shortcutHeader", True)
            self._content_layout.addWidget(header)

            row_entries: list[tuple[QtWidgets.QWidget, str, str]] = []

            for key_combo, description in shortcuts:
                row = QtWidgets.QWidget()
                row_layout = QtWidgets.QHBoxLayout(row)
                row_layout.setContentsMargins(8, 2, 8, 2)
                row_layout.setSpacing(12)

                key_label = QtWidgets.QLabel(key_combo)
                key_label.setProperty("shortcutKey", True)
                key_label.setFixedWidth(140)
                key_label.setAlignment(
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                )
                row_layout.addWidget(key_label)

                desc_label = QtWidgets.QLabel(description)
                desc_label.setAlignment(
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                )
                row_layout.addWidget(desc_label, stretch=1)

                self._content_layout.addWidget(row)
                row_entries.append((row, key_combo, description))

            self._group_widgets.append((header, row_entries))

        self._content_layout.addStretch()

    def _on_filter_changed(self, text: str):
        needle = text.strip().lower()

        for header, row_entries in self._group_widgets:
            any_visible = False
            for row_widget, key_combo, description in row_entries:
                if not needle:
                    row_widget.setVisible(True)
                    any_visible = True
                else:
                    matches = needle in key_combo.lower() or needle in description.lower()
                    row_widget.setVisible(matches)
                    if matches:
                        any_visible = True
            header.setVisible(any_visible)

    def _apply_stylesheet(self):
        theme = self._theme
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.background};
                color: {theme.text};
            }}
            QLineEdit {{
                background-color: {theme.current_line};
                color: {theme.text};
                border: 1px solid {theme.line_number_fg};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
            }}
            QScrollArea {{
                background-color: {theme.background};
            }}
            QWidget {{
                background-color: {theme.background};
                color: {theme.text};
            }}
            QLabel {{
                color: {theme.text};
                font-size: 12px;
            }}
            QLabel[shortcutHeader="true"] {{
                color: {theme.keyword};
                font-size: 13px;
                font-weight: bold;
                padding-top: 8px;
                padding-bottom: 2px;
            }}
            QLabel[shortcutKey="true"] {{
                font-family: "Source Code Pro", "Consolas", "Menlo", monospace;
                color: {theme.text};
                font-size: 11px;
                background-color: {theme.current_line};
                border: 1px solid {theme.toolbar_separator};
                border-bottom: 2px solid {theme.toolbar_separator};
                border-radius: 4px;
                padding: 3px 8px;
            }}
            QScrollBar:vertical {{
                background-color: {theme.background};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.line_number_fg};
                min-height: 20px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.line_number_active_fg};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                height: 0px;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: none;
            }}
        """)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
