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

from __future__ import annotations

import os
import sys
import ctypes

import numpy as np

from ..libs import theron

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

    _HAS_PYQT = True
except ImportError:
    _HAS_PYQT = False


_win = None

_OPTS = list(theron.PARTICLE_PROPERTY_NAMES.values()) + ["Speed"]
_DEFAULT_OPTS = ["ID", "Age", "Distance", "Mass", "Radius", "Speed"]

_INV_OPTS_LOOKUP = {v: k for k, v in theron.PARTICLE_PROPERTY_NAMES.items()} | {
    "Speed": theron.TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY
}
_PARTICLE_FETCH_PROPS = []
_COLUMNS = []

# Local numpy array cache of particle data for display in the console
_PARTICLE_COUNT = 0
_CACHED_PARTICLE_DATA = []
_MIN_MAX_DATA = []


def update_particle_data(pipeline: int):
    """
    Triggers a refresh of the cached particle data for the console.

    Args:
        pipeline: The modifier pipeline to fetch particle data from.
    """

    global _PARTICLE_COUNT, _CACHED_PARTICLE_DATA, _MIN_MAX_DATA

    if _win is None or _win.data_model is None:
        return

    _CACHED_PARTICLE_DATA = []
    _MIN_MAX_DATA = []

    _PARTICLE_COUNT = theron.get_particle_count(pipeline)
    if _PARTICLE_COUNT > 0:
        # Get the enabled particle properties from theron
        prop_data = {}
        for prop in _PARTICLE_FETCH_PROPS:
            data_ptr = theron.get_particle_property_data(pipeline, prop)
            if data_ptr is None or data_ptr.value is None:
                continue

            dtype = theron.PARTICLE_PROPERTY_TYPES[prop]
            nbytes = _PARTICLE_COUNT * np.dtype(dtype).itemsize
            buf = (ctypes.c_char * nbytes).from_address(data_ptr.value)

            prop_data[prop] = np.frombuffer(buf, dtype=dtype, count=_PARTICLE_COUNT)

        # Build cache data - some require calculation
        for col in _COLUMNS:
            if col == "Speed":
                vel_dat = prop_data.get(
                    theron.TrParticleProperty.TR_PARTICLE_PROPERTY_VELOCITY, None
                )
                if vel_dat is None:
                    _CACHED_PARTICLE_DATA.append(None)
                else:
                    speed_dat = np.linalg.norm(vel_dat[:, :3], axis=1)
                    _CACHED_PARTICLE_DATA.append(speed_dat)
            else:
                prop = _INV_OPTS_LOOKUP[col]
                if prop not in prop_data:
                    _CACHED_PARTICLE_DATA.append(None)
                else:
                    _CACHED_PARTICLE_DATA.append(prop_data[prop].copy())

            last_data = _CACHED_PARTICLE_DATA[-1]
            if last_data is not None:
                _MIN_MAX_DATA.append((last_data.min(axis=0), last_data.max(axis=0)))
            else:
                _MIN_MAX_DATA.append(None)

    # Refresh Qt dialog
    _win.data_model.layoutChanged.emit()
    _win.min_max_model.layoutChanged.emit()
    _win.count_label.setText(f"{_PARTICLE_COUNT} particles")


def has_open_window():
    return _win is not None


if _HAS_PYQT:

    class _ParticleModel(QtCore.QAbstractTableModel):
        def rowCount(self, parent=QtCore.QModelIndex()):
            return 0 if parent.isValid() else _PARTICLE_COUNT

        def columnCount(self, parent=QtCore.QModelIndex()):
            return 0 if parent.isValid() else len(_COLUMNS)

        def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
            if not index.isValid():
                return None
            col = index.column()
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                dat = _CACHED_PARTICLE_DATA[col]
                if dat is None:
                    return "N/A"
                return str(dat[index.row()])
            if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
                return int(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            return None

        def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
            if (
                orientation == QtCore.Qt.Orientation.Horizontal
                and role == QtCore.Qt.ItemDataRole.DisplayRole
            ):
                return _COLUMNS[section]
            return None

    class _MinMaxModel(QtCore.QAbstractTableModel):
        _LABELS = ("Min", "Max")

        def rowCount(self, parent=QtCore.QModelIndex()):
            return 0 if parent.isValid() else 2

        def columnCount(self, parent=QtCore.QModelIndex()):
            return 0 if parent.isValid() else len(_COLUMNS)

        def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
            if not index.isValid() or len(_MIN_MAX_DATA) == 0:
                return None
            col = index.column()
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                if _MIN_MAX_DATA[col] is None:
                    return "N/A"
                return str(_MIN_MAX_DATA[col][index.row()])
            if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
                return int(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            if role == QtCore.Qt.ItemDataRole.BackgroundRole:
                return QtGui.QColor(50, 52, 62)
            if role == QtCore.Qt.ItemDataRole.ForegroundRole:
                return QtGui.QColor(200, 200, 210)
            if role == QtCore.Qt.ItemDataRole.FontRole:
                f = QtGui.QFont()
                f.setBold(True)
                return f
            return None

        def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
            if (
                orientation == QtCore.Qt.Orientation.Vertical
                and role == QtCore.Qt.ItemDataRole.DisplayRole
            ):
                return self._LABELS[section]
            return None

    class ParticleConsoleWindow(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._setup_ui()

        def _setup_ui(self):
            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            tabs = QtWidgets.QTabWidget()
            outer.addWidget(tabs)

            particle_tab = QtWidgets.QWidget()
            self._build_particle_tab(particle_tab)
            tabs.addTab(particle_tab, "Particle Data")

            options_tab = QtWidgets.QWidget()
            self._build_options_tab(options_tab)
            tabs.addTab(options_tab, "Options")

        def _build_particle_tab(self, widget):

            layout = QtWidgets.QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)

            self.count_label = QtWidgets.QLabel(f"{_PARTICLE_COUNT} particles")
            layout.addWidget(self.count_label)

            self.data_model = _ParticleModel()

            self._table = QtWidgets.QTableView()
            self._table.setModel(self.data_model)
            self._table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
            self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            self._table.setAlternatingRowColors(True)
            self._table.setShowGrid(True)

            # tvh = self._table.verticalHeader()
            # tvh.setFixedWidth(_VH_WIDTH)
            # tvh.setDefaultSectionSize(self._ROW_H)

            thh = self._table.horizontalHeader()
            thh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
            thh.setHighlightSections(False)

            layout.addWidget(self._table, stretch=1)

            # separator
            layout.addWidget(QtWidgets.QFrame())

            self.min_max_model = _MinMaxModel()

            self._summary = QtWidgets.QTableView()
            self._summary.setModel(self.min_max_model)
            self._summary.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            self._summary.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self._summary.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            self._summary.setShowGrid(True)

            shh = self._summary.horizontalHeader()
            shh.hide()
            shh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)

            self._summary.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self._summary.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Height: 2 rows + top/bottom frame border (1px each)
            # self._summary.setFixedHeight(self._ROW_H * 2 + self._summary.frameWidth() * 2)

            layout.addWidget(self._summary)

            # Sync horizontal scroll so summary tracks main when columns are narrow
            self._table.horizontalScrollBar().valueChanged.connect(
                self._summary.horizontalScrollBar().setValue
            )

        def _build_request_props(self):

            global _PARTICLE_FETCH_PROPS, _COLUMNS
            _PARTICLE_FETCH_PROPS.clear()
            _COLUMNS.clear()

            tmp_cols = set()
            props_set = set()
            for c in self._checkboxes:
                if c.isChecked():
                    props_set.add(_INV_OPTS_LOOKUP[c.text()])
                    tmp_cols.add(c.text())

            _PARTICLE_FETCH_PROPS = list(props_set)

            # Use preferred column order, ID first then alphabetical
            if "ID" in tmp_cols:
                _COLUMNS.append("ID")
            _COLUMNS.extend(sorted(tmp_cols - {"ID"}))

        def _build_options_tab(self, widget):
            layout = QtWidgets.QVBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

            container = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(container)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(6)

            self._checkboxes = []
            for i, name in enumerate(_OPTS):
                cb = QtWidgets.QCheckBox(name)
                cb.toggled.connect(lambda _: self._build_request_props())
                self._checkboxes.append(cb)

                if name in _DEFAULT_OPTS:
                    cb.setChecked(True)
                else:
                    cb.setChecked(False)

                grid.addWidget(cb, i // 4, i % 4)

            grid.setRowStretch(grid.rowCount(), 1)
            scroll.setWidget(container)
            layout.addWidget(scroll, stretch=1)

            btn_row = QtWidgets.QHBoxLayout()
            show_all = QtWidgets.QPushButton("Show All")
            hide_all = QtWidgets.QPushButton("Hide All")
            show_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self._checkboxes])
            hide_all.clicked.connect(lambda: [cb.setChecked(False) for cb in self._checkboxes])
            btn_row.addWidget(show_all)
            btn_row.addWidget(hide_all)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        def closeEvent(self, event):
            global _win
            _win = None
            event.accept()


def open_particle_console():
    """Spawns a new Qt particle console window."""
    if not _HAS_PYQT:
        return
    global _win

    if _win is not None:
        _win.raise_()
        _win.activateWindow()
        return

    _win = ParticleConsoleWindow()
    _win.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    _win.setWindowFlags(
        _win.windowFlags()
        | QtCore.Qt.WindowType.Window
        | QtCore.Qt.WindowType.WindowStaysOnTopHint
    )
    _win.setWindowTitle("NeXus Particle Console")

    icon_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "icons",
        "images",
        "brand",
        "insydium_black.png",
    )
    _win.setWindowIcon(QtGui.QIcon(icon_path))
    _win.resize(1000, 800)
    _win.show()
