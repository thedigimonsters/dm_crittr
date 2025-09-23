# crittr/ui/timeline/ruler.py
from __future__ import annotations
from typing import Optional
from crittr.qt import QtCore, QtGui, QtWidgets

def sec_to_x(t: float, px_per_sec: float) -> float:
    return float(t) * float(px_per_sec)

class RulerItem(QtWidgets.QGraphicsItem):
    def __init__(self, px_per_sec: float, height: int = 24):
        super().__init__()
        self.px_per_sec = px_per_sec
        self._height = height
        self.setZValue(1000)  # on top

    def set_px_per_sec(self, v: float) -> None:
        if v <= 1e-6:
            v = 1.0
        self.prepareGeometryChange()
        self.px_per_sec = v

    def boundingRect(self) -> QtCore.QRectF:
        # Big width; scene/view will clip
        return QtCore.QRectF(0, 0, 1_000_000, self._height)

    def paint(self, p: QtGui.QPainter, opt: QtWidgets.QStyleOptionGraphicsItem, widget=None) -> None:
        rect = opt.exposedRect
        p.fillRect(rect, QtGui.QColor("#2a2a2a"))
        pen_minor = QtGui.QPen(QtGui.QColor("#5a5a5a"))
        pen_major = QtGui.QPen(QtGui.QColor("#aaaaaa"))
        p.setPen(pen_minor)

        # Determine tick spacing
        s_per_major = 1.0
        if self.px_per_sec < 40:
            s_per_major = 2.0
        if self.px_per_sec < 20:
            s_per_major = 5.0
        s_per_minor = s_per_major / 10.0

        x0 = max(0.0, rect.left())
        x1 = rect.right()
        # Convert to seconds range
        t_start = x0 / max(1e-6, self.px_per_sec)
        t_end = x1 / max(1e-6, self.px_per_sec)

        # Minor ticks
        minor = int(t_start / s_per_minor) - 2
        end_minor = int(t_end / s_per_minor) + 2
        for i in range(minor, end_minor + 1):
            t = i * s_per_minor
            x = sec_to_x(t, self.px_per_sec)
            p.drawLine(QtCore.QPointF(x, self._height * 0.5), QtCore.QPointF(x, self._height))

        # Major ticks + labels
        p.setPen(pen_major)
        font = p.font()
        font.setPointSizeF(8.0)
        p.setFont(font)
        major = int(t_start / s_per_major) - 2
        end_major = int(t_end / s_per_major) + 2
        for i in range(major, end_major + 1):
            t = i * s_per_major
            if t < 0:
                continue
            x = sec_to_x(t, self.px_per_sec)
            p.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, self._height))
            label = f"{int(t):d}s"
            p.drawText(QtCore.QPointF(x + 3, self._height - 6), label)