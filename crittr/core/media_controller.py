from __future__ import annotations
from typing import Optional, Callable
import numpy as np

from crittr.qt import QtCore
from crittr.core.video import VideoBackendFFPyPlayer
from crittr.core.logging import get_logger


def pts_to_ms(pts_s: float) -> int:
    return int(round(max(0.0, float(pts_s)) * 1000.0))


def ms_to_pts(ms: int) -> float:
    return max(0, int(ms)) / 1000.0


def frame_of(pts_s: float, fps_est: float) -> int:
    return int(round(max(0.0, float(pts_s)) * max(1e-6, float(fps_est))))


class MediaController(QtCore.QObject):
    """
    Owns canonical media time and decoding backend.
    pts_s (float seconds) is the only canonical timeline value.
    """
    timeChanged = QtCore.Signal(float)                 # pts_s
    durationChanged = QtCore.Signal(float)             # duration_s
    frameReady = QtCore.Signal(object, float)          # (rgb: np.ndarray, pts_s)
    ended = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self._log = get_logger(__name__)
        self._backend: Optional[VideoBackendFFPyPlayer] = None

        # Canonical model
        self.pts_s: float = 0.0
        self.duration_s: float = 0.0
        self.duration_known: bool = False
        self.fps_est: float = 24.0  # hint, not a clock

        # EMA stability for fps estimate (used only for frame_of/stepping, never as a clock)
        self._ema_alpha = 0.1

        # Play state (controller perspective)
        self.is_playing: bool = False

    # Core controls
    def open(self, path: str) -> None:
        self._log.info("MediaController.open(%s)", path)
        # Close existing backend
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:
                pass
            self._backend = None

        # Create backend
        self._backend = VideoBackendFFPyPlayer(path)
        self._backend.frame_ready.connect(self._on_backend_frame)
        self._backend.ended.connect(self._on_backend_ended)

        # Reset model
        self.pts_s = 0.0
        self.is_playing = False
        self.fps_est = 24.0

        # Obtain duration if available (metadata or OpenCV probe)
        dur = None
        try:
            dur = self._backend.get_duration()
        except Exception as ex:
            self._log.debug("get_duration failed: %s", ex)

        if dur is not None and dur > 0:
            self.duration_s = float(dur)
            self.duration_known = True
            self.durationChanged.emit(self.duration_s)
        else:
            self.duration_s = 0.0
            self.duration_known = False

        # Poster frame (non-blocking: use backend helper)
        try:
            got = self._backend.read_one_frame(timeout_ms=350)
        except Exception:
            got = None
        if got is not None:
            arr, pts = got
            self._publish_frame(arr, float(pts))

    def play(self) -> None:
        if not self._backend or self.is_playing:
            return
        # If the thread is already running, just resume; otherwise start it.
        try:
            if self._backend.is_running():
                self._backend.resume()
            else:
                self._backend.start()
        except Exception:
            # Fallback to start if capability check fails
            self._backend.start()
        self.is_playing = True

    def pause(self) -> None:
        if not self._backend or not self.is_playing:
            return
        try:
            self._backend.pause()
        except Exception as ex:
            self._log.debug("pause(): backend pause raised: %s", ex)
        self.is_playing = False

    def seek_to_time(self, pts_s: float) -> Optional[tuple[np.ndarray, float]]:
        """Precise seek; leaves backend paused at that position."""
        if not self._backend:
            return None
        got = self._backend.seek_to_time(max(0.0, float(pts_s)))
        if got is not None:
            arr, pts = got
            self._publish_frame(arr, float(pts))
            self.is_playing = False
        return got

    def preview_frame_at(self, pts_s: float) -> Optional[np.ndarray]:
        """Fast preview during scrubbing; does not change backend state."""
        if not self._backend:
            return None
        try:
            rgb = self._backend.get_preview_frame_at(max(0.0, float(pts_s)))
        except Exception:
            rgb = None
        if rgb is not None:
            # Only publish frameReady when we have a frame; timeChanged is caller/UI responsibility while scrubbing.
            self.frameReady.emit(rgb, float(pts_s))
        return rgb

    # Internals
    @QtCore.Slot(object, float)
    def _on_backend_frame(self, rgb, pts: float) -> None:
        """Backend decode → controller: update pts_s, fps_est (EMA), and publish events."""
        # Update fps_est from PTS deltas (EMA); never used as canonical clock
        dt = max(1e-6, float(pts) - float(self.pts_s))
        self.fps_est = (1.0 - self._ema_alpha) * self.fps_est + self._ema_alpha * (1.0 / dt)

        self._publish_frame(rgb, float(pts))

    def _publish_frame(self, rgb, pts: float) -> None:
        self.pts_s = max(0.0, float(pts))
        # Emit canonical time first so views can update slider before the frame if needed
        self.timeChanged.emit(self.pts_s)
        # Then the frame itself
        self.frameReady.emit(rgb, self.pts_s)

    def _on_backend_ended(self) -> None:
        self.is_playing = False
        self.ended.emit()