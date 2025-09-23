# crittr/ui/main_window.py
from __future__ import annotations
from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.core.config import get_settings
from crittr.ui.player_widget import PlayerWidget
from crittr.ui.notes_view import NotesPanel
from crittr.ui.playlist_view import PlaylistView
from crittr.ui.inspector_tabs import InspectorTabs
from crittr.ui.timeline.view import TimelineView
from crittr.ui.timeline.controller import TimelineController
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
        self.notes = NotesPanel(self)

        self.inspector = InspectorTabs(self)

        # Timeline at the bottom
        self._timeline_view = TimelineView(self)
        self._timeline_ctrl = TimelineController(self._timeline_view, self)

        splitter = QtWidgets.QSplitter()
        left_col = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_col)
        left_layout.addWidget(self.player, 1)
        left_layout.addWidget(self._timeline_view, 0)
        splitter.addWidget(left_col)
        splitter.addWidget(self.inspector)

        self.setCentralWidget(splitter)


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
        # If player exposes controller and duration, wire the clock to the timeline controller
        try:
            self.player.controller.timeChanged.connect(self._timeline_ctrl.on_time_changed)
            # Set duration when known
            def _on_duration(d):
                self._timeline_ctrl.set_duration(d)
            self.player.controller.durationChanged.connect(_on_duration)
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
