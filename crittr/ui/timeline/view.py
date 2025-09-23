# crittr/ui/timeline/view.py
from __future__ import annotations
from typing import List
from crittr.qt import QtCore, QtGui, QtWidgets
from .ruler import RulerItem
from .layer_track import LayerTrackItem

class TimelineScene(QtWidgets.QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QtGui.QColor("#1f1f1f"))

class TimelineView(QtWidgets.QGraphicsView):
    playheadColor = QtGui.QColor("#ff5252")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(TimelineScene(self))
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.px_per_sec: float = 100.0
        self.row_height: int = 36
        self.header_h: int = 24

        # Items
        self._ruler = RulerItem(self.px_per_sec, height=self.header_h)
        self.scene().addItem(self._ruler)

        self._layer_tracks: List[LayerTrackItem] = []
        self._playhead = self._make_playhead()

        # Initial rows
        self.set_layers_count(3)
        self._layout_static()

    def _make_playhead(self) -> QtWidgets.QGraphicsItem:
        line = self.scene().addLine(0, 0, 0, self.header_h + 3 * self.row_height, QtGui.QPen(self.playheadColor, 1.5))
        line.setZValue(900)
        return line

    def set_layers_count(self, count: int) -> None:
        for it in self._layer_tracks:
            self.scene().removeItem(it)
        self._layer_tracks.clear()
        for i in range(count):
            y = self.header_h + i * self.row_height
            track = LayerTrackItem(y, self.row_height, i)
            self.scene().addItem(track)
            self._layer_tracks.append(track)
        self._layout_static()

    def _layout_static(self) -> None:
        # Extend scene rect to cover reasonable range
        width = 60 * self.px_per_sec  # 60 seconds visible width envelope
        height = self.header_h + max(1, len(self._layer_tracks)) * self.row_height
        self.scene().setSceneRect(0, 0, width, height)
        # Ruler already spans a large width

    def set_playhead_time(self, pts_s: float) -> None:
        x = float(max(0.0, pts_s)) * self.px_per_sec
        # Update playhead line geometry
        h = self.scene().sceneRect().height()
        self._playhead.setLine(x, 0, x, h)

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        if e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            # Zoom horizontally around cursor
            delta = e.angleDelta().y()
            factor = 1.0 + (0.0015 * delta)
            old_pps = self.px_per_sec
            self.px_per_sec = float(max(5.0, min(800.0, self.px_per_sec * factor)))
            self._ruler.set_px_per_sec(self.px_per_sec)
            self._layout_static()

            # Keep cursor time under cursor after zoom
            view_pos = e.position()
            scene_pos_before = self.mapToScene(QtCore.QPoint(int(view_pos.x()), int(view_pos.y())))
            self.centerOn(scene_pos_before)
            e.accept()
            return
        super().wheelEvent(e)