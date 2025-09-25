from __future__ import annotations
from typing import List, Optional

from crittr.qt import QtCore, QtGui, QtWidgets
from .notes_tree import NotesTree, Note, Layer

class Theme:
    text        = QtGui.QColor("#d6d7d9")
    panel_alt   = QtGui.QColor("#2c3036")

class _AddNoteDialog(QtWidgets.QDialog):
    """Collect group + note info from the user."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Note")
        self.setModal(True)
        form = QtWidgets.QFormLayout(self)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.group_name = QtWidgets.QLineEdit()
        self.color_btn = QtWidgets.QToolButton()
        self._color = QtGui.QColor("#8ab4f8")
        self._update_color_btn()
        self.color_btn.clicked.connect(self._pick_color)

        self.note_title = QtWidgets.QLineEdit()
        self.note_body = QtWidgets.QPlainTextEdit()
        self.note_body.setMinimumHeight(100)

        color_row = QtWidgets.QHBoxLayout()
        color_row.addWidget(self.color_btn)
        color_row.addStretch(1)

        form.addRow("Group name", self.group_name)
        form.addRow("Group color", color_row)
        form.addRow("Note title", self.note_title)
        form.addRow("Note body", self.note_body)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _pick_color(self):
        col = QtWidgets.QColorDialog.getColor(self._color, self, options=QtWidgets.QColorDialog.DontUseNativeDialog)
        if col.isValid():
            self._color = col
            self._update_color_btn()

    def _update_color_btn(self):
        c = self._color
        self.color_btn.setText("Pick…")
        self.color_btn.setStyleSheet(f"QToolButton {{ background:{c.name()}; border:1px solid #444; color:#000; padding:4px; }}")

    def _accept(self):
        if not self.group_name.text().strip():
            QtWidgets.QMessageBox.warning(self, "Add Note", "Please enter a group name.")
            return
        if not self.note_title.text().strip() and not self.note_body.toPlainText().strip():
            QtWidgets.QMessageBox.warning(self, "Add Note", "Please enter a note title or body.")
            return
        self.accept()

    def result_data(self):
        return {
            "group_name": self.group_name.text().strip(),
            "color": self._color,
            "note_title": self.note_title.text().strip(),
            "note_body": self.note_body.toPlainText().strip(),
        }

class NotesPanel(QtWidgets.QWidget):
    groupActivated = QtCore.Signal(str, float, float)
    groupMenuRequested = QtCore.Signal(str, QtCore.QPoint)
    groupRenamed = QtCore.Signal(str, str)
    groupColorChanged = QtCore.Signal(str, QtGui.QColor)
    groupDeleted = QtCore.Signal(str)
    groupVisibilityChanged = QtCore.Signal(str, bool)
    groupLockChanged = QtCore.Signal(str, bool)

    noteActivated = QtCore.Signal(str, float, float, str)
    noteEditRequested = QtCore.Signal(str)
    noteDeleteRequested = QtCore.Signal(str)
    noteDuplicateRequested = QtCore.Signal(str)

    notePillDragStarted = QtCore.Signal(str, float, float)
    notePillDragging = QtCore.Signal(str, float, float, float)
    notePillDragFinished = QtCore.Signal(str, float, float, bool)

    noteDrawingAddRequested = QtCore.Signal(str)
    noteDrawingClearRequested = QtCore.Signal(str)
    noteDrawingOpacityRequested = QtCore.Signal(str, float)
    noteOpenDetailRequested = QtCore.Signal(str)

    selectionChangedSig = QtCore.Signal(list, object)

    def __init__(self, duration_s: float, parent=None):
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(0,0,0,0); v.setSpacing(0)

        tb = QtWidgets.QWidget(); tb.setStyleSheet(f"background:{Theme.panel_alt.name()};")
        tl = QtWidgets.QHBoxLayout(tb); tl.setContentsMargins(8,6,8,6)
        title = QtWidgets.QLabel("Notes"); title.setStyleSheet(f"color:{Theme.text.name()}; font-weight:700;")
        add_btn = QtWidgets.QToolButton(); add_btn.setText("＋ Note"); add_btn.setToolTip("Add a new note")
        add_btn.setAutoRaise(True)
        tl.addWidget(title); tl.addStretch(1); tl.addWidget(add_btn)
        v.addWidget(tb)

        self.tree = NotesTree(duration_s); v.addWidget(self.tree, 1)

        self.tree.groupActivated.connect(self.groupActivated)
        self.tree.groupMenuRequested.connect(self.groupMenuRequested)
        self.tree.groupRenamed.connect(self.groupRenamed)
        self.tree.groupColorChanged.connect(self.groupColorChanged)
        self.tree.groupDeleted.connect(self.groupDeleted)
        self.tree.groupVisibilityChanged.connect(self.groupVisibilityChanged)
        self.tree.groupLockChanged.connect(self.groupLockChanged)

        self.tree.noteActivated.connect(self.noteActivated)
        self.tree.noteEditRequested.connect(self.noteEditRequested)
        self.tree.noteDeleteRequested.connect(self.noteDeleteRequested)
        self.tree.noteDuplicateRequested.connect(self.noteDuplicateRequested)
        self.tree.notePillDragStarted.connect(self.notePillDragStarted)
        self.tree.notePillDragging.connect(self.notePillDragging)
        self.tree.notePillDragFinished.connect(self.notePillDragFinished)

        self.tree.noteDrawingAddRequested.connect(self.noteDrawingAddRequested)
        self.tree.noteDrawingClearRequested.connect(self.noteDrawingClearRequested)
        self.tree.noteDrawingOpacityRequested.connect(self.noteDrawingOpacityRequested)
        self.tree.noteOpenDetailRequested.connect(self.noteOpenDetailRequested)

        self.tree.selectionChangedSig.connect(self.selectionChangedSig)

        add_btn.clicked.connect(self._toolbar_add)

    def _toolbar_add(self):
        # Pop up dialog for group + note details
        dlg = _AddNoteDialog(self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dlg.result_data()
        group_name: str = data["group_name"]
        color: QtGui.QColor = data["color"]
        note_title: str = data["note_title"]
        note_body: str = data["note_body"]

        # Ensure layer exists (create if missing)
        lid = self.tree.find_layer_by_name(group_name)
        if lid is None:
            lid = self.tree.add_layer_simple(group_name, color)
        else:
            # If the group exists and user picked new color, optionally apply it to the header
            hdr = self.tree._layer_headers.get(lid)
            if hdr and color.isValid():
                hdr.setColor(color)
                self.groupColorChanged.emit(lid, color)

        # Compose note text
        txt_parts = []
        if note_title:
            txt_parts.append(note_title)
        if note_body:
            if note_title:
                txt_parts.append("")  # blank line between title and body
            txt_parts.append(note_body)
        note_text = "\n".join(txt_parts)

        # Create note with default range (0–2s). Later phases can center at current time.
        nid = self.tree.alloc_note_id()
        new_note = Note(id=nid, layer_id=lid, start_s=0.0, end_s=2.0, text=note_text)
        self.tree.add_note(lid, new_note)

        # Select the new note and emit selection
        self.tree._select_only(nid)

    def set_duration(self, duration_s: float) -> None:
        """Public API: update the panel's duration (seconds)."""
        try:
            self.tree.set_duration(duration_s)
        except Exception:
            pass

    def add_layer(self, layer: Layer, notes: List[Note]):
        self.tree.add_layer(layer, notes)