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
except Exception as e:
    MediaPlayer = None


class VideoBackendFFPyPlayer(QtCore.QObject):
    """Minimal wrapper around ffpyplayer for Phase 0 playback."""
    # Signal includes frame and pts (seconds)
    frame_ready = QtCore.Signal(np.ndarray, float)
    ended = QtCore.Signal()

    def __init__(self, path: str):
        super().__init__()
        if MediaPlayer is None:
            raise RuntimeError("ffpyplayer not installed")
        self._path = path
        self._log = get_logger(__name__)
        self._log.debug("FFPyPlayer init for path=%s", path)
        ff_opts = {
            "threads": FFMPEG_THREADS,
            "an": 1,
            "fflags": "genpts",
            "sync": "video",
            "out_fmt": "rgb24",
        }
        self._player = MediaPlayer(path, ff_opts=ff_opts, loglevel="warning")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._wall_start: float = 0.0
        self._pts0: Optional[float] = None
        # Cache duration (seconds) from metadata if available
        self._duration: Optional[float] = None
        try:
            md = self._player.get_metadata() or {}
            self._log.info("Media metadata: %s", md)
            dur = md.get("duration")
            # Some builds return duration as float seconds; ensure type safety
            if dur is not None:
                self._duration = float(dur)
                self._log.info("Parsed duration (seconds): %s", self._duration)
            else:
                self._log.info("No duration field in metadata")
        except Exception as ex:
            self._log.debug("Could not read duration metadata: %s", ex)
        # Fallback: probe duration via OpenCV if ffpyplayer doesn't provide it
        if self._duration is None:
            probed = self._probe_duration_via_opencv()
            if probed and probed > 0:
                self._duration = probed
                self._log.info("OpenCV-probed duration (seconds): %.3f", self._duration)
            else:
                self._log.info("OpenCV did not provide a valid duration")
        # Cached OpenCV capture for fast preview during scrubbing
        self._cv_cap: Optional[cv2.VideoCapture] = None

    # Helper: convert ffpyplayer Image -> numpy RGB array (H, W, 3), uint8
    def _img_to_numpy(self, img) -> Optional[np.ndarray]:
        try:
            w, h = img.get_size()
            buf = img.to_bytearray()[0]
            try:
                line_sizes = img.get_linesize()
                stride = int(line_sizes[0]) if line_sizes else 3 * w
            except Exception:
                stride = 3 * w
            flat = np.frombuffer(buf, dtype=np.uint8)
            if flat.size < h * stride:
                self._log.error("Frame buffer smaller than expected: size=%d, h*stride=%d", flat.size, h * stride)
                return None
            arr = flat.reshape(h, stride)[:, : 3 * w].reshape(h, w, 3)
            return arr
        except Exception as ex:
            self._log.error("Failed converting frame to numpy: %s", ex)
            return None

    def _probe_duration_via_opencv(self) -> Optional[float]:
        """
        Use OpenCV to compute duration = frame_count / fps.
        Returns seconds or None on failure.
        """
        cap = None
        try:
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                self._log.debug("OpenCV VideoCapture could not open: %s", self._path)
                return None
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0 and frames and frames > 0:
                dur = float(frames) / float(fps)
                # Guard against absurdly small or large values
                if 0 < dur < 24 * 60 * 60:
                    return dur
                self._log.debug("OpenCV duration out of expected range: frames=%s fps=%s dur=%s", frames, fps, dur)
            else:
                self._log.debug("OpenCV missing/invalid props: frames=%s fps=%s", frames, fps)
        except Exception as ex:
            self._log.debug("OpenCV probe failed: %s", ex)
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
        return None

    def get_duration(self) -> Optional[float]:
        """Return media duration in seconds if available, else None."""
        return self._duration

    def get_preview_frame_at(self, seconds: float) -> Optional[np.ndarray]:
        """
        Fast preview frame for scrubbing using OpenCV.
        Returns an RGB uint8 numpy array (H, W, 3) or None on failure.
        """
        try:
            if self._cv_cap is None:
                self._cv_cap = cv2.VideoCapture(self._path)
                if not self._cv_cap.isOpened():
                    self._log.debug("OpenCV preview: cannot open capture")
                    self._cv_cap.release()
                    self._cv_cap = None
                    return None
            # Position in milliseconds
            self._cv_cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds)) * 1000.0)
            ok, bgr = self._cv_cap.read()
            if not ok or bgr is None:
                return None
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            return rgb
        except Exception as ex:
            self._log.debug("OpenCV preview failed at %.3f s: %s", seconds, ex)
            return None

    def start(self):
        if self._running:
            self._log.debug("start() ignored: already running")
            return
        self._log.info("Starting decode thread")
        self._running = True
        self._pts0 = None
        self._wall_start = time.monotonic()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CrittrFFPyLoop")
        self._thread.start()

    def stop(self):
        """Stop decode loop, keep underlying player open so we can start again."""
        self._log.info("Stopping decode thread...")
        self._running = False
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            self._log.debug("Joining decode thread...")
            t.join(timeout=1.0)

    def close(self):
        """Fully close the underlying ffpyplayer instance."""
        self._log.info("Closing player")
        self.stop()
        try:
            self._player.close_player()
            self._log.debug("Player closed")
        except Exception as ex:
            self._log.warning("Error closing player: %s", ex)
        # Release preview capture too
        try:
            if self._cv_cap is not None:
                self._cv_cap.release()
        except Exception:
            pass
        self._cv_cap = None

    def read_one_frame(self, timeout_ms: int = 500) -> Optional[tuple[np.ndarray, float]]:
        """
        Synchronously return (frame, pts) without starting the background loop.
        Returns None if no frame before timeout.
        """
        self._log.debug("read_one_frame(timeout_ms=%d)", timeout_ms)
        deadline = QtCore.QDeadlineTimer(timeout_ms)
        while not deadline.hasExpired():
            try:
                frame, val = self._player.get_frame()
            except Exception as ex:
                self._log.error("get_frame() exception in read_one_frame: %s", ex)
                return None
            if val == 'eof':
                self._log.debug("read_one_frame: EOF")
                return None
            if frame is None:
                QtCore.QThread.msleep(5)
                continue
            img, pts = frame
            arr = self._img_to_numpy(img)
            if arr is not None:
                self._log.debug("read_one_frame: got frame %sx%s (pts=%s)", arr.shape[1], arr.shape[0], pts)
            return (arr, float(pts) if pts is not None else 0.0)
        self._log.debug("read_one_frame: timeout with no frame")
        return None

    def seek_to_time(self, seconds: float, poster_timeout_ms: int = 3_000) -> Optional[tuple[np.ndarray, float]]:
        """
        Crude but robust seek: recreate the internal player and fast-forward to 'seconds',
        return (frame, pts) at/after that time. Leaves player positioned to continue
        from that point on start().
        """
        self._log.info("seek_to_time(seconds=%.3f)", seconds)
        # Fully recreate
        try:
            self.close()
        except Exception:
            pass
        ff_opts = {
            "threads": FFMPEG_THREADS,
            "an": 1,
            "fflags": "genpts",
            "sync": "video",
            "out_fmt": "rgb24",
        }
        self._player = MediaPlayer(self._path, ff_opts=ff_opts, loglevel="warning")

        # Fast-forward loop up to target seconds
        deadline = time.monotonic() + (poster_timeout_ms / 1000.0)
        last = None
        while time.monotonic() < deadline:
            frame, val = self._player.get_frame()
            if val == 'eof':
                break
            if frame is None:
                time.sleep(0.005)
                continue
            img, pts = frame
            if pts is None:
                continue
            last = (img, float(pts))
            if float(pts) >= seconds:
                break

        if last is None:
            self._log.warning("seek_to_time: could not reach requested time")
            return None

        arr = self._img_to_numpy(last[0])
        if arr is None:
            return None
        return (arr, last[1])

    def _loop(self):
        self._log.debug("Decode loop entered")
        while self._running:
            try:
                frame, val = self._player.get_frame()
            except Exception as ex:
                self._log.error("get_frame() exception in loop: %s", ex)
                self.ended.emit()
                break
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

            # PTS-based pacing
            now = time.monotonic()
            if pts is None:
                pts = 0.0
            pts = float(pts)
            if self._pts0 is None:
                self._pts0 = pts
                self._wall_start = now
            target = self._wall_start + (pts - self._pts0)
            delay = target - now
            if delay > 0:
                # Sleep in small chunks to remain responsive to stop()
                while self._running and delay > 0:
                    chunk = 0.005 if delay > 0.02 else delay
                    time.sleep(max(0, chunk))
                    now = time.monotonic()
                    delay = target - now

            self.frame_ready.emit(arr, pts)

        self._log.debug("Decode loop exited")
