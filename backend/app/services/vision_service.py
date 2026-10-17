"""VisionService: owns the camera worker processes and persists the events they emit.

FastAPI only calls start()/stop()/status(); the heavy loop runs in a child process.

    worker process --(mp.Queue of event dicts)--> drain thread --> PostgreSQL
"""
import logging
import multiprocessing as mp
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

from ..config import Settings
from ..database import db as dbmod
from ..database.repository import CameraRepository, EventRepository
from .overlay import DEFAULT_MASK, apply_changes, mask_to_dict
from .vision_worker import BACKEND_DIR, resolve_path, run_camera_pipeline

log = logging.getLogger("aegis.vision")


class CameraAlreadyRunning(Exception):
    pass


class CameraNotRunning(Exception):
    pass


class CameraSourceError(Exception):
    pass


@dataclass
class _Handle:
    process: Any
    stop_event: Any
    started_at: datetime
    events_persisted: int = 0
    last_error: Optional[str] = None
    last_view: Any = None      # shared float: when a browser last asked for frames
    frame_queue: Any = None


class VisionService:
    def __init__(self, settings: Settings, max_queue: int = 10_000):
        self.settings = settings
        self._ctx = mp.get_context("spawn")  # clean child: no inherited DB connections / threads
        self._queue = self._ctx.Queue(maxsize=max_queue)
        self._handles: Dict[int, _Handle] = {}
        self._last_error: Dict[int, str] = {}
        self._lock = threading.RLock()
        # Live view: overlay bit masks (shared with the workers) and the newest frame per camera.
        self._masks: Dict[int, Any] = {}
        self._frames: Dict[int, tuple] = {}   # camera_id -> (seq, jpeg_bytes, meta)
        self._drain_stop = threading.Event()
        self._drain_thread: Optional[threading.Thread] = None

    # --- lifecycle ----------------------------------------------------
    def startup(self) -> None:
        """Called when the API boots. No processes survive a restart, so clear stale flags."""
        self._drain_stop.clear()
        self._drain_thread = threading.Thread(target=self._drain_loop, name="event-writer", daemon=True)
        self._drain_thread.start()
        try:
            with dbmod.SessionLocal() as db:
                CameraRepository(db).deactivate_all()
        except SQLAlchemyError as exc:  # the API must still come up without the DB
            log.warning("Could not reset camera flags at startup: %s", exc)

    def shutdown(self) -> None:
        for cam_id in list(self._handles):
            try:
                self.stop(cam_id)
            except Exception:  # noqa: BLE001
                log.exception("error stopping camera %s", cam_id)
        self._drain_stop.set()
        if self._drain_thread:
            self._drain_thread.join(timeout=10)
        self._queue.close()

    # --- control ------------------------------------------------------
    def is_running(self, camera_id: int) -> bool:
        with self._lock:
            h = self._handles.get(camera_id)
            return bool(h and h.process.is_alive())

    def start(self, camera: Any) -> _Handle:
        if camera.source_type == "mp4":
            import os
            if not os.path.isfile(resolve_path(camera.source_uri)):
                raise CameraSourceError(f"video file not found: {camera.source_uri}")
        with self._lock:
            if self.is_running(camera.id):
                raise CameraAlreadyRunning(camera.id)
            self._handles.pop(camera.id, None)
            self._last_error.pop(camera.id, None)
            stop_event = self._ctx.Event()
            frame_queue = self._ctx.Queue(maxsize=2)
            last_view = self._ctx.Value("d", 0.0)
            self._frames.pop(camera.id, None)
            proc = self._ctx.Process(
                target=run_camera_pipeline,
                args=(
                    {"id": camera.id, "source_type": camera.source_type, "source_uri": camera.source_uri},
                    {"zones_path": self.settings.zones_path, "model": self.settings.model},
                    self._queue, stop_event, frame_queue, self._mask(camera.id), last_view,
                ),
                name=f"camera-{camera.id}", daemon=True,
            )
            proc.start()
            h = _Handle(proc, stop_event, datetime.now(timezone.utc), last_view=last_view, frame_queue=frame_queue)
            self._handles[camera.id] = h
            threading.Thread(target=self._frame_loop, args=(camera.id, h), name=f"frames-{camera.id}",
                             daemon=True).start()
            return h

    def stop(self, camera_id: int, timeout: float = 10.0) -> None:
        with self._lock:
            h = self._handles.get(camera_id)
            if h is None or not h.process.is_alive():
                raise CameraNotRunning(camera_id)
            h.stop_event.set()
            h.process.join(timeout)
            if h.process.is_alive():  # stuck (e.g. blocked on a dead RTSP read)
                log.warning("camera %s did not stop gracefully; terminating", camera_id)
                h.process.terminate()
                h.process.join(3)
                if h.process.is_alive():
                    h.process.kill()
                    h.process.join(3)
        self._mark_inactive(camera_id)

    # --- live view ----------------------------------------------------
    def _mask(self, camera_id: int):
        with self._lock:
            if camera_id not in self._masks:
                self._masks[camera_id] = self._ctx.Value("i", DEFAULT_MASK)
            return self._masks[camera_id]

    def get_overlay(self, camera_id: int) -> Dict[str, bool]:
        return mask_to_dict(self._mask(camera_id).value)

    def set_overlay(self, camera_id: int, changes: Dict[str, bool]) -> Dict[str, bool]:
        m = self._mask(camera_id)
        with m.get_lock():
            m.value = apply_changes(m.value, changes)
        return mask_to_dict(m.value)

    def touch_view(self, camera_id: int) -> None:
        """Tell the worker someone is watching (it only renders frames while this is recent)."""
        with self._lock:
            h = self._handles.get(camera_id)
        if h and h.last_view is not None:
            h.last_view.value = time.time()

    def latest_frame(self, camera_id: int) -> Optional[tuple]:
        return self._frames.get(camera_id)

    def _frame_loop(self, camera_id: int, h: _Handle) -> None:
        """Move the worker's newest rendered frame into memory for the HTTP stream."""
        seq = 0
        while True:
            try:
                jpg, meta = h.frame_queue.get(timeout=0.5)
            except queue.Empty:
                if not h.process.is_alive():
                    return
                continue
            except (OSError, ValueError, EOFError):
                return
            seq += 1
            self._frames[camera_id] = (seq, jpg, meta)

    def status(self, camera_id: int) -> Dict[str, Any]:
        with self._lock:
            h = self._handles.get(camera_id)
            running = bool(h and h.process.is_alive())
            return {
                "camera_id": camera_id,
                "running": running,
                "pid": h.process.pid if running else None,
                "started_at": h.started_at if h else None,
                "events_persisted": h.events_persisted if h else 0,
                "last_error": self._last_error.get(camera_id),
            }

    # --- event persistence -------------------------------------------
    def _mark_inactive(self, camera_id: int) -> None:
        try:
            with dbmod.SessionLocal() as db:
                CameraRepository(db).set_active(camera_id, False)
        except SQLAlchemyError as exc:
            log.warning("could not clear is_active for camera %s: %s", camera_id, exc)

    def _persist(self, batch: List[Dict[str, Any]]) -> int:
        for attempt in range(5):
            try:
                with dbmod.SessionLocal() as db:
                    return EventRepository(db).add_many(batch)
            except SQLAlchemyError as exc:
                log.warning("event write failed (attempt %d/5): %s", attempt + 1, exc)
                time.sleep(min(2 ** attempt, 8))
        log.error("dropping %d events after repeated database failures", len(batch))
        return 0

    def _drain_loop(self) -> None:
        while True:
            batch: List[Dict[str, Any]] = []
            per_cam: Dict[int, int] = {}
            done: List[tuple] = []
            deadline = time.monotonic() + 0.5
            while len(batch) < 100 and time.monotonic() < deadline:
                try:
                    msg = self._queue.get(timeout=0.2)
                except queue.Empty:
                    break
                except (OSError, ValueError, EOFError):
                    return
                if msg[0] == "event":
                    batch.append(msg[2])
                    per_cam[msg[1]] = per_cam.get(msg[1], 0) + 1
                elif msg[0] == "done":
                    done.append(msg)
            if batch:
                written = self._persist(batch)
                with self._lock:
                    for cam_id, n in per_cam.items():
                        if cam_id in self._handles:
                            self._handles[cam_id].events_persisted += n if written else 0
            for _, cam_id, error, pid in done:  # finished on its own (EOF), crashed, or was stopped
                with self._lock:
                    h = self._handles.get(cam_id)
                    if h is not None and h.process.pid != pid:
                        continue  # stale message from a previous run; camera has been restarted
                if error:
                    self._last_error[cam_id] = error
                self._mark_inactive(cam_id)
            if self._drain_stop.is_set() and not batch and not done:
                return
