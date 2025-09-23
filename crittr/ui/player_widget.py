from __future__ import annotations
from typing import Optional, List
import numpy as np
 
from crittr.core.video import VideoBackendFFPyPlayer
from crittr.qt import QtCore, QtGui, QtWidgets
from crittr.ui.frame_view import FrameView
from crittr.ui.marker_slider import MarkerSlider
from crittr.core.logging import get_logger
import math
 
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
        # State
        self.video_player: Optional[VideoBackendFFPyPlayer] = None
        self.is_playing = False
        self.current_frame = 0
        self._last_pts: float = 0.0
        self._fps_est: float = 24.0
        self._duration_est: Optional[float] = None  # seconds
        self._fps = 24.0  # placeholder until backend metadata is wired
        self._total_frames_estimate = 100  # until proper metadata
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
        self.timeline.setMaximum(self._total_frames_estimate)
        self.timeline.valueChanged.connect(self._on_slider_changed)
        self.timeline.markerClicked.connect(self._jump_to_frame)
 
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
        # Optional: keyboard shortcuts could be added later (e.g., J/K/L or arrow keys)
 
       # Scrubbing lifecycle
        self.timeline.sliderPressed.connect(self._on_slider_pressed)
        self.timeline.sliderReleased.connect(self._on_slider_released)
        self._is_scrubbing = False
 
    # ──────────────────────────────────────────────────────────────────────────
    # Public API for composition
    # ──────────────────────────────────────────────────────────────────────────
    def open(self, path: str) -> None:
        """Open media file. Starts paused; caller can press play()."""
        self._log.info("PlayerWidget.open(%s)", path)
        # Cleanup existing
        if self.video_player:
            try:
                self._log.debug("Closing previous backend")
                self.video_player.close()
            except Exception as ex:
                self._log.warning("Error closing previous backend: %s", ex)
            self.video_player = None
 
        self.video_player = VideoBackendFFPyPlayer(path)
        # Connect to new signature (frame, pts)
        self.video_player.frame_ready.connect(self._on_frame_pts)
        self.video_player.ended.connect(self._on_ended)
 
        # Reset state
        self.is_playing = False
        self.current_frame = 0
        self._last_pts = 0.0
        self._fps_est = 24.0
        self._duration_est = None
        self.timeline.blockSignals(True)
        self.timeline.setValue(0)
        self.timeline.blockSignals(False)
        # If we know the duration, set a fixed maximum in milliseconds; otherwise start at 0 and grow.
        duration_sec = None
        try:
            duration_sec = self.video_player.get_duration() if self.video_player else None
        except Exception as ex:
            self._log.debug("Duration unavailable from backend: %s", ex)
        if duration_sec and duration_sec > 0:
            self.timeline.setMaximum(int(round(duration_sec * 1000.0)))
        else:
            self.timeline.setMaximum(0)
        self._update_time_labels()
 
        # Poster frame with pts
        got = self.video_player.read_one_frame(timeout_ms=350)
        if got is not None:
            arr, pts = got
            self._last_pts = pts
            self.frame_view.set_frame(arr)
            # Initialize the time-based slider position (ms)
            pos_ms = int(round(max(0.0, float(pts)) * 1000.0))
            if self.timeline.maximum() <= 0 and pos_ms > self.timeline.maximum():
                self.timeline.setMaximum(pos_ms + 2000)  # grow if duration unknown
            self.timeline.blockSignals(True)
            self.timeline.setValue(pos_ms)
            self.timeline.blockSignals(False)
            self._update_time_labels_from_pts(pts)
        else:
            self._log.debug("No poster frame available (yet)")
 
        self.mediaOpened.emit(path)
 
    def play(self) -> None:
        self._log.info("play() pressed")
        if not self.video_player or self.is_playing:
            self._log.info("play() ignored: player=%s, is_playing=%s", bool(self.video_player), self.is_playing)
            return
        self.video_player.start()
        self.is_playing = True
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause))
        self.playStateChanged.emit(True)
 
    def pause(self) -> None:
        self._log.info("pause() pressed")
        if not self.video_player or not self.is_playing:
            self._log.info("pause() ignored: player=%s, is_playing=%s", bool(self.video_player), self.is_playing)
            return
        try:
            self.video_player.stop()   # do not close here
        except Exception as ex:
            self._log.error("pause(): backend stop raised: %s", ex)
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
        fps = float(self._fps_est) if self._fps_est and self._fps_est > 0.1 else 24.0
        frame_sec = 1.0 / fps
        # Current time from last PTS
        cur_sec = max(0.0, float(self._last_pts))
        # Compute target time and clamp to [0, duration]
        duration_sec = None
        try:
            duration_sec = self.video_player.get_duration() if self.video_player else None
        except Exception:
            duration_sec = None
        if duration_sec is None or duration_sec <= 0:
            # Use slider maximum if duration unknown
            duration_sec = max(0.0, self.timeline.maximum() / 1000.0)
        target_sec = cur_sec + (frame_sec * (1 if direction >= 0 else -1))
        target_sec = min(max(0.0, target_sec), duration_sec)
        # Set the slider (ms); normal seek path will update the image
        target_ms = int(round(target_sec * 1000.0))
        self.timeline.setValue(target_ms)
 
    def _change_rate(self, text: str) -> None:
        # Placeholder: backend rate control not yet exposed; store selection for later.
        pass
 
    # Respect PTS for time and update an FPS estimate
    @QtCore.Slot(object, float)
    def _on_frame_pts(self, rgb, pts: float) -> None:
        # FPS estimate from PTS deltas (EMA)
        if pts is not None:
            dt = max(1e-6, float(pts) - float(self._last_pts))
            self._fps_est = 0.9 * self._fps_est + 0.1 * (1.0 / dt)
            self._last_pts = float(pts)
 
        # Throttle actual painting to reduce cost
        if self._display_timer.elapsed() < self._display_min_interval_ms:
            # Drive slider by time (milliseconds) for stability
            pos_ms = int(round(max(0.0, self._last_pts) * 1000.0))
            if self.timeline.maximum() <= 0 and pos_ms > self.timeline.maximum():
                self.timeline.setMaximum(pos_ms + 2000)  # grow only if duration unknown
            self.timeline.blockSignals(True)
            self.timeline.setValue(pos_ms)
            self.timeline.blockSignals(False)
            return
        self._display_timer.restart()
 
        try:
            self.frame_view.set_frame(rgb)
        except Exception as ex:
            self._log.error("Error updating FrameView: %s", ex)
 
        # Drive the slider from time (ms), not the evolving FPS estimate
        fps = max(1e-6, self._fps_est)
        pos_ms = int(round(max(0.0, self._last_pts) * 1000.0))
        if self.timeline.maximum() <= 0 and pos_ms > self.timeline.maximum():
            self.timeline.setMaximum(pos_ms + 2000)  # grow only if duration unknown
        self.timeline.blockSignals(True)
        self.timeline.setValue(pos_ms)
        self.timeline.blockSignals(False)
        self._update_time_labels_from_pts(self._last_pts)
        # Still emit an approximate frame index for external listeners
        self.current_frame = int(round(self._last_pts * fps))
        self.frameChanged.emit(self.current_frame)
 
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
        self.frame_label.setText(f"#{int(round(secs * self._fps_est)):06d}")
        self.timecodeChanged.emit(self.time_label.text())
 
    def _on_ended(self) -> None:
        self._log.debug("_on_ended: playback ended")
        self.is_playing = False
        try:
            if self.video_player:
                self.video_player.stop()
        except Exception as ex:
            self._log.warning("_on_ended: stop raised: %s", ex)
        self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
        self.mediaEnded.emit()
 
    def _on_slider_changed(self, value: int) -> None:
        self._log.debug("_on_slider_changed: %d", value)
        # Slider is time-based (milliseconds). Convert to seconds for seeking.
        fps = max(1e-6, self._fps_est)
        secs = max(0.0, value / 1000.0)
        if not self.video_player:
            return
        if self._is_scrubbing:
            # Fast, lightweight preview while dragging
            try:
                rgb = self.video_player.get_preview_frame_at(secs)
            except Exception as ex:
                self._log.debug("preview during scrub failed: %s", ex)
                rgb = None
            if rgb is not None:
                self.frame_view.set_frame(rgb)
                self._last_pts = secs
                self._update_time_labels_from_pts(self._last_pts)
                # Do not change play state or backend here
            return
        # Not actively scrubbing: do a single backend seek (heavier) and update UI
        got = self.video_player.seek_to_time(secs)
        if got is not None:
            arr, pts = got
            self._last_pts = pts
            self.frame_view.set_frame(arr)
            # Update slider position using time (ms)
            pos_ms = int(round(max(0.0, pts) * 1000.0))
            if self.timeline.maximum() <= 0 and pos_ms > self.timeline.maximum():
                self.timeline.setMaximum(pos_ms + 2000)  # grow only if duration unknown
            self.timeline.blockSignals(True)
            self.timeline.setValue(pos_ms)
            self.timeline.blockSignals(False)
            self._update_time_labels_from_pts(pts)
            # Leave paused after seeking
            self.is_playing = False
            self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
            self.playStateChanged.emit(False)
        # Emit frame index separately for listeners that need it
        self.current_frame = int(round(max(0.0, self._last_pts) * fps))
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
        secs = max(0.0, val / 1000.0)
        if not self.video_player:
            return
        got = self.video_player.seek_to_time(secs)
        if got is not None:
            arr, pts = got
            self._last_pts = pts
            self.frame_view.set_frame(arr)
            self._update_time_labels_from_pts(pts)
            # Leave paused after scrubbing; user can hit play
            self.is_playing = False
            self.play_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
            self.playStateChanged.emit(False)
