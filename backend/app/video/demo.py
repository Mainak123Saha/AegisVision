"""Live AegisVision demo.

Pipeline per frame:
    VideoSource -> resize -> FrameProcessor -> YOLODetector -> [ByteTracker]
    -> [AnalyticsEngine: line crossing / intrusion / loitering -> Events]
    -> draw boxes, zones, event banners -> FPS/detection/track overlay -> cv2.imshow

Run from backend/:  python -m app.video.demo [--webcam | --rtsp URL | --path FILE] [--track]
                    python -m app.video.demo --track --zones config/zones.json
Keys: Space = pause/resume, q = quit.
"""
import argparse
import json
import time

import cv2
from .mp4_source import MP4Source
from .webcam_source import WebcamSource
from .rtsp_source import RTSPSource
from .frame_processor import FrameProcessor
from ..config import Config, MAX_WIDTH, add_common_args, config_from_args
from ..analytics.engine import load_engine
from ..analytics.visualizer import draw_event_banners, draw_lines, draw_stats, draw_zones
from ..detection.yolo_detector import YOLODetector
from ..detection.visualizer import draw_detections
from ..tracking.bytetrack import ByteTracker
from ..tracking.tracker import TrackState
from ..tracking.visualizer import draw_tracks


def resize_frame(frame, max_width=MAX_WIDTH):
    """Downscale `frame` to at most `max_width` pixels wide, keeping aspect ratio.

    Frames that are already small enough are returned untouched (never upscaled).
    """
    h, w = frame.shape[:2]

    if w <= max_width:
        return frame

    scale = max_width / w
    # INTER_AREA gives the best quality when shrinking images.
    return cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)


def build_source(cfg: Config):
    """The rest of the pipeline only sees a VideoSource, never the origin of the frames."""
    # Priority: RTSP stream > webcam > MP4 file.
    if cfg.rtsp:
        return RTSPSource(cfg.rtsp)
    if cfg.webcam:
        return WebcamSource(0)
    return MP4Source(cfg.path)


def build_detector(cfg: Config):
    """Create the YOLO detector from config."""
    return YOLODetector(
        cfg.model,
        confidence=cfg.confidence,
        classes=cfg.classes,
        imgsz=cfg.imgsz,
    )


def build_tracker(cfg: Config):
    """Create the ByteTrack tracker from config."""
    return ByteTracker(
        track_high_thresh=cfg.track_high_thresh,
        track_low_thresh=cfg.track_low_thresh,
        new_track_thresh=cfg.new_track_thresh,
        track_buffer=cfg.track_buffer,
        match_thresh=cfg.match_thresh,
    )


def put_text(img, text, y, color):
    """Draw one overlay line at row `y` on the left edge."""
    cv2.putText(img, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)


def main():
    """Parse arguments, set up source + detector (+ tracker + analytics), and run the loop."""

    parser = argparse.ArgumentParser()
    add_common_args(parser)
    parser.add_argument("--no-detect", action="store_true", help="Disable YOLO detection")
    cfg = config_from_args(parser.parse_args())

    source = build_source(cfg)
    processor = FrameProcessor()
    # detector stays None with --no-detect, turning the demo into a plain player.
    detector = build_detector(cfg) if cfg.detect else None
    # Tracking needs detections, so it is only active when both are enabled.
    tracker = build_tracker(cfg) if (cfg.track and detector is not None) else None

    if cfg.zones and tracker is None:
        raise SystemExit("--zones needs tracking: add --track (and don't use --no-detect)")
    engine = None  # built on the first frame, once the processed frame size is known

    fps = source.fps

    # Some sources (webcams, streams) report 0 FPS; fall back to a sane default.
    if fps <= 0:
        fps = 30

    # Milliseconds to wait between frames so playback matches the video's speed.
    delay = int(1000 / fps)

    # Live sources have no meaningful frame index, so analytics time = wall-clock elapsed.
    # Files use video time (frame_index / fps), which stays correct even if processing is slow.
    live = cfg.webcam or bool(cfg.rtsp)
    start_wall = time.perf_counter()
    frame_index = 0
    stream_time = 0.0

    events_file = open(cfg.events_log, "a") if cfg.events_log else None
    writer = None  # annotated-video writer, created on the first frame

    paused = False
    frame = None  # last processed frame, re-shown while paused
    num_detections = 0
    active_tracks = 0
    lost_tracks = 0
    processing_fps = 0.0  # smoothed measured throughput

    while True:

        # While paused we skip reading/processing and just redraw the last frame.
        if not paused or frame is None:
            success, frame = source.read()

            # End of file or lost stream (or --max-frames reached).
            if not success or (cfg.max_frames and frame_index >= cfg.max_frames):
                break

            t0 = time.perf_counter()

            stream_time = (t0 - start_wall) if live else frame_index / fps
            frame_index += 1

            frame = resize_frame(frame, cfg.width)
            frame = processor.process(frame)

            num_detections = 0
            active_tracks = 0
            lost_tracks = 0
            if detector is not None:
                detections = detector.detect(frame)
                num_detections = len(detections)

                if tracker is not None:
                    # Detections -> persistent IDs. Boxes are drawn from tracks, not raw detections.
                    tracks = tracker.update(detections, frame)

                    alert_ids = set()
                    if cfg.zones:
                        if engine is None:
                            h, w = frame.shape[:2]
                            engine = load_engine(cfg.zones, (w, h))
                        # Tracks -> events (line crossing / intrusion / loitering).
                        for ev in engine.update(tracks, stream_time):
                            print(f"[{stream_time:7.2f}s] {ev.event_type.value} track={ev.track_id} {ev.metadata}")
                            if events_file:
                                events_file.write(json.dumps(ev.to_dict()) + "\n")
                                events_file.flush()
                        alert_ids = engine.alert_ids()
                        # Zones/lines go under the boxes so the people stay visible.
                        draw_zones(frame, engine)
                        draw_lines(frame, engine)

                    active_tracks = draw_tracks(frame, tracks, cfg.show_lost, alert_ids)
                    lost_tracks = sum(1 for t in tracks if t.state == TrackState.LOST)
                else:
                    # Boxes are drawn onto `frame` in place.
                    draw_detections(frame, detections)

            # Actual processing FPS (smoothed), excludes display/wait time
            dt = time.perf_counter() - t0
            if dt > 0:
                current = 1 / dt
                # Exponential moving average so the number doesn't flicker.
                processing_fps = current if processing_fps == 0 else 0.9 * processing_fps + 0.1 * current

        # Draw the overlay on a copy so the stored frame stays clean (no stacking text while paused).
        display = frame.copy()

        y = 40
        # Display video's FPS
        put_text(display, f"FPS: {fps:.1f}", y, (0, 255, 0))
        y += 40
        # Display actual processing FPS
        put_text(display, f"Processing FPS: {processing_fps:.1f}", y, (0, 255, 255))
        y += 40
        # Display number of detections
        put_text(display, f"Detections: {num_detections}", y, (255, 255, 0))
        y += 40

        if tracker is not None:
            # Active = currently visible tracked objects; Lost = remembered but unmatched.
            put_text(display, f"Active Tracks: {active_tracks}", y, (255, 0, 255))
            y += 40
            put_text(display, f"Lost Tracks: {lost_tracks}", y, (160, 160, 160))
            y += 40

        if engine is not None:
            # Recent events as banners (bottom-left) and running totals (top-right).
            draw_event_banners(display, engine.recent(stream_time))
            draw_stats(display, engine)

        if paused:
            put_text(display, "PAUSED", y, (0, 0, 255))

        if cfg.output:
            if writer is None:
                h, w = display.shape[:2]
                writer = cv2.VideoWriter(cfg.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            writer.write(display)

        if cfg.headless:
            continue  # no window, no pacing: process as fast as possible

        cv2.imshow("AegisVision", display)

        # waitKey doubles as the frame-rate limiter and the keyboard handler.
        key = cv2.waitKey(delay) & 0xFF

        if key == ord("q"):
            break

        if key == ord(" "):
            paused = not paused

    source.release()
    if writer is not None:
        writer.release()
    if events_file:
        events_file.close()
    if engine is not None:
        print("Summary:", engine.stats())
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()