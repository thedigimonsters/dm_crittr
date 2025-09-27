from __future__ import annotations
from typing import Optional, Tuple

from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.ui.theme import Theme, NOTE_RAIL_COLOR
import qtawesome as qta

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
    renameRequested    = QtCore.Signal()       # new
    colorChangeRequested = QtCore.Signal()     # new
    deleteRequested    = QtCore.Signal()       # new

    def __init__(self, layer, duration_s: float, group_range: Tuple[Optional[float], Optional[float]] = (None, None), parent=None):
        super().__init__(parent)
        self.layer = layer
        self.duration_s = max(0.001, float(duration_s))
        self.in_s, self.out_s = group_range
        self._hovered = False
        self._active = False

        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        # Fixed header height and padding per spec
        self.setFixedHeight(44)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8); layout.setSpacing(8)

        self.title = ClickLabel(layer.name)
        self.title.setStyleSheet(f"color:{Theme.text.name()}; font-weight:600;")

        # Replace stacked layout with a QStackedWidget to avoid first-show geometry issues
        self._title_stack = QtWidgets.QStackedWidget()
        self._title_stack.setContentsMargins(0, 0, 0, 0)
        self._title_stack.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # Page 0: display label
        self._title_stack.addWidget(self.title)

        # Page 1: inline editor (hidden until rename)
        self.title_edit = QtWidgets.QLineEdit(self.layer.name)
        self.title_edit.setFont(self.title.font())
        self.title_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: 1px solid transparent; color:{Theme.text.name()}; font-weight:600; padding:0; }}"
        )
        self._title_stack.addWidget(self.title_edit)
        self._title_stack.setCurrentWidget(self.title)  # start on label
        self._rename_wired = False

        # Add to row
        layout.addWidget(self._title_stack)

        layout.addStretch(1)

        # Right-side control bar with QtAwesome icons
        self.controls = QtWidgets.QWidget(self)
        c_lay = QtWidgets.QHBoxLayout(self.controls)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(4)

        self.eye = QtWidgets.QToolButton(); self.eye.setCheckable(True); self.eye.setChecked(layer.visible)
        self.eye.setToolTip("Toggle visibility")
        self.lock = QtWidgets.QToolButton(); self.lock.setCheckable(True); self.lock.setChecked(layer.locked)
        self.lock.setToolTip("Toggle lock")
        self.add_btn = QtWidgets.QToolButton(); self.add_btn.setToolTip("Add note to this layer")

        self.rename_btn = QtWidgets.QToolButton(); self.rename_btn.setToolTip("Rename group")
        self.color_btn  = QtWidgets.QToolButton(); self.color_btn.setToolTip("Change group color")
        self.delete_btn = QtWidgets.QToolButton(); self.delete_btn.setToolTip("Delete group")

        # Icon-only, transparent, square hit area; smaller icons to avoid overlap
        btn_css = (
            "QToolButton { background: transparent; border: 0; padding: 0; margin: 0; }"
            "QToolButton:hover { background: transparent; }"
            "QToolButton:pressed { background: transparent; }"
            "QToolButton:checked { background: transparent; }"
            "QToolButton:focus { outline: none; }"
        )
        for b in (self.eye, self.lock, self.add_btn, self.rename_btn, self.color_btn, self.delete_btn):
            b.setAutoRaise(False)
            b.setStyleSheet(btn_css)
            b.setIconSize(QtCore.QSize(14, 14))
            b.setFixedSize(24, 24)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            c_lay.addWidget(b)

        layout.addWidget(self.controls)
        # Fade controls in/out
        self._controls_fx = QtWidgets.QGraphicsOpacityEffect(self.controls)
        self.controls.setGraphicsEffect(self._controls_fx)
        self._fade = QtCore.QPropertyAnimation(self._controls_fx, b"opacity", self)
        self._fade.setDuration(120)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self.controls.setVisible(False)

        # Initial icons
        self._update_icons(hover=False)

        self.title.clicked.connect(self.titleClicked)
        self.title.doubleClicked.connect(self.titleDoubleClicked)
        self.eye.toggled.connect(self._on_eye_toggled)
        self.lock.toggled.connect(self._on_lock_toggled)
        self.add_btn.clicked.connect(self.addNoteRequested)
        self.rename_btn.clicked.connect(self._begin_inline_rename)
        self.color_btn.clicked.connect(self.colorChangeRequested)
        self.delete_btn.clicked.connect(self.deleteRequested)

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
        self.layer.name = new_name  # keep model in sync
        self.title.setText(new_name)
        # keep editor in sync so subsequent renames start with the right text
        if hasattr(self, "title_edit"):
            self.title_edit.blockSignals(True)
            self.title_edit.setText(new_name)
            self.title_edit.blockSignals(False)
        self.update()

    def setColor(self, color: QtGui.QColor):
        self.layer.color = color
        self.update()

    def setActive(self, active: bool) -> None:
        """Called by the tree to reflect selection/active state."""
        if self._active != bool(active):
            self._active = bool(active)
            self._update_controls_visibility()
            self.update()

    # Hover tracking for icon reveal and hover brightness
    def enterEvent(self, e: QtCore.QEvent) -> None:
        self._hovered = True
        self._update_icons(hover=True)
        self._update_controls_visibility()
        super().enterEvent(e)

    def leaveEvent(self, e: QtCore.QEvent) -> None:
        self._hovered = False
        self._update_icons(hover=False)
        self._update_controls_visibility()
        super().leaveEvent(e)

    def _update_controls_visibility(self) -> None:
        want_visible = self._hovered or self._active
        if want_visible and not self.controls.isVisible():
            self.controls.setVisible(True)
            self._fade.stop()
            self._controls_fx.setOpacity(0.0)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        elif not want_visible and self.controls.isVisible():
            # Fade out then hide
            def _hide():
                self.controls.setVisible(False)
                self._fade.finished.disconnect(_hide)
            self._fade.stop()
            self._controls_fx.setOpacity(1.0)
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(0.0)
            self._fade.finished.connect(_hide)
            self._fade.start()

    def _on_eye_toggled(self, checked: bool) -> None:
        self.visibilityToggled.emit(bool(checked))
        self.layer.visible = bool(checked)
        self._update_icons(hover=self._hovered)

    def _on_lock_toggled(self, checked: bool) -> None:
        self.lockToggled.emit(bool(checked))
        self.layer.locked = bool(checked)
        self._update_icons(hover=self._hovered)

    def _update_icons(self, hover: bool) -> None:
        """Set icons using Font Awesome 5 (solid). Fallback to text on error."""
        col = Theme.icon_hover.name() if hover else Theme.icon_idle.name()
        try:
            eye_on  = qta.icon('fa5s.eye', color=col)
            eye_off = qta.icon('fa5s.eye-slash', color=col)
            lock_on  = qta.icon('fa5s.lock', color=col)
            lock_off = qta.icon('fa5s.lock-open', color=col)
            plus_ic  = qta.icon('fa5s.plus', color=col)
            rename_ic= qta.icon('fa5s.edit', color=col)
            color_ic = qta.icon('fa5s.palette', color=col)
            del_ic   = qta.icon('fa5s.trash', color=col)

            # Clear any previous text fallback if used earlier
            for b in (self.eye, self.lock, self.add_btn, self.rename_btn, self.color_btn, self.delete_btn):
                b.setText("")

            self.eye.setIcon(eye_on if self.layer.visible else eye_off)
            self.lock.setIcon(lock_on if self.layer.locked else lock_off)
            self.add_btn.setIcon(plus_ic)
            self.rename_btn.setIcon(rename_ic)
            self.color_btn.setIcon(color_ic)
            self.delete_btn.setIcon(del_ic)
        except Exception:
            # Safe fallback so UI continues to work without QtAwesome fonts
            self.eye.setIcon(QtGui.QIcon());    self.eye.setText("👁" if self.layer.visible else "🙈")
            self.lock.setIcon(QtGui.QIcon());   self.lock.setText("🔒" if self.layer.locked else "🔓")
            self.add_btn.setIcon(QtGui.QIcon()); self.add_btn.setText("＋")
            self.rename_btn.setIcon(QtGui.QIcon()); self.rename_btn.setText("✎")
            self.color_btn.setIcon(QtGui.QIcon());  self.color_btn.setText("🎨")
            self.delete_btn.setIcon(QtGui.QIcon()); self.delete_btn.setText("🗑")

    def paintEvent(self, e: QtGui.QPaintEvent):
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect()

        # Compute y under the title for the range strip (crisp, integer-aligned)
        m = self.layout().contentsMargins()
        top_y = rect.y() + m.top()
        # Use title font metrics to place the strip below the label
        fm = self.title.fontMetrics()
        title_h = fm.height()
        y = int(top_y + title_h + 8)  # 8px gap below title
        h = 3  # 2–3 px strip; pick 3 for better visibility

        left = rect.x() + m.left()
        right = rect.right() - m.right()
        width = max(0, right - left)

        # Base rail (underlay)
        base_h = h  # keep same height as the colored span for a clean overlay
        base = QtCore.QRect(left, y, width, base_h)
        p.fillRect(base, NOTE_RAIL_COLOR)

        # Colored span at ~40% alpha
        if self.in_s is not None and self.out_s is not None and self.out_s > self.in_s and width > 0:
            x0 = left + int((float(self.in_s) / self.duration_s) * width)
            x1 = left + int((float(self.out_s) / self.duration_s) * width)
            span = QtCore.QRect(min(x0, x1), y, max(6, abs(x1 - x0)), h)
            band = QtGui.QColor(self.layer.color); band.setAlpha(int(255 * 0.40))
            p.fillRect(span, band)

        p.end()

    # ── Inline rename helpers ──────────────────────────────────────────
    def _begin_inline_rename(self) -> None:
        """Enter inline edit mode for the title."""
        cur = self.title.text()

        # Ensure editor text is up to date
        self.title_edit.blockSignals(True)
        self.title_edit.setText(cur)
        self.title_edit.blockSignals(False)

        # Show editor page
        self._show_title_editor(True)

        # Defer focus/select to the next event loop cycle so geometry is valid on first show
        def _focus_and_select():
            if not self.title_edit.isVisible():
                return
            self.title_edit.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            self.title_edit.selectAll()
        QtCore.QTimer.singleShot(0, _focus_and_select)

        # Wire signals (disconnect specific slot if previously connected)
        if self._rename_wired:
            try:
                self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception:
                pass
            try:
                self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception:
                pass
        self.title_edit.returnPressed.connect(self._commit_inline_rename)
        self.title_edit.editingFinished.connect(self._commit_inline_rename)  # focus-out commits
        self._rename_wired = True

    def _show_title_editor(self, on: bool) -> None:
        # Switch pages; no manual setVisible toggles to avoid layout/geometry races
        self._title_stack.setCurrentWidget(self.title_edit if on else self.title)
        self.update()

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        # Allow Esc to cancel inline rename when editor is active
        if self.title_edit.isVisible() and e.key() == QtCore.Qt.Key_Escape:
            self._cancel_inline_rename()
            e.accept()
            return
        super().keyPressEvent(e)

    def _commit_inline_rename(self) -> None:
        """Commit the inline rename, update the label/model, and clean up wiring."""
        # Grab and normalize text
        new_text = (self.title_edit.text() or "").strip()
        if not new_text:
            # If blank, treat as cancel to avoid empty names
            self._cancel_inline_rename()
            return

        # Apply if changed
        if new_text != self.title.text():
            self.setName(new_text)
            # Let external code react if connected
            try:
                self.renameRequested.emit()
            except Exception:
                pass

        # Switch back to label and disconnect rename wiring
        self._show_title_editor(False)
        if self._rename_wired:
            try:
                self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception:
                pass
            try:
                self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception:
                pass
            self._rename_wired = False

    def _cancel_inline_rename(self) -> None:
        """Cancel inline rename: discard edits and restore view."""
        # Restore editor text to current title to keep them in sync
        cur = self.title.text()
        self.title_edit.blockSignals(True)
        self.title_edit.setText(cur)
        self.title_edit.blockSignals(False)

        # Switch back to label and disconnect rename wiring
        self._show_title_editor(False)
        if self._rename_wired:
            try:
                self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception:
                pass
            try:
                self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception:
                pass
            self._rename_wired = False