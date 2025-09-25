from PySide6 import QtCore
from .notes_tree import Note  # use existing Note type

class NotesController(QtCore.QObject):
    def __init__(self, player, notes_panel):
        super().__init__()
        self.player = player
        self.notes  = notes_panel
        self._connect()

    def _connect(self):
        self.notes.groupActivated.connect(lambda _lid, s, _e: self._seek(s))
        self.notes.noteActivated.connect(lambda _nid, s, _e, _lid: self._seek(s))
        self.notes.notePillDragStarted.connect(self._on_drag_start)
        self.notes.notePillDragging.connect(self._on_drag)
        self.notes.notePillDragFinished.connect(self._on_drag_finish)
        self.notes.addNoteRequested.connect(self._on_add_note)
        # Drawing actions (stub for MVP)
        self.notes.noteDrawingAddRequested.connect(self._noop)
        self.notes.noteDrawingClearRequested.connect(self._noop)
        self.notes.noteDrawingOpacityRequested.connect(self._noop)

    def _seek(self, s):
        self.player.pause()
        self.player.seek(float(s))

    def _on_drag_start(self, *_):
        self.player.pause()

    def _on_drag(self, _nid, _s, _e, t):
        self.player.preview(float(t))

    def _on_drag_finish(self, _nid, s, _e, _commit):
        self.player.seek(float(s))

    def _on_add_note(self, layer_id: str):
        """Create a new note at current player time into the requested layer."""
        try:
            duration = float(self.notes.tree.duration_s)
            cur = float(getattr(self.notes, "_current_time", 0.0))
            start = max(0.0, min(cur, max(0.0, duration - 0.5)))
            end = min(duration, start + 2.0)
            nid = self.notes.tree.alloc_note_id()
            note = Note(id=nid, layer_id=layer_id, start_s=start, end_s=end, text="")
            self.notes.tree.add_note(layer_id, note)
            # Select/focus the new note
            self.notes.tree._select_only(nid)
        except Exception:
            pass

    def _noop(self, *a, **k): pass