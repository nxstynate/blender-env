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

"""Find / Replace bar widget for the GLSL Script Editor.

Provides ``FindReplaceBar``, a compact horizontal bar with find-next,
find-previous, replace, replace-all, regex toggle, case-sensitivity
toggle, and whole-word toggle.  Match highlights are stored internally
and exposed via ``get_find_selections()`` so the parent editor can merge
them with other extra selections (bracket matching, current-line
highlight, etc.).
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


class FindReplaceBar(QtWidgets.QWidget):
    """A compact find/replace bar for a ``QPlainTextEdit``."""

    matches_changed = QtCore.pyqtSignal()

    def __init__(
        self,
        editor: QtWidgets.QPlainTextEdit,
        theme: GLSLEditorTheme,
        parent=None,
    ):
        super().__init__(parent)
        self._editor = editor
        self._theme = theme
        self._find_selections: list[QtWidgets.QTextEdit.ExtraSelection] = []
        self._match_count = 0
        self._current_match_index = 0

        self._build_ui()
        self._connect_signals()

        self._highlight_timer = QtCore.QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(100)
        self._highlight_timer.timeout.connect(self._do_deferred_highlight)

        self.hide()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(
            f"FindReplaceBar {{ border-bottom: 1px solid {self._theme.toolbar_separator}; }}"
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(2)

        self._find_row = self._build_find_row()
        self._replace_row = self._build_replace_row()

        main_layout.addLayout(self._find_row)
        main_layout.addLayout(self._replace_row["layout"])

        self._set_replace_visible(False)

    def _build_find_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._find_field = QtWidgets.QLineEdit()
        self._find_field.setPlaceholderText("Find...")
        self._find_field.setMinimumWidth(160)

        self._btn_prev = QtWidgets.QPushButton()
        self._btn_prev.setText("\u25b2")
        self._btn_prev.setFixedSize(QtCore.QSize(24, 24))
        self._btn_prev.setToolTip("Previous match")

        self._btn_next = QtWidgets.QPushButton()
        self._btn_next.setText("\u25bc")
        self._btn_next.setFixedSize(QtCore.QSize(24, 24))
        self._btn_next.setToolTip("Next match")

        toggle_style = self._toggle_button_stylesheet()

        self._chk_case = QtWidgets.QPushButton()
        self._chk_case.setCheckable(True)
        self._chk_case.setText("Aa")
        self._chk_case.setFixedSize(QtCore.QSize(24, 24))
        self._chk_case.setToolTip("Case sensitive")
        self._chk_case.setStyleSheet(toggle_style)

        self._chk_whole_word = QtWidgets.QPushButton()
        self._chk_whole_word.setCheckable(True)
        self._chk_whole_word.setText("[W]")
        self._chk_whole_word.setFixedSize(QtCore.QSize(24, 24))
        self._chk_whole_word.setToolTip("Whole word")
        self._chk_whole_word.setStyleSheet(toggle_style)

        self._chk_regex = QtWidgets.QPushButton()
        self._chk_regex.setCheckable(True)
        self._chk_regex.setText(".*")
        self._chk_regex.setFixedSize(QtCore.QSize(24, 24))
        self._chk_regex.setToolTip("Regular expression")
        self._chk_regex.setStyleSheet(toggle_style)

        self._lbl_count = QtWidgets.QLabel("")
        self._lbl_count.setMinimumWidth(60)

        self._btn_close = QtWidgets.QPushButton()
        self._btn_close.setText("\u2715")
        self._btn_close.setFixedSize(QtCore.QSize(24, 24))
        self._btn_close.setToolTip("Close")

        row.addWidget(self._find_field)
        row.addWidget(self._btn_prev)
        row.addWidget(self._btn_next)
        row.addWidget(self._chk_case)
        row.addWidget(self._chk_whole_word)
        row.addWidget(self._chk_regex)
        row.addWidget(self._lbl_count)
        row.addStretch()
        row.addWidget(self._btn_close)
        return row

    def _build_replace_row(self) -> dict:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._replace_field = QtWidgets.QLineEdit()
        self._replace_field.setPlaceholderText("Replace...")
        self._replace_field.setMinimumWidth(160)

        self._btn_replace = QtWidgets.QPushButton()
        self._btn_replace.setText("\u21b7")
        self._btn_replace.setFixedSize(QtCore.QSize(24, 24))
        self._btn_replace.setToolTip("Replace current match")

        self._btn_replace_all = QtWidgets.QPushButton()
        self._btn_replace_all.setText("\u21c4")
        self._btn_replace_all.setFixedSize(QtCore.QSize(24, 24))
        self._btn_replace_all.setToolTip("Replace all matches")

        row.addWidget(self._replace_field)
        row.addWidget(self._btn_replace)
        row.addWidget(self._btn_replace_all)
        row.addStretch()

        return {
            "layout": row,
            "widgets": [self._replace_field, self._btn_replace, self._btn_replace_all],
        }

    def _set_replace_visible(self, visible: bool):
        for widget in self._replace_row["widgets"]:
            widget.setVisible(visible)

    def _toggle_button_stylesheet(self) -> str:
        return (
            f"QPushButton {{"
            f"  border: 1px solid transparent;"
            f"  border-radius: 3px;"
            f"  background-color: transparent;"
            f"  color: {self._theme.line_number_fg};"
            f"  font-family: 'Source Code Pro', 'Consolas', 'Menlo', monospace;"
            f"  font-size: 12px;"
            f"  font-weight: bold;"
            f"}}"
            f" QPushButton:hover {{"
            f"  background-color: {self._theme.current_line};"
            f"  color: {self._theme.text};"
            f"  border: 1px solid {self._theme.toolbar_separator};"
            f"}}"
            f" QPushButton:checked {{"
            f"  background-color: {self._theme.selection};"
            f"  border: 1px solid {self._theme.selection};"
            f"  color: {self._theme.text};"
            f"}}"
            f" QPushButton:checked:hover {{"
            f"  background-color: {self._theme.selection};"
            f"  border: 1px solid {self._theme.text};"
            f"}}"
        )

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._find_field.textChanged.connect(self._on_search_text_changed)
        self._chk_case.toggled.connect(self._on_option_toggled)
        self._chk_regex.toggled.connect(self._on_option_toggled)
        self._chk_whole_word.toggled.connect(self._on_option_toggled)
        self._btn_next.clicked.connect(self.find_next)
        self._btn_prev.clicked.connect(self.find_previous)
        self._btn_replace.clicked.connect(self.replace_current)
        self._btn_replace_all.clicked.connect(self.replace_all)
        self._btn_close.clicked.connect(self.hide_bar)
        self._find_field.installEventFilter(self)
        self._replace_field.installEventFilter(self)

    def _on_search_text_changed(self):
        self._highlight_timer.start()

    def _do_deferred_highlight(self):
        self._highlight_all_matches()
        self.find_next()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                if obj is self._find_field:
                    if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                        self.find_previous()
                    else:
                        self.find_next()
                    return True
                if obj is self._replace_field:
                    self.replace_current()
                    return True
        return super().eventFilter(obj, event)

    def _on_option_toggled(self):
        if self._chk_regex.isChecked():
            self._chk_whole_word.setEnabled(False)
        else:
            self._chk_whole_word.setEnabled(True)
        self._highlight_all_matches()
        self.find_next()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_find(self):
        """Show the bar in find-only mode and focus the search field."""
        self._set_replace_visible(False)
        self.show()
        self._seed_search_from_selection()
        self._find_field.setFocus()
        self._find_field.selectAll()

    def show_replace(self):
        """Show the bar with both find and replace rows."""
        self._set_replace_visible(True)
        self.show()
        self._seed_search_from_selection()
        self._find_field.setFocus()
        self._find_field.selectAll()

    def hide_bar(self):
        """Hide the bar and clear all find-match highlights."""
        self.hide()
        self._find_selections.clear()
        self._match_count = 0
        self._current_match_index = 0
        self._lbl_count.setText("")
        self.matches_changed.emit()

    def find_next(self):
        """Search forward from the current cursor position."""
        self._do_search(forward=True)

    def find_previous(self):
        """Search backward from the current cursor position."""
        self._do_search(forward=False)

    def replace_current(self):
        """Replace the current match with the replacement text, then find next."""
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            self.find_next()
            return

        search_text = self._find_field.text()
        if not search_text:
            return

        selected = cursor.selectedText()
        if self._chk_regex.isChecked():
            regex = QtCore.QRegularExpression(search_text)
            if not self._chk_case.isChecked():
                regex.setPatternOptions(
                    QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption,
                )
            match = regex.match(selected)
            if not match.hasMatch() or match.capturedLength() != len(selected):
                self.find_next()
                return
        else:
            if self._chk_case.isChecked():
                if selected != search_text:
                    self.find_next()
                    return
            else:
                if selected.lower() != search_text.lower():
                    self.find_next()
                    return

        cursor.beginEditBlock()
        cursor.insertText(self._replace_field.text())
        cursor.endEditBlock()
        self._highlight_all_matches()
        self.find_next()

    def replace_all(self):
        """Replace every match in the document."""
        search_text = self._find_field.text()
        if not search_text:
            return

        replace_text = self._replace_field.text()
        document = self._editor.document()
        cursor = QtGui.QTextCursor(document)
        flags = self._build_find_flags(forward=True)

        cursor.beginEditBlock()
        count = 0
        last_pos = -1
        found = self._find_in_document(document, search_text, cursor, flags)
        while not found.isNull():
            if found.position() <= last_pos:
                break
            last_pos = found.position()
            found.insertText(replace_text)
            count += 1
            found = self._find_in_document(document, search_text, found, flags)
        cursor.endEditBlock()

        self._highlight_all_matches()
        self._lbl_count.setText(f"{count} replaced")

    def search_word(self, word: str, forward: bool = True):
        """Search for *word* with whole-word matching, without showing the bar."""
        self._find_field.setText(word)
        self._chk_whole_word.setChecked(True)
        self._highlight_all_matches()
        if forward:
            self.find_next()
        else:
            self.find_previous()

    def get_find_selections(self) -> list[QtWidgets.QTextEdit.ExtraSelection]:
        """Return the current list of find-match extra selections."""
        return list(self._find_selections)

    # ------------------------------------------------------------------
    # Search internals
    # ------------------------------------------------------------------

    def _do_search(self, forward: bool = True):
        search_text = self._find_field.text()
        if not search_text:
            self._lbl_count.setText("")
            return

        document = self._editor.document()
        cursor = self._editor.textCursor()
        flags = self._build_find_flags(forward=forward)

        found = self._find_in_document(document, search_text, cursor, flags)

        if found.isNull():
            wrap_cursor = QtGui.QTextCursor(document)
            if forward:
                wrap_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            else:
                wrap_cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            found = self._find_in_document(document, search_text, wrap_cursor, flags)

        if not found.isNull():
            self._editor.setTextCursor(found)

        self._update_current_match_highlight()
        self._update_match_count()

    def _build_find_flags(self, forward: bool = True) -> QtGui.QTextDocument.FindFlag:
        flags = QtGui.QTextDocument.FindFlag(0)
        if not forward:
            flags |= QtGui.QTextDocument.FindFlag.FindBackward
        if self._chk_case.isChecked():
            flags |= QtGui.QTextDocument.FindFlag.FindCaseSensitively
        if self._chk_whole_word.isChecked() and not self._chk_regex.isChecked():
            flags |= QtGui.QTextDocument.FindFlag.FindWholeWords
        return flags

    def _find_in_document(
        self,
        document: QtGui.QTextDocument,
        search_text: str,
        cursor: QtGui.QTextCursor,
        flags: QtGui.QTextDocument.FindFlag,
    ) -> QtGui.QTextCursor:
        if self._chk_regex.isChecked():
            regex = QtCore.QRegularExpression(search_text)
            if not self._chk_case.isChecked():
                regex.setPatternOptions(
                    QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption
                )
            return document.find(regex, cursor, flags)
        return document.find(search_text, cursor, flags)

    def _highlight_all_matches(self):
        self._find_selections.clear()
        search_text = self._find_field.text()
        if not search_text:
            self._match_count = 0
            self._current_match_index = 0
            self._lbl_count.setText("")
            self.matches_changed.emit()
            return

        document = self._editor.document()
        flags = self._build_find_flags(forward=True)
        cursor = QtGui.QTextCursor(document)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)

        match_color = self._theme.qcolor("find_match")

        last_pos = -1
        found = self._find_in_document(document, search_text, cursor, flags)
        while not found.isNull():
            if found.position() <= last_pos:
                break
            last_pos = found.position()
            selection = QtWidgets.QTextEdit.ExtraSelection()
            selection.format.setBackground(match_color)
            selection.cursor = found
            self._find_selections.append(selection)
            found = self._find_in_document(document, search_text, found, flags)

        self._match_count = len(self._find_selections)
        self._update_current_match_highlight()
        self._update_match_count()
        self.matches_changed.emit()

    def _update_current_match_highlight(self):
        """Set the current match to a distinct color, others to the default."""
        if not self._find_selections:
            return

        editor_pos = self._editor.textCursor().position()
        match_color = self._theme.qcolor("find_match")
        current_color = self._theme.qcolor("find_match_current")

        current_idx = -1
        for i, sel in enumerate(self._find_selections):
            if sel.cursor.selectionStart() <= editor_pos <= sel.cursor.selectionEnd():
                current_idx = i
                break

        if current_idx == -1:
            for i, sel in enumerate(self._find_selections):
                if sel.cursor.selectionStart() >= editor_pos:
                    current_idx = i
                    break

        for i, sel in enumerate(self._find_selections):
            if i == current_idx:
                sel.format.setBackground(current_color)
            else:
                sel.format.setBackground(match_color)

        self.matches_changed.emit()

    def _update_match_count(self):
        if self._match_count == 0:
            self._lbl_count.setText("No results")
            return

        editor_cursor = self._editor.textCursor()
        editor_pos = editor_cursor.position()
        current_index = 0

        for i, sel in enumerate(self._find_selections):
            if sel.cursor.selectionStart() <= editor_pos <= sel.cursor.selectionEnd():
                current_index = i + 1
                break

        if current_index == 0 and self._match_count > 0:
            for i, sel in enumerate(self._find_selections):
                if sel.cursor.selectionStart() >= editor_pos:
                    current_index = i + 1
                    break
            if current_index == 0:
                current_index = self._match_count

        self._current_match_index = current_index
        self._lbl_count.setText(f"{current_index} of {self._match_count}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _seed_search_from_selection(self):
        """Pre-fill the search field with the editor's current selection."""
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace("\u2029", "\n")
            if "\n" in text:
                text = text.split("\n")[0]
            if text:
                self._find_field.setText(text)
