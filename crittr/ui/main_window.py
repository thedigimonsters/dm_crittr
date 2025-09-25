# crittr/ui/main_window.py
from __future__ import annotations
from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.core.config import get_settings
from crittr.ui.player_widget import PlayerWidget
# from crittr.ui.notes_view import NotesPanel
# from crittr.ui.timeline import NotesPanel
from crittr.ui.inspector_tabs import InspectorTabs
from app_config import APP_NAME, APP_PNG

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        print(APP_PNG)
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


        from crittr.ui.timeline.notes_tree import Layer, Note
        layers = [Layer("L1", "Blocking"), Layer("L2", "Polish"), Layer("L3", "FX")]
        self.inspector.notes_panel.tree.add_layer(layers[0], [Note("n1", "L1", 10, 20, "Example")])

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

    def _restore_state(self):
        # Example: restore window geometry
        g = self.settings.get("ui/main_geometry")
        if isinstance(g, QtCore.QByteArray):
            self.restoreGeometry(g)

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        self.settings.set("ui/main_geometry", self.saveGeometry())
        return super().closeEvent(e)
