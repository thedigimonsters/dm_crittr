# crittr/ui/timeline/controller.py
from __future__ import annotations
from typing import List, Optional
from crittr.qt import QtCore
from .model import Layer
from .view import TimelineView

class TimelineController(QtCore.QObject):
    def __init__(self, view: TimelineView, parent=None):
        super().__init__(parent)
        self.view = view
        self.layers: List[Layer] = []
        self.duration_s: float = 0.0
        self.duration_known: bool = False

        # Bootstrap with a few layers (top-down)
        self.set_layers([Layer(name="Layer 1", order=0),
                         Layer(name="Layer 2", order=1),
                         Layer(name="Layer 3", order=2)])

    def set_layers(self, layers: List[Layer]) -> None:
        self.layers = sorted(layers, key=lambda l: l.order)
        self.view.set_layers_count(len(self.layers))

    def set_duration(self, duration_s: Optional[float]) -> None:
        if duration_s and duration_s > 0:
            self.duration_s = float(duration_s)
            self.duration_known = True
        else:
            self.duration_s = 0.0
            self.duration_known = False

    @QtCore.Slot(float)
    def on_time_changed(self, pts_s: float) -> None:
        self.view.set_playhead_time(pts_s)