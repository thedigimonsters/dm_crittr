from __future__ import annotations
from typing import Dict, List
from crittr.qt import QtCore, QtWidgets

class NotesPanel(QtWidgets.QWidget):
    notePosted = QtCore.Signal(int, str)     # frame, text
    noteActivated = QtCore.Signal(int)       # frame

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._notes: Dict[int, List[str]] = {}
        self._build()

    def _build(self):
        self.note_edit = QtWidgets.QLineEdit(placeholderText="Leave some feedback...")
        self.post_btn = QtWidgets.QPushButton("Post")
        self.list = QtWidgets.QListWidget()

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.note_edit, 1)
        row.addWidget(self.post_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(row)
        layout.addWidget(self.list, 1)

        self.post_btn.clicked.connect(self._post)
        self.list.itemActivated.connect(self._jump)
        self.list.itemClicked.connect(self._jump)

    def set_notes(self, notes: Dict[int, List[str]]) -> None:
        self._notes = {int(k): list(v) for k, v in (notes or {}).items()}
        self._refresh()

    def add_note(self, frame: int, text: str) -> None:
        self._notes.setdefault(int(frame), []).append(text)
        self._refresh()

    def _post(self):
        text = self.note_edit.text().strip()
        if not text:
            return
        # caller should pass in current frame when connecting this panel
        self.notePosted.emit(-1, text)  # -1 placeholder; caller can override before connect
        self.note_edit.clear()

    def _jump(self, item: QtWidgets.QListWidgetItem):
        f = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
        self.noteActivated.emit(f)

    def _refresh(self):
        self.list.clear()
        for f in sorted(self._notes.keys()):
            for txt in self._notes[f]:
                it = QtWidgets.QListWidgetItem(f"#{f:06d}  •  {txt}")
                it.setData(QtCore.Qt.ItemDataRole.UserRole, f)
                self.list.addItem(it)
