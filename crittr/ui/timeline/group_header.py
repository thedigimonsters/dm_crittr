from __future__ import annotations
from typing import Optional, Tuple

from crittr.qt import QtCore, QtGui, QtWidgets

NOTE_RAIL_COLOR = QtGui.QColor("#32363c")

class Theme:
    text        = QtGui.QColor("#d6d7d9")
    panel_alt   = QtGui.QColor("#2c3036")

class ClickLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()
    doubleClicked = QtCore.Signal()
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self.doubleClicked.emit()

class GroupHeaderWidget(QtWidgets.QWidget):
    titleClicked       = QtCore.Signal()
    titleDoubleClicked = QtCore.Signal()
    menuRequested      = QtCore.Signal(QtCore.QPoint)
    addNoteRequested   = QtCore.Signal()
    visibilityToggled  = QtCore.Signal(bool)
    lockToggled        = QtCore.Signal(bool)

    def __init__(self, layer, duration_s: float, group_range: Tuple[Optional[float], Optional[float]] = (None, None), parent=None):
        super().__init__(parent)
        self.layer = layer
        self.duration_s = max(0.001, float(duration_s))
        self.in_s, self.out_s = group_range

        self.setAutoFillBackground(False)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6); layout.setSpacing(8)

        self.title = ClickLabel(layer.name)
        self.title.setStyleSheet(f"color:{Theme.text.name()}; font-weight:600;")
        layout.addWidget(self.title)

        layout.addStretch(1)

        self.eye = QtWidgets.QToolButton(); self.eye.setCheckable(True); self.eye.setChecked(layer.visible)
        self.eye.setText("👁"); self.eye.setToolTip("Toggle visibility")
        self.lock = QtWidgets.QToolButton(); self.lock.setCheckable(True); self.lock.setChecked(layer.locked)
        self.lock.setText("🔒"); self.lock.setToolTip("Toggle lock")
        self.add_btn = QtWidgets.QToolButton(); self.add_btn.setText("＋ Note"); self.add_btn.setToolTip("Add note to this layer")
        self.menu_btn= QtWidgets.QToolButton(); self.menu_btn.setText("⋯"); self.menu_btn.setToolTip("Layer menu")

        for b in (self.eye, self.lock, self.add_btn, self.menu_btn):
            b.setAutoRaise(True)
        layout.addWidget(self.eye); layout.addWidget(self.lock); layout.addWidget(self.add_btn); layout.addWidget(self.menu_btn)

        self.title.clicked.connect(self.titleClicked)
        self.title.doubleClicked.connect(self.titleDoubleClicked)
        self.eye.toggled.connect(self.visibilityToggled)
        self.lock.toggled.connect(self.lockToggled)
        self.add_btn.clicked.connect(self.addNoteRequested)
        self.menu_btn.clicked.connect(lambda: self.menuRequested.emit(self.menu_btn.mapToGlobal(QtCore.QPoint(self.menu_btn.width()//2, self.menu_btn.height()))))

    def setRange(self, in_s, out_s):
        self.in_s, self.out_s = in_s, out_s
        self.update()

    def setDuration(self, duration_s: float) -> None:
        """Update header duration; used to scale the group span band."""
        new_d = max(0.001, float(duration_s))
        if abs(new_d - self.duration_s) > 1e-9:
            self.duration_s = new_d
            self.update()

    def setName(self, new_name: str):
        self.title.setText(new_name)
        self.update()

    def setColor(self, color: QtGui.QColor):
        self.layer.color = color
        self.update()

    def paintEvent(self, e: QtGui.QPaintEvent):
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect()
        rail_y = rect.bottom() - 6
        base = QtCore.QRect(12, rail_y, rect.width() - 24, 4)
        p.fillRect(base, NOTE_RAIL_COLOR)
        if self.in_s is not None and self.out_s is not None and self.out_s > self.in_s:
            x0 = base.x() + int((self.in_s / self.duration_s) * base.width())
            x1 = base.x() + int((self.out_s / self.duration_s) * base.width())
            span = QtCore.QRect(min(x0, x1), rail_y, max(6, abs(x1 - x0)), 4)
            band = QtGui.QColor(self.layer.color); band.setAlpha(140)
            p.fillRect(span, band)
        p.end()