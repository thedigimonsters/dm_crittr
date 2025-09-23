from __future__ import annotations
from typing import List, Optional
from crittr.qt import QtCore, QtGui, QtWidgets

class MarkerSlider(QtWidgets.QSlider):
    """
    QSlider that draws small tick markers for frames that have notes/bookmarks.
    Not a full timeline yet, but gives visual anchors you can click on.
    """
    markerClicked = QtCore.Signal(int)  # frame

    def __init__(self, orientation: QtCore.Qt.Orientation, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(orientation, parent)
        self._markers: List[int] = []
        self.setMouseTracking(True)
        self.setMinimum(0)
        self.setMaximum(100)  # will be adjusted dynamically

    def set_markers(self, frames: List[int]) -> None:
        self._markers = sorted(set(int(f) for f in frames if f >= 0))
        self.update()

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        super().paintEvent(e)
        if not self._markers:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_Slider, opt,
            QtWidgets.QStyle.SubControl.SC_SliderGroove, self,
        )
        # Draw markers as small green ticks
        p.setPen(QtGui.QPen(QtGui.QColor("#4CAF50"), 2))
        span = max(1, self.maximum() - self.minimum())
        for f in self._markers:
            ratio = (f - self.minimum()) / span
            x = int(groove_rect.left() + ratio * groove_rect.width())
            y1 = groove_rect.center().y() - 6
            y2 = groove_rect.center().y() + 6
            p.drawLine(x, y1, x, y2)
        p.end()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            # Jump to position and see if close to a marker
            val = self._pixel_pos_to_value(e.position().x())
            self.setValue(val)
            hit = self._nearest_marker(val)
            if hit is not None and abs(hit - val) <= max(1, int(0.01 * (self.maximum() - self.minimum()))):
                self.markerClicked.emit(hit)
        super().mousePressEvent(e)

    def _pixel_pos_to_value(self, px: float) -> int:
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_Slider, opt,
            QtWidgets.QStyle.SubControl.SC_SliderGroove, self,
        )
        if groove.width() <= 0:
            return self.value()
        ratio = (px - groove.left()) / groove.width()
        ratio = max(0.0, min(1.0, ratio))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def _nearest_marker(self, value: int) -> Optional[int]:
        if not self._markers:
            return None
        return min(self._markers, key=lambda m: abs(m - value))
