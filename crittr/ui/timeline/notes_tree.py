from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict

from crittr.qt import QtCore, QtGui, QtWidgets
from .note_card import NoteCard
from .group_header import GroupHeaderWidget

@dataclass
class Note:
    id: str
    layer_id: str
    start_s: float
    end_s: float
    text: str = ""
    drawing_id: Optional[str] = None
    drawing_opacity: float = 1.0  # 0..1

@dataclass
class Layer:
    id: str
    name: str
    visible: bool = True
    locked: bool = False
    color: QtGui.QColor = field(default_factory=lambda: QtGui.QColor("#8ab4f8"))

class NotesTree(QtWidgets.QTreeWidget):
    groupActivated = QtCore.Signal(str, float, float)
    groupMenuRequested = QtCore.Signal(str, QtCore.QPoint)
    groupRenamed = QtCore.Signal(str, str)
    groupColorChanged = QtCore.Signal(str, QtGui.QColor)
    groupDeleted = QtCore.Signal(str)
    groupVisibilityChanged = QtCore.Signal(str, bool)
    groupLockChanged = QtCore.Signal(str, bool)

    noteActivated = QtCore.Signal(str, float, float, str)
    noteEditRequested = QtCore.Signal(str)
    noteDeleteRequested = QtCore.Signal(str)
    noteDuplicateRequested = QtCore.Signal(str)

    notePillDragStarted = QtCore.Signal(str, float, float)
    notePillDragging = QtCore.Signal(str, float, float, float)
    notePillDragFinished = QtCore.Signal(str, float, float, bool)

    noteDrawingAddRequested = QtCore.Signal(str)
    noteDrawingClearRequested = QtCore.Signal(str)
    noteDrawingOpacityRequested = QtCore.Signal(str, float)
    noteOpenDetailRequested = QtCore.Signal(str)

    selectionChangedSig = QtCore.Signal(list, object)
    addNoteRequested = QtCore.Signal(str)  # layer_id where the add was requested

    def __init__(self, duration_s: float, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(18)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QTreeWidget { background: #26292e; border: 0; }")

        self.duration_s = max(0.001, float(duration_s))
        self._layer_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._layer_headers: Dict[str, GroupHeaderWidget] = {}
        self._notes_by_layer: Dict[str, List[Note]] = {}
        self._note_id_counter = 0

    def set_duration(self, duration_s: float) -> None:
        """Update duration for all visuals (headers, cards)."""
        new_d = max(0.001, float(duration_s))
        if abs(new_d - self.duration_s) <= 1e-9:
            return
        self.duration_s = new_d
        # Update headers
        for lid, hdr in self._layer_headers.items():
            hdr.setDuration(self.duration_s)
            # Refresh span drawing
            hdr.setRange(*self._compute_layer_range(lid))
        # Update cards
        for i in range(self.topLevelItemCount()):
            parent = self.topLevelItem(i)
            for r in range(parent.childCount()):
                it = parent.child(r)
                w = self.itemWidget(it, 0)
                if isinstance(w, NoteCard):
                    w.setDuration(self.duration_s)
        self.viewport().update()

    def add_layer(self, layer: Layer, notes: List[Note]):
        header_item = QtWidgets.QTreeWidgetItem(self)
        header_item.setFirstColumnSpanned(True)
        header_item.setData(0, QtCore.Qt.UserRole, ("layer", layer.id))
        self.addTopLevelItem(header_item)
        self._layer_items[layer.id] = header_item
        self._notes_by_layer[layer.id] = list(notes)

        group_range = self._compute_layer_range(layer.id)
        header = GroupHeaderWidget(layer, self.duration_s, group_range)
        self._layer_headers[layer.id] = header
        self.setItemWidget(header_item, 0, header)

        header.titleClicked.connect(lambda lid=layer.id: self._emit_group_activate(lid))
        header.titleDoubleClicked.connect(lambda it=header_item: it.setExpanded(not it.isExpanded()))
        header.visibilityToggled.connect(lambda v, lid=layer.id: self.groupVisibilityChanged.emit(lid, v))
        header.lockToggled.connect(lambda v, lid=layer.id: (self.groupLockChanged.emit(lid, v), self.setLayerLocked(lid, v)))
        header.addNoteRequested.connect(lambda lid=layer.id: self._emit_add_note(lid))
        header.menuRequested.connect(lambda pos, lid=layer.id: self._open_group_menu(lid, pos))

        spacer = QtWidgets.QTreeWidgetItem(header_item)
        spacer.setDisabled(True)
        div = QtWidgets.QFrame(); div.setFixedHeight(1); div.setStyleSheet("background:#3a3f46;")
        self.setItemWidget(spacer, 0, div)

        for n in notes:
            self._add_note_row(header_item, n, layer)

        header_item.setExpanded(True)

    # Convenience/public helpers for external composition

    def find_layer_by_name(self, name: str) -> Optional[str]:
        """Return layer_id for a given display name, if exists."""
        nm = (name or "").strip().lower()
        for lid, hdr in self._layer_headers.items():
            if hdr.title.text().strip().lower() == nm:
                return lid
        return None

    def get_layer(self, layer_id: str) -> Optional[Layer]:
        """Return the Layer object for an id."""
        hdr = self._layer_headers.get(layer_id)
        return hdr.layer if hdr else None

    def add_layer_simple(self, name: str, color: QtGui.QColor) -> str:
        """Create a new layer with no notes and return its id."""
        lid = self._alloc_layer_id(name)
        layer = Layer(lid, name.strip() or "Layer", True, False, color if color.isValid() else QtGui.QColor("#8ab4f8"))
        self.add_layer(layer, [])
        return lid

    def add_note(self, layer_id: str, note: Note) -> None:
        """Add one note to an existing layer and refresh visuals."""
        parent_item = self._layer_items.get(layer_id)
        layer = self.get_layer(layer_id)
        if not parent_item or not layer:
            return
        note.layer_id = layer_id
        self._notes_by_layer.setdefault(layer_id, []).append(note)
        self._add_note_row(parent_item, note, layer)
        self.refreshLayerRange(layer_id)

    def alloc_note_id(self) -> str:
        nid = f"n{self._note_id_counter}"
        self._note_id_counter += 1
        return nid

    def _alloc_layer_id(self, name: str) -> str:
        # Keep IDs simple and unique; derive from name when possible
        base = "".join(ch for ch in (name or "L").strip() if ch.isalnum()) or "L"
        candidate = f"{base}"
        suffix = 1
        existing = set(self._layer_items.keys())
        while candidate in existing:
            suffix += 1
            candidate = f"{base}{suffix}"
        return candidate

    def _add_note_row(self, parent_item: QtWidgets.QTreeWidgetItem, n: Note, layer: Layer):
        it = QtWidgets.QTreeWidgetItem(parent_item)
        it.setData(0, QtCore.Qt.UserRole, ("note", n.id))
        card = NoteCard(n, layer, self.duration_s)
        self.setItemWidget(it, 0, card)

        card.activated.connect(self.noteActivated)
        card.editRequested.connect(self.noteEditRequested)
        card.deleteRequested.connect(self.noteDeleteRequested)
        card.duplicateRequested.connect(self.noteDuplicateRequested)
        card.pillDragStarted.connect(self.notePillDragStarted)
        card.pillDragging.connect(self.notePillDragging)
        card.pillDragFinished.connect(self._on_pill_finished)
        card.drawingAddRequested.connect(self._on_draw_add)
        card.drawingClearRequested.connect(self._on_draw_clear)
        card.drawingOpacityRequested.connect(self.noteDrawingOpacityRequested)
        card.openDetailRequested.connect(self.noteOpenDetailRequested)
        card.activated.connect(lambda nid, s, e, lid: self._select_only(nid))

    def _select_only(self, note_id: str):
        selected_ids = []
        for i in range(self.topLevelItemCount()):
            parent = self.topLevelItem(i)
            for r in range(parent.childCount()):
                it = parent.child(r)
                w = self.itemWidget(it, 0)
                if isinstance(w, NoteCard):
                    sel = (w.note.id == note_id)
                    w.setSelected(sel)
                    if sel:
                        selected_ids.append(w.note.id)
        layer_id = None
        if selected_ids:
            nid = selected_ids[0]
            for L, notes in self._notes_by_layer.items():
                if any(n.id == nid for n in notes):
                    layer_id = L
                    break
        self.selectionChangedSig.emit(selected_ids, layer_id)

    def setLayerLocked(self, layer_id: str, locked: bool):
        it = self._layer_items.get(layer_id)
        if not it:
            return
        for r in range(it.childCount()):
            child = it.child(r)
            w = self.itemWidget(child, 0)
            if isinstance(w, NoteCard):
                w.setLocked(locked)

    def _find_note_and_layer(self, note_id: str) -> tuple[Optional[Note], Optional[str]]:
        """Return (note_obj, layer_id) for a given note_id, or (None, None) if not found."""
        for layer_id, notes in self._notes_by_layer.items():
            for n in notes:
                if n.id == note_id:
                    return n, layer_id
        return None, None

    def _on_pill_finished(self, note_id: str, s: float, e: float, commit: bool):
        """Handle end of pill drag from a NoteCard: update state, refresh header range, and re-emit."""
        note, layer_id = self._find_note_and_layer(note_id)
        if note is not None:
            note.start_s = float(s)
            note.end_s = float(e)
            if layer_id:
                self.refreshLayerRange(layer_id)
        # Re-emit so external consumers (MainWindow wiring) can react.
        self.notePillDragFinished.emit(note_id, float(s), float(e), bool(commit))

    def _on_draw_add(self, note_id: str):
        """Forward draw-add request from a NoteCard."""
        self.noteDrawingAddRequested.emit(note_id)

    def _on_draw_clear(self, note_id: str):
        """Forward draw-clear request from a NoteCard."""
        self.noteDrawingClearRequested.emit(note_id)


    def _compute_layer_range(self, layer_id: str) -> Tuple[Optional[float], Optional[float]]:
        notes = self._notes_by_layer.get(layer_id) or []
        if not notes:
            return (None, None)
        start = min(n.start_s for n in notes)
        end   = max(n.end_s for n in notes)
        return (start, end)

    def refreshLayerRange(self, layer_id: str):
        hdr = self._layer_headers.get(layer_id)
        if not hdr:
            return
        hdr.setRange(*self._compute_layer_range(layer_id))

    def _emit_group_activate(self, layer_id: str):
        rng = self._compute_layer_range(layer_id)
        s = rng[0] if rng[0] is not None else 0.0
        e = rng[1] if rng[1] is not None else 0.0
        self.groupActivated.emit(layer_id, s, e)

    def _emit_add_note(self, layer_id: str):
        self.selectionChangedSig.emit([], layer_id)
        self.addNoteRequested.emit(layer_id)

    def _open_group_menu(self, layer_id: str, at_global_pos: QtCore.QPoint):
        self.groupMenuRequested.emit(layer_id, at_global_pos)
        m = QtWidgets.QMenu(self)
        act_rename = m.addAction("Rename Group…")
        act_color  = m.addAction("Change Group Color…")
        act_del    = m.addAction("Delete Group")
        m.addSeparator()
        it = self._layer_items.get(layer_id)
        hdr = self._layer_headers.get(layer_id)
        is_locked = hdr.lock.isChecked() if hdr else False
        is_visible = hdr.eye.isChecked() if hdr else True
        act_lock  = m.addAction("Unlock Group" if is_locked else "Lock Group")
        act_show  = m.addAction("Hide Group" if is_visible else "Show Group")
        chosen = m.exec(at_global_pos)
        if not chosen:
            return
        if chosen is act_rename:
            new, ok = QtWidgets.QInputDialog.getText(self, "Rename Group", "Name:", text=hdr.title.text() if hdr else "")
            if ok and new.strip():
                if hdr: hdr.setName(new.strip())
                self.groupRenamed.emit(layer_id, new.strip())
        elif chosen is act_color:
            col = QtWidgets.QColorDialog.getColor(hdr.layer.color if hdr else QtGui.QColor("#8ab4f8"), self, options=QtWidgets.QColorDialog.DontUseNativeDialog)
            if col.isValid():
                if hdr: hdr.setColor(col)
                if it:
                    for r in range(it.childCount()):
                        w = self.itemWidget(it.child(r), 0)
                        if isinstance(w, NoteCard):
                            w.layer.color = col; w.update()
                self.groupColorChanged.emit(layer_id, col)
        elif chosen is act_del:
            self.groupDeleted.emit(layer_id)
            idx = self.indexOfTopLevelItem(it)
            if idx >= 0:
                self.takeTopLevelItem(idx)
            self._layer_items.pop(layer_id, None)
            self._layer_headers.pop(layer_id, None)
            self._notes_by_layer.pop(layer_id, None)
        elif chosen is act_lock:
            new_state = not is_locked
            if hdr: hdr.lock.setChecked(new_state)
            self.groupLockChanged.emit(layer_id, new_state)
            self.setLayerLocked(layer_id, new_state)
        elif chosen is act_show:
            new_state = not is_visible
            if hdr: hdr.eye.setChecked(new_state)
            self.groupVisibilityChanged.emit(layer_id, new_state)