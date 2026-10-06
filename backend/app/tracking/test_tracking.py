"""Headless tracking checks.

    python -m app.tracking.test_tracking            # synthetic lifecycle test (no model needed)
    python -m app.tracking.test_tracking --video assets/videos/surveillance_clip.mp4 [--frames 300]

The synthetic test moves one box, hides it briefly, then removes it, and
asserts: same ID while moving, LOST during the gap, same ID on reappearance,
REMOVED once after the buffer expires.
The video mode runs YOLO + ByteTrack and prints lifecycle events and ID statistics.
"""
import argparse
from collections import Counter

import numpy as np

from ..detection.models import Detection
from .bytetrack import ByteTracker
from .tracker import TrackState


def _det(x, y, w=80, h=200, conf=0.9):
    return Detection(0, "person", conf, x, y, x + w, y + h)


def synthetic():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker = ByteTracker(track_buffer=10)
    seen_states = []
    ids = set()

    # Frames 0-19: person walks right. 20-24: occluded. 25-34: reappears. 35+: gone.
    for f in range(60):
        if f < 20:
            dets = [_det(100 + f * 5, 100)]
        elif f < 25:
            dets = []
        elif f < 35:
            dets = [_det(100 + f * 5, 100)]
        else:
            dets = []
        tracks = tracker.update(dets, frame)
        for t in tracks:
            ids.add(t.track_id)
            seen_states.append((f, t.track_id, t.state.name))

    states_by_frame = {f: s for f, _, s in seen_states}
    print("states:", Counter(s for _, _, s in seen_states))
    assert len(ids) == 1, f"ID changed across occlusion: {ids}"
    assert any(s == "LOST" for s in states_by_frame.values()), "never went LOST"
    assert sum(1 for _, _, s in seen_states if s == "REMOVED") == 1, "REMOVED should be reported exactly once"
    assert sum(1 for _, _, s in seen_states if s == "NEW") == 1, "NEW should be reported exactly once"
    print("synthetic lifecycle test OK  (single ID:", ids.pop(), ")")


def on_video(path, frames, confidence, width):
    from ..video.mp4_source import MP4Source
    from ..video.demo import resize_frame
    from ..detection.yolo_detector import YOLODetector

    source = MP4Source(path)
    detector = YOLODetector(confidence=confidence, classes=["person"])
    tracker = ByteTracker()

    lengths = Counter()  # id -> frames visible
    for n in range(frames):
        ok, frame = source.read()
        if not ok:
            break
        frame = resize_frame(frame, width)
        dets = detector.detect(frame)
        tracks = tracker.update(dets, frame)
        for t in tracks:
            if t.state in (TrackState.NEW, TrackState.ACTIVE):
                lengths[t.track_id] += 1
            # Log transitions only (first LOST frame, not every frame while lost).
            if t.state in (TrackState.NEW, TrackState.REMOVED) or (
                t.state == TrackState.LOST and t.frames_lost == 1
            ):
                print(f"frame {n:4d}  #{t.track_id:<3d} {t.state.name}")
        if n % 30 == 0:
            vis = sum(1 for t in tracks if t.state in (TrackState.NEW, TrackState.ACTIVE))
            print(f"frame {n:4d}  detections={len(dets)} active_tracks={vis}")
    source.release()

    print(f"\nunique IDs: {len(lengths)}")
    for tid, ln in sorted(lengths.items()):
        print(f"  #{tid}: visible {ln} frames")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=None)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--width", type=int, default=960)
    args = parser.parse_args()

    if args.video:
        on_video(args.video, args.frames, args.confidence, args.width)
    else:
        synthetic()


if __name__ == "__main__":
    main()
