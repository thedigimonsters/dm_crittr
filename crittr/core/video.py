from __future__ import annotations
import threading
from typing import Optional, Tuple
import numpy as np
import time

from app_config import FFMPEG_THREADS
from crittr.qt import QtCore
from crittr.core.logging import get_logger
import cv2

try:
    from ffpyplayer.player import MediaPlayer
except Exception:
    MediaPlayer = None


class VideoBackendFFPyPlayer(QtCore.QObject):
    """FFmpeg-backed backend with real pause/resume and fast scrubbing preview."""
    frame_ready = QtCore.Signal(np.ndarray, float)  # (rgb, pts_s)
    ended = QtCore.Signal()

    def __init__(self, path: str):
        super().__init__()
        if MediaPlayer is None:
            raise RuntimeError("ffpyplayer not installed")
        self._path = path
        self._log = get_logger(__name__)
        self._log.debug("FFPyPlayer init for path=%s", path)

        self._player = MediaPlayer(
            path,
            ff_opts={
                "threads": FFMPEG_THREADS,
                "an": 1,
                "fflags": "genpts",
                "sync": "video",
                "out_fmt": "rgb24",
                "framedrop": "1",
            },
            loglevel="warning",
        )

        self._running = False
        self._paused = False
        self._cond = threading.Condition()
        self._thread: Optional[threading.Thread] = None

        # Metadata / duration cache
        self._duration: Optional[float] = None
        try:
            md = self._player.get_metadata() or {}
            dur = md.get("duration")
            if dur is not None:
                self._duration = float(dur)
                self._log.info("Duration (s): %.3f", self._duration)
        except Exception as ex:
            self._log.debug("No/invalid metadata: %s", ex)
        if self._duration is None:
            probed = self._probe_duration_via_opencv()
            if probed and 0 < probed < 24 * 60 * 60:
                self._duration = probed
                self._log.info("OpenCV-probed duration (s): %.3f", self._duration)

        # Preview capture (OpenCV) for scrubbing
        self._cv_cap: Optional[cv2.VideoCapture] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────
    def get_duration(self) -> Optional[float]:
        return self._duration

    def start(self) -> None:
        if self._running:
            self._log.debug("start() ignored: already running")
            return
        self._log.info("Starting decode thread")
        self._running = True
        with self._cond:
            self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CrittrFFPyLoop")
        self._thread.start()

    def pause(self) -> None:
        """Pause decoding without tearing down."""
        with self._cond:
            if not self._running:
                return
            self._paused = True
            try:
                # Stop ffpyplayer from queuing/buffering in the background.
                self._player.set_pause(True)
            except Exception as ex:
                self._log.debug("player.set_pause(True) failed: %s", ex)
            self._cond.notify_all()

    def resume(self) -> None:
        """Resume decoding in the same context (no teardown, no draining)."""
        with self._cond:
            if not self._running:
                return
            self._paused = False
            try:
                self._player.set_pause(False)
            except Exception as ex:
                self._log.debug("player.set_pause(False) failed: %s", ex)
            self._cond.notify_all()
        # NOTE: Do NOT call get_frame() here. The decode loop owns get_frame().

    def stop(self) -> None:
        """Stop the decode loop (keeps player for close())."""
        self._log.info("Stopping decode thread...")
        with self._cond:
            self._running = False
            self._paused = False
            self._cond.notify_all()
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            self._log.debug("Joining decode thread…")
            t.join(timeout=1.0)

    def close(self) -> None:
        """Fully close the player and preview resources."""
        self.stop()
        try:
            self._player.close_player()
        except Exception as ex:
            self._log.warning("Error closing player: %s", ex)
        if self._cv_cap is not None:
            try:
                self._cv_cap.release()
            except Exception:
                pass
        self._cv_cap = None

    def is_running(self) -> bool:
        return self._running

    def is_paused(self) -> bool:
        return self._paused

    # ──────────────────────────────────────────────────────────────────────────
    # Scrub preview (OpenCV)
    # ──────────────────────────────────────────────────────────────────────────
    def get_preview_frame_at(self, seconds: float) -> Optional[np.ndarray]:
        """Fast-ish preview frame using OpenCV, independent of the decode loop."""
        try:
            if self._cv_cap is None:
                self._cv_cap = cv2.VideoCapture(self._path)
                if not self._cv_cap.isOpened():
                    self._log.debug("OpenCV preview: cannot open capture")
                    self._cv_cap.release()
                    self._cv_cap = None
                    return None
            self._cv_cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds)) * 1000.0)
            ok, bgr = self._cv_cap.read()
            if not ok or bgr is None:
                return None
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception as ex:
            self._log.debug("OpenCV preview failed at %.3f s: %s", seconds, ex)
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Precise seek (poster frame)
    # ──────────────────────────────────────────────────────────────────────────
    def seek_to_time(self, seconds: float, poster_timeout_ms: int = 3000) -> Optional[Tuple[np.ndarray, float]]:
        """
        Seek to absolute time (seconds). Returns (frame_rgb, pts_s) at/after requested time.
        Keeps the decode thread paused during the operation to avoid races.
        """
        target_s = max(0.0, float(seconds))
        self._log.info("seek_to_time(seconds=%.3f)", target_s)

        # Ensure the decode thread is paused so it won't consume frames while we seek.
        was_playing = False
        with self._cond:
            was_playing = self._running and not self._paused
            self._paused = True
            self._cond.notify_all()

        try:
            # Temporarily unpause ffpyplayer so get_frame() can advance to the poster frame.
            try:
                self._player.set_pause(False)
            except Exception:
                pass

            self._player.seek(target_s, relative=False)

            deadline = time.monotonic() + (poster_timeout_ms / 1000.0)
            last = None
            while time.monotonic() < deadline:
                frame, val = self._player.get_frame()
                if val == 'eof':
                    break
                if frame is None:
                    time.sleep(0.003)
                    continue
                img, pts = frame
                if pts is None:
                    continue
                pts_f = float(pts)
                last = (img, pts_f)
                if pts_f >= target_s:
                    break

            if last is None:
                self._log.warning("seek_to_time: could not reach requested time")
                return None

            arr = self._img_to_numpy(last[0])
            if arr is None:
                return None
            return (arr, last[1])

        finally:
            # Restore paused state to match UI: stay paused unless we were playing before.
            try:
                self._player.set_pause(True)
            except Exception:
                pass
            if was_playing:
                self.resume()  # will set_pause(False) and wake the loop

    # ──────────────────────────────────────────────────────────────────────────
    # Decode loop
    # ──────────────────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        self._log.debug("Decode loop entered")
        try:
            while True:
                # Stop?
                with self._cond:
                    if not self._running:
                        break
                    # Pause gate
                    while self._paused and self._running:
                        self._cond.wait(timeout=0.1)
                    if not self._running:
                        break
                    # Make sure ffpyplayer isn't paused when we intend to play
                    try:
                        self._player.set_pause(False)
                    except Exception:
                        pass

                # Decode one frame
                try:
                    frame, val = self._player.get_frame()
                except Exception as ex:
                    self._log.error("get_frame() exception in loop: %s", ex)
                    self.ended.emit()
                    break

                # End-of-file / idle
                if val == 'eof':
                    self._log.debug("Decode loop: EOF")
                    self.ended.emit()
                    break
                if frame is None:
                    QtCore.QThread.msleep(5)
                    continue

                img, pts = frame
                arr = self._img_to_numpy(img)
                if arr is None:
                    continue
                pts_f = float(pts or 0.0)

                # Pacing: trust ffpyplayer's recommended delay (val)
                if isinstance(val, float) and val > 0:
                    # Sleep in small chunks so we remain responsive to pause/stop
                    waited = 0.0
                    while waited < val and self._running and not self._paused:
                        chunk = min(0.02, val - waited)
                        time.sleep(chunk)
                        waited += chunk

                self.frame_ready.emit(arr, pts_f)
        finally:
            self._log.debug("Decode loop exited")

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _img_to_numpy(self, img) -> Optional[np.ndarray]:
        try:
            w, h = img.get_size()
            buf = img.to_bytearray()[0]
            line_sizes = None
            try:
                line_sizes = img.get_linesize()
            except Exception:
                pass
            stride = int(line_sizes[0]) if line_sizes else 3 * w
            flat = np.frombuffer(buf, dtype=np.uint8)
            if flat.size < h * stride:
                return None
            return flat.reshape(h, stride)[:, : 3 * w].reshape(h, w, 3)
        except Exception as ex:
            self._log.error("Failed converting frame to numpy: %s", ex)
            return None

    def _probe_duration_via_opencv(self) -> Optional[float]:
        cap = None
        try:
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                return None
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0 and frames and frames > 0:
                return float(frames) / float(fps)
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return None
