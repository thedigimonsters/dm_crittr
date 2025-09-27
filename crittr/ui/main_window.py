# crittr/ui/main_window.py
from __future__ import annotations
from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.core.config import get_settings
from crittr.ui.player_widget import PlayerWidget
# from crittr.ui.notes_view import NotesPanel
# from crittr.ui.timeline import NotesPanel
from crittr.ui.inspector_tabs import InspectorTabs
from app_config import APP_NAME, APP_PNG
from crittr.ui.timeline.notes_controller import NotesController

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QtGui.QIcon(APP_PNG))
        self.resize(1200, 720)
        self.settings = get_settings()

        self.player = PlayerWidget(self)
        # Notes panel now lives inside InspectorTabs as the "Notes" tab
        # self.notes = NotesPanel(0.0, self)

        self.inspector = InspectorTabs(self)

        splitter = QtWidgets.QSplitter()
        left_col = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_col)
        left_layout.addWidget(self.player, 1)
        # Left column no longer hosts Notes; it's in the right tabs
        splitter.addWidget(left_col)
        splitter.addWidget(self.inspector)

        self.setCentralWidget(splitter)

        # Minimal timeline ↔ playback wiring (use the notes panel from InspectorTabs)
        self._wire_timeline()

        self._build_menu()
        self._restore_state()

    # Menu to open media
    def _build_menu(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")

        open_act = QtGui.QAction("&Open...", self)
        open_act.triggered.connect(self._open_dialog)
        file_menu.addAction(open_act)

        exit_act = QtGui.QAction("E&xit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

    def _open_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open media", self.settings.get("paths/last_open_dir", ""),
            "Media Files (*.mp4 *.mov *.avi *.mkv *.m4v *.webm *.wmv *.mpg *.mpeg *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.exr)"
        )
        if not path:
            return
        self.settings.set("paths/last_open_dir", QtCore.QFileInfo(path).absolutePath())
        self.player.open(path)
        # Duration will be updated via controller signal wiring

    def _wire_timeline(self):
        np = getattr(self.inspector, "notes_panel", None)
        if np is None:
            return

        # Update timeline duration when known
        self.player.controller.durationChanged.connect(np.set_duration)
        # Forward current player time (seconds PTS) to notes panel
        self.player.controller.timeChanged.connect(np.set_current_time)

        # Bridge notes panel signals to player via controller to decouple UI from playback
        self.notes_controller = NotesController(self.player, np)

        # Group header click → seek to group start (paused seek)
        def _on_group_activated(layer_id: str, start_s: float, end_s: float):
            try:
                self.player.pause()
            except Exception:
                pass
            try:
                self.player.controller.seek_to_time(float(start_s))
            except Exception:
                pass

        np.groupActivated.connect(_on_group_activated)

        # Note activation → seek to note start (paused seek)
        def _on_note_activated(note_id: str, start_s: float, end_s: float, layer_id: str):
            try:
                self.player.pause()
            except Exception:
                pass
            try:
                self.player.controller.seek_to_time(float(start_s))
            except Exception:
                pass

        np.noteActivated.connect(_on_note_activated)

        # Pill scrubbing hooks
        def _on_pill_drag_started(note_id: str, s: float, e: float):
            try:
                self.player.pause()
            except Exception:
                pass

        def _on_pill_dragging(note_id: str, s: float, e: float, preview_t: float):
            try:
                self.player.controller.preview_frame_at(float(preview_t))
            except Exception:
                pass

        def _on_pill_drag_finished(note_id: str, s: float, e: float, commit: bool):
            center = 0.5 * (float(s) + float(e))
            try:
                self.player.controller.seek_to_time(center)
            except Exception:
                pass

        np.notePillDragStarted.connect(_on_pill_drag_started)
        np.notePillDragging.connect(_on_pill_dragging)
        np.notePillDragFinished.connect(_on_pill_drag_finished)

        # After wiring is in place, perform dev-mode seeding (auto-open + layers/notes)
        try:
            self._dev_seed_from_config()
        except Exception:
            pass

        # Hook global slider interactions to avoid competition with note timelines:
        try:
            tl = getattr(self.player, "timeline", None)
            if tl is not None:
                tl.sliderPressed.connect(lambda: (np.setGlobalInteraction(True), np.clearSelection()))
                tl.sliderMoved.connect(lambda _v: (np.setGlobalInteraction(True), np.clearSelection()))
                tl.sliderReleased.connect(lambda: np.setGlobalInteraction(False))
        except Exception:
            pass


    def _restore_state(self):
        # Example: restore window geometry
        g = self.settings.get("ui/main_geometry")
        if isinstance(g, QtCore.QByteArray):
            self.restoreGeometry(g)

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        self.settings.set("ui/main_geometry", self.saveGeometry())
        return super().closeEvent(e)

    def _dev_seed_from_config(self) -> None:
        """
        Dev seeding and auto-open controlled by app_config:
          - DEV_MODE: enable features when True
          - DEV_STARTUP_MOV: absolute path to auto-open on startup ("" disables)
          - DEV_LAYER: optional seed data (layers + notes)
        """
        from app_config import DEV_MODE, DEV_STARTUP_MOV, DEV_LAYER  # read contract from app_config
        import os
        if not DEV_MODE:
            return

        # 1) Auto-open video if configured and exists
        mov = (DEV_STARTUP_MOV or "").strip()
        if mov and os.path.isabs(mov) and os.path.exists(mov):
            try:
                self.player.open(mov)
            except Exception:
                pass

        # 2) Seed layers/notes if provided
        try:
            npanel = getattr(self.inspector, "notes_panel", None)
            if npanel is None:
                return
            tree = npanel.tree
            if not DEV_LAYER:
                return

            from crittr.ui.timeline.notes_tree import Layer, Note  # reuse existing types
            for L in DEV_LAYER:
                # Extract layer fields with reasonable defaults
                lid = str(L.get("id") or "").strip()
                lname = str(L.get("name") or "Layer").strip()
                color_hex = str(L.get("color") or "#8ab4f8").strip()
                qcolor = QtGui.QColor(color_hex) if QtGui.QColor(color_hex).isValid() else QtGui.QColor("#8ab4f8")

                notes_spec = L.get("notes") or []

                # If layer id is provided, construct Layer explicitly so we preserve the id
                if lid:
                    layer_obj = Layer(lid, lname, True, False, qcolor)
                    # Build Note objects bound to this layer id
                    notes_objs = []
                    for nd in notes_spec:
                        nid = str(nd.get("id") or tree.alloc_note_id())
                        s = float(nd.get("start_s") or 0.0)
                        e = float(nd.get("end_s") or max(0.0, s + 2.0))
                        txt = str(nd.get("text") or "")
                        notes_objs.append(Note(nid, lid, s, e, txt))
                    tree.add_layer(layer_obj, notes_objs)
                else:
                    # No explicit id → let tree allocate, then add notes individually
                    new_lid = tree.add_layer_simple(lname, qcolor)
                    for nd in notes_spec:
                        nid = str(nd.get("id") or tree.alloc_note_id())
                        s = float(nd.get("start_s") or 0.0)
                        e = float(nd.get("end_s") or max(0.0, s + 2.0))
                        txt = str(nd.get("text") or "")
                        tree.add_note(new_lid, Note(nid, new_lid, s, e, txt))
        except Exception:
            pass

