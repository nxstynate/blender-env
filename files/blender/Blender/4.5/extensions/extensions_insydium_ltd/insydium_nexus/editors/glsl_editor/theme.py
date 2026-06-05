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

"""Color theme definitions for the GLSL Script Editor.

Provides a ``GLSLEditorTheme`` dataclass with all colors needed by the editor
widget, syntax highlighter, and gutter.  Two factory helpers build themes:

* ``create_theme()`` -- standalone dark-mode defaults (no bpy dependency).
* ``create_theme_from_blender(colors)`` -- derives colors from the dict
  returned by ``_get_blender_colors()`` in ``operators/__init__.py``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
except ImportError:
    pass


def _hex(color: QtGui.QColor) -> str:
    return color.name()


def _darken(hex_color: str, factor: float = 0.85) -> str:
    """Return *hex_color* darkened by *factor* (0-1, lower is darker)."""
    c = QtGui.QColor(hex_color)
    return QtGui.QColor.fromHslF(
        c.hslHueF(),
        c.hslSaturationF(),
        max(0.0, c.lightnessF() * factor),
    ).name()


def _lighten(hex_color: str, factor: float = 1.2) -> str:
    """Return *hex_color* lightened by *factor* (>1 is lighter)."""
    c = QtGui.QColor(hex_color)
    return QtGui.QColor.fromHslF(
        c.hslHueF(),
        c.hslSaturationF(),
        min(1.0, c.lightnessF() * factor),
    ).name()


def _alpha_blend(hex_color: str, alpha: int) -> str:
    """Return *hex_color* with the given alpha (0-255) as #aarrggbb."""
    c = QtGui.QColor(hex_color)
    c.setAlpha(alpha)
    r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
    return f"#{a:02x}{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# Theme dataclass
# ---------------------------------------------------------------------------


@dataclass
class GLSLEditorTheme:
    """All colors used by the GLSL code editor."""

    # -- Editor chrome -------------------------------------------------------
    background: str = "#1e1e1e"
    current_line: str = "#2a2d2e"
    line_number_bg: str = "#1e1e1e"
    line_number_fg: str = "#858585"
    line_number_active_fg: str = "#c6c6c6"
    selection: str = "#264f78"
    text: str = "#d4d4d4"

    # -- Syntax highlighting -------------------------------------------------
    keyword: str = "#569cd6"
    type_color: str = "#4ec9b0"
    builtin_func: str = "#dcdcaa"
    number: str = "#b5cea8"
    string: str = "#ce9178"
    comment: str = "#6a9955"
    preprocessor: str = "#c586c0"

    # -- Bracket matching ----------------------------------------------------
    bracket_match: str = "#c586c0"
    bracket_mismatch: str = "#f44747"

    # -- Error / diagnostics -------------------------------------------------
    error_underline: str = "#f44747"
    warning_underline: str = "#cca700"
    gutter_error: str = "#f44747"
    gutter_warning: str = "#cca700"

    # -- Find ----------------------------------------------------------------
    find_match: str = "#515c6a"
    find_match_current: str = "#613214"

    # -- UI chrome -----------------------------------------------------------
    toolbar_separator: str = "#404040"

    # -- Occurrence highlighting -----------------------------------------------
    occurrence_highlight: str = "#264f78"

    # -- Indent guides ---------------------------------------------------------
    indent_guide: str = "#404040"
    indent_guide_active: str = "#707070"

    # -- Completer popup -------------------------------------------------------
    completer_bg: str = "#252526"
    completer_selected: str = "#062f4a"

    # -- Completer popup - item rendering --------------------------------------
    completer_type_fg: str = "#858585"
    completer_access_fg: str = "#6a6a6a"
    completer_detail_fg: str = "#9d9d9d"

    # -- Completer popup - kind icons ------------------------------------------
    completer_icon_keyword: str = "#569cd6"
    completer_icon_type: str = "#4ec9b0"
    completer_icon_function: str = "#dcdcaa"
    completer_icon_property: str = "#9cdcfe"
    completer_icon_method: str = "#dcdcaa"
    completer_icon_variable: str = "#9cdcfe"
    completer_icon_namespace: str = "#c586c0"
    completer_icon_swizzle: str = "#d4d4d4"
    completer_icon_snippet: str = "#d4d4d4"
    completer_icon_define: str = "#d19a66"

    # -- Snippet tabstops ------------------------------------------------------
    snippet_tabstop_active: str = "#264f78"
    snippet_tabstop_inactive: str = "#374754"

    # -- Signature help widget -------------------------------------------------
    signature_bg: str = "#252526"
    signature_border: str = "#454545"
    signature_fg: str = "#cccccc"
    signature_active_param: str = "#dcdcaa"
    signature_type_fg: str = "#4ec9b0"

    # -- Code folding ----------------------------------------------------------
    fold_marker: str = "#858585"
    fold_marker_hover: str = "#c6c6c6"
    fold_line: str = "#404040"
    fold_indicator_text: str = "#9e9e9e"

    # -- Minimap ---------------------------------------------------------------
    minimap_bg: str = "#1a1a1a"
    minimap_viewport: str = "#ffffff30"
    minimap_text: str = "#d4d4d4"

    # -- Status bar ------------------------------------------------------------
    status_bar_bg: str = "#007acc"
    status_bar_fg: str = "#ffffff"
    status_bar_hover: str = "#1c8cd9"
    status_bar_active: str = "#005f99"

    # -- Error panel -----------------------------------------------------------
    error_panel_bg: str = "#1e1e1e"
    error_panel_row_hover: str = "#2a2d2e"
    error_panel_border: str = "#404040"
    error_panel_location_fg: str = "#858585"

    # -- Interactive states ----------------------------------------------------
    hover_bg: str = "#2a2d2e"
    focus_border: str = "#007acc"
    disabled_fg: str = "#5a5a5a"

    # -- Menus and tooltips ----------------------------------------------------
    menu_bg: str = "#252526"
    menu_border: str = "#454545"
    menu_hover: str = "#094771"

    # -- Find bar --------------------------------------------------------------
    find_input_bg: str = "#3c3c3c"
    find_input_border: str = "#3c3c3c"
    find_input_focus_border: str = "#007acc"

    # -- Vim mode indicator ----------------------------------------------------
    vim_normal_bg: str = "#007acc"  # Blue (matches VS Code vim / status bar)
    vim_insert_bg: str = "#16825d"  # Green (VS Code vim insert color)
    vim_visual_bg: str = "#c2590a"  # Orange (VS Code vim visual color)
    vim_command_bg: str = "#007acc"  # Blue (same as normal)
    vim_replace_bg: str = "#8b3e6f"  # Magenta (future REPLACE mode)
    vim_status_fg: str = "#ffffff"  # White text on all mode indicators

    # -- Derived QColor instances (populated by __post_init__) ---------------
    _q_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def qcolor(self, attr: str) -> QtGui.QColor:
        """Return a cached ``QColor`` for the named theme attribute."""
        cached = self._q_cache.get(attr)
        if cached is not None:
            return cached
        value = getattr(self, attr)
        qc = QtGui.QColor(value)
        self._q_cache[attr] = qc
        return qc


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def create_theme() -> GLSLEditorTheme:
    """Return a theme with sensible dark-mode defaults."""
    return GLSLEditorTheme()


def create_theme_from_blender(blender_colors: dict[str, str]) -> GLSLEditorTheme:
    """Derive a ``GLSLEditorTheme`` from Blender's active theme colors.

    *blender_colors* is the dict returned by ``_get_blender_colors()`` with
    keys: bg, bg_field, bg_btn, bg_active, accent, text, text_label, border,
    window_bg.
    """
    bg = blender_colors.get("bg", "#1e1e1e")
    accent = blender_colors.get("accent", "#264f78")
    text = blender_colors.get("text", "#d4d4d4")
    bg_field = blender_colors.get("bg_field", bg)

    editor_bg = _darken(bg_field, 0.80)
    current_line = _lighten(editor_bg, 1.12)
    gutter_bg = editor_bg
    gutter_fg = _lighten(editor_bg, 1.8)
    gutter_active = _lighten(gutter_fg, 1.5)
    selection_bg = _alpha_blend(accent, 160)
    find_bg = _lighten(editor_bg, 1.6)

    find_current_bg = _lighten(accent, 1.4)
    separator_color = _lighten(editor_bg, 1.3)

    occurrence_bg = _alpha_blend(accent, 100)
    guide_color = _lighten(editor_bg, 1.5)
    guide_active_color = _lighten(editor_bg, 2.0)
    completer_bg_color = _darken(editor_bg, 0.9)
    completer_selected_color = _darken(accent, 0.7)

    completer_type_fg_color = _darken(text, 0.4)
    completer_access_fg_color = _darken(text, 0.55)
    completer_detail_fg_color = _darken(text, 0.3)

    minimap_bg_color = _darken(editor_bg, 0.85)
    minimap_viewport_color = _alpha_blend(text, 25)

    keyword_color = GLSLEditorTheme.keyword
    type_color = GLSLEditorTheme.type_color
    builtin_func_color = GLSLEditorTheme.builtin_func
    preprocessor_color = GLSLEditorTheme.preprocessor
    property_color = _lighten(keyword_color, 1.3)
    variable_color = property_color

    return GLSLEditorTheme(
        background=editor_bg,
        current_line=current_line,
        line_number_bg=gutter_bg,
        line_number_fg=gutter_fg,
        line_number_active_fg=gutter_active,
        selection=selection_bg,
        text=text,
        bracket_match=accent,
        find_match=find_bg,
        find_match_current=find_current_bg,
        toolbar_separator=separator_color,
        occurrence_highlight=occurrence_bg,
        indent_guide=guide_color,
        indent_guide_active=guide_active_color,
        completer_bg=completer_bg_color,
        completer_selected=completer_selected_color,
        completer_type_fg=completer_type_fg_color,
        completer_access_fg=completer_access_fg_color,
        completer_detail_fg=completer_detail_fg_color,
        completer_icon_keyword=keyword_color,
        completer_icon_type=type_color,
        completer_icon_function=builtin_func_color,
        completer_icon_property=property_color,
        completer_icon_method=builtin_func_color,
        completer_icon_variable=variable_color,
        completer_icon_namespace=preprocessor_color,
        completer_icon_swizzle=text,
        completer_icon_snippet=text,
        completer_icon_define=_lighten(builtin_func_color, 1.1),
        snippet_tabstop_active=_alpha_blend(accent, 160),
        snippet_tabstop_inactive=_alpha_blend(accent, 80),
        signature_bg=completer_bg_color,
        signature_border=_lighten(editor_bg, 1.5),
        signature_fg=text,
        signature_active_param=builtin_func_color,
        signature_type_fg=type_color,
        fold_marker=gutter_fg,
        fold_marker_hover=gutter_active,
        fold_line=separator_color,
        fold_indicator_text=_lighten(gutter_fg, 1.2),
        minimap_bg=minimap_bg_color,
        minimap_viewport=minimap_viewport_color,
        minimap_text=text,
        status_bar_bg=accent,
        status_bar_fg="#ffffff",
        status_bar_hover=_lighten(accent, 1.2),
        status_bar_active=_darken(accent, 0.8),
        hover_bg=current_line,
        focus_border=accent,
        disabled_fg=_lighten(editor_bg, 1.6),
        menu_bg=_lighten(editor_bg, 1.1),
        menu_border=_lighten(editor_bg, 1.5),
        menu_hover=_darken(accent, 0.85),
        find_input_bg=_lighten(editor_bg, 1.35),
        find_input_border=_lighten(editor_bg, 1.35),
        find_input_focus_border=accent,
        error_panel_bg=editor_bg,
        error_panel_row_hover=current_line,
        error_panel_border=separator_color,
        error_panel_location_fg=gutter_fg,
    )


# ---------------------------------------------------------------------------
# Shared icon helper
# ---------------------------------------------------------------------------


def create_text_icon(
    text: str,
    size: int,
    color: str,
    font_family: str = "",
) -> QtGui.QIcon:
    """Render a text glyph into a QIcon at the given size and color."""
    ratio = 1
    app = QtWidgets.QApplication.instance()
    if app is not None:
        ratio = int(app.devicePixelRatio())
    px_size = size * max(1, ratio)
    pixmap = QtGui.QPixmap(px_size, px_size)
    pixmap.setDevicePixelRatio(max(1, ratio))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    if font_family:
        font = QtGui.QFont(font_family, int(size * 0.65))
    else:
        font = QtGui.QFont()
        font.setPointSize(int(size * 0.65))
    painter.setFont(font)
    painter.setPen(QtGui.QColor(color))
    painter.drawText(
        QtCore.QRect(0, 0, size, size),
        QtCore.Qt.AlignmentFlag.AlignCenter,
        text,
    )
    painter.end()
    return QtGui.QIcon(pixmap)
