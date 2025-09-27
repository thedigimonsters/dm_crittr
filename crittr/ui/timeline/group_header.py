from __future__ import annotations
from typing import Optional, Tuple

from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.ui.theme import Theme, NOTE_RAIL_COLOR
import qtawesome as qta
from crittr.core.logging import get_logger

# 12 dark presets that sit well on a dark UI with white text
_DARK_PRESET_HEX = [
    "#1E40AF",  # blue-800
    "#3730A3",  # indigo-800
    "#4C1D95",  # purple-900
    "#6D28D9",  # violet-700
    "#0F766E",  # teal-700
    "#065F46",  # emerald-800
    "#14532D",  # green-900
    "#92400E",  # amber-800
    "#B45309",  # amber-700
    "#B91C1C",  # red-700
    "#9D174D",  # rose-800
    "#334155",  # slate-700
]


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
    # External signals (unchanged)
    titleClicked = QtCore.Signal()
    titleDoubleClicked = QtCore.Signal()
    menuRequested = QtCore.Signal(QtCore.QPoint)
    addNoteRequested = QtCore.Signal()
    visibilityToggled = QtCore.Signal(bool)
    lockToggled = QtCore.Signal(bool)
    renameRequested = QtCore.Signal()
    colorChangeRequested = QtCore.Signal()   # emitted after swatch pick
    deleteRequested = QtCore.Signal()

    def __init__(
        self,
        layer,
        duration_s: float,
        group_range: Tuple[Optional[float], Optional[float]] = (None, None),
        parent=None,
    ):
        super().__init__(parent)
        self.layer = layer
        self.duration_s = max(0.001, float(duration_s))
        self.in_s, self.out_s = group_range
        self.logger = get_logger("critter.ui.timeline.group_header")

        self._hovered = False
        self._active = False
        self._rename_wired = False
        self._color_menu: Optional[QtWidgets.QMenu] = None

        # Allow style sheets to paint the widget background
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        # Use the Theme colors you added (camelCase or UPPER, match your Theme)
        self.setStyleSheet(
            f"""
            GroupHeaderWidget {{
                background-color: {Theme.header_bg.name()};
            }}
            GroupHeaderWidget:hover {{
                background-color: {Theme.header_bg_hover.name()};
            }}
            GroupHeaderWidget[active="true"] {{
                background-color: {Theme.header_bg_active.name()};
            }}
            """
        )

        self.setMouseTracking(True)
        #self.setAutoFillBackground(False)
        self.setFixedHeight(44)  # comfy header height

        # Layout
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # Title (clickable) + inline editor stack
        self.title = ClickLabel(layer.name)
        self.title.setStyleSheet(f"color:{Theme.text.name()}; font-weight:600;")

        self.title_edit = QtWidgets.QLineEdit(layer.name)
        self.title_edit.setFont(self.title.font())
        self.title_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: 1px solid transparent; "
            f"color:{Theme.text.name()}; font-weight:600; padding:0; }}"
        )

        self._title_stack = QtWidgets.QStackedWidget()
        self._title_stack.addWidget(self.title)
        self._title_stack.addWidget(self.title_edit)
        self._title_stack.setCurrentWidget(self.title)
        self._title_stack.setContentsMargins(0, 0, 0, 0)
        self._title_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )

        root.addWidget(self._title_stack)
        root.addStretch(1)

        # Right-side controls (show on hover/active)
        self.controls = QtWidgets.QWidget(self)
        c = QtWidgets.QHBoxLayout(self.controls)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(4)

        btn_css = (
            "QToolButton { background: transparent; border: 0; padding: 0; margin: 0; }"
            "QToolButton:hover { background: transparent; }"
            "QToolButton:pressed { background: transparent; }"
            "QToolButton:checked { background: transparent; }"
            "QToolButton:focus { outline: none; }"
        )

        self.eye = QtWidgets.QToolButton(self); self.eye.setCheckable(True); self.eye.setChecked(layer.visible)
        self.eye.setToolTip("Toggle visibility")
        self.lock = QtWidgets.QToolButton(self); self.lock.setCheckable(True); self.lock.setChecked(layer.locked)
        self.lock.setToolTip("Toggle lock")
        self.add_btn = QtWidgets.QToolButton(self); self.add_btn.setToolTip("Add note to this layer")
        self.rename_btn = QtWidgets.QToolButton(self); self.rename_btn.setToolTip("Rename group")
        self.color_btn  = QtWidgets.QToolButton(self); self.color_btn.setToolTip("Change group color")
        self.delete_btn = QtWidgets.QToolButton(self); self.delete_btn.setToolTip("Delete group")

        for b in (self.eye, self.lock, self.add_btn, self.rename_btn, self.color_btn, self.delete_btn):
            b.setStyleSheet(btn_css)
            b.setAutoRaise(False)
            b.setIconSize(QtCore.QSize(14, 14))
            b.setFixedSize(24, 24)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            c.addWidget(b)

        root.addWidget(self.controls)

        # Hover fade for controls
        self._controls_fx = QtWidgets.QGraphicsOpacityEffect(self.controls)
        self.controls.setGraphicsEffect(self._controls_fx)
        self._fade = QtCore.QPropertyAnimation(self._controls_fx, b"opacity", self)
        self._fade.setDuration(120)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self.controls.setVisible(False)

        # Icon setup
        self._update_icons(hover=False)

        # Wire signals
        self.title.clicked.connect(self.titleClicked)
        self.title.doubleClicked.connect(self.titleDoubleClicked)

        self.eye.toggled.connect(self._on_eye_toggled)
        self.lock.toggled.connect(self._on_lock_toggled)
        self.add_btn.clicked.connect(self.addNoteRequested)
        self.rename_btn.clicked.connect(self._begin_inline_rename)
        self.color_btn.clicked.connect(self._show_color_menu)
        self.delete_btn.clicked.connect(self.deleteRequested)

    # ───────────────────────────────────────────────────────────────────
    # Public setters/state
    # ───────────────────────────────────────────────────────────────────
    def setRange(self, in_s, out_s):
        self.in_s, self.out_s = in_s, out_s
        self.update()

    def setDuration(self, duration_s: float) -> None:
        new_d = max(0.001, float(duration_s))
        if abs(new_d - self.duration_s) > 1e-9:
            self.duration_s = new_d
            self.update()

    def setName(self, new_name: str):
        self.layer.name = new_name
        self.title.setText(new_name)
        self.title_edit.blockSignals(True)
        self.title_edit.setText(new_name)
        self.title_edit.blockSignals(False)
        self.update()

    def setColor(self, color: QtGui.QColor):
        self.layer.color = color
        self.update()

    def setActive(self, active: bool) -> None:
        self.logger.debug(f"GroupHeaderWidget.setActive({active})")
        if self._active != bool(active):
            self._active = bool(active)
            # expose state to the stylesheet
            self.setProperty("active", self._active)
            # re-evaluate the stylesheet for this widget
            self.style().unpolish(self)
            self.style().polish(self)
            self._update_controls_visibility()
            self.update()
    # ───────────────────────────────────────────────────────────────────
    # Hover & controls visibility
    # ───────────────────────────────────────────────────────────────────
    def enterEvent(self, e: QtCore.QEvent) -> None:
        self._hovered = True
        self._update_icons(hover=True)
        self._update_controls_visibility()
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e: QtCore.QEvent) -> None:
        self._hovered = False
        self._update_icons(hover=False)
        self._update_controls_visibility()
        self.update()
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
            def _hide():
                self.controls.setVisible(False)
                try:
                    self._fade.finished.disconnect(_hide)
                except Exception:
                    pass
            self._fade.stop()
            self._controls_fx.setOpacity(1.0)
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(0.0)
            self._fade.finished.connect(_hide)
            self._fade.start()

    # ───────────────────────────────────────────────────────────────────
    # Icons
    # ───────────────────────────────────────────────────────────────────
    def _on_eye_toggled(self, checked: bool) -> None:
        self.visibilityToggled.emit(bool(checked))
        self.layer.visible = bool(checked)
        self._update_icons(hover=self._hovered)

    def _on_lock_toggled(self, checked: bool) -> None:
        self.lockToggled.emit(bool(checked))
        self.layer.locked = bool(checked)
        self._update_icons(hover=self._hovered)

    def _update_icons(self, hover: bool) -> None:
        col = Theme.icon_hover.name() if hover or self._active else Theme.icon_idle.name()
        try:
            self.eye.setIcon(qta.icon('fa5s.eye' if self.layer.visible else 'fa5s.eye-slash', color=col))
            self.lock.setIcon(qta.icon('fa5s.lock' if self.layer.locked else 'fa5s.lock-open', color=col))
            self.add_btn.setIcon(qta.icon('fa5s.plus', color=col))
            self.rename_btn.setIcon(qta.icon('fa5s.edit', color=col))
            self.color_btn.setIcon(qta.icon('fa5s.palette', color=col))
            self.delete_btn.setIcon(qta.icon('fa5s.trash', color=col))
        except Exception:
            # basic fallbacks if QtAwesome missing
            self.eye.setText("👁" if self.layer.visible else "🙈")
            self.lock.setText("🔒" if self.layer.locked else "🔓")
            self.add_btn.setText("＋")
            self.rename_btn.setText("✎")
            self.color_btn.setText("🎨")
            self.delete_btn.setText("🗑")

    # ───────────────────────────────────────────────────────────────────
    # Paint (background + group range strip)
    # ───────────────────────────────────────────────────────────────────
    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        # Do NOT fill the background here; stylesheet handles it.
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Range strip under the title (unchanged)
        m = self.layout().contentsMargins()
        top_y = self.rect().y() + m.top()
        fm = self.title.fontMetrics()
        title_h = fm.height()
        y = int(top_y + title_h + 8)
        h = 3

        left = self.rect().x() + m.left()
        right = self.rect().right() - m.right()
        width = max(0, right - left)

        p.fillRect(QtCore.QRect(left, y, width, h), NOTE_RAIL_COLOR)

        if self.in_s is not None and self.out_s is not None and self.out_s > self.in_s and width > 0:
            x0 = left + int((float(self.in_s) / self.duration_s) * width)
            x1 = left + int((float(self.out_s) / self.duration_s) * width)
            span = QtCore.QRect(min(x0, x1), y, max(6, abs(x1 - x0)), h)
            band = QtGui.QColor(self.layer.color);
            band.setAlpha(int(255 * 0.40))
            p.fillRect(span, band)

        p.end()

    # ───────────────────────────────────────────────────────────────────
    # Inline rename
    # ───────────────────────────────────────────────────────────────────
    def _begin_inline_rename(self) -> None:
        cur = self.title.text()
        self.title_edit.blockSignals(True)
        self.title_edit.setText(cur)
        self.title_edit.blockSignals(False)
        self._show_title_editor(True)

        def _focus_and_select():
            if self.title_edit.isVisible():
                self.title_edit.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
                self.title_edit.selectAll()

        QtCore.QTimer.singleShot(0, _focus_and_select)

        if self._rename_wired:
            try: self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception: pass
            try: self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception: pass
        self.title_edit.returnPressed.connect(self._commit_inline_rename)
        self.title_edit.editingFinished.connect(self._commit_inline_rename)
        self._rename_wired = True

    def _show_title_editor(self, on: bool) -> None:
        self._title_stack.setCurrentWidget(self.title_edit if on else self.title)
        self.update()

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if self.title_edit.isVisible() and e.key() == QtCore.Qt.Key_Escape:
            self._cancel_inline_rename()
            e.accept()
            return
        super().keyPressEvent(e)

    def _commit_inline_rename(self) -> None:
        new_text = (self.title_edit.text() or "").strip()
        if not new_text:
            self._cancel_inline_rename()
            return
        if new_text != self.title.text():
            self.setName(new_text)
            self.renameRequested.emit()
        self._show_title_editor(False)
        if self._rename_wired:
            try: self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception: pass
            try: self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception: pass
            self._rename_wired = False

    def _cancel_inline_rename(self) -> None:
        cur = self.title.text()
        self.title_edit.blockSignals(True)
        self.title_edit.setText(cur)
        self.title_edit.blockSignals(False)
        self._show_title_editor(False)
        if self._rename_wired:
            try: self.title_edit.returnPressed.disconnect(self._commit_inline_rename)
            except Exception: pass
            try: self.title_edit.editingFinished.disconnect(self._commit_inline_rename)
            except Exception: pass
            self._rename_wired = False

    # ───────────────────────────────────────────────────────────────────
    # Color palette menu
    # ───────────────────────────────────────────────────────────────────
    def _show_color_menu(self) -> None:
        """Show a 12-swatch palette; pick applies immediately and emits colorChangeRequested."""
        if self._color_menu is None:
            self._color_menu = self._build_color_menu()
        pos = self.color_btn.mapToGlobal(QtCore.QPoint(0, self.color_btn.height()))
        self._color_menu.popup(pos)

    def _build_color_menu(self) -> QtWidgets.QMenu:
        m = QtWidgets.QMenu(self)
        m.setStyleSheet("QMenu { padding: 6px; }")

        grid_host = QtWidgets.QWidget(m)
        gl = QtWidgets.QGridLayout(grid_host)
        gl.setContentsMargins(6, 6, 6, 6)
        gl.setSpacing(6)

        # 3 rows x 4 cols
        for i, hx in enumerate(_DARK_PRESET_HEX):
            r, c = divmod(i, 4)
            btn = QtWidgets.QToolButton(grid_host)
            btn.setFixedSize(22, 22)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setAutoRaise(True)
            btn.setToolTip(hx)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid rgba(0,0,0,110); border-radius: 4px; background:%s; }"
                "QToolButton:hover { border-color: white; }" % hx
            )
            btn.clicked.connect(lambda _=False, color_hex=hx: self._apply_palette_pick(color_hex))
            gl.addWidget(btn, r, c)

        wact = QtWidgets.QWidgetAction(m)
        wact.setDefaultWidget(grid_host)
        m.addAction(wact)
        return m

    def _apply_palette_pick(self, color_hex: str) -> None:
        col = QtGui.QColor(color_hex)
        if not col.isValid():
            return
        self.setColor(col)               # update model + repaint
        self.colorChangeRequested.emit()  # keep existing signature (no payload)
        if self._color_menu is not None:
            self._color_menu.hide()
