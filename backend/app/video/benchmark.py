"""Headless baseline benchmark: python -m app.video.benchmark [--frames 100]

Runs the same frames through several YOLO configurations and prints a
markdown table of processing FPS (resize + YOLO + draw, no display).
"""
import argparse
import statistics
import time

from .demo import add_common_args, build_source, parse_classes, resize_frame
from ..detection.yolo_detector import YOLODetector
from ..detection.visualizer import draw_detections

# Initial frames excluded from timing (model load / first-inference overhead).
WARMUP = 5

# (label, classes, imgsz) – each row of the results table.
CONFIGS = [
    ("All classes, imgsz 640 (baseline)", None, 640),
    ("Person-only, imgsz 640", ["person"], 640),
    ("All classes, imgsz 480", None, 480),
    ("All classes, imgsz 320", None, 320),
    ("Person-only, imgsz 320", ["person"], 320),
]


def load_frames(args, count):
    """Read `count` (+ warmup) frames once so every config sees identical input."""
    source = build_source(args)
    frames = []
    while len(frames) < count + WARMUP:
        ok, frame = source.read()
        if not ok:
            break
        frames.append(resize_frame(frame, args.width))
    source.release()
    return frames


def run(args, frames, classes, imgsz):
    """Time detection + drawing over `frames`; return (mean FPS, mean detections)."""
    detector = YOLODetector(
        args.model, confidence=args.confidence, classes=classes, imgsz=imgsz
    )
    times, counts = [], []
    for i, frame in enumerate(frames):
        f = frame.copy()  # drawing mutates the frame; keep the shared one clean
        t0 = time.perf_counter()
        result = detector.detect(f)
        n = draw_detections(f, result)
        dt = time.perf_counter() - t0
        if i >= WARMUP:
            times.append(dt)
            counts.append(n)
    return 1 / statistics.mean(times), statistics.mean(counts)


def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    parser.add_argument("--frames", type=int, default=100)
    args = parser.parse_args()

    frames = load_frames(args, args.frames)
    print(f"Source frames: {len(frames) - WARMUP} (+{WARMUP} warmup), size {frames[0].shape[1]}x{frames[0].shape[0]}\n")

    print("| Configuration | Processing FPS | Avg detections |")
    print("|---|---|---|")
    for label, classes, imgsz in CONFIGS:
        fps, avg = run(args, frames, classes, imgsz)
        print(f"| {label} | {fps:.1f} | {avg:.1f} |", flush=True)


if __name__ == "__main__":
    main()
