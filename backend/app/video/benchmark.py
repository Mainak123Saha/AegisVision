"""Headless baseline benchmark: python -m app.video.benchmark [--frames 100]

Runs the same frames through several YOLO configurations and prints a
markdown table of processing FPS (resize + YOLO [+ tracking] + draw, no display).

Example input:
python -m app.video.benchmark --path assets/videos/test.mp4 --width 960 --confidence 0.5 --frames 100
"""
import argparse
import statistics
import time

from .demo import build_source, build_tracker, resize_frame
from ..config import add_common_args, config_from_args
from ..detection.yolo_detector import YOLODetector
from ..detection.visualizer import draw_detections
from ..tracking.visualizer import draw_tracks

# Initial frames excluded from timing (model load / first-inference overhead).
WARMUP = 5

# (label, classes, imgsz, track) – each row of the results table.
CONFIGS = [
    ("All classes, imgsz 640 (baseline)", None, 640, False),
    ("Person-only, imgsz 640", ["person"], 640, False),
    ("All classes, imgsz 480", None, 480, False),
    ("All classes, imgsz 320", None, 320, False),
    ("Person-only, imgsz 320", ["person"], 320, False),
    ("Person-only, imgsz 640 + ByteTrack", ["person"], 640, True),
    ("Person-only, imgsz 320 + ByteTrack", ["person"], 320, True),
]


def load_frames(cfg, count):
    """Read `count` (+ warmup) frames once so every config sees identical input."""
    source = build_source(cfg)
    frames = []
    while len(frames) < count + WARMUP:
        ok, frame = source.read()
        if not ok:
            break
        frames.append(resize_frame(frame, cfg.width))
    source.release()
    return frames


def run(cfg, frames, classes, imgsz, track):
    """Time detection (+ tracking) + drawing over `frames`; return (mean FPS, mean detections)."""
    detector = YOLODetector(
        cfg.model, confidence=cfg.confidence, classes=classes, imgsz=imgsz
    )
    tracker = build_tracker(cfg) if track else None
    times, counts = [], []
    for i, frame in enumerate(frames):
        f = frame.copy()  # drawing mutates the frame; keep the shared one clean
        t0 = time.perf_counter()
        detections = detector.detect(f)
        if tracker is not None:
            draw_tracks(f, tracker.update(detections, f))
        else:
            draw_detections(f, detections)
        dt = time.perf_counter() - t0
        if i >= WARMUP:
            times.append(dt)
            counts.append(len(detections))
    return 1 / statistics.mean(times), statistics.mean(counts)


def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    parser.add_argument("--frames", type=int, default=100)
    args = parser.parse_args()
    cfg = config_from_args(args)

    frames = load_frames(cfg, args.frames)
    print(f"Source frames: {len(frames) - WARMUP} (+{WARMUP} warmup), size {frames[0].shape[1]}x{frames[0].shape[0]}\n")

    print("| Configuration | Processing FPS | Avg detections |")
    print("|---|---|---|")
    for label, classes, imgsz, track in CONFIGS:
        fps, avg = run(cfg, frames, classes, imgsz, track)
        print(f"| {label} | {fps:.1f} | {avg:.1f} |", flush=True)


if __name__ == "__main__":
    main()
