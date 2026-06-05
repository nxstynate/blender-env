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

import os
import shutil
import sys
import tempfile

import bpy

from ..libs import theron

_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "vendor")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402
    _HAS_PYQT = True
except ImportError:
    _HAS_PYQT = False


_win = None


def has_open_window():
    return _win is not None


if _HAS_PYQT:
    class BugReportDialog(QtWidgets.QWidget):
        def closeEvent(self, event):

            # Set _win to None so we can open a new window when needed
            global _win
            _win = None

            event.accept()


def open_bug_report_dialog():
    """
    Spawns a new Qt bug report dialog window.
    """
    if not _HAS_PYQT:
        return

    from ..utils import get_blender_addon

    global _win

    # Only one window at a time
    if _win is not None:
        # Focus the existing window
        _win.raise_()
        _win.activateWindow()
        return

    _win = BugReportDialog()
    _win.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)  # Delete the object when closed
    _win.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint)

    _win.setWindowTitle("INSYDIUM Bug Reporter")
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

    root = QtWidgets.QVBoxLayout(_win)
    root.setContentsMargins(16, 16, 16, 12)

    def add_field(label_text, widget):
        """Helper to add a labelled field."""
        root.addWidget(QtWidgets.QLabel(label_text))
        root.addWidget(widget)

    def add_field_row(*fields):
        """Pass pairs of (label, widget) to place them side by side."""
        row = QtWidgets.QHBoxLayout()
        for label_text, widget in fields:
            add_field(label_text, widget)
        root.addLayout(row)

    prefs = get_blender_addon().preferences

    name_edit = QtWidgets.QLineEdit()
    name_edit.setText(prefs.license_name)

    email_edit = QtWidgets.QLineEdit()
    email_edit.setText(prefs.license_email)

    subject_edit = QtWidgets.QLineEdit()

    add_field_row(("Name", name_edit), ("Email", email_edit))

    add_field_row(
        ("Subject", subject_edit),
    )

    sep = QtWidgets.QFrame()
    sep.setObjectName("separator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    root.addWidget(sep)

    header = QtWidgets.QLabel(
        "Please describe what happened, what you expected, and include any steps we can follow to "
        "reproduce the problem. Add any relevant files or details that may help us investigate."
    )
    header.setObjectName("header")
    root.addWidget(header)

    root.addWidget(QtWidgets.QLabel("Description"))
    desc_edit = QtWidgets.QTextEdit()
    desc_edit.setText("""Description:

Steps to Reproduce:

Expected Result:

Actual Result:
""")
    root.addWidget(desc_edit, stretch=1)

    attach_row = QtWidgets.QHBoxLayout()
    combo = QtWidgets.QComboBox()
    combo.addItems(["Scene Only", "Scene File"])

    file_edit = QtWidgets.QLineEdit()
    file_edit.setPlaceholderText("Select a .blend file...")
    file_edit.setEnabled(False)

    browse_btn = QtWidgets.QPushButton("Browse")
    browse_btn.setEnabled(False)

    def on_combo_change(text):
        enabled = text == "Scene File"
        file_edit.setEnabled(enabled)
        browse_btn.setEnabled(enabled)

    def on_browse():
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            _win, "Select .blend file", "", "Blender Files (*.blend)"
        )
        if path:
            file_edit.setText(path)

    combo.currentTextChanged.connect(on_combo_change)
    browse_btn.clicked.connect(on_browse)

    attach_row.addWidget(combo)
    attach_row.addWidget(file_edit)
    attach_row.addWidget(browse_btn)
    root.addLayout(attach_row)

    footer = QtWidgets.QLabel(
        "Please Note: this is an automated bug tracking system, if you need a reply please contact"
        " us through our website."
    )
    footer.setObjectName("footer")
    root.addWidget(footer)

    sep2 = QtWidgets.QFrame()
    sep2.setObjectName("separator")
    sep2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    root.addWidget(sep2)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    cancel_btn = QtWidgets.QPushButton("Cancel")
    submit_btn = QtWidgets.QPushButton("Submit")
    submit_btn.setObjectName("submit")

    def on_submit():
        global _win

        if _win is None:
            return

        is_temp = False
        if combo.currentText() == "Scene Only":
            if bpy.data.filepath:
                filepath = bpy.data.filepath
            else:
                # If the document is unsaved, save a temporary copy to upload
                is_temp = True
                temp_dir = tempfile.mkdtemp()
                filepath = os.path.join(temp_dir, "Untitled.blend")
                bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True)
        else:
            filepath = file_edit.text()

        report_id = theron.submit_bug_report(
            name_edit.text(),
            email_edit.text(),
            subject_edit.text(),
            desc_edit.toPlainText(),
            filepath,
        )

        if is_temp:
            shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)

        if report_id != -1:
            QtWidgets.QMessageBox.information(
                _win,
                "INSYDIUM Bug Reporter",
                f"Your report (#{report_id}) has been submitted successfully.",
            )
        else:
            QtWidgets.QMessageBox.critical(
                _win,
                "INSYDIUM Bug Reporter",
                "Failed to submit your report.\n"
                "Please check your internet connection and try again.",
            )

        _win.close()
        _win = None

    def on_cancel():
        global _win
        if _win is None:
            return

        _win.close()
        _win = None

    cancel_btn.clicked.connect(on_cancel)
    submit_btn.clicked.connect(on_submit)

    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(submit_btn)
    root.addLayout(btn_row)

    _win.show()
    subject_edit.setFocus()
