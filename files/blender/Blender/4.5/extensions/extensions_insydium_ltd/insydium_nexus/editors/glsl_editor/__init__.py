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

"""NeXus GLSL Script Editor package.

Provides a PyQt6-based code editor window for authoring GLSL particle
scripts.  Use ``open_glsl_editor()`` to open or focus an editor for a
specific question modifier item.

Window Registry
---------------
Only one editor window per (object_name, item_index) pair is allowed.
Re-opening an already-visible editor brings it to focus.  All open
editors can be closed at once via ``close_all_glsl_editors()``.
"""

from __future__ import annotations

from .editor_window import GLSLEditorWindow

_open_editors: dict[tuple[str, int], GLSLEditorWindow] = {}


def open_glsl_editor(
    object_name: str,
    item_index: int,
    item_name: str,
    initial_source: str,
    theme,
    on_save_callback: callable,
    user_vars: tuple = (),
    refresh_vars_callback: callable | None = None,
) -> None:
    """Open a GLSL editor window, or focus the existing one for this item."""
    key = (object_name, item_index)

    existing = _open_editors.get(key)
    if existing is not None:
        try:
            existing.raise_()
            existing.activateWindow()
            return
        except RuntimeError:
            del _open_editors[key]

    window = GLSLEditorWindow(
        object_name,
        item_index,
        item_name,
        initial_source,
        theme,
        on_save_callback,
        user_vars=user_vars,
        refresh_vars_callback=refresh_vars_callback,
    )
    _open_editors[key] = window

    window.destroyed.connect(lambda _obj, _key=key: _open_editors.pop(_key, None))

    window.show()


def close_all_glsl_editors() -> None:
    """Close every open GLSL editor window."""
    for window in list(_open_editors.values()):
        try:
            window.close()
        except RuntimeError:
            pass
    _open_editors.clear()


def close_editor_for_item(object_name: str, item_index: int) -> None:
    """Close the editor window for a specific item, if one is open."""
    key = (object_name, item_index)
    window = _open_editors.get(key)
    if window is not None:
        try:
            window.close()
        except RuntimeError:
            pass
        _open_editors.pop(key, None)


def close_all_editors_for_object(object_name: str) -> None:
    """Close all editors associated with the given object."""
    keys_to_close = [k for k in _open_editors if k[0] == object_name]
    for key in keys_to_close:
        win = _open_editors.pop(key, None)
        if win is not None:
            try:
                win.close()
            except RuntimeError:
                pass


def has_open_editors() -> bool:
    """Return True if any GLSL editor windows are currently open."""
    return bool(_open_editors)
