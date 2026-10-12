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


def run_camera_pipeline(camera: Dict[str, Any], opts: Dict[str, Any], out_queue, stop_event) -> None:
    """Process entry point. `camera` = {id, source_type, source_uri}; `opts` = {zones_path, model}."""
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

        fps = source.fps if source.fps and source.fps > 0 else 30
        start_wall = time.perf_counter()
        frame_index = 0

        while not stop_event.is_set():
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

            for ev in engine.update(tracks, stream_time):
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
        out_queue.close()
        out_queue.join_thread()
