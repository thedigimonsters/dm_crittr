from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import time

from crittr.qt import QtCore, QtGui, QtWidgets

NOTE_RAIL_COLOR = QtGui.QColor("#32363c")
GRIP_WIDTH_PX = 8

class Theme:
    bg          = QtGui.QColor("#1f2124")
    panel       = QtGui.QColor("#26292e")
    panel_alt   = QtGui.QColor("#2c3036")
    stroke      = QtGui.QColor("#3a3f46")
    text        = QtGui.QColor("#d6d7d9")
    text_dim    = QtGui.QColor("#aab0b7")
    accent      = QtGui.QColor("#3fb6ff")
    accent_dim  = QtGui.QColor("#2a90cc")

class NoteCard(QtWidgets.QWidget):
    activated  = QtCore.Signal(str, float, float, str)  # note_id, start, end, layer_id
    pillDragStarted  = QtCore.Signal(str, float, float)
    pillDragging     = QtCore.Signal(str, float, float, float)  # note_id, start, end, preview_t
    pillDragFinished = QtCore.Signal(str, float, float, bool)
    editRequested       = QtCore.Signal(str)
    deleteRequested     = QtCore.Signal(str)
    duplicateRequested  = QtCore.Signal(str)
    drawingAddRequested      = QtCore.Signal(str)
    drawingClearRequested    = QtCore.Signal(str)
    drawingOpacityRequested  = QtCore.Signal(str, float)
    openDetailRequested      = QtCore.Signal(str)

    PAD    = 8
    PILL_H = 16
    EDGE_W = GRIP_WIDTH_PX
    TEXT_L = 24   # left gutter for layer stripe

    def __init__(self, note, layer, duration_s: float, fps_est: float = 24.0, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMouseTracking(True)
        self.note = note
        self.layer = layer
        self.duration_s = max(0.001, float(duration_s))
        self.fps_est = max(1e-6, float(fps_est))

        self._drag_mode: Optional[str] = None  # "move" | "left" | "right"
        self._orig: Optional[Tuple[float, float]] = None
        self._last_emit_ms = 0.0
        self.locked: bool = False
        self.selected: bool = False

        self._pen_btn = QtWidgets.QToolButton(self)
        self._pen_btn.setAutoRaise(True)
        self._pen_btn.setText("✎")
        self._pen_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._pen_btn.setToolTip("Drawing actions")
        self._pen_btn.setStyleSheet("QToolButton { border:0; }")
        self._pen_menu = QtWidgets.QMenu(self)
        act_add = self._pen_menu.addAction("Add/Replace Drawing…")
        act_clr = self._pen_menu.addAction("Clear Drawing")
        self._pen_menu.addSeparator()
        act_opc = self._pen_menu.addAction("Set Drawing Opacity…")
        self._pen_menu.addSeparator()
        act_det = self._pen_menu.addAction("Open Detail Editor…")
        self._pen_btn.setMenu(self._pen_menu)
        self._pen_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        act_add.triggered.connect(lambda: self.drawingAddRequested.emit(self.note.id))
        act_clr.triggered.connect(lambda: self.drawingClearRequested.emit(self.note.id))
        act_opc.triggered.connect(self._ask_opacity)
        act_det.triggered.connect(lambda: self.openDetailRequested.emit(self.note.id))

    def resizeEvent(self, e: QtGui.QResizeEvent):
        self._pen_btn.setFixedSize(20, 20)
        self._pen_btn.move(self.width() - self.PAD - self._pen_btn.width(), self.PAD)

    def setLocked(self, v: bool):
        if self.locked != v:
            self.locked = v
            self.update()

    def setSelected(self, v: bool):
        if self.selected != v:
            self.selected = v
            self.update()

    def setDuration(self, duration_s: float) -> None:
        """Update the card's total duration; affects mapping between seconds and rail X coordinates."""
        new_d = max(0.001, float(duration_s))
        if abs(new_d - self.duration_s) > 1e-9:
            self.duration_s = new_d
            self.update()

    def _text_rects(self) -> tuple[QtCore.QRect, QtCore.QRect]:
        r = self.rect().adjusted(self.PAD + self.TEXT_L, self.PAD, -self.PAD - 90, -self.PAD)
        title_h = self.fontMetrics().height()
        title_r = QtCore.QRect(r.x(), r.y(), r.width(), title_h)
        sub_r   = QtCore.QRect(r.x(), r.y() + title_h + 2, r.width(), title_h)
        return title_r, sub_r

    def _pill_rail_rect(self) -> QtCore.QRect:
        _, sub = self._text_rects()
        y = sub.bottom() + 6
        w = self.width() - (self.PAD + self.TEXT_L) - (self.PAD + 90)
        return QtCore.QRect(self.PAD + self.TEXT_L, y, max(40, w), self.PILL_H)

    def _sec_to_x(self, t: float) -> int:
        pr = self._pill_rail_rect()
        x = pr.x() + int((t / self.duration_s) * pr.width())
        return max(pr.left(), min(pr.right() - 1, x))

    def _x_to_sec(self, x: int) -> float:
        pr = self._pill_rail_rect()
        ratio = (x - pr.x()) / max(1, pr.width())
        return max(0.0, min(self.duration_s, ratio * self.duration_s))

    def _snap(self, t: float, shift: bool) -> float:
        if not shift:
            return t
        step = 1.0 / self.fps_est
        return round(t / step) * step

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        bg = Theme.panel_alt if (self.selected or (self.underMouse() and not self.locked)) else Theme.panel
        p.fillRect(self.rect(), bg)

        stripe = QtCore.QRect(self.PAD, self.PAD, 6, self.height() - 2 * self.PAD)
        p.fillRect(stripe, self.layer.color)

        title_r, sub_r = self._text_rects()
        fm = self.fontMetrics()
        title = self.note.text.splitlines()[0] or "(note)"
        title = fm.elidedText(title, QtCore.Qt.ElideRight, title_r.width())
        p.setPen(Theme.text_dim if self.locked else Theme.text)
        p.drawText(title_r, QtCore.Qt.AlignVCenter, title)
        p.setPen(Theme.text_dim)
        p.drawText(sub_r, QtCore.Qt.AlignVCenter, f"{self.note.start_s:0.2f}s – {self.note.end_s:0.2f}s")

        rail = self._pill_rail_rect()
        rail_y = int(rail.center().y())
        rail_line = QtCore.QRect(rail.x(), rail_y - 2, rail.width(), 4)
        p.fillRect(rail_line, NOTE_RAIL_COLOR)

        x0 = self._sec_to_x(self.note.start_s)
        x1 = self._sec_to_x(self.note.end_s)
        pill_left  = min(x0, x1)
        pill_width = max(16, abs(x1 - x0))
        pill = QtCore.QRect(pill_left, rail.y(), pill_width, rail.height())

        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(pill), 7, 7)
        pill_fill   = Theme.stroke if self.locked else Theme.accent_dim
        pill_stroke = Theme.stroke if self.locked else Theme.accent
        p.fillPath(path, pill_fill)
        p.setPen(QtGui.QPen(pill_stroke, 1.2))
        p.drawPath(path)

        if not self.locked:
            p.setPen(QtCore.Qt.NoPen)
            left_grip  = QtCore.QRect(pill.left(), pill.top(), self.EDGE_W, pill.height())
            right_grip = QtCore.QRect(pill.right() - self.EDGE_W, pill.top(), self.EDGE_W, pill.height())
            p.fillRect(left_grip, Theme.accent)
            p.fillRect(right_grip, Theme.accent)

        if getattr(self.note, "drawing_id", None):
            self._pen_btn.setStyleSheet(
                "QToolButton { background: %s; color: %s; border-radius:4px; }"
                % (Theme.stroke.name(), Theme.text.name())
            )
        else:
            self._pen_btn.setStyleSheet("QToolButton { border:0; }")

        p.end()

    def _hit(self, pos: QtCore.QPoint) -> Optional[str]:
        rail = self._pill_rail_rect()
        x0 = self._sec_to_x(self.note.start_s)
        x1 = self._sec_to_x(self.note.end_s)
        pill_left  = min(x0, x1)
        pill_width = max(16, abs(x1 - x0))
        pill = QtCore.QRect(pill_left, rail.y(), pill_width, rail.height())
        if not pill.contains(pos):
            return None
        if pos.x() <= pill.left() + self.EDGE_W:
            return "left"
        if pos.x() >= pill.right() - self.EDGE_W:
            return "right"
        return "move"

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if self.locked:
            if e.button() == QtCore.Qt.LeftButton:
                self.activated.emit(self.note.id, self.note.start_s, self.note.end_s, self.note.layer_id)
            return
        if e.button() == QtCore.Qt.RightButton:
            self._open_context_menu(e.globalPosition().toPoint())
            return
        hit = self._hit(e.position().toPoint())
        if hit:
            self._drag_mode = hit
            self._orig = (self.note.start_s, self.note.end_s)
            self._last_emit_ms = 0.0
            self.pillDragStarted.emit(self.note.id, self.note.start_s, self.note.end_s)
            self.setCursor(QtCore.Qt.SizeHorCursor if hit != "move" else QtCore.Qt.ClosedHandCursor)
            e.accept()
            return
        if e.button() == QtCore.Qt.LeftButton:
            self.activated.emit(self.note.id, self.note.start_s, self.note.end_s, self.note.layer_id)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self.locked:
            self.setCursor(QtCore.Qt.ArrowCursor)
            return
        if self._drag_mode:
            shift = bool(e.modifiers() & QtCore.Qt.ShiftModifier)
            x = int(e.position().x())
            t = self._snap(self._x_to_sec(x), shift)
            s0, e0 = self._orig
            if self._drag_mode == "move":
                length = e0 - s0
                s = self._snap(t - 0.5 * length, shift)
                e_ = s + length
            elif self._drag_mode == "left":
                s = min(t, e0 - (1.0 / self.fps_est)); e_ = e0
            else:
                s = s0; e_ = max(t, s0 + (1.0 / self.fps_est))
            s = max(0.0, min(self.duration_s, s))
            e_ = max(0.0, min(self.duration_s, e_))
            self.note.start_s, self.note.end_s = s, e_
            self.update()

            now_ms = time.monotonic() * 1000.0
            if now_ms - self._last_emit_ms >= 33.0:
                preview_t = 0.5 * (s + e_)
                self.pillDragging.emit(self.note.id, s, e_, preview_t)
                self._last_emit_ms = now_ms

            e.accept()
            return

        hit = self._hit(e.position().toPoint())
        self.setCursor(
            QtCore.Qt.SizeHorCursor if hit in ("left", "right")
            else QtCore.Qt.OpenHandCursor if hit == "move"
            else QtCore.Qt.ArrowCursor
        )
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if self.locked:
            return
        if self._drag_mode:
            self._drag_mode = None
            self._orig = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            self.pillDragFinished.emit(self.note.id, self.note.start_s, self.note.end_s, True)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def _open_context_menu(self, global_pos: QtCore.QPoint):
        m = QtWidgets.QMenu(self)
        act_edit = m.addAction("Edit Note…")
        act_dup  = m.addAction("Duplicate Note")
        act_del  = m.addAction("Delete Note")
        m.addSeparator()
        act_add  = m.addAction("Add/Replace Drawing…")
        act_clr  = m.addAction("Clear Drawing")
        act_opc  = m.addAction("Set Drawing Opacity…")

        for a in (act_edit, act_dup, act_del, act_add, act_clr, act_opc):
            a.setEnabled(not self.locked)

        chosen = m.exec(global_pos)
        if not chosen:
            return
        if chosen is act_edit: self.editRequested.emit(self.note.id)
        elif chosen is act_dup: self.duplicateRequested.emit(self.note.id)
        elif chosen is act_del: self.deleteRequested.emit(self.note.id)
        elif chosen is act_add: self.drawingAddRequested.emit(self.note.id)
        elif chosen is act_clr: self.drawingClearRequested.emit(self.note.id)
        elif chosen is act_opc: self._ask_opacity()

    def _ask_opacity(self):
        if self.locked:
            return
        val, ok = QtWidgets.QInputDialog.getInt(self, "Drawing Opacity", "Opacity (0–100):",
                                                int(getattr(self.note, "drawing_opacity", 1.0) * 100), 0, 100, 5)
        if ok:
            self.drawingOpacityRequested.emit(self.note.id, val / 100.0)