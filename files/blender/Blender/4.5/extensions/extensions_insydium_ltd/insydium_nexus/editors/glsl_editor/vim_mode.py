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

"""Vim emulation state machine for the NeXus GLSL Script Editor.

Provides ``VimHandler``, a ``QObject`` that intercepts key events from
``GLSLCodeEditor`` and translates them into vim-style motions, operators,
and mode transitions.  The handler owns no widget — it reads and mutates
the editor's ``QTextCursor`` and emits signals for higher-level actions
(save, quit, search).
"""

from __future__ import annotations

import enum
import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui  # noqa: E402
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Mode enum
# ---------------------------------------------------------------------------


class VimMode(enum.Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    VISUAL = "VISUAL"
    VISUAL_LINE = "VISUAL_LINE"
    COMMAND = "COMMAND"


def _char_class(ch: str) -> int:
    """Classify a character for vim word motion: 0=whitespace, 1=word, 2=punctuation."""
    if not ch or ch in ("\n", "\r", "\u2029"):
        return 0
    if ch.isspace():
        return 0
    if ch.isalnum() or ch == "_":
        return 1
    return 2


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class VimHandler(QtCore.QObject):
    """Core vim state machine — intercepts key events and drives the editor."""

    mode_changed = QtCore.pyqtSignal(object)
    command_text_changed = QtCore.pyqtSignal(str)
    save_requested = QtCore.pyqtSignal()
    close_requested = QtCore.pyqtSignal()
    save_close_requested = QtCore.pyqtSignal()
    force_close_requested = QtCore.pyqtSignal()
    goto_line_requested = QtCore.pyqtSignal(int)
    clear_search_requested = QtCore.pyqtSignal()
    find_requested = QtCore.pyqtSignal()
    find_word_requested = QtCore.pyqtSignal(str, bool)
    find_next_requested = QtCore.pyqtSignal()
    find_prev_requested = QtCore.pyqtSignal()

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor

        self._mode: VimMode = VimMode.NORMAL
        self._enabled: bool = False

        self._count_prefix: str = ""
        self._pending_operator: str | None = None
        self._pending_keys: str = ""
        self._awaiting_char: str | None = None
        self._awaiting_text_object: str | None = None

        self._visual_anchor: int | None = None
        self._command_buffer: str = ""

        self._register_text: str = ""
        self._register_linewise: bool = False

        self._last_find_char: str = ""
        self._last_find_forward: bool = True
        self._last_find_inclusive: bool = True

        self._last_edit: tuple | None = None
        self._insert_start_pos: int = 0
        self._insert_entry_command: tuple | None = None

    # --------------------------------------------------------------------- #
    # Properties
    # --------------------------------------------------------------------- #

    @property
    def mode(self) -> VimMode:
        return self._mode

    @property
    def enabled(self) -> bool:
        return self._enabled

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled = True
            self._set_mode(VimMode.NORMAL)
        else:
            self._enabled = False
            self._reset_state()
            self._editor.setCursorWidth(1)
            self.mode_changed.emit(VimMode.NORMAL)

    def reset(self) -> None:
        self._reset_state()
        self._set_mode(VimMode.NORMAL)

    def handle_key(self, event: QtGui.QKeyEvent) -> bool:
        if not self._enabled:
            return False
        if self._mode == VimMode.INSERT:
            return self._handle_insert(event)
        if self._mode == VimMode.COMMAND:
            return self._handle_command(event)
        if self._mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            return self._handle_visual(event)
        return self._handle_normal(event)

    def escape_from_insert(self) -> None:
        if self._mode != VimMode.INSERT:
            return
        cursor = self._editor.textCursor()
        col = cursor.positionInBlock()
        if col > 0:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
            self._editor.setTextCursor(cursor)
        self._set_mode(VimMode.NORMAL)

    # --------------------------------------------------------------------- #
    # Mode transition
    # --------------------------------------------------------------------- #

    def _set_mode(self, new_mode: VimMode) -> None:
        old_mode = self._mode
        self._mode = new_mode

        self._count_prefix = ""
        self._pending_operator = None
        self._pending_keys = ""
        self._awaiting_char = None
        self._awaiting_text_object = None

        if new_mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            self._visual_anchor = self._editor.textCursor().position()
        elif old_mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            cursor = self._editor.textCursor()
            cursor.clearSelection()
            self._editor.setTextCursor(cursor)
            self._visual_anchor = None

        if new_mode == VimMode.INSERT:
            self._editor.setCursorWidth(1)
            self._insert_start_pos = self._editor.textCursor().position()
        elif new_mode == VimMode.NORMAL:
            char_w = self._editor.fontMetrics().horizontalAdvance("M")
            self._editor.setCursorWidth(char_w)
        elif new_mode == VimMode.COMMAND:
            self._command_buffer = ""

        self.mode_changed.emit(new_mode)

    # --------------------------------------------------------------------- #
    # INSERT mode
    # --------------------------------------------------------------------- #

    def _handle_insert(self, event: QtGui.QKeyEvent) -> bool:
        return False

    # --------------------------------------------------------------------- #
    # COMMAND mode
    # --------------------------------------------------------------------- #

    def _handle_command(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()

        if key == QtCore.Qt.Key.Key_Escape:
            self._set_mode(VimMode.NORMAL)
            return True

        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._execute_command()
            self._set_mode(VimMode.NORMAL)
            return True

        if key == QtCore.Qt.Key.Key_Backspace:
            if self._command_buffer:
                self._command_buffer = self._command_buffer[:-1]
            if not self._command_buffer:
                self._set_mode(VimMode.NORMAL)
                return True
            self.command_text_changed.emit(":" + self._command_buffer)
            return True

        text = event.text()
        if text and text.isprintable():
            self._command_buffer += text
            self.command_text_changed.emit(":" + self._command_buffer)
            return True

        return True

    def _execute_command(self) -> None:
        buf = self._command_buffer.strip()
        if not buf:
            return

        if buf == "w":
            self.save_requested.emit()
        elif buf == "q":
            self.close_requested.emit()
        elif buf in ("wq", "x"):
            self.save_close_requested.emit()
        elif buf == "q!":
            self.force_close_requested.emit()
        elif buf in ("noh", "nohlsearch"):
            self.clear_search_requested.emit()
        elif buf.isdigit():
            self.goto_line_requested.emit(int(buf))

    # --------------------------------------------------------------------- #
    # VISUAL / VISUAL_LINE mode
    # --------------------------------------------------------------------- #

    def _handle_visual(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        if key == QtCore.Qt.Key.Key_Escape:
            self._set_mode(VimMode.NORMAL)
            return True

        if self._awaiting_text_object is not None:
            if text:
                inner = self._awaiting_text_object == "i"
                self._awaiting_text_object = None
                result = self._find_text_object(text, inner)
                if result is not None:
                    start, end = result
                    cursor = self._editor.textCursor()
                    cursor.setPosition(start)
                    cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self._editor.setTextCursor(cursor)
                    self._visual_anchor = start
            else:
                self._awaiting_text_object = None
            return True

        if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            return False

        if text and text.isdigit() and (self._count_prefix or text != "0"):
            self._count_prefix += text
            return True

        if text == "v":
            if self._mode == VimMode.VISUAL:
                self._set_mode(VimMode.NORMAL)
            else:
                self._set_mode(VimMode.VISUAL)
            return True

        if text == "V":
            if self._mode == VimMode.VISUAL_LINE:
                self._set_mode(VimMode.NORMAL)
            else:
                self._set_mode(VimMode.VISUAL_LINE)
            return True

        if text in ("d", "x"):
            self._visual_delete()
            self._set_mode(VimMode.NORMAL)
            return True

        if text == "c":
            self._visual_delete()
            self._set_mode(VimMode.INSERT)
            return True

        if text == "y":
            self._visual_yank()
            self._set_mode(VimMode.NORMAL)
            return True

        if text == ">":
            self._visual_indent(forward=True)
            self._set_mode(VimMode.NORMAL)
            return True

        if text == "<":
            self._visual_indent(forward=False)
            self._set_mode(VimMode.NORMAL)
            return True

        if text == "~":
            self._visual_swap_case()
            self._set_mode(VimMode.NORMAL)
            return True

        if text in ("i", "a"):
            self._awaiting_text_object = text
            return True

        handled = self._apply_visual_motion(key, text)
        if handled:
            return True

        return True

    def _apply_visual_motion(self, key: int, text: str) -> bool:
        """Execute a motion and extend the selection from the visual anchor."""
        cursor = self._editor.textCursor()
        count = self._get_count()
        anchor = self._visual_anchor
        if anchor is None:
            return False

        moved = False

        if text == "h" or key == QtCore.Qt.Key.Key_Left:
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
            moved = True
        elif text == "j" or key == QtCore.Qt.Key.Key_Down:
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Down)
            moved = True
        elif text == "k" or key == QtCore.Qt.Key.Key_Up:
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
            moved = True
        elif text == "l" or key == QtCore.Qt.Key.Key_Right:
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
            moved = True
        elif text == "w":
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.NextWord)
            moved = True
        elif text == "b":
            for _ in range(count):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.PreviousWord)
            moved = True
        elif text == "0":
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            moved = True
        elif text == "$":
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            moved = True
        elif key == QtCore.Qt.Key.Key_G:
            if text == "G":
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
                moved = True
        elif text == "{":
            for _ in range(count):
                self._move_paragraph(cursor, forward=False)
            moved = True
        elif text == "}":
            for _ in range(count):
                self._move_paragraph(cursor, forward=True)
            moved = True

        if not moved:
            return False

        new_pos = cursor.position()

        if self._mode == VimMode.VISUAL_LINE:
            doc = self._editor.document()
            anchor_block = doc.findBlock(anchor)
            pos_block = doc.findBlock(new_pos)
            if anchor_block.blockNumber() <= pos_block.blockNumber():
                sel_start = anchor_block.position()
                sel_end = pos_block.position() + pos_block.length() - 1
            else:
                sel_start = pos_block.position()
                sel_end = anchor_block.position() + anchor_block.length() - 1
            cursor.setPosition(sel_start)
            cursor.setPosition(sel_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        else:
            if new_pos >= anchor:
                cursor.setPosition(anchor)
                cursor.setPosition(new_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
            else:
                cursor.setPosition(anchor)
                cursor.setPosition(new_pos, QtGui.QTextCursor.MoveMode.KeepAnchor)

        self._editor.setTextCursor(cursor)
        return True

    def _visual_delete(self) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        self._register_text = cursor.selectedText().replace("\u2029", "\n")
        self._register_linewise = self._mode == VimMode.VISUAL_LINE
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        if self._register_linewise:
            block = cursor.block()
            if block.text() == "" and block.next().isValid():
                cursor.deleteChar()
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)

    def _visual_yank(self) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        self._register_text = cursor.selectedText().replace("\u2029", "\n")
        self._register_linewise = self._mode == VimMode.VISUAL_LINE
        cursor.clearSelection()
        self._editor.setTextCursor(cursor)

    def _visual_indent(self, forward: bool) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        doc = self._editor.document()
        start_block = doc.findBlock(cursor.selectionStart()).blockNumber()
        end_block = doc.findBlock(cursor.selectionEnd()).blockNumber()
        if cursor.selectionEnd() == doc.findBlock(cursor.selectionEnd()).position():
            end_block = max(start_block, end_block - 1)

        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = doc.findBlockByNumber(block_num)
            if not block.isValid():
                continue
            c = QtGui.QTextCursor(block)
            if forward:
                c.insertText("    ")
            else:
                line = block.text()
                remove = 0
                for ch in line[:4]:
                    if ch == " ":
                        remove += 1
                    elif ch == "\t":
                        remove += 1
                        break
                    else:
                        break
                if remove > 0:
                    c.movePosition(
                        QtGui.QTextCursor.MoveOperation.Right,
                        QtGui.QTextCursor.MoveMode.KeepAnchor,
                        remove,
                    )
                    c.removeSelectedText()
        cursor.endEditBlock()

    def _visual_swap_case(self) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return
        selected = cursor.selectedText()
        swapped = "".join(c.lower() if c.isupper() else c.upper() for c in selected)
        cursor.beginEditBlock()
        cursor.insertText(swapped)
        cursor.endEditBlock()

    # --------------------------------------------------------------------- #
    # NORMAL mode
    # --------------------------------------------------------------------- #

    def _handle_normal(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        # --- Awaiting character (f/F/t/T/r) ---
        if self._awaiting_char is not None:
            if text:
                self._handle_awaited_char(text)
            else:
                self._awaiting_char = None
            return True

        # --- Awaiting text object target (i/a + target) ---
        if self._awaiting_text_object is not None:
            if text:
                self._handle_text_object(text)
            else:
                self._awaiting_text_object = None
                self._pending_operator = None
            return True

        # --- Ctrl shortcuts pass through (except Ctrl+R -> redo) ---
        if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            if key == QtCore.Qt.Key.Key_R:
                self._editor.redo()
                return True
            return False

        # --- Escape ---
        if key == QtCore.Qt.Key.Key_Escape:
            self._count_prefix = ""
            self._pending_operator = None
            self._pending_keys = ""
            self._awaiting_char = None
            return True

        # --- Count prefix ---
        if text and text.isdigit() and (self._count_prefix or text != "0"):
            self._count_prefix += text
            return True

        # --- Pending operator + motion ---
        if self._pending_operator is not None:
            return self._handle_operator_motion(event)

        # --- Multi-key sequences (g...) ---
        if self._pending_keys:
            return self._handle_pending_keys(event)

        # --- Mode transitions ---
        if text == "i":
            self._set_mode(VimMode.INSERT)
            return True

        if text == "a":
            cursor = self._editor.textCursor()
            block_len = len(cursor.block().text())
            col = cursor.positionInBlock()
            if block_len > 0 and col < block_len:
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
                self._editor.setTextCursor(cursor)
            self._set_mode(VimMode.INSERT)
            return True

        if text == "I":
            self._move_to_first_non_whitespace()
            self._set_mode(VimMode.INSERT)
            return True

        if text == "A":
            cursor = self._editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            self._editor.setTextCursor(cursor)
            self._set_mode(VimMode.INSERT)
            return True

        if text == "o":
            self._insert_line_below()
            self._set_mode(VimMode.INSERT)
            return True

        if text == "O":
            self._insert_line_above()
            self._set_mode(VimMode.INSERT)
            return True

        if text == "v":
            self._set_mode(VimMode.VISUAL)
            return True

        if text == "V":
            self._set_mode(VimMode.VISUAL_LINE)
            return True

        if text == ":":
            self._set_mode(VimMode.COMMAND)
            self.command_text_changed.emit(":")
            return True

        # --- Motions ---
        if text == "h" or key == QtCore.Qt.Key.Key_Left:
            self._move_left()
            return True

        if text == "j" or key == QtCore.Qt.Key.Key_Down:
            self._move_down()
            return True

        if text == "k" or key == QtCore.Qt.Key.Key_Up:
            self._move_up()
            return True

        if text == "l" or key == QtCore.Qt.Key.Key_Right:
            self._move_right()
            return True

        if text == "w":
            self._move_word_forward()
            return True

        if text == "W":
            self._move_word_forward(big=True)
            return True

        if text == "b":
            self._move_word_backward()
            return True

        if text == "B":
            self._move_word_backward(big=True)
            return True

        if text == "e":
            self._move_word_end()
            return True

        if text == "E":
            self._move_word_end(big=True)
            return True

        if text == "0":
            cursor = self._editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            self._editor.setTextCursor(cursor)
            return True

        if text == "^":
            self._move_to_first_non_whitespace()
            return True

        if text == "$":
            cursor = self._editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            self._editor.setTextCursor(cursor)
            self._clamp_cursor_eol()
            return True

        if text == "G":
            count = self._get_count_raw()
            cursor = self._editor.textCursor()
            if count is not None:
                block = self._editor.document().findBlockByNumber(count - 1)
                if block.isValid():
                    cursor.setPosition(block.position())
            else:
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self._editor.setTextCursor(cursor)
            self._clamp_cursor_eol()
            return True

        if text == "{":
            count = self._get_count()
            cursor = self._editor.textCursor()
            for _ in range(count):
                self._move_paragraph(cursor, forward=False)
            self._editor.setTextCursor(cursor)
            return True

        if text == "}":
            count = self._get_count()
            cursor = self._editor.textCursor()
            for _ in range(count):
                self._move_paragraph(cursor, forward=True)
            self._editor.setTextCursor(cursor)
            return True

        if text in ("f", "F", "t", "T"):
            self._awaiting_char = text
            return True

        if text == ";":
            self._repeat_find_char(reverse=False)
            return True

        if text == ",":
            self._repeat_find_char(reverse=True)
            return True

        if text == "%":
            self._move_matching_bracket()
            return True

        if text == "H":
            self._move_screen_top()
            return True

        if text == "M":
            self._move_screen_middle()
            return True

        if text == "L":
            self._move_screen_bottom()
            return True

        if text == "n":
            self.find_next_requested.emit()
            return True

        if text == "N":
            self.find_prev_requested.emit()
            return True

        # --- Operators ---
        if text in ("d", "c", "y", ">", "<"):
            if self._pending_operator == text:
                self._do_linewise_operator(text)
                self._pending_operator = None
            else:
                self._pending_operator = text
            return True

        # --- Single-key edits ---
        if text == "x":
            self._delete_char_forward()
            return True

        if text == "X":
            self._delete_char_backward()
            return True

        if text == "r":
            self._awaiting_char = "r"
            return True

        if text == "p":
            self._paste_after()
            return True

        if text == "P":
            self._paste_before()
            return True

        if text == "u":
            self._editor.undo()
            return True

        if text == "J":
            self._join_lines()
            return True

        if text == "~":
            self._swap_case_char()
            return True

        if text == ".":
            self._replay_last_edit()
            return True

        if text == "D":
            self._delete_to_eol()
            return True

        if text == "C":
            self._delete_to_eol()
            self._set_mode(VimMode.INSERT)
            return True

        if text == "Y":
            self._yank_line()
            return True

        # --- Multi-key prefix ---
        if text == "g":
            self._pending_keys = "g"
            return True

        # --- Search ---
        if text == "/":
            self.find_requested.emit()
            return True

        if text == "*":
            word = self._word_under_cursor()
            if word:
                self.find_word_requested.emit(word, True)
            return True

        if text == "#":
            word = self._word_under_cursor()
            if word:
                self.find_word_requested.emit(word, False)
            return True

        return True

    # --------------------------------------------------------------------- #
    # Multi-key sequences
    # --------------------------------------------------------------------- #

    def _handle_pending_keys(self, event: QtGui.QKeyEvent) -> bool:
        text = event.text()
        pending = self._pending_keys
        self._pending_keys = ""

        if pending == "g":
            if text == "g":
                cursor = self._editor.textCursor()
                count = self._get_count_raw()
                if count is not None:
                    block = self._editor.document().findBlockByNumber(count - 1)
                    if block.isValid():
                        cursor.setPosition(block.position())
                else:
                    cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
                self._editor.setTextCursor(cursor)
                self._clamp_cursor_eol()
                return True

            if text == "e":
                self._move_word_end_backward()
                return True

            if text == "E":
                self._move_word_end_backward(big=True)
                return True

        return True

    # --------------------------------------------------------------------- #
    # Operator + motion
    # --------------------------------------------------------------------- #

    def _handle_operator_motion(self, event: QtGui.QKeyEvent) -> bool:
        """Resolve an operator with the given motion key."""
        key = event.key()
        text = event.text()
        op = self._pending_operator
        self._pending_operator = None

        if text == op:
            self._do_linewise_operator(op)
            return True

        cursor = self._editor.textCursor()
        start = cursor.position()
        count = self._get_count()

        target_cursor = QtGui.QTextCursor(cursor)
        motion_linewise = False
        motion_found = False

        if text == "h" or key == QtCore.Qt.Key.Key_Left:
            for _ in range(count):
                target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
            motion_found = True
        elif text == "l" or key == QtCore.Qt.Key.Key_Right:
            for _ in range(count):
                target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
            motion_found = True
        elif text == "j" or key == QtCore.Qt.Key.Key_Down:
            for _ in range(count):
                target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Down)
            motion_linewise = True
            motion_found = True
        elif text == "k" or key == QtCore.Qt.Key.Key_Up:
            for _ in range(count):
                target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
            motion_linewise = True
            motion_found = True
        elif text in ("w", "W"):
            end = self._compute_word_forward_pos(start, count, big=(text == "W"))
            target_cursor.setPosition(end)
            motion_found = True
        elif text in ("b", "B"):
            end = self._compute_word_backward_pos(start, count, big=(text == "B"))
            target_cursor.setPosition(end)
            motion_found = True
        elif text in ("e", "E"):
            end = self._compute_word_end_pos(start, count, big=(text == "E"))
            target_cursor.setPosition(end + 1)
            motion_found = True
        elif text == "0":
            target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            motion_found = True
        elif text == "^":
            block_text = target_cursor.block().text()
            stripped = block_text.lstrip()
            offset = len(block_text) - len(stripped)
            target_cursor.setPosition(target_cursor.block().position() + offset)
            motion_found = True
        elif text == "$":
            target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            motion_found = True
        elif text == "G":
            target_cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            motion_linewise = True
            motion_found = True
        elif text == "g":
            self._pending_keys = "g"
            self._pending_operator = op
            self._count_prefix = ""
            return True
        elif text == "{":
            for _ in range(count):
                self._move_paragraph(target_cursor, forward=False)
            motion_linewise = True
            motion_found = True
        elif text == "}":
            for _ in range(count):
                self._move_paragraph(target_cursor, forward=True)
            motion_linewise = True
            motion_found = True

        elif text in ("f", "F", "t", "T"):
            self._awaiting_char = text
            self._pending_operator = op
            self._count_prefix = str(count) if count > 1 else ""
            return True

        elif text in ("i", "a"):
            self._awaiting_text_object = text
            self._pending_operator = op
            return True

        if not motion_found:
            return True

        end = target_cursor.position()
        if motion_linewise:
            self._execute_operator_linewise(op, start, end)
        else:
            self._execute_operator_charwise(op, min(start, end), max(start, end))

        self._clamp_cursor_eol()
        return True

    def _do_linewise_operator(self, op: str) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        start_block = cursor.blockNumber()
        end_block = min(start_block + count - 1, self._editor.document().blockCount() - 1)
        self._execute_operator_linewise_blocks(op, start_block, end_block)
        if op in ("d", "c"):
            self._record_edit(op + op, count)

    def _execute_operator_linewise(self, op: str, pos_a: int, pos_b: int) -> None:
        doc = self._editor.document()
        block_a = doc.findBlock(min(pos_a, pos_b)).blockNumber()
        block_b = doc.findBlock(max(pos_a, pos_b)).blockNumber()
        self._execute_operator_linewise_blocks(op, block_a, block_b)

    def _execute_operator_linewise_blocks(self, op: str, start_block: int, end_block: int) -> None:
        doc = self._editor.document()
        first = doc.findBlockByNumber(start_block)
        last = doc.findBlockByNumber(end_block)
        if not first.isValid() or not last.isValid():
            return

        lines = []
        b = first
        for _ in range(end_block - start_block + 1):
            lines.append(b.text())
            b = b.next()
        text = "\n".join(lines)

        if op == "d":
            self._register_text = text
            self._register_linewise = True
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.setPosition(first.position())
            if last.next().isValid():
                cursor.setPosition(last.next().position(), QtGui.QTextCursor.MoveMode.KeepAnchor)
            else:
                cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.End, QtGui.QTextCursor.MoveMode.KeepAnchor
                )
                if first.previous().isValid():
                    cursor.setPosition(first.previous().position())
                    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
                    cursor.setPosition(
                        last.position() + last.length() - 1, QtGui.QTextCursor.MoveMode.KeepAnchor
                    )
            cursor.removeSelectedText()
            cursor.endEditBlock()
            self._editor.setTextCursor(cursor)

        elif op == "c":
            self._register_text = text
            self._register_linewise = True
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.setPosition(first.position())
            if last.next().isValid():
                cursor.setPosition(last.next().position(), QtGui.QTextCursor.MoveMode.KeepAnchor)
            else:
                cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.End, QtGui.QTextCursor.MoveMode.KeepAnchor
                )
            cursor.removeSelectedText()
            cursor.endEditBlock()
            self._editor.setTextCursor(cursor)
            self._set_mode(VimMode.INSERT)

        elif op == "y":
            self._register_text = text
            self._register_linewise = True

        elif op == ">":
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            for bn in range(start_block, end_block + 1):
                blk = doc.findBlockByNumber(bn)
                if blk.isValid():
                    c = QtGui.QTextCursor(blk)
                    c.insertText("    ")
            cursor.endEditBlock()

        elif op == "<":
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            for bn in range(start_block, end_block + 1):
                blk = doc.findBlockByNumber(bn)
                if not blk.isValid():
                    continue
                line = blk.text()
                remove = 0
                for ch in line[:4]:
                    if ch == " ":
                        remove += 1
                    elif ch == "\t":
                        remove += 1
                        break
                    else:
                        break
                if remove > 0:
                    c = QtGui.QTextCursor(blk)
                    c.movePosition(
                        QtGui.QTextCursor.MoveOperation.Right,
                        QtGui.QTextCursor.MoveMode.KeepAnchor,
                        remove,
                    )
                    c.removeSelectedText()
            cursor.endEditBlock()

    def _execute_operator_charwise(self, op: str, start: int, end: int) -> None:
        if start == end:
            return

        if op == "d":
            self._register_text = self._editor.toPlainText()[start:end]
            self._register_linewise = False
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.setPosition(start)
            cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.endEditBlock()
            self._editor.setTextCursor(cursor)

        elif op == "c":
            self._register_text = self._editor.toPlainText()[start:end]
            self._register_linewise = False
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.setPosition(start)
            cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.endEditBlock()
            self._editor.setTextCursor(cursor)
            self._set_mode(VimMode.INSERT)

        elif op == "y":
            self._register_text = self._editor.toPlainText()[start:end]
            self._register_linewise = False

        elif op == ">":
            doc = self._editor.document()
            start_block = doc.findBlock(start).blockNumber()
            end_block = doc.findBlock(end).blockNumber()
            self._execute_operator_linewise_blocks(">", start_block, end_block)

        elif op == "<":
            doc = self._editor.document()
            start_block = doc.findBlock(start).blockNumber()
            end_block = doc.findBlock(end).blockNumber()
            self._execute_operator_linewise_blocks("<", start_block, end_block)

    # --------------------------------------------------------------------- #
    # Awaiting character (f/F/t/T/r)
    # --------------------------------------------------------------------- #

    def _handle_awaited_char(self, ch: str) -> None:
        cmd = self._awaiting_char
        self._awaiting_char = None

        if cmd == "r":
            self._replace_char(ch)
            return

        count = self._get_count()
        self._last_find_char = ch
        self._last_find_forward = cmd in ("f", "t")
        self._last_find_inclusive = cmd in ("f", "F")

        cursor = self._editor.textCursor()
        start_pos = cursor.position()

        if cmd == "f":
            self._find_char_inline(cursor, ch, forward=True, inclusive=True, count=count)
        elif cmd == "F":
            self._find_char_inline(cursor, ch, forward=False, inclusive=True, count=count)
        elif cmd == "t":
            self._find_char_inline(cursor, ch, forward=True, inclusive=False, count=count)
        elif cmd == "T":
            self._find_char_inline(cursor, ch, forward=False, inclusive=False, count=count)

        end_pos = cursor.position()

        if self._pending_operator is not None and start_pos != end_pos:
            op = self._pending_operator
            self._pending_operator = None
            if cmd in ("f", "t") and end_pos > start_pos:
                self._execute_operator_charwise(op, start_pos, end_pos + 1)
            elif cmd in ("F", "T") and end_pos < start_pos:
                self._execute_operator_charwise(op, end_pos, start_pos)
            else:
                lo, hi = min(start_pos, end_pos), max(start_pos, end_pos)
                self._execute_operator_charwise(op, lo, hi + 1)
            self._clamp_cursor_eol()
            return

        if self._pending_operator is not None:
            self._pending_operator = None

        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _find_char_inline(
        self,
        cursor: QtGui.QTextCursor,
        ch: str,
        forward: bool,
        inclusive: bool,
        count: int,
    ) -> None:
        block_text = cursor.block().text()
        col = cursor.positionInBlock()

        if forward:
            search_start = col + 1
            for _ in range(count):
                idx = block_text.find(ch, search_start)
                if idx == -1:
                    return
                search_start = idx + 1
            target_col = idx if inclusive else idx - 1
        else:
            search_end = col - 1
            for _ in range(count):
                idx = block_text.rfind(ch, 0, search_end + 1)
                if idx == -1:
                    return
                search_end = idx - 1
            target_col = idx if inclusive else idx + 1

        target_col = max(0, min(target_col, len(block_text) - 1))
        cursor.setPosition(cursor.block().position() + target_col)

    def _repeat_find_char(self, reverse: bool) -> None:
        if not self._last_find_char:
            return
        count = self._get_count()
        forward = self._last_find_forward if not reverse else not self._last_find_forward
        cursor = self._editor.textCursor()
        self._find_char_inline(
            cursor,
            self._last_find_char,
            forward=forward,
            inclusive=self._last_find_inclusive,
            count=count,
        )
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _replace_char(self, ch: str) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        if col + count > len(block_text):
            return
        cursor.beginEditBlock()
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, count
        )
        cursor.insertText(ch * count)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._record_edit("r", ch)

    # --------------------------------------------------------------------- #
    # Basic motions
    # --------------------------------------------------------------------- #

    def _move_left(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        for _ in range(count):
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        self._editor.setTextCursor(cursor)

    def _move_right(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        for _ in range(count):
            if cursor.positionInBlock() < len(block_text) - 1:
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
        self._editor.setTextCursor(cursor)

    def _move_up(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        for _ in range(count):
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_down(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        for _ in range(count):
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Down)
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_word_forward(self, big: bool = False) -> None:
        count = self._get_count()
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()
        max_pos = doc.characterCount() - 1

        for _ in range(count):
            if pos >= max_pos:
                break
            ch = doc.characterAt(pos)
            if big:
                cur_ws = ch.isspace()
                while pos < max_pos:
                    c = doc.characterAt(pos)
                    if c.isspace() != cur_ws:
                        break
                    pos += 1
                while pos < max_pos and doc.characterAt(pos).isspace():
                    pos += 1
            else:
                cls = _char_class(ch)
                while pos < max_pos:
                    c = doc.characterAt(pos)
                    if _char_class(c) != cls:
                        break
                    pos += 1
                while pos < max_pos and _char_class(doc.characterAt(pos)) == 0:
                    pos += 1

        cursor.setPosition(min(pos, max_pos))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_word_backward(self, big: bool = False) -> None:
        count = self._get_count()
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()

        for _ in range(count):
            if pos <= 0:
                break
            pos -= 1
            while pos > 0 and (
                doc.characterAt(pos).isspace() or doc.characterAt(pos) in ("\n", "\u2029")
            ):
                pos -= 1
            if big:
                while pos > 0:
                    prev = doc.characterAt(pos - 1)
                    if prev.isspace() or prev in ("\n", "\u2029"):
                        break
                    pos -= 1
            else:
                cls = _char_class(doc.characterAt(pos))
                while pos > 0:
                    prev = doc.characterAt(pos - 1)
                    if _char_class(prev) != cls:
                        break
                    pos -= 1

        cursor.setPosition(max(pos, 0))
        self._editor.setTextCursor(cursor)

    def _move_word_end(self, big: bool = False) -> None:
        count = self._get_count()
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()
        max_pos = doc.characterCount() - 1

        for _ in range(count):
            if pos >= max_pos:
                break
            pos += 1
            while pos < max_pos and (
                doc.characterAt(pos).isspace() or doc.characterAt(pos) in ("\n", "\u2029")
            ):
                pos += 1
            if big:
                while pos < max_pos:
                    nxt = doc.characterAt(pos + 1)
                    if nxt.isspace() or nxt in ("\n", "\u2029"):
                        break
                    pos += 1
            else:
                cls = _char_class(doc.characterAt(pos))
                while pos < max_pos:
                    nxt = doc.characterAt(pos + 1)
                    if _char_class(nxt) != cls:
                        break
                    pos += 1

        cursor.setPosition(min(pos, max_pos))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_to_first_non_whitespace(self) -> None:
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        stripped = block_text.lstrip()
        offset = len(block_text) - len(stripped)
        cursor.setPosition(cursor.block().position() + offset)
        self._editor.setTextCursor(cursor)

    def _move_paragraph(self, cursor: QtGui.QTextCursor, forward: bool) -> None:
        block = cursor.block()

        while block.isValid() and block.text().strip() == "":
            block = block.next() if forward else block.previous()
        while block.isValid() and block.text().strip() != "":
            block = block.next() if forward else block.previous()

        if block.isValid():
            cursor.setPosition(block.position())
        elif forward:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        else:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)

    def _move_matching_bracket(self) -> None:
        cursor = self._editor.textCursor()
        pos = cursor.position()
        doc = self._editor.document()
        ch = doc.characterAt(pos)

        bracket_pairs = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{"}
        if ch not in bracket_pairs:
            return

        target = bracket_pairs[ch]
        forward = ch in ("(", "[", "{")
        depth = 0
        scan_pos = pos

        for _ in range(5000):
            scan_pos += 1 if forward else -1
            if scan_pos < 0 or scan_pos >= doc.characterCount():
                return
            scan_ch = doc.characterAt(scan_pos)
            if scan_ch == ch:
                depth += 1
            elif scan_ch == target:
                if depth == 0:
                    cursor.setPosition(scan_pos)
                    self._editor.setTextCursor(cursor)
                    return
                depth -= 1

    def _move_screen_top(self) -> None:
        cursor = self._editor.cursorForPosition(QtCore.QPoint(0, 0))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_screen_middle(self) -> None:
        vp = self._editor.viewport()
        cursor = self._editor.cursorForPosition(QtCore.QPoint(0, vp.height() // 2))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    def _move_screen_bottom(self) -> None:
        vp = self._editor.viewport()
        cursor = self._editor.cursorForPosition(QtCore.QPoint(0, vp.height() - 1))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    # --------------------------------------------------------------------- #
    # Edit commands
    # --------------------------------------------------------------------- #

    def _delete_char_forward(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        avail = len(block_text) - col
        n = min(count, avail)
        if n <= 0:
            return
        cursor.beginEditBlock()
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, n
        )
        self._register_text = cursor.selectedText()
        self._register_linewise = False
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("x", count)

    def _delete_char_backward(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        col = cursor.positionInBlock()
        n = min(count, col)
        if n <= 0:
            return
        cursor.beginEditBlock()
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Left, QtGui.QTextCursor.MoveMode.KeepAnchor, n
        )
        self._register_text = cursor.selectedText()
        self._register_linewise = False
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._record_edit("X", count)

    def _delete_to_eol(self) -> None:
        cursor = self._editor.textCursor()
        col = cursor.positionInBlock()
        block_text = cursor.block().text()
        if col >= len(block_text):
            return
        cursor.beginEditBlock()
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.EndOfBlock, QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        self._register_text = cursor.selectedText()
        self._register_linewise = False
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("D")

    def _yank_line(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        start_block = cursor.blockNumber()
        end_block = min(start_block + count - 1, self._editor.document().blockCount() - 1)
        doc = self._editor.document()
        lines = []
        for bn in range(start_block, end_block + 1):
            blk = doc.findBlockByNumber(bn)
            if blk.isValid():
                lines.append(blk.text())
        self._register_text = "\n".join(lines)
        self._register_linewise = True

    def _paste_after(self) -> None:
        if not self._register_text:
            return
        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        if self._register_linewise:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n" + self._register_text)
        else:
            block_text = cursor.block().text()
            if block_text:
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
            cursor.insertText(self._register_text)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("p")

    def _paste_before(self) -> None:
        if not self._register_text:
            return
        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        if self._register_linewise:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
            cursor.insertText(self._register_text + "\n")
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
        else:
            cursor.insertText(self._register_text)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("P")

    def _join_lines(self) -> None:
        count = self._get_count()
        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        for _ in range(count):
            if not cursor.block().next().isValid():
                break
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor
            )
            next_text = cursor.block().text() if cursor.block().isValid() else ""
            stripped = next_text.lstrip()
            remove_count = len(next_text) - len(stripped)
            if remove_count > 0:
                cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.Right,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                    remove_count,
                )
            cursor.insertText(" ")
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("J", count)

    def _swap_case_char(self) -> None:
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        if col >= len(block_text):
            return
        ch = block_text[col]
        swapped = ch.lower() if ch.isupper() else ch.upper()
        cursor.beginEditBlock()
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(swapped)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()
        self._record_edit("~")

    def _insert_line_below(self) -> None:
        cursor = self._editor.textCursor()
        indent = self._leading_whitespace(cursor.block().text())
        cursor.beginEditBlock()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText("\n" + indent)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)

    def _insert_line_above(self) -> None:
        cursor = self._editor.textCursor()
        indent = self._leading_whitespace(cursor.block().text())
        cursor.beginEditBlock()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText(indent + "\n")
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Up)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
        cursor.endEditBlock()
        self._editor.setTextCursor(cursor)

    # --------------------------------------------------------------------- #
    # Text objects
    # --------------------------------------------------------------------- #

    def _handle_text_object(self, target: str) -> None:
        inner = self._awaiting_text_object == "i"
        self._awaiting_text_object = None
        op = self._pending_operator
        self._pending_operator = None

        result = self._find_text_object(target, inner)
        if result is None:
            return

        start, end = result
        if op is not None:
            self._execute_operator_charwise(op, start, end)
            self._clamp_cursor_eol()
        elif self._mode in (VimMode.VISUAL, VimMode.VISUAL_LINE):
            cursor = self._editor.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self._editor.setTextCursor(cursor)

    def _find_text_object(self, target: str, inner: bool) -> tuple[int, int] | None:
        if target == "w":
            return self._text_object_word(inner)
        if target in ('"', "'"):
            return self._text_object_quote(target, inner)
        if target in ("(", ")", "b"):
            return self._text_object_bracket("(", ")", inner)
        if target in ("{", "}", "B"):
            return self._text_object_bracket("{", "}", inner)
        if target in ("[", "]"):
            return self._text_object_bracket("[", "]", inner)
        return None

    def _text_object_word(self, inner: bool) -> tuple[int, int] | None:
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()
        max_pos = doc.characterCount() - 1

        if pos > max_pos:
            return None

        ch = doc.characterAt(pos)
        cls = _char_class(ch)

        start = pos
        while start > 0 and _char_class(doc.characterAt(start - 1)) == cls:
            start -= 1

        end = pos
        while end < max_pos and _char_class(doc.characterAt(end)) == cls:
            end += 1

        if not inner:
            trail_end = end
            while trail_end < max_pos and _char_class(doc.characterAt(trail_end)) == 0:
                trail_end += 1
            if trail_end > end:
                end = trail_end
            else:
                while start > 0 and _char_class(doc.characterAt(start - 1)) == 0:
                    start -= 1

        return (start, end)

    def _text_object_quote(self, quote: str, inner: bool) -> tuple[int, int] | None:
        cursor = self._editor.textCursor()
        block = cursor.block()
        line = block.text()
        col = cursor.positionInBlock()
        block_pos = block.position()

        pairs: list[tuple[int, int]] = []
        i = 0
        while i < len(line):
            if line[i] == quote:
                if i > 0 and line[i - 1] == "\\":
                    i += 1
                    continue
                start_q = i
                i += 1
                while i < len(line):
                    if line[i] == quote and (i == 0 or line[i - 1] != "\\"):
                        pairs.append((start_q, i))
                        i += 1
                        break
                    i += 1
                else:
                    break
            else:
                i += 1

        for open_q, close_q in pairs:
            if open_q <= col <= close_q:
                if inner:
                    return (block_pos + open_q + 1, block_pos + close_q)
                else:
                    return (block_pos + open_q, block_pos + close_q + 1)

        return None

    def _text_object_bracket(
        self, open_ch: str, close_ch: str, inner: bool
    ) -> tuple[int, int] | None:
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()

        depth = 0
        open_pos = None

        if doc.characterAt(pos) == open_ch:
            open_pos = pos
        else:
            scan = pos - 1
            while scan >= 0:
                ch = doc.characterAt(scan)
                if ch == close_ch:
                    depth += 1
                elif ch == open_ch:
                    if depth == 0:
                        open_pos = scan
                        break
                    depth -= 1
                scan -= 1

        if open_pos is None:
            return None

        depth = 0
        scan = open_pos + 1
        close_pos = None
        max_pos = doc.characterCount()

        while scan < max_pos:
            ch = doc.characterAt(scan)
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                if depth == 0:
                    close_pos = scan
                    break
                depth -= 1
            scan += 1

        if close_pos is None:
            return None

        if inner:
            return (open_pos + 1, close_pos)
        else:
            return (open_pos, close_pos + 1)

    # --------------------------------------------------------------------- #
    # Word end backward (ge / gE)
    # --------------------------------------------------------------------- #

    def _move_word_end_backward(self, big: bool = False) -> None:
        count = self._get_count()
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        pos = cursor.position()

        for _ in range(count):
            if pos <= 0:
                break
            pos -= 1
            while pos > 0 and (
                doc.characterAt(pos).isspace() or doc.characterAt(pos) in ("\n", "\u2029")
            ):
                pos -= 1
            if big:
                while pos > 0:
                    prev = doc.characterAt(pos - 1)
                    if prev.isspace() or prev in ("\n", "\u2029"):
                        break
                    pos -= 1
            else:
                cls = _char_class(doc.characterAt(pos))
                while pos > 0:
                    prev = doc.characterAt(pos - 1)
                    if _char_class(prev) != cls:
                        break
                    pos -= 1

        cursor.setPosition(max(pos, 0))
        self._editor.setTextCursor(cursor)
        self._clamp_cursor_eol()

    # --------------------------------------------------------------------- #
    # Compute word positions (for operator-pending mode)
    # --------------------------------------------------------------------- #

    def _compute_word_forward_pos(
        self,
        pos: int,
        count: int,
        big: bool = False,
    ) -> int:
        doc = self._editor.document()
        max_pos = doc.characterCount() - 1
        for _ in range(count):
            if pos >= max_pos:
                break
            ch = doc.characterAt(pos)
            if big:
                cur_ws = ch.isspace()
                while pos < max_pos:
                    if doc.characterAt(pos).isspace() != cur_ws:
                        break
                    pos += 1
                while pos < max_pos and doc.characterAt(pos).isspace():
                    pos += 1
            else:
                cls = _char_class(ch)
                while pos < max_pos:
                    if _char_class(doc.characterAt(pos)) != cls:
                        break
                    pos += 1
                while pos < max_pos and _char_class(doc.characterAt(pos)) == 0:
                    pos += 1
        return min(pos, max_pos)

    def _compute_word_backward_pos(
        self,
        pos: int,
        count: int,
        big: bool = False,
    ) -> int:
        doc = self._editor.document()
        for _ in range(count):
            if pos <= 0:
                break
            pos -= 1
            while pos > 0 and doc.characterAt(pos).isspace():
                pos -= 1
            if big:
                while pos > 0 and not doc.characterAt(pos - 1).isspace():
                    pos -= 1
            else:
                cls = _char_class(doc.characterAt(pos))
                while pos > 0 and _char_class(doc.characterAt(pos - 1)) == cls:
                    pos -= 1
        return max(pos, 0)

    def _compute_word_end_pos(
        self,
        pos: int,
        count: int,
        big: bool = False,
    ) -> int:
        doc = self._editor.document()
        max_pos = doc.characterCount() - 1
        for _ in range(count):
            if pos >= max_pos:
                break
            pos += 1
            while pos < max_pos and doc.characterAt(pos).isspace():
                pos += 1
            if big:
                while pos < max_pos and not doc.characterAt(pos + 1).isspace():
                    pos += 1
            else:
                cls = _char_class(doc.characterAt(pos))
                while pos < max_pos and _char_class(doc.characterAt(pos + 1)) == cls:
                    pos += 1
        return min(pos, max_pos)

    # --------------------------------------------------------------------- #
    # Dot repeat
    # --------------------------------------------------------------------- #

    def _record_edit(self, *args) -> None:
        self._last_edit = args

    def _replay_last_edit(self) -> None:
        if self._last_edit is None:
            return
        cmd = self._last_edit[0]
        if cmd == "x":
            self._count_prefix = str(self._last_edit[1])
            self._delete_char_forward()
        elif cmd == "X":
            self._count_prefix = str(self._last_edit[1])
            self._delete_char_backward()
        elif cmd == "D":
            self._delete_to_eol()
        elif cmd == "J":
            self._count_prefix = str(self._last_edit[1])
            self._join_lines()
        elif cmd == "~":
            self._swap_case_char()
        elif cmd == "r":
            self._replace_char(self._last_edit[1])
        elif cmd == "dd":
            self._count_prefix = str(self._last_edit[1])
            self._do_linewise_operator("d")
        elif cmd == "cc":
            self._count_prefix = str(self._last_edit[1])
            self._do_linewise_operator("c")
        elif cmd == "p":
            self._paste_after()
        elif cmd == "P":
            self._paste_before()

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #

    def _get_count(self) -> int:
        if self._count_prefix:
            n = int(self._count_prefix)
            self._count_prefix = ""
            return max(1, n)
        return 1

    def _get_count_raw(self) -> int | None:
        """Return the count prefix as an int, or None if no prefix was entered."""
        if self._count_prefix:
            n = int(self._count_prefix)
            self._count_prefix = ""
            return n
        return None

    def _clamp_cursor_eol(self) -> None:
        if self._mode != VimMode.NORMAL:
            return
        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        if not block_text:
            return
        col = cursor.positionInBlock()
        if col >= len(block_text):
            cursor.setPosition(cursor.block().position() + len(block_text) - 1)
            self._editor.setTextCursor(cursor)

    def _word_under_cursor(self) -> str:
        cursor = self._editor.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def _reset_state(self) -> None:
        self._mode = VimMode.NORMAL
        self._count_prefix = ""
        self._pending_operator = None
        self._pending_keys = ""
        self._awaiting_char = None
        self._awaiting_text_object = None
        self._visual_anchor = None
        self._command_buffer = ""
        self._last_edit = None
        self._insert_entry_command = None

    @staticmethod
    def _leading_whitespace(text: str) -> str:
        return text[: len(text) - len(text.lstrip())]
