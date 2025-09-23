from __future__ import annotations
from typing import Iterable
from crittr.qt import QtCore, QtWidgets

class PlaylistView(QtWidgets.QListWidget):
    itemActivatedPath = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setIconSize(QtCore.QSize(96, 54))
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setMovement(QtWidgets.QListView.Movement.Static)
        self.setMaximumHeight(90)
        self.setSpacing(8)
        self.setStyleSheet("QListWidget { background: #1a1a1a; }")
        self.itemActivated.connect(self._emit_path)
        self.itemClicked.connect(self._emit_path)

    def set_paths(self, paths: Iterable[str]) -> None:
        self.clear()
        for p in paths:
            it = QtWidgets.QListWidgetItem(p)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.addItem(it)

    def _emit_path(self, item: QtWidgets.QListWidgetItem):
        self.itemActivatedPath.emit(str(item.data(QtCore.Qt.ItemDataRole.UserRole)))
