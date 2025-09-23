from __future__ import annotations
from typing import Optional
import numpy as np
from crittr.qt import QtCore, QtGui, QtWidgets

class FrameView(QtWidgets.QLabel):
    """
    Simple frame view. Accepts numpy RGB frames and shows them.
    Future: replace with a custom paintable canvas for annotations.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("background-color: #222;")
        self._qimage: Optional[QtGui.QImage] = None

    @staticmethod
    def _np_to_qimage(rgb: np.ndarray) -> QtGui.QImage:
        # rgb shape expected (h, w, 3), uint8
        h, w, ch = rgb.shape
        assert ch == 3
        bytes_per_line = 3 * w
        # copy() is important to avoid showing garbage when numpy buffer changes
        return QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888).copy()

    @QtCore.Slot(object)
    def set_frame(self, rgb: np.ndarray) -> None:
        try:
            self._qimage = self._np_to_qimage(rgb)
            self.update()
        except Exception:
            # Defensive: ignore malformed frames
            pass

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        super().paintEvent(e)
        if not self._qimage:
            return
        p = QtGui.QPainter(self)
        target = QtCore.QRectF(self.rect())
        # FastTransformation is much cheaper per-frame; we can switch to Smooth when paused or for stills later.
        scaled = QtGui.QImage(self._qimage).scaled(
            target.size().toSize(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.FastTransformation,
        )
        x = (self.width() - scaled.width()) / 2
        y = (self.height() - scaled.height()) / 2
        p.drawImage(QtCore.QPointF(x, y), scaled)
        p.end()
