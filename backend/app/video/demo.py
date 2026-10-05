"""Live AegisVision demo.

Pipeline per frame:
    VideoSource -> resize -> FrameProcessor -> YOLODetector -> draw boxes
    -> FPS/detection overlay -> cv2.imshow

Run from backend/:  python -m app.video.demo [--webcam | --rtsp URL | --path FILE]
Keys: Space = pause/resume, q = quit.
"""
import argparse
import time

import cv2
from .mp4_source import MP4Source
from .webcam_source import WebcamSource
from .rtsp_source import RTSPSource
from .frame_processor import FrameProcessor
from ..detection.yolo_detector import YOLODetector
from ..detection.visualizer import draw_detections

# Frames wider than this (pixels) are downscaled before processing.
MAX_WIDTH = 960


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


def build_source(args):
    """The rest of the pipeline only sees a VideoSource, never the origin of the frames."""
    # Priority: RTSP stream > webcam > MP4 file.
    if args.rtsp:
        return RTSPSource(args.rtsp)
    if args.webcam:
        return WebcamSource(0)
    return MP4Source(args.path)


def parse_classes(value):
    """'person' -> ['person'], 'person,car' -> [...], 'all' -> None (no filtering)."""
    if value.strip().lower() == "all":
        return None
    return [c for c in value.split(",") if c.strip()]


def add_common_args(parser):
    """Register the CLI options shared by the demo and the benchmark."""
    parser.add_argument("--webcam", action="store_true", help="Use webcam instead of MP4")
    parser.add_argument("--rtsp", default=None, help="RTSP/HTTP stream URL")
    parser.add_argument("--path", default="assets/videos/surveillance_clip.mp4")
    parser.add_argument("--width", type=int, default=MAX_WIDTH, help="Max frame width")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLO model weights")
    parser.add_argument("--confidence", type=float, default=0.25, help="Min detection confidence (0-1)")
    parser.add_argument(
        "--classes", default="person",
        help="Comma-separated class names to keep (e.g. person,car) or 'all'"
    )
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO inference size")


def main():
    """Parse arguments, set up source + detector, and run the display loop."""

    parser = argparse.ArgumentParser()
    add_common_args(parser)
    parser.add_argument("--no-detect", action="store_true", help="Disable YOLO detection")
    args = parser.parse_args()

    source = build_source(args)
    processor = FrameProcessor()
    # detector stays None when --no-detect is given, turning the demo into a plain player.
    detector = None if args.no_detect else YOLODetector(
        args.model,
        confidence=args.confidence,
        classes=parse_classes(args.classes),
        imgsz=args.imgsz,
    )

    fps = source.fps

    # Some sources (webcams, streams) report 0 FPS; fall back to a sane default.
    if fps <= 0:
        fps = 30

    # Milliseconds to wait between frames so playback matches the video's speed.
    delay = int(1000 / fps)

    paused = False
    frame = None  # last processed frame, re-shown while paused
    num_detections = 0
    processing_fps = 0.0  # smoothed measured throughput

    while True:

        # While paused we skip reading/processing and just redraw the last frame.
        if not paused or frame is None:
            success, frame = source.read()

            # End of file or lost stream.
            if not success:
                break

            t0 = time.perf_counter()

            frame = resize_frame(frame, args.width)
            frame = processor.process(frame)

            num_detections = 0
            if detector is not None:
                result = detector.detect(frame)
                # Boxes are drawn onto `frame` in place; returns how many were drawn.
                num_detections = draw_detections(frame, result)

            # Actual processing FPS (smoothed), excludes display/wait time
            dt = time.perf_counter() - t0
            if dt > 0:
                current = 1 / dt
                # Exponential moving average so the number doesn't flicker.
                processing_fps = current if processing_fps == 0 else 0.9 * processing_fps + 0.1 * current

        # Draw the overlay on a copy so the stored frame stays clean (no stacking text while paused).
        display = frame.copy()

        # Display video's FPS
        cv2.putText(
            display,
            f"FPS: {fps:.1f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # Display actual processing FPS
        cv2.putText(
            display,
            f"Processing FPS: {processing_fps:.1f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2
        )

        # Display number of detections
        cv2.putText(
            display,
            f"Detections: {num_detections}",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 0),
            2
        )

        if paused:
            cv2.putText(
                display,
                "PAUSED",
                (20, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

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