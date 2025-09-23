from __future__ import annotations
from typing import Optional, List
import numpy as np

from crittr.core.video import VideoBackendFFPyPlayer  # legacy import still used by controller
from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.ui.frame_view import FrameView
from crittr.ui.marker_slider import MarkerSlider
from crittr.core.logging import get_logger
import math
from crittr.core.media_controller import MediaController, pts_to_ms, ms_to_pts, frame_of

class PlayerWidget(QtWidgets.QWidget):
    """
    Lean media player widget:
      - Frame display (FrameView)
      - Transport controls (prev/play/pause/next, rate)
      - MarkerSlider timeline
    Exposes signals and simple API so higher-level containers can add notes, playlists, etc.
    """
    # Signals for composition
    mediaOpened = QtCore.Signal(str)
    mediaEnded = QtCore.Signal()
    playStateChanged = QtCore.Signal(bool)        # True if playing
    frameChanged = QtCore.Signal(int)             # current frame index (approx for now)
    timecodeChanged = QtCore.Signal(str)          # "HH:MM:SS.mmm"

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._log = get_logger(__name__)
        # Controller (canonical time owner)
        self.controller = MediaController()
        # View state
        self.is_playing = False
        self.current_frame = 0
        self._last_pts: float = 0.0
        self._fps_est: float = 24.0
        self._duration_known: bool = False  # UI-side guard
        self._duration_s: float = 0.0
        self._display_timer = QtCore.QElapsedTimer()
        self._display_timer.start()
        self._display_min_interval_ms = 1000 // 30  # ~30 FPS UI refresh

        # View
        self.frame_view = FrameView(self)

        # Transport
        self.play_btn = QtWidgets.QToolButton(text="")
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        # Go to start/end
        self.prev_btn = QtWidgets.QToolButton()
        self.prev_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.prev_btn.setToolTip("Go to start")
        self.next_btn = QtWidgets.QToolButton()
        self.next_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next_btn.setToolTip("Go to end")
        # Step one frame backward/forward
        self.step_back_btn = QtWidgets.QToolButton()
        self.step_back_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSeekBackward))
        self.step_back_btn.setToolTip("Step back 1 frame")
        self.step_fwd_btn = QtWidgets.QToolButton()
        self.step_fwd_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSeekForward))
        self.step_fwd_btn.setToolTip("Step forward 1 frame")

        self.rate_combo = QtWidgets.QComboBox()
        self.rate_combo.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.rate_combo.setCurrentText("1x")

        self.time_label = QtWidgets.QLabel("00:00:00.000")
        self.frame_label = QtWidgets.QLabel("#000000")

        # Timeline
        self.timeline = MarkerSlider(QtCore.Qt.Orientation.Horizontal)
        self.timeline.setMinimum(0)
        self.timeline.setMaximum(0)  # will be set when duration_known or auto-grown
        self.timeline.valueChanged.connect(self._on_slider_changed)
        self.timeline.markerClicked.connect(self._jump_to_frame)
        self.timeline.sliderPressed.connect(self._on_slider_pressed)
        self.timeline.sliderReleased.connect(self._on_slider_released)
        self._is_scrubbing = False

        # Layout
        transport = QtWidgets.QHBoxLayout()
        transport.setContentsMargins(6, 6, 6, 0)
        transport.setSpacing(8)
        transport.addWidget(self.prev_btn)
        transport.addWidget(self.step_back_btn)
        transport.addWidget(self.play_btn)
        transport.addWidget(self.step_fwd_btn)
        transport.addWidget(self.next_btn)
        transport.addSpacing(12)
        transport.addWidget(QtWidgets.QLabel("Rate"))
        transport.addWidget(self.rate_combo)
        transport.addStretch()
        transport.addWidget(self.time_label)
        transport.addSpacing(8)
        transport.addWidget(self.frame_label)

        timeline_box = QtWidgets.QVBoxLayout()
        timeline_box.setContentsMargins(6, 0, 6, 6)
        timeline_box.addWidget(self.timeline)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.frame_view, 1)
        root.addLayout(transport)
        root.addLayout(timeline_box)

        # Wire controls
        self.play_btn.clicked.connect(self._toggle_play)
        self.prev_btn.clicked.connect(self._goto_start)
        self.next_btn.clicked.connect(self._goto_end)
        self.step_back_btn.clicked.connect(lambda: self._step_frame(-1))
        self.step_fwd_btn.clicked.connect(lambda: self._step_frame(1))
        self.rate_combo.currentTextChanged.connect(self._change_rate)
        # Controller signals → UI
        self.controller.frameReady.connect(self._on_frame_ready)
        self.controller.timeChanged.connect(self._on_time_changed)
        self.controller.durationChanged.connect(self._on_duration_changed)
        self.controller.ended.connect(self._on_ended)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API for composition
    # ──────────────────────────────────────────────────────────────────────────
    def open(self, path: str) -> None:
        """Open media file. Starts paused; caller can press play()."""
        self._log.info("PlayerWidget.open(%s)", path)
        # Reset view state
        self.is_playing = False
        self.current_frame = 0
        self._last_pts = 0.0
        self._fps_est = 24.0
        self._duration_s = 0.0
        self._duration_known = False
        self.timeline.blockSignals(True)
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        self.timeline.setMaximum(0)  # will be set when duration is known
        self._update_time_labels()
        # Delegate to controller (emits durationChanged if known, may also emit a poster frame)
        self.controller.open(path)

        self.mediaOpened.emit(path)

    def play(self) -> None:
        self._log.info("play() pressed")
        if self.is_playing:
            self._log.info("play() ignored: player=%s, is_playing=%s", bool(self.video_player), self.is_playing)
            return
        self.controller.play()
        self.is_playing = True
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause))
        self.playStateChanged.emit(True)

    def pause(self) -> None:
        self._log.info("pause() pressed")
        if not self.is_playing:
            self._log.info("pause() ignored: player=%s, is_playing=%s", bool(self.video_player), self.is_playing)
            return
        self.controller.pause()
        self.is_playing = False
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.playStateChanged.emit(False)

    def _toggle_play(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    @QtCore.Slot(int)
    def _jump_to_frame(self, frame_index: int) -> None:
        """Jump to a specific frame index via the timeline slider."""
        if self.timeline is None:
            return
        # Clamp to valid range
        max_val = self.timeline.maximum()
        frame_index = int(max(0, min(frame_index, max_val)))
        # If the slider is already at this value, explicitly trigger the seek
        if self.timeline.value() == frame_index:
            self._on_slider_changed(frame_index)
            return
        # Otherwise set the slider; this will invoke _on_slider_changed via the signal
        self.timeline.setValue(frame_index)

    @QtCore.Slot(object, float)
    def _on_frame_ready(self, rgb, pts_s: float) -> None:
        # Basic UI throttling to avoid overpainting
        if self._display_timer.elapsed() < self._display_min_interval_ms:
            return
        self._display_timer.restart()
        # Paint and derived frame index for listeners
        try:
            self.frame_view.set_frame(rgb)
        except Exception as ex:
            self._log.error("Error updating FrameView: %s", ex)
        self._fps_est = self.controller.fps_est
        self._last_pts = float(pts_s)
        self._update_time_labels_from_pts(self._last_pts)
        self.current_frame = frame_of(self._last_pts, self._fps_est)
        self.frameChanged.emit(self.current_frame)

    @QtCore.Slot(float)
    def _on_time_changed(self, pts_s: float) -> None:
        """Keep the slider in sync with canonical time (ms)."""
        v = pts_to_ms(pts_s)
        # Auto-grow only while duration is unknown
        if not self._duration_known and v > self.timeline.maximum():
            self.timeline.setMaximum(v + 2000)  # small cushion
        if self.timeline.value() != v:
            self.timeline.blockSignals(True)
            self.timeline.setValue(v)
            self.timeline.blockSignals(False)

    @QtCore.Slot(float)
    def _on_duration_changed(self, duration_s: float) -> None:
        self._duration_s = max(0.0, float(duration_s))
        self._duration_known = True
        self.timeline.setMaximum(pts_to_ms(self._duration_s))

    def _on_ended(self) -> None:
        self._log.debug("_on_ended: playback ended")
        self.is_playing = False
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.mediaEnded.emit()

    def _on_slider_changed(self, value: int) -> None:
        self._log.debug("_on_slider_changed: %d", value)
        # Slider is time-based (milliseconds). Convert to seconds for seeking/preview.
        pts_s = ms_to_pts(value)
        if self._is_scrubbing:
            rgb = self.controller.preview_frame_at(pts_s)
            if rgb is not None:
                self._last_pts = pts_s
                self._update_time_labels_from_pts(self._last_pts)
            return
        # Not scrubbing → precise seek, remain paused
        got = self.controller.seek_to_time(pts_s)
        if got is not None:
            # controller emits frameReady/timeChanged; just mirror state here
            self._last_pts = got[1]
            self._update_time_labels_from_pts(self._last_pts)
            self.is_playing = False
            self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
            self.playStateChanged.emit(False)
        # Emit frame index for listeners
        self.current_frame = frame_of(self._last_pts, max(1e-6, self._fps_est))
        self.frameChanged.emit(self.current_frame)

    def _on_slider_pressed(self) -> None:
        self._log.debug("Slider pressed: begin scrubbing")
        self._is_scrubbing = True
        # Pause playback while scrubbing for responsiveness
        if self.is_playing:
            self.pause()

    def _on_slider_released(self) -> None:
        self._log.debug("Slider released: commit seek")
        self._is_scrubbing = False
        # Commit final seek to backend at the slider's current time
        val = self.timeline.value()
        secs = ms_to_pts(val)
        got = self.controller.seek_to_time(secs)
        if got is not None:
            arr, pts = got
            self._last_pts = pts
            self.frame_view.set_frame(arr)
            self._update_time_labels_from_pts(pts)
            # Leave paused after scrubbing; user can hit play
            self.is_playing = False
            self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
            self.playStateChanged.emit(False)

    def _goto_start(self) -> None:
        """Jump to the start of the clip."""
        if not self.timeline:
            return
        self.timeline.setValue(self.timeline.minimum())

    def _goto_end(self) -> None:
        """Jump to the end of the clip."""
        if not self.timeline:
            return
        self.timeline.setValue(self.timeline.maximum())

    def _step_frame(self, direction: int) -> None:
        """
        Step exactly one frame backward/forward relative to current time.
        direction: -1 for back, +1 for forward.
        """
        if not self.timeline:
            return
        # Determine effective fps; fall back to a sane default if estimate is unset
        fps = float(self.controller.fps_est) if self.controller.fps_est and self.controller.fps_est > 0.1 else 24.0
        frame_sec = 1.0 / fps
        # Current time from last PTS
        cur_sec = max(0.0, float(self._last_pts))
        # Compute target time and clamp to [0, duration]
        duration_sec = self._duration_s if self._duration_known else max(0.0, self.timeline.maximum() / 1000.0)
        target_sec = cur_sec + (frame_sec * (1 if direction >= 0 else -1))
        target_sec = min(max(0.0, target_sec), duration_sec)
        # Set the slider (ms); normal seek path will update the image
        target_ms = pts_to_ms(target_sec)
        self.timeline.setValue(target_ms)

    def _change_rate(self, text: str) -> None:
        # Placeholder: backend rate control not yet exposed; store selection for later.
        pass

    def _update_time_labels(self) -> None:
        """
        Update the time and frame labels from the current internal state.
        This is a convenience wrapper used when we don't have a fresh frame yet.
        """
        pts = getattr(self, "_last_pts", 0.0)
        try:
            self._update_time_labels_from_pts(float(pts))
        except Exception:
            # Fallback to zeros if something goes wrong
            self.time_label.setText("00:00:00.000")
            self.frame_label.setText("#000000")
            self.timecodeChanged.emit(self.time_label.text())

    def _update_time_labels_from_pts(self, pts: float) -> None:
        secs = max(0.0, float(pts))
        msec = int((secs - int(secs)) * 1000)
        s = int(secs) % 60
        m = (int(secs) // 60) % 60
        h = int(secs) // 3600
        self.time_label.setText(f"{h:02d}:{m:02d}:{s:02d}.{msec:03d}")
        self.frame_label.setText(f"#{frame_of(secs, max(1e-6, self._fps_est)):06d}")
        self.timecodeChanged.emit(self.time_label.text())
