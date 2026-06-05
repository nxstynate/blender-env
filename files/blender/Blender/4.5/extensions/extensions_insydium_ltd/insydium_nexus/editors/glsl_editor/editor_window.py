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

"""Main window for the NeXus GLSL Script Editor.

Assembles the toolbar, code editor, find/replace bar, and status bar into
a complete IDE-like window for editing GLSL particle scripts.
"""

from __future__ import annotations

import functools
import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass

from .code_editor import GLSLCodeEditor  # noqa: E402
from .error_panel import ErrorPanel  # noqa: E402
from .find_replace import FindReplaceBar  # noqa: E402
from .minimap import MinimapWidget  # noqa: E402
from .shortcuts import ShortcutReferenceDialog  # noqa: E402
from .templates import GLSL_TEMPLATES  # noqa: E402
from .theme import GLSLEditorTheme, _lighten, create_text_icon  # noqa: E402
from .validator import Severity, get_validator_info, validate_glsl  # noqa: E402
from .vim_command import VimCommandOverlay  # noqa: E402
from .vim_mode import VimMode  # noqa: E402

_ICON_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "icons",
    "images",
    "question",
)
_ICON_PATH = os.path.join(_ICON_DIR, "nx_question_script.png")


class _GoToLineOverlay(QtWidgets.QFrame):
    """Inline overlay for Go to Line, VS Code command palette style."""

    line_accepted = QtCore.pyqtSignal(int)

    def __init__(self, max_line: int, theme, parent=None):
        super().__init__(parent)
        self._max_line = max_line
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setFixedWidth(300)
        self.setFixedHeight(36)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText(f"Go to Line (1-{max_line})...")
        self._input.setValidator(QtGui.QIntValidator(1, max_line, self))
        self._input.returnPressed.connect(self._on_accept)
        layout.addWidget(self._input)

        self.setStyleSheet(
            f"_GoToLineOverlay {{"
            f"  background-color: {theme.line_number_bg};"
            f"  border: 1px solid {theme.toolbar_separator};"
            f"  border-radius: 6px;"
            f"}}"
            f" QLineEdit {{"
            f"  background-color: transparent;"
            f"  color: {theme.text};"
            f"  border: none;"
            f"  font-size: 13px;"
            f"  padding: 2px;"
            f"}}"
        )

    def _on_accept(self):
        text = self._input.text().strip()
        if text:
            line = int(text)
            if 1 <= line <= self._max_line:
                self.line_accepted.emit(line)
        self.hide()

    def show_overlay(self, parent_widget):
        if hasattr(parent_widget, "_editor"):
            self._max_line = parent_widget._editor.blockCount()
        self._input.setValidator(
            QtGui.QIntValidator(1, self._max_line, self),
        )
        self._input.setPlaceholderText(
            f"Go to Line (1-{self._max_line})...",
        )
        self._input.clear()
        pw = parent_widget.width()
        x = (pw - self.width()) // 2
        self.move(x, 60)
        self.show()
        self.raise_()
        self._input.setFocus()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class GLSLEditorWindow(QtWidgets.QWidget):
    """Top-level GLSL script editor window."""

    def __init__(
        self,
        object_name: str,
        item_index: int,
        item_name: str,
        initial_source: str,
        theme: GLSLEditorTheme,
        on_save_callback: callable,
        user_vars: tuple = (),
        refresh_vars_callback: callable | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._object_name = object_name
        self._item_index = item_index
        self._item_name = item_name
        self._on_save_callback = on_save_callback
        self._modified = False
        self._user_vars = user_vars
        self._refresh_vars_callback = refresh_vars_callback

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle(f"GLSL Script - {item_name} [{object_name}]")

        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(_ICON_PATH))

        self.resize(900, 700)
        self.setMinimumSize(600, 400)

        self._settings = QtCore.QSettings("INSYDIUM", "NeXusGLSLEditor")
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._theme = theme

        self._build_ui(theme)
        self._apply_stylesheet(theme)

        self._validation_revision: int = 0
        self._validation_timer = QtCore.QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(500)
        self._validation_timer.timeout.connect(self._run_validation)

        if self._refresh_vars_callback is not None:
            self._var_refresh_timer = QtCore.QTimer(self)
            self._var_refresh_timer.setInterval(2000)
            self._var_refresh_timer.timeout.connect(self._poll_user_vars)
            self._var_refresh_timer.start()

        self._connect_signals()

        vim_enabled = self._settings.value("vim_mode", False, type=bool)
        if vim_enabled:
            self._action_vim_mode.setChecked(True)
            self._editor.set_vim_mode_enabled(True)
            self._btn_vim_mode.setVisible(True)

        self._goto_overlay = _GoToLineOverlay(1, theme, self)
        self._goto_overlay.hide()
        self._goto_overlay.line_accepted.connect(self._on_goto_line_accepted)

        self._editor.setPlainText(initial_source)
        self._modified = False
        self._update_title()
        self._update_status_modified()

        cursor = self._editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor)

        QtCore.QTimer.singleShot(0, self._run_validation)

        self.setWindowOpacity(0.0)
        self._fade_in = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._fade_in.start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, theme: GLSLEditorTheme):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._editor = GLSLCodeEditor(theme, self, user_vars=self._user_vars)
        self._find_bar = FindReplaceBar(self._editor, theme, self)
        self._minimap = MinimapWidget(self._editor, theme, self)

        self._create_actions(theme)
        self._build_menu_bar(theme)
        self._build_toolbar(theme)

        layout.addWidget(self._menu_bar)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._find_bar)

        editor_container = QtWidgets.QWidget()
        editor_container.setObjectName("editorContainer")
        editor_row = QtWidgets.QHBoxLayout(editor_container)
        editor_row.setContentsMargins(0, 0, 0, 0)
        editor_row.setSpacing(0)
        editor_row.addWidget(self._editor, stretch=1)
        editor_row.addWidget(self._minimap)

        self._error_panel = ErrorPanel(theme, self)

        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._splitter.addWidget(editor_container)
        self._splitter.addWidget(self._error_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setChildrenCollapsible(False)
        layout.addWidget(self._splitter, stretch=1)

        self._vim_command_overlay = VimCommandOverlay(theme, self)
        layout.addWidget(self._vim_command_overlay)

        self._build_status_bar()
        layout.addWidget(self._status_bar)

    def _create_actions(self, theme: GLSLEditorTheme):
        find_icon_path = os.path.join(_ICON_DIR, "nx_question_script_search.png")
        if os.path.isfile(find_icon_path):
            find_icon = QtGui.QIcon(find_icon_path)
        else:
            find_icon = create_text_icon("\u2315", 16, theme.text)

        self._action_save = QtGui.QAction(
            create_text_icon("\u2913", 16, theme.text),
            "Save",
            self,
        )
        self._action_save.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self._action_save.setToolTip("Save (Ctrl+S)")
        self._action_save.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_save)

        self._action_close = QtGui.QAction("Close Editor", self)
        self._action_close.setShortcut(QtGui.QKeySequence("Ctrl+W"))
        self._action_close.setToolTip("Close Editor (Ctrl+W)")
        self._action_close.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_close)

        # Edit actions
        self._action_undo = QtGui.QAction(
            create_text_icon("\u21b6", 16, theme.text),
            "Undo",
            self,
        )
        self._action_undo.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        self._action_undo.setToolTip("Undo (Ctrl+Z)")
        self._action_undo.setEnabled(False)
        self._action_undo.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_undo)

        self._action_redo = QtGui.QAction(
            create_text_icon("\u21b7", 16, theme.text),
            "Redo",
            self,
        )
        self._action_redo.setShortcut(QtGui.QKeySequence("Ctrl+Shift+Z"))
        self._action_redo.setToolTip("Redo (Ctrl+Shift+Z)")
        self._action_redo.setEnabled(False)
        self._action_redo.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_redo)

        self._action_find = QtGui.QAction(find_icon, "Find", self)
        self._action_find.setShortcut(QtGui.QKeySequence("Ctrl+F"))
        self._action_find.setToolTip("Find (Ctrl+F)")
        self._action_find.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_find)

        self._action_replace = QtGui.QAction("Replace", self)
        self._action_replace.setShortcut(QtGui.QKeySequence("Ctrl+H"))
        self._action_replace.setToolTip("Replace (Ctrl+H)")
        self._action_replace.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.addAction(self._action_replace)

        self._action_duplicate_line = QtGui.QAction("Duplicate Line", self)
        self._action_duplicate_line.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self._action_duplicate_line.setToolTip("Duplicate Line (Ctrl+D)")
        self._action_duplicate_line.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_duplicate_line)

        self._action_toggle_comment = QtGui.QAction("Toggle Comment", self)
        self._action_toggle_comment.setShortcut(QtGui.QKeySequence("Ctrl+/"))
        self._action_toggle_comment.setToolTip("Toggle Comment (Ctrl+/)")
        self._action_toggle_comment.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_toggle_comment)

        self._action_move_line_up = QtGui.QAction("Move Line Up", self)
        self._action_move_line_up.setShortcut(QtGui.QKeySequence("Alt+Up"))
        self._action_move_line_up.setToolTip("Move Line Up (Alt+Up)")
        self._action_move_line_up.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_move_line_up)

        self._action_move_line_down = QtGui.QAction("Move Line Down", self)
        self._action_move_line_down.setShortcut(QtGui.QKeySequence("Alt+Down"))
        self._action_move_line_down.setToolTip("Move Line Down (Alt+Down)")
        self._action_move_line_down.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_move_line_down)

        # View actions
        self._action_word_wrap = QtGui.QAction("Word Wrap", self)
        self._action_word_wrap.setShortcut(QtGui.QKeySequence("Alt+Z"))
        self._action_word_wrap.setToolTip("Toggle Word Wrap (Alt+Z)")
        self._action_word_wrap.setCheckable(True)
        self._action_word_wrap.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_word_wrap)

        self._action_minimap = QtGui.QAction("Minimap", self)
        self._action_minimap.setShortcut(QtGui.QKeySequence("Ctrl+Shift+M"))
        self._action_minimap.setToolTip("Toggle Minimap (Ctrl+Shift+M)")
        self._action_minimap.setCheckable(True)
        self._action_minimap.setChecked(True)
        self._action_minimap.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_minimap)

        self._action_zoom_in = QtGui.QAction("Zoom In", self)
        self._action_zoom_in.setShortcuts(
            [
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.ZoomIn),
                QtGui.QKeySequence("Ctrl+="),
            ]
        )
        self._action_zoom_in.setToolTip("Zoom In (Ctrl+=)")
        self._action_zoom_in.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_zoom_in)

        self._action_zoom_out = QtGui.QAction("Zoom Out", self)
        self._action_zoom_out.setShortcuts(
            [
                QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.ZoomOut),
                QtGui.QKeySequence("Ctrl+-"),
            ]
        )
        self._action_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        self._action_zoom_out.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_zoom_out)

        self._action_zoom_reset = QtGui.QAction("Reset Zoom", self)
        self._action_zoom_reset.setShortcut(QtGui.QKeySequence("Ctrl+0"))
        self._action_zoom_reset.setToolTip("Reset Zoom (Ctrl+0)")
        self._action_zoom_reset.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_zoom_reset)

        self._action_goto_line = QtGui.QAction("Go to Line...", self)
        self._action_goto_line.setShortcut(QtGui.QKeySequence("Ctrl+G"))
        self._action_goto_line.setToolTip("Go to Line (Ctrl+G)")
        self._action_goto_line.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_goto_line)

        # Code actions
        self._action_format = QtGui.QAction("Auto-Format", self)
        self._action_format.setToolTip("Auto-format code")
        self._action_format.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_format)

        self._action_fold = QtGui.QAction("Fold Region", self)
        self._action_fold.setShortcut(QtGui.QKeySequence("Ctrl+Shift+["))
        self._action_fold.setToolTip("Fold Region (Ctrl+Shift+[)")
        self._action_fold.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.addAction(self._action_fold)

        self._action_unfold = QtGui.QAction("Unfold Region", self)
        self._action_unfold.setShortcut(QtGui.QKeySequence("Ctrl+Shift+]"))
        self._action_unfold.setToolTip("Unfold Region (Ctrl+Shift+])")
        self._action_unfold.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.addAction(self._action_unfold)

        self._template_actions = []
        for i, (name, description, _code) in enumerate(GLSL_TEMPLATES):
            action = QtGui.QAction(f"{name} - {description}", self)
            action.triggered.connect(functools.partial(self._on_template_insert, i))
            self._template_actions.append(action)

        # Help actions
        self._action_shortcuts = QtGui.QAction("Keyboard Shortcuts", self)
        self._action_shortcuts.setToolTip("Keyboard Shortcuts")
        self._action_shortcuts.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self.addAction(self._action_shortcuts)

        self._action_vim_mode = QtGui.QAction("Vim-Lite", self)
        self._action_vim_mode.setCheckable(True)
        self._action_vim_mode.setChecked(False)
        self._action_vim_mode.setShortcutContext(
            QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.addAction(self._action_vim_mode)

    def _build_menu_bar(self, theme: GLSLEditorTheme):
        self._menu_bar = QtWidgets.QMenuBar(self)
        self._menu_bar.setNativeMenuBar(False)

        menu_file = self._menu_bar.addMenu("&File")
        menu_file.addAction(self._action_save)
        menu_file.addSeparator()
        menu_file.addAction(self._action_close)

        menu_edit = self._menu_bar.addMenu("&Edit")
        menu_edit.addAction(self._action_undo)
        menu_edit.addAction(self._action_redo)
        menu_edit.addSeparator()
        menu_edit.addAction(self._action_find)
        menu_edit.addAction(self._action_replace)
        menu_edit.addSeparator()
        menu_edit.addAction(self._action_duplicate_line)
        menu_edit.addAction(self._action_toggle_comment)
        menu_edit.addSeparator()
        menu_edit.addAction(self._action_move_line_up)
        menu_edit.addAction(self._action_move_line_down)

        menu_view = self._menu_bar.addMenu("&View")
        menu_view.addAction(self._action_word_wrap)
        menu_view.addAction(self._action_minimap)
        menu_view.addSeparator()
        menu_view.addAction(self._action_zoom_in)
        menu_view.addAction(self._action_zoom_out)
        menu_view.addAction(self._action_zoom_reset)
        menu_view.addSeparator()
        menu_view.addAction(self._action_goto_line)
        menu_view.addSeparator()
        menu_view.addAction(self._action_vim_mode)

        menu_code = self._menu_bar.addMenu("&Code")
        menu_code.addAction(self._action_format)
        menu_code.addSeparator()
        menu_code.addAction(self._action_fold)
        menu_code.addAction(self._action_unfold)
        menu_code.addSeparator()
        template_menu = menu_code.addMenu("Insert Template")
        for action in self._template_actions:
            template_menu.addAction(action)

        menu_help = self._menu_bar.addMenu("&Help")
        menu_help.addAction(self._action_shortcuts)

    def _build_toolbar(self, theme: GLSLEditorTheme):
        self._toolbar = QtWidgets.QToolBar(self)
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QtCore.QSize(16, 16))
        self._toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._toolbar.addAction(self._action_save)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._action_undo)
        self._toolbar.addAction(self._action_redo)

    def _build_status_bar(self):
        self._status_bar = QtWidgets.QWidget(self)
        self._status_bar.setObjectName("statusBar")
        self._status_bar.setFixedHeight(24)

        layout = QtWidgets.QHBoxLayout(self._status_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn_vim_mode = QtWidgets.QPushButton("")
        self._btn_vim_mode.setObjectName("vimModeIndicator")
        self._btn_vim_mode.setFlat(True)
        self._btn_vim_mode.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._btn_vim_mode.setVisible(False)

        self._btn_position = QtWidgets.QPushButton("Ln 1, Col 1")
        self._btn_modified = QtWidgets.QPushButton("Saved")
        self._btn_diagnostics = QtWidgets.QPushButton("\u2714 No Issues")
        self._btn_tab_info = QtWidgets.QPushButton("Spaces: 4")
        self._btn_zoom = QtWidgets.QPushButton("100%")
        self._btn_encoding = QtWidgets.QPushButton("UTF-8")
        self._btn_language = QtWidgets.QPushButton("GLSL")
        self._btn_language.setToolTip(get_validator_info())

        for btn in (
            self._btn_position,
            self._btn_modified,
            self._btn_diagnostics,
            self._btn_tab_info,
            self._btn_zoom,
            self._btn_encoding,
            self._btn_language,
        ):
            btn.setFlat(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self._btn_vim_mode)
        layout.addWidget(self._btn_position)
        layout.addWidget(self._btn_modified)
        layout.addWidget(self._btn_diagnostics)
        layout.addStretch()
        layout.addWidget(self._btn_tab_info)
        layout.addWidget(self._btn_zoom)
        layout.addWidget(self._btn_encoding)
        layout.addWidget(self._btn_language)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._action_save.triggered.connect(self._on_save)
        self._action_close.triggered.connect(self.close)
        self._action_undo.triggered.connect(self._editor.undo)
        self._action_redo.triggered.connect(self._editor.redo)
        self._action_find.triggered.connect(self._find_bar.show_find)
        self._action_replace.triggered.connect(self._find_bar.show_replace)
        self._action_duplicate_line.triggered.connect(self._editor.duplicate_line)
        self._action_toggle_comment.triggered.connect(self._editor.toggle_comment)
        self._action_move_line_up.triggered.connect(self._editor.move_line_up)
        self._action_move_line_down.triggered.connect(self._editor.move_line_down)
        self._action_word_wrap.triggered.connect(self._on_toggle_word_wrap)
        self._action_minimap.triggered.connect(self._on_toggle_minimap)
        self._action_zoom_in.triggered.connect(self._editor.zoom_in)
        self._action_zoom_out.triggered.connect(self._editor.zoom_out)
        self._action_zoom_reset.triggered.connect(self._editor.zoom_reset)
        self._action_goto_line.triggered.connect(self._on_goto_line)
        self._action_format.triggered.connect(self._on_format)
        self._action_fold.triggered.connect(self._on_fold_current)
        self._action_unfold.triggered.connect(self._on_unfold_current)
        self._action_shortcuts.triggered.connect(self._on_show_shortcuts)

        self._editor.undoAvailable.connect(self._action_undo.setEnabled)
        self._editor.redoAvailable.connect(self._action_redo.setEnabled)
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.cursorPositionChanged.connect(self._on_cursor_changed)
        self._editor.zoom_changed.connect(self._on_zoom_changed)

        self._action_vim_mode.triggered.connect(self._on_toggle_vim_mode)
        self._editor.vim_mode_changed.connect(self._on_vim_mode_changed)
        self._editor.vim_handler.save_requested.connect(self._on_save)
        self._editor.vim_handler.close_requested.connect(self.close)
        self._editor.vim_handler.save_close_requested.connect(self._on_vim_save_close)
        self._editor.vim_handler.force_close_requested.connect(self._on_vim_force_close)
        self._editor.vim_handler.goto_line_requested.connect(self._on_goto_line_accepted)
        self._editor.vim_handler.clear_search_requested.connect(self._on_vim_clear_search)
        self._editor.vim_find_requested.connect(self._find_bar.show_find)
        self._editor.vim_find_word_requested.connect(self._on_vim_search_word)
        self._editor.vim_find_next_requested.connect(self._on_find_next_global)
        self._editor.vim_find_prev_requested.connect(self._on_find_prev_global)

        self._vim_command_overlay.command_accepted.connect(self._on_vim_command)
        self._vim_command_overlay.dismissed.connect(self._on_vim_command_dismissed)
        self._editor.vim_handler.command_text_changed.connect(self._on_vim_command_text)

        self._btn_position.clicked.connect(self._on_goto_line)
        self._btn_zoom.clicked.connect(self._editor.zoom_reset)
        self._btn_diagnostics.clicked.connect(self._on_toggle_error_panel)
        self._error_panel.line_clicked.connect(self._on_error_panel_line_clicked)
        self._error_panel.close_requested.connect(self._on_hide_error_panel)

        self._find_bar.matches_changed.connect(self._on_find_matches_changed)

        self._shortcut_escape = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape),
            self,
        )
        self._shortcut_escape.activated.connect(self._on_escape)

        self._shortcut_find_next = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_F3),
            self,
        )
        self._shortcut_find_next.activated.connect(self._on_find_next_global)

        self._shortcut_find_prev = QtGui.QShortcut(
            QtGui.QKeySequence("Shift+F3"),
            self,
        )
        self._shortcut_find_prev.activated.connect(self._on_find_prev_global)

        self._shortcut_goto_bracket = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+Shift+\\"),
            self,
        )
        self._shortcut_goto_bracket.activated.connect(
            self._editor.goto_matching_bracket,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_save(self):
        result = self._on_save_callback(
            self._object_name,
            self._item_index,
            self._editor.toPlainText(),
        )
        if result is False:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Failed",
                "The save target is no longer valid. The object may have been "
                "renamed, deleted, or the script node was removed.\n\n"
                "Your code is still in the editor — copy it manually before "
                "closing this window.",
            )
            return
        self._modified = False
        self._update_title()
        self._update_status_modified()

    def _on_text_changed(self):
        self._modified = True
        self._update_title()
        self._update_status_modified()
        self._validation_revision += 1
        self._validation_timer.start()

    def _on_cursor_changed(self):
        cursor = self._editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        text = f"Ln {line}, Col {col}"
        if cursor.hasSelection():
            selected = cursor.selectedText()
            line_count = selected.count("\u2029") + 1
            if line_count > 1:
                text += f" | {line_count} lines selected"
            else:
                text += f" | {len(selected)} chars"
        self._btn_position.setText(text)

    def _on_goto_first_diagnostic(self):
        """Jump to the first diagnostic line."""
        diags = self._editor.diagnostics()
        if not diags:
            return
        block = self._editor.document().findBlockByNumber(diags[0].line - 1)
        if block.isValid():
            cursor = self._editor.textCursor()
            cursor.setPosition(block.position())
            self._editor.setTextCursor(cursor)
            self._editor.centerCursor()
            self._editor.setFocus()

    def _on_toggle_error_panel(self):
        """Toggle the error panel visibility."""
        if self._error_panel.isVisible():
            self._last_splitter_sizes = self._splitter.sizes()
            self._error_panel.hide()
        else:
            self._error_panel.show()
            if hasattr(self, "_last_splitter_sizes"):
                self._splitter.setSizes(self._last_splitter_sizes)

    def _on_hide_error_panel(self):
        """Hide the error panel, preserving splitter sizes."""
        self._last_splitter_sizes = self._splitter.sizes()
        self._error_panel.hide()

    def _on_error_panel_line_clicked(self, line: int):
        """Navigate to the clicked diagnostic line."""
        block = self._editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = self._editor.textCursor()
            cursor.setPosition(block.position())
            self._editor.setTextCursor(cursor)
            self._editor.centerCursor()
            self._editor.setFocus()

    def _on_template_insert(self, index: int):
        template_name, _desc, template_code = GLSL_TEMPLATES[index]

        if self._editor.toPlainText().strip():
            result = QtWidgets.QMessageBox.question(
                self,
                "Insert Template",
                f'Replace current content with template "{template_name}"?',
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if result != QtWidgets.QMessageBox.StandardButton.Yes:
                return

        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QtGui.QTextCursor.SelectionType.Document)
        cursor.insertText(template_code)
        cursor.endEditBlock()

    @staticmethod
    def _strip_for_brace_counting(
        line: str,
        in_block_comment: bool,
    ) -> tuple[str, bool]:
        """Remove comment/string content, returning cleaned line and updated state."""
        result = []
        in_string = False
        i = 0

        while i < len(line):
            ch = line[i]

            if in_block_comment:
                if ch == "*" and i + 1 < len(line) and line[i + 1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue

            if in_string:
                if ch == '"':
                    num_backslashes = 0
                    j = i - 1
                    while j >= 0 and line[j] == "\\":
                        num_backslashes += 1
                        j -= 1
                    if num_backslashes % 2 == 0:
                        in_string = False
                i += 1
                continue

            if ch == "/" and i + 1 < len(line):
                if line[i + 1] == "/":
                    break
                if line[i + 1] == "*":
                    in_block_comment = True
                    i += 2
                    continue

            if ch == '"':
                in_string = True
                i += 1
                continue

            result.append(ch)
            i += 1

        return "".join(result), in_block_comment

    def _on_format(self):
        source = self._editor.toPlainText()
        lines = source.split("\n")
        formatted_lines = []
        indent_level = 0
        in_block_comment = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if formatted_lines and formatted_lines[-1] == "":
                    in_block_comment = self._strip_for_brace_counting(
                        "",
                        in_block_comment,
                    )[1]
                    continue
                formatted_lines.append("")
                in_block_comment = self._strip_for_brace_counting(
                    "",
                    in_block_comment,
                )[1]
                continue

            if stripped.startswith("#"):
                formatted_lines.append(stripped)
                in_block_comment = self._strip_for_brace_counting(
                    stripped,
                    in_block_comment,
                )[1]
                continue

            cleaned, in_block_comment = self._strip_for_brace_counting(
                stripped,
                in_block_comment,
            )

            if cleaned.startswith("}") or cleaned.startswith(")"):
                indent_level = max(0, indent_level - 1)

            if stripped.startswith("case ") or stripped.startswith("default:"):
                formatted_lines.append(
                    "    " * max(0, indent_level - 1) + stripped,
                )
            else:
                formatted_lines.append("    " * indent_level + stripped)

            temp = cleaned
            if temp.startswith("}"):
                temp = temp[1:]
            if temp.startswith(")"):
                temp = temp[1:]

            open_braces = temp.count("{") - temp.count("}")
            open_parens = temp.count("(") - temp.count(")")

            indent_level = max(0, indent_level + open_braces + open_parens)

        while formatted_lines and formatted_lines[-1] == "":
            formatted_lines.pop()

        formatted = "\n".join(formatted_lines)
        if source != formatted:
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.select(QtGui.QTextCursor.SelectionType.Document)
            cursor.insertText(formatted)
            cursor.endEditBlock()

    def _on_show_shortcuts(self):
        dialog = ShortcutReferenceDialog(self._theme, self)
        dialog.exec()

    def _on_find_matches_changed(self):
        self._editor.set_find_selections(
            self._find_bar.get_find_selections(),
        )

    def _on_escape(self):
        if self._vim_command_overlay.isVisible():
            self._vim_command_overlay.hide()
            self._editor.setFocus()
            return
        if self._goto_overlay.isVisible():
            self._goto_overlay.hide()
        elif self._find_bar.isVisible():
            self._find_bar.hide_bar()

    def _on_goto_line(self):
        self._goto_overlay.show_overlay(self)

    def _on_goto_line_accepted(self, line_num: int):
        block = self._editor.document().findBlockByNumber(line_num - 1)
        if block.isValid():
            cursor = self._editor.textCursor()
            cursor.setPosition(block.position())
            self._editor.setTextCursor(cursor)
            self._editor.centerCursor()
            self._editor.setFocus()

    def _on_find_next_global(self):
        if self._find_bar.isVisible():
            self._find_bar.find_next()
        else:
            self._find_bar.show_find()

    def _on_find_prev_global(self):
        if self._find_bar.isVisible():
            self._find_bar.find_previous()
        else:
            self._find_bar.show_find()

    def _on_toggle_word_wrap(self):
        if self._action_word_wrap.isChecked():
            self._editor.setWordWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
        else:
            self._editor.setWordWrapMode(QtGui.QTextOption.WrapMode.NoWrap)

    def _on_fold_current(self):
        block_num = self._editor.textCursor().blockNumber()
        self._editor._ensure_fold_regions()
        if (
            block_num in self._editor._fold_regions
            and block_num not in self._editor._folded_blocks
        ):
            self._editor._toggle_fold(block_num)

    def _on_unfold_current(self):
        block_num = self._editor.textCursor().blockNumber()
        if block_num in self._editor._folded_blocks:
            self._editor._toggle_fold(block_num)

    def _on_zoom_changed(self, percentage: int):
        self._btn_zoom.setText(f"{percentage}%")

    def _on_toggle_minimap(self):
        self._minimap.setVisible(self._action_minimap.isChecked())

    def _on_toggle_vim_mode(self):
        enabled = self._action_vim_mode.isChecked()
        self._editor.set_vim_mode_enabled(enabled)
        self._btn_vim_mode.setVisible(enabled)
        if enabled:
            self._on_vim_mode_changed(self._editor.vim_handler.mode)
        self._settings.setValue("vim_mode", enabled)

    def _on_vim_mode_changed(self, mode):
        labels = {
            VimMode.NORMAL: "-- NORMAL --",
            VimMode.INSERT: "-- INSERT --",
            VimMode.VISUAL: "-- VISUAL --",
            VimMode.VISUAL_LINE: "-- V-LINE --",
            VimMode.COMMAND: "-- COMMAND --",
        }
        colors = {
            VimMode.NORMAL: self._theme.vim_normal_bg,
            VimMode.INSERT: self._theme.vim_insert_bg,
            VimMode.VISUAL: self._theme.vim_visual_bg,
            VimMode.VISUAL_LINE: self._theme.vim_visual_bg,
            VimMode.COMMAND: self._theme.vim_command_bg,
        }
        label = labels.get(mode, "-- NORMAL --")
        bg = colors.get(mode, self._theme.vim_normal_bg)
        fg = self._theme.vim_status_fg
        self._btn_vim_mode.setText(label)
        self._btn_vim_mode.setStyleSheet(
            f"#vimModeIndicator {{"
            f"  background-color: {bg};"
            f"  color: {fg};"
            f"  font-weight: bold;"
            f"  border: none;"
            f"  border-radius: 0px;"
            f"  padding: 0px 10px;"
            f"  font-size: 11px;"
            f"}}"
        )

        if mode == VimMode.COMMAND:
            self._vim_command_overlay.show_command()
        else:
            if self._vim_command_overlay.isVisible():
                self._vim_command_overlay.hide()

    def _on_vim_save_close(self):
        self._on_save()
        if not self._modified:
            self.close()

    def _on_vim_force_close(self):
        self._modified = False
        self.close()

    def _on_vim_clear_search(self):
        self._find_bar.hide_bar()

    def _on_vim_search_word(self, word, forward):
        self._find_bar.search_word(word, forward)

    def _on_vim_command(self, command):
        """Execute a vim : command."""
        cmd = command.strip()
        if cmd == "w":
            self._on_save()
        elif cmd == "q":
            self.close()
        elif cmd in ("wq", "x"):
            self._on_save()
            if not self._modified:
                self.close()
        elif cmd == "q!":
            self._modified = False
            self.close()
        elif cmd.isdigit():
            self._on_goto_line_accepted(int(cmd))
        elif cmd in ("noh", "nohlsearch"):
            self._find_bar.hide_bar()
        else:
            self._vim_command_overlay.flash_error()
        self._editor.setFocus()

    def _on_vim_command_dismissed(self):
        """Return focus to editor after command line dismissed."""
        if self._editor.vim_handler.enabled:
            if self._editor.vim_handler.mode == VimMode.COMMAND:
                self._editor.vim_handler._set_mode(VimMode.NORMAL)
        self._editor.setFocus()

    def _on_vim_command_text(self, _text):
        """Update command overlay input field as text changes (for external sync)."""
        pass

    # ------------------------------------------------------------------
    # Window title and status helpers
    # ------------------------------------------------------------------

    def _update_title(self):
        if self._modified:
            self.setWindowTitle(
                f"* GLSL Script - {self._item_name} [{self._object_name}]",
            )
        else:
            self.setWindowTitle(
                f"GLSL Script - {self._item_name} [{self._object_name}]",
            )

    def _update_status_modified(self):
        self._btn_modified.setText("Modified" if self._modified else "Saved")

    def _poll_user_vars(self):
        """Refresh VAR data from Blender and update editor if changed."""
        try:
            fresh = self._refresh_vars_callback(self._object_name)
        except Exception:
            return
        if fresh == self._user_vars:
            return
        self._user_vars = fresh
        self._editor.set_user_vars(fresh)
        self._validation_timer.start()

    def _run_validation(self):
        """Compile the current source and apply diagnostics."""
        revision = self._validation_revision
        source = self._editor.toPlainText()
        diagnostics = validate_glsl(source, user_vars=self._user_vars)

        if self._validation_revision != revision:
            return

        self._editor.set_diagnostics(diagnostics)
        self._update_status_diagnostics(diagnostics)
        self._error_panel.set_diagnostics(diagnostics)
        self._btn_language.setToolTip(get_validator_info())

    def _update_status_diagnostics(self, diagnostics):
        """Update the status bar diagnostic count."""
        errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
        warnings = sum(1 for d in diagnostics if d.severity == Severity.WARNING)

        if errors == 0 and warnings == 0:
            self._btn_diagnostics.setText("\u2714 No Issues")
        else:
            parts: list[str] = []
            if errors:
                parts.append(f"\u2716 {errors}")
            if warnings:
                parts.append(f"\u26a0 {warnings}")
            self._btn_diagnostics.setText("  ".join(parts))

    # ------------------------------------------------------------------
    # Stylesheet
    # ------------------------------------------------------------------

    def _apply_stylesheet(self, theme: GLSLEditorTheme):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.background};
                color: {theme.text};
            }}
            QMenuBar {{
                background-color: {theme.line_number_bg};
                color: {theme.text};
                border-bottom: 1px solid {theme.toolbar_separator};
                padding: 1px 0px;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 4px 8px;
                border-radius: 3px;
                margin: 1px 2px;
            }}
            QMenuBar::item:selected {{
                background-color: {theme.current_line};
            }}
            QMenuBar::item:pressed {{
                background-color: {theme.selection};
            }}
            QMenu {{
                background-color: {theme.menu_bg};
                color: {theme.text};
                border: 1px solid {theme.menu_border};
                padding: 4px 0px;
            }}
            QMenu::item {{
                padding: 5px 30px 5px 20px;
                border-radius: 3px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.menu_hover};
            }}
            QMenu::item:disabled {{
                color: {theme.disabled_fg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.toolbar_separator};
                margin: 4px 8px;
            }}
            QToolBar {{
                background-color: {theme.line_number_bg};
                border: none;
                border-bottom: 1px solid {theme.toolbar_separator};
                spacing: 2px;
                padding: 2px 4px;
            }}
            QToolBar::separator {{
                width: 1px;
                background-color: {theme.toolbar_separator};
                margin: 4px 2px;
            }}
            QToolButton {{
                background-color: transparent;
                color: {theme.text};
                border: none;
                border-radius: 4px;
                padding: 4px 6px;
                margin: 1px;
            }}
            QToolButton:hover {{
                background-color: {theme.hover_bg};
            }}
            QToolButton:pressed {{
                background-color: {theme.selection};
            }}
            QToolButton:disabled {{
                color: {theme.disabled_fg};
            }}
            QPushButton {{
                background-color: transparent;
                color: {theme.text};
                border: 1px solid {theme.toolbar_separator};
                border-radius: 4px;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.hover_bg};
                border-color: {theme.focus_border};
            }}
            QPushButton:pressed {{
                background-color: {theme.selection};
            }}
            QPushButton:disabled {{
                color: {theme.disabled_fg};
            }}
            QLineEdit {{
                background-color: {theme.find_input_bg};
                color: {theme.text};
                border: 1px solid {theme.find_input_border};
                border-radius: 4px;
                padding: 3px 8px;
                selection-background-color: {theme.selection};
            }}
            QLineEdit:focus {{
                border-color: {theme.find_input_focus_border};
            }}
            QCheckBox {{
                color: {theme.text};
                spacing: 4px;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 12px;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background-color: transparent;
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {theme.line_number_fg};
                min-width: 20px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {theme.line_number_active_fg};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            QToolTip {{
                background-color: {theme.menu_bg};
                color: {theme.text};
                border: 1px solid {theme.menu_border};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            #statusBar {{
                background-color: {theme.status_bar_bg};
                border-top: 1px solid {_lighten(theme.status_bar_bg, 1.15)};
            }}
            #statusBar QPushButton {{
                background-color: transparent;
                color: {theme.status_bar_fg};
                border: none;
                border-radius: 0px;
                padding: 0px 8px;
                font-size: 12px;
            }}
            #statusBar QPushButton:hover {{
                background-color: {theme.status_bar_hover};
            }}
            #statusBar QPushButton:pressed {{
                background-color: {theme.status_bar_active};
            }}
            QMessageBox {{
                background-color: {theme.background};
                color: {theme.text};
            }}
            QMessageBox QPushButton {{
                min-width: 60px;
                padding: 4px 12px;
            }}
            #editorContainer {{
                background: transparent;
            }}
            QSplitter::handle:vertical {{
                background-color: {theme.error_panel_border};
                height: 3px;
            }}
            QSplitter::handle:vertical:hover {{
                background-color: {theme.focus_border};
            }}
            #errorPanel {{
                background-color: {theme.error_panel_bg};
            }}
            #errorPanel QListWidget {{
                background-color: {theme.error_panel_bg};
                border: none;
                outline: none;
            }}
            #errorPanel QListWidget::item {{
                padding: 0px;
                border: none;
            }}
            #errorPanel QListWidget::item:hover {{
                background-color: {theme.error_panel_row_hover};
            }}
            #errorPanel QListWidget::item:selected {{
                background-color: {theme.error_panel_row_hover};
            }}
        """)

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._modified:
            result = QtWidgets.QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save changes to script before closing?",
                (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
                    | QtWidgets.QMessageBox.StandardButton.Cancel
                ),
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if result == QtWidgets.QMessageBox.StandardButton.Yes:
                self._on_save()
            elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._validation_timer.stop()
        self._settings.setValue("geometry", self.saveGeometry())
        event.accept()
