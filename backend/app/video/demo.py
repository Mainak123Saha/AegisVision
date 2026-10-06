"""Live AegisVision demo.

Pipeline per frame:
    VideoSource -> resize -> FrameProcessor -> YOLODetector -> [ByteTracker]
    -> draw boxes -> FPS/detection/track overlay -> cv2.imshow

Run from backend/:  python -m app.video.demo [--webcam | --rtsp URL | --path FILE] [--track]
Keys: Space = pause/resume, q = quit.
"""
import argparse
import time

import cv2
from .mp4_source import MP4Source
from .webcam_source import WebcamSource
from .rtsp_source import RTSPSource
from .frame_processor import FrameProcessor
from ..config import Config, MAX_WIDTH, add_common_args, config_from_args
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
    """Parse arguments, set up source + detector (+ tracker), and run the display loop."""

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

    fps = source.fps

    # Some sources (webcams, streams) report 0 FPS; fall back to a sane default.
    if fps <= 0:
        fps = 30

    # Milliseconds to wait between frames so playback matches the video's speed.
    delay = int(1000 / fps)

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

            # End of file or lost stream.
            if not success:
                break

            t0 = time.perf_counter()

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
                    active_tracks = draw_tracks(frame, tracks, cfg.show_lost)
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

        if paused:
            put_text(display, "PAUSED", y, (0, 0, 255))

        cv2.imshow("AegisVision", display)

        # waitKey doubles as the frame-rate limiter and the keyboard handler.
        key = cv2.waitKey(delay) & 0xFF

        if key == ord("q"):
            break

        if key == ord(" "):
            paused = not paused

    source.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()