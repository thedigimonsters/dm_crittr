from __future__ import annotations
from crittr.qt import QtCore, QtWidgets

class InspectorTabs(QtWidgets.QTabWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        # Placeholder tabs you can replace later
        self.addTab(self._placeholder("Notes panel (WIP)"), "Notes")
        self.addTab(self._placeholder("Versions (WIP)"), "Versions")
        self.addTab(self._placeholder("Info (WIP)"), "Info")

    def _placeholder(self, title: str) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        l = QtWidgets.QVBoxLayout(w)
        l.setContentsMargins(12, 12, 12, 12)
        lbl = QtWidgets.QLabel(title)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet("color: #aaa;")
        l.addStretch(1)
        l.addWidget(lbl)
        l.addStretch(1)
        return w
