# crittr/ui/timeline/layer_track.py
from __future__ import annotations
from crittr.qt import QtCore, QtGui, QtWidgets

class LayerTrackItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, y: float, height: int, index: int):
        super().__init__(0, y, 1_000_000, height)
        color = QtGui.QColor("#262626") if (index % 2 == 0) else QtGui.QColor("#2d2d2d")
        self.setBrush(color)
        self.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        self.setZValue(-10)