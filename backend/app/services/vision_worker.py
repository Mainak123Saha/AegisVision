"""Vision pipeline that runs in its OWN process (never inside a request handler).

OpenCV -> YOLO -> ByteTrack -> AnalyticsEngine. The only thing that leaves this
process is a stream of plain event dicts pushed onto a multiprocessing queue; the
API process owns persistence. A crash here cannot take the API down.
"""
import os
import queue
import time
import traceback
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def resolve_path(p: str) -> str:
    path = Path(p)
    return str(path if path.is_absolute() else BACKEND_DIR / path)


VIEW_TIMEOUT = 3.0  # seconds without a viewer request before frames stop being rendered/encoded


def _put_latest(q, item) -> None:
    """Queue only the newest frame: if the consumer is behind, drop the stale one."""
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass


def run_camera_pipeline(camera: Dict[str, Any], opts: Dict[str, Any], out_queue, stop_event,
                        frame_queue=None, overlay_mask=None, last_view=None) -> None:
    """Process entry point. `camera` = {id, source_type, source_uri}; `opts` = {zones_path, model}.

    Live view: `overlay_mask` (shared int) selects what is drawn, `last_view` (shared float) is the
    time a browser last asked for the stream. Frames are rendered + JPEG-encoded and pushed onto
    `frame_queue` only while somebody is watching, so an unwatched camera costs nothing extra.
    """
    cam_id = camera["id"]
    error = None
    source = None
    try:
        # Heavy imports happen here (in the child) so the API process stays light.
        from ..analytics.engine import load_engine
        from ..config import Config
        from ..detection.yolo_detector import YOLODetector
        from ..tracking.bytetrack import ByteTracker
        from ..video.demo import resize_frame
        from ..video.frame_processor import FrameProcessor
        from ..video.mp4_source import MP4Source
        from ..video.rtsp_source import RTSPSource
        from ..video.webcam_source import WebcamSource
        from .overlay import DEFAULT_MASK, TrailBook, render_frame
        import cv2

        cfg = Config(model=resolve_path(opts["model"]), classes=["person"], track=True)
        stype, uri = camera["source_type"], camera["source_uri"]
        if stype == "mp4":
            source = MP4Source(resolve_path(uri))
        elif stype == "webcam":
            source = WebcamSource(int(uri))
        elif stype == "rtsp":
            source = RTSPSource(uri)
        else:
            raise ValueError(f"unknown source_type {stype!r}")
        live = stype != "mp4"

        detector = YOLODetector(cfg.model, confidence=cfg.confidence, classes=cfg.classes, imgsz=cfg.imgsz)
        tracker = ByteTracker(
            track_high_thresh=cfg.track_high_thresh, track_low_thresh=cfg.track_low_thresh,
            new_track_thresh=cfg.new_track_thresh, track_buffer=cfg.track_buffer,
            match_thresh=cfg.match_thresh,
        )
        processor = FrameProcessor()
        engine = None
        trails = TrailBook()
        proc_fps = 0.0

        fps = source.fps if source.fps and source.fps > 0 else 30
        start_wall = time.perf_counter()
        frame_index = 0

        while not stop_event.is_set():
            t0 = time.perf_counter()
            ok, frame = source.read()
            if not ok:
                break
            stream_time = (time.perf_counter() - start_wall) if live else frame_index / fps
            frame_index += 1

            frame = processor.process(resize_frame(frame, cfg.width))
            tracks = tracker.update(detector.detect(frame), frame)

            if engine is None:
                h, w = frame.shape[:2]
                engine = load_engine(resolve_path(opts["zones_path"]), (w, h))
                # Events are attributed to the DB camera, not the id in the zones file.
                for rule in engine.rules:
                    rule.camera_id = str(cam_id)

            new_events = engine.update(tracks, stream_time)
            trails.update(tracks)

            if frame_queue is not None and last_view is not None and time.time() - last_view.value < VIEW_TIMEOUT:
                alert_ids = engine.alert_ids()
                render_frame(
                    frame, mask=overlay_mask.value if overlay_mask is not None else DEFAULT_MASK,
                    tracks=tracks, engine=engine, trails=trails, alert_ids=alert_ids,
                    recent_events=engine.recent(stream_time), fps=proc_fps)
                ok_jpg, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok_jpg:
                    meta = {
                        "frame": frame_index, "stream_time": round(stream_time, 2), "fps": round(proc_fps, 1),
                        "tracks": [
                            {"track_id": t.track_id, "class_name": t.class_name,
                             "confidence": round(float(t.confidence), 3), "alert": t.track_id in alert_ids}
                            for t in tracks if t.state.value in ("new", "active")
                        ],
                        "stats": engine.stats(),
                    }
                    _put_latest(frame_queue, (jpg.tobytes(), meta))
                if not live:  # files would otherwise race through; play them at their own speed
                    delay = 1.0 / fps - (time.perf_counter() - t0)
                    if delay > 0:
                        stop_event.wait(delay)

            dt = time.perf_counter() - t0
            if dt > 0:
                proc_fps = 1 / dt if proc_fps == 0 else 0.9 * proc_fps + 0.1 / dt

            for ev in new_events:
                payload = ev.to_dict()
                payload["camera_id"] = str(cam_id)
                try:
                    out_queue.put(("event", cam_id, payload), timeout=5)
                except queue.Full:
                    pass  # backend overloaded; dropping beats stalling the video loop
    except BaseException as exc:  # noqa: BLE001 - report everything to the parent
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        if source is not None:
            try:
                source.release()
            except Exception:
                pass
        try:
            out_queue.put(("done", cam_id, error, os.getpid()), timeout=5)
        except Exception:
            pass
        if frame_queue is not None:
            frame_queue.cancel_join_thread()  # never block exit on frames nobody will read
        out_queue.close()
        out_queue.join_thread()
