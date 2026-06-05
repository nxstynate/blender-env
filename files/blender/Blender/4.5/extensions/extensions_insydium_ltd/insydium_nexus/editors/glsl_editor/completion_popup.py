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

"""VSCode-style completion popup widget for the GLSL Script Editor.

Renders a filterable list of ``CompletionItem`` entries with kind icons,
type annotations, and a detail label. Designed to float over a
``QPlainTextEdit`` without stealing keyboard focus.
"""

from __future__ import annotations

import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "vendor")
try:
    from PyQt6.QtCore import (  # noqa: E402
        QModelIndex,
        QPoint,
        QRect,
        QSize,
        QSortFilterProxyModel,
        Qt,
        pyqtSignal,
    )
    from PyQt6.QtGui import (  # noqa: E402
        QColor,
        QFont,
        QFontMetrics,
        QPainter,
        QPainterPath,
        QPixmap,
        QStandardItem,
        QStandardItemModel,
    )
    from PyQt6.QtWidgets import (  # noqa: E402
        QApplication,
        QFrame,
        QLabel,
        QListView,
        QStyle,
        QStyledItemDelegate,
        QVBoxLayout,
    )
except ImportError:
    pass

from .completer import CompletionItem, CompletionKind  # noqa: E402
from .theme import GLSLEditorTheme  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COMPLETION_ITEM_ROLE = Qt.ItemDataRole.UserRole + 1

_ROW_HEIGHT = 24
_ICON_SIZE = 20
_ICON_LEFT_MARGIN = 4
_ICON_RIGHT_MARGIN = 6
_TYPE_RIGHT_PADDING = 8
_MAX_VISIBLE_ITEMS = 10
_MIN_WIDTH = 200
_MAX_WIDTH = 450

_KIND_ICON_MAP: dict[CompletionKind, tuple[str, str]] = {
    CompletionKind.KEYWORD: ("K", "completer_icon_keyword"),
    CompletionKind.TYPE: ("T", "completer_icon_type"),
    CompletionKind.FUNCTION: ("F", "completer_icon_function"),
    CompletionKind.PROPERTY: ("P", "completer_icon_property"),
    CompletionKind.METHOD: ("M", "completer_icon_method"),
    CompletionKind.VARIABLE: ("V", "completer_icon_variable"),
    CompletionKind.NAMESPACE: ("N", "completer_icon_namespace"),
    CompletionKind.SWIZZLE: ("S", "completer_icon_swizzle"),
    CompletionKind.SNIPPET: ("X", "completer_icon_snippet"),
    CompletionKind.DEFINE: ("D", "completer_icon_define"),
}


# ---------------------------------------------------------------------------
# Icon cache
# ---------------------------------------------------------------------------


def _build_icon_cache(
    theme: GLSLEditorTheme,
    font: QFont,
) -> dict[CompletionKind, QPixmap]:
    ratio = 1
    app = QApplication.instance()
    if app is not None:
        ratio = max(1, int(app.devicePixelRatio()))

    px = _ICON_SIZE * ratio
    icon_font = QFont(font)
    icon_font.setPixelSize(int(11 * ratio))
    icon_font.setBold(True)

    cache: dict[CompletionKind, QPixmap] = {}
    for kind, (letter, color_attr) in _KIND_ICON_MAP.items():
        pixmap = QPixmap(px, px)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)

        fg_color = QColor(getattr(theme, color_attr))
        bg_color = QColor(fg_color)
        bg_color.setAlpha(77)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, _ICON_SIZE - 1, _ICON_SIZE - 1, 4.0, 4.0)
        painter.fillPath(path, bg_color)

        painter.setFont(icon_font)
        painter.setPen(fg_color)
        painter.drawText(
            QRect(0, 0, _ICON_SIZE, _ICON_SIZE),
            Qt.AlignmentFlag.AlignCenter,
            letter,
        )
        painter.end()

        cache[kind] = pixmap

    return cache


# ---------------------------------------------------------------------------
# Item delegate
# ---------------------------------------------------------------------------


class CompletionItemDelegate(QStyledItemDelegate):
    def __init__(
        self,
        theme: GLSLEditorTheme,
        icon_cache: dict[CompletionKind, QPixmap],
        editor_font: QFont,
        parent=None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._icon_cache = icon_cache
        self._font = QFont(editor_font)
        self._font.setPixelSize(13)
        self._type_font = QFont(self._font)
        self._type_font.setPixelSize(11)
        self._metrics = QFontMetrics(self._font)
        self._type_metrics = QFontMetrics(self._type_font)

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex):
        item: CompletionItem | None = index.data(_COMPLETION_ITEM_ROLE)
        if item is None:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if is_selected:
            painter.fillRect(rect, QColor(self._theme.completer_selected))
        elif bool(option.state & QStyle.StateFlag.State_MouseOver):
            hover = QColor(self._theme.completer_bg)
            hover = hover.lighter(120)
            painter.fillRect(rect, hover)

        icon_x = rect.left() + _ICON_LEFT_MARGIN
        icon_y = rect.top() + (rect.height() - _ICON_SIZE) // 2
        pixmap = self._icon_cache.get(item.kind)
        if pixmap is not None:
            painter.drawPixmap(icon_x, icon_y, pixmap)

        label_x = rect.left() + _ICON_LEFT_MARGIN + _ICON_SIZE + _ICON_RIGHT_MARGIN

        right_parts: list[tuple[str, QColor]] = []
        if item.access:
            right_parts.append((item.access, QColor(self._theme.completer_access_fg)))
        if item.type_text:
            right_parts.append((item.type_text, QColor(self._theme.completer_type_fg)))

        right_total_width = 0
        for text, _ in right_parts:
            right_total_width += self._type_metrics.horizontalAdvance(text) + 6

        right_x = rect.right() - _TYPE_RIGHT_PADDING - right_total_width

        painter.setFont(self._font)
        painter.setPen(QColor(self._theme.text))
        label_rect = QRect(
            label_x,
            rect.top(),
            max(0, right_x - label_x - 4),
            rect.height(),
        )
        elided = self._metrics.elidedText(
            item.label,
            Qt.TextElideMode.ElideRight,
            label_rect.width(),
        )
        painter.drawText(
            label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided
        )

        painter.setFont(self._type_font)
        draw_x = right_x
        for text, color in reversed(right_parts):
            w = self._type_metrics.horizontalAdvance(text) + 6
            painter.setPen(color)
            painter.drawText(
                QRect(draw_x, rect.top(), w, rect.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
            draw_x += w

        painter.restore()


# ---------------------------------------------------------------------------
# Completion popup
# ---------------------------------------------------------------------------


class CompletionPopup(QFrame):
    item_accepted = pyqtSignal(object)

    def __init__(self, theme: GLSLEditorTheme, editor_font: QFont, parent=None):
        super().__init__(parent)
        self._theme = theme

        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._icon_cache = _build_icon_cache(theme, editor_font)

        self._source_model = QStandardItemModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.setFilterRole(Qt.ItemDataRole.DisplayRole)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)

        self._delegate = CompletionItemDelegate(
            theme,
            self._icon_cache,
            editor_font,
            self,
        )

        self._list_view = QListView(self)
        self._list_view.setModel(self._proxy_model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list_view.setMouseTracking(True)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list_view.setFrameShape(QFrame.Shape.NoFrame)
        self._list_view.setUniformItemSizes(True)
        self._list_view.setAlternatingRowColors(False)
        self._list_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self._list_view.setSpacing(0)
        self._list_view.setViewportMargins(0, 0, 0, 0)

        self._list_view.setStyleSheet(
            f"QListView {{"
            f"  background: {theme.completer_bg};"
            f"  border: none;"
            f"  outline: none;"
            f"}}"
            f"QListView::item {{"
            f"  padding: 0px;"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  background: {theme.completer_bg};"
            f"  width: 8px;"
            f"  margin: 0;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {theme.menu_border};"
            f"  min-height: 20px;"
            f"  border-radius: 4px;"
            f"}}"
            f"QScrollBar::add-line:vertical,"
            f"QScrollBar::sub-line:vertical {{"
            f"  height: 0;"
            f"}}"
            f"QScrollBar::add-page:vertical,"
            f"QScrollBar::sub-page:vertical {{"
            f"  background: none;"
            f"}}"
        )

        self._detail_label = QLabel(self)
        self._detail_label.setWordWrap(True)
        self._detail_label.setMaximumHeight(_ROW_HEIGHT * 2)
        self._detail_label.setStyleSheet(
            f"QLabel {{"
            f"  background: {_darken_hex(theme.completer_bg, 0.9)};"
            f"  color: {theme.completer_detail_fg};"
            f"  padding: 4px 8px;"
            f"  font-size: 11px;"
            f"}}"
        )
        self._detail_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 4, 1, 4)
        layout.setSpacing(0)
        layout.addWidget(self._list_view)
        layout.addWidget(self._detail_label)

        self.setStyleSheet(
            f"CompletionPopup {{"
            f"  background: {theme.completer_bg};"
            f"  border: 1px solid {theme.menu_border};"
            f"  border-radius: 4px;"
            f"}}"
        )

        sel_model = self._list_view.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self._on_current_changed)

        self._list_view.doubleClicked.connect(self._on_double_clicked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_items(self, items: list[CompletionItem], cursor_rect: QRect):
        self._source_model.clear()
        for completion_item in items:
            si = QStandardItem(completion_item.label)
            si.setData(completion_item.label, Qt.ItemDataRole.DisplayRole)
            si.setData(completion_item, _COMPLETION_ITEM_ROLE)
            si.setEditable(False)
            self._source_model.appendRow(si)

        self._proxy_model.setFilterFixedString("")

        if self._proxy_model.rowCount() == 0:
            self.hide()
            return

        self._select_index(0)
        self._position_and_resize(items, cursor_rect)
        self.show()

    def filter_prefix(self, prefix: str):
        self._proxy_model.setFilterFixedString(prefix)
        if self._proxy_model.rowCount() == 0:
            self.hide()
            return
        self._select_index(0)
        self._update_detail_label()
        self.show()

    def accept_current(self) -> CompletionItem | None:
        index = self._list_view.currentIndex()
        if not index.isValid():
            self.hide()
            return None
        item: CompletionItem | None = index.data(_COMPLETION_ITEM_ROLE)
        self.hide()
        if item is not None:
            self.item_accepted.emit(item)
        return item

    def select_next(self):
        self._move_selection(1)

    def select_previous(self):
        self._move_selection(-1)

    def select_page_down(self):
        visible = self._visible_row_count()
        self._move_selection(max(1, visible))

    def select_page_up(self):
        visible = self._visible_row_count()
        self._move_selection(-max(1, visible))

    def is_visible(self) -> bool:
        return self.isVisible()

    def dismiss(self):
        self.hide()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_index(self, row: int):
        idx = self._proxy_model.index(row, 0)
        if idx.isValid():
            self._list_view.setCurrentIndex(idx)
            self._update_detail_label()

    def _move_selection(self, delta: int):
        current = self._list_view.currentIndex()
        total = self._proxy_model.rowCount()
        if total == 0:
            return
        new_row = 0
        if current.isValid():
            new_row = max(0, min(current.row() + delta, total - 1))
        self._select_index(new_row)

    def _visible_row_count(self) -> int:
        viewport_height = self._list_view.viewport().height()
        return max(1, viewport_height // _ROW_HEIGHT)

    def _update_detail_label(self):
        index = self._list_view.currentIndex()
        if not index.isValid():
            self._detail_label.hide()
            return
        item: CompletionItem | None = index.data(_COMPLETION_ITEM_ROLE)
        if item is None or not item.detail:
            self._detail_label.hide()
            return
        self._detail_label.setText(item.detail)
        self._detail_label.show()

    def _position_and_resize(
        self,
        items: list[CompletionItem],
        cursor_rect: QRect,
    ):
        metrics = self._delegate._metrics
        type_metrics = self._delegate._type_metrics

        icon_area = _ICON_LEFT_MARGIN + _ICON_SIZE + _ICON_RIGHT_MARGIN
        max_label_width = 0
        max_right_width = 0
        for ci in items:
            label_w = metrics.horizontalAdvance(ci.label)
            if label_w > max_label_width:
                max_label_width = label_w

            right_w = 0
            if ci.type_text:
                right_w += type_metrics.horizontalAdvance(ci.type_text) + 6
            if ci.access:
                right_w += type_metrics.horizontalAdvance(ci.access) + 6
            if right_w > max_right_width:
                max_right_width = right_w

        content_width = icon_area + max_label_width + 12 + max_right_width + _TYPE_RIGHT_PADDING
        width = max(_MIN_WIDTH, min(_MAX_WIDTH, content_width + 16))

        visible_count = min(len(items), _MAX_VISIBLE_ITEMS)
        list_height = visible_count * _ROW_HEIGHT
        # Single-item lists need extra height so Qt doesn't clip the row
        if visible_count == 1:
            list_height += _ROW_HEIGHT

        detail_height = 0
        if self._detail_label.isVisible():
            detail_height = self._detail_label.sizeHint().height()

        # Layout margins (4+4) + border (1+1)
        frame_overhead = 10
        total_height = list_height + detail_height + frame_overhead

        parent = self.parent()
        if parent is not None:
            global_pos = parent.mapToGlobal(
                QPoint(cursor_rect.left(), cursor_rect.bottom()),
            )
        else:
            global_pos = QPoint(cursor_rect.left(), cursor_rect.bottom())

        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()

        screen_geom = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        x = global_pos.x()
        y = global_pos.y() + 2

        if y + total_height > screen_geom.bottom():
            above_y = global_pos.y() - cursor_rect.height() - total_height - 2
            if above_y >= screen_geom.top():
                y = above_y
            else:
                y = screen_geom.bottom() - total_height

        if x + width > screen_geom.right():
            x = screen_geom.right() - width

        x = max(screen_geom.left(), x)
        y = max(screen_geom.top(), y)

        self.setFixedSize(width, total_height)
        self.move(x, y)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex):
        self._update_detail_label()

    def _on_double_clicked(self, index: QModelIndex):
        if index.isValid():
            self.accept_current()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _darken_hex(hex_color: str, factor: float = 0.85) -> str:
    c = QColor(hex_color)
    return QColor.fromHslF(
        c.hslHueF(),
        c.hslSaturationF(),
        max(0.0, c.lightnessF() * factor),
    ).name()
