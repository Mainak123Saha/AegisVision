"""Central configuration for AegisVision.

One `Config` object holds every setting (source, detection, tracking, display).
The CLI is just one way to fill it; later it can also come from a file or an API.
"""
import argparse
from dataclasses import dataclass
from typing import List, Optional

# Frames wider than this (pixels) are downscaled before processing.
MAX_WIDTH = 960


@dataclass
class Config:
    # --- source ---
    webcam: bool = False
    rtsp: Optional[str] = None
    path: str = "assets/videos/gettyimages-2193516363-640_adpp.mp4"
    width: int = MAX_WIDTH

    # --- detection ---
    detect: bool = True
    model: str = "yolo11n.pt"
    confidence: float = 0.5
    classes: Optional[List[str]] = None  # None = all classes
    imgsz: int = 640

    # --- tracking ---
    track: bool = False
    track_high_thresh: float = 0.25
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.25
    track_buffer: int = 60
    match_thresh: float = 0.8
    show_lost: bool = False

    # --- analytics (needs tracking) ---
    zones: Optional[str] = None        # JSON file defining lines/zones (see config/zones.json)
    events_log: Optional[str] = None   # append events as JSON lines to this file

    # --- output ---
    output: Optional[str] = None       # write the annotated video to this file
    headless: bool = False             # no window; process as fast as possible
    max_frames: int = 0                # stop after this many frames (0 = whole video)


def parse_classes(value):
    """'person' -> ['person'], 'person,car' -> [...], 'all' -> None (no filtering)."""
    if value.strip().lower() == "all":
        return None
    return [c for c in value.split(",") if c.strip()]


def add_common_args(parser):
    """Register the CLI options shared by the demo and the benchmark."""
    d = Config()

    parser.add_argument("--webcam", action="store_true", help="Use webcam instead of MP4")
    parser.add_argument("--rtsp", default=d.rtsp, help="RTSP/HTTP stream URL")
    parser.add_argument("--path", default=d.path)
    parser.add_argument("--width", type=int, default=d.width, help="Max frame width")
    parser.add_argument("--model", default=d.model, help="YOLO model weights")
    parser.add_argument("--confidence", type=float, default=d.confidence, help="Min detection confidence (0-1)")
    parser.add_argument(
        "--classes", default="person",
        help="Comma-separated class names to keep (e.g. person,car) or 'all'"
    )
    parser.add_argument("--imgsz", type=int, default=d.imgsz, help="YOLO inference size")

    # Tracking
    parser.add_argument("--track", action="store_true", help="Enable ByteTrack multi-object tracking")
    parser.add_argument("--track-high-thresh", type=float, default=d.track_high_thresh)
    parser.add_argument("--track-low-thresh", type=float, default=d.track_low_thresh)
    parser.add_argument("--new-track-thresh", type=float, default=d.new_track_thresh)
    parser.add_argument("--track-buffer", type=int, default=d.track_buffer,
                        help="Frames a lost track is kept before removal")
    parser.add_argument("--match-thresh", type=float, default=d.match_thresh)
    parser.add_argument("--show-lost", action="store_true", help="Also draw LOST tracks (grey)")

    # Analytics
    parser.add_argument("--zones", default=d.zones,
                        help="JSON file with lines/zones for line-crossing, intrusion and loitering (requires --track)")
    parser.add_argument("--events-log", default=d.events_log, help="Append events as JSON lines to this file")

    # Output
    parser.add_argument("--output", default=d.output, help="Save the annotated video to this file (e.g. out.mp4)")
    parser.add_argument("--headless", action="store_true", help="No window; run as fast as possible")
    parser.add_argument("--max-frames", type=int, default=d.max_frames, help="Stop after N frames (0 = all)")


def config_from_args(args) -> Config:
    """Build a Config from parsed CLI arguments (extra demo-only flags are ignored)."""
    return Config(
        webcam=args.webcam,
        rtsp=args.rtsp,
        path=args.path,
        width=args.width,
        detect=not getattr(args, "no_detect", False),
        model=args.model,
        confidence=args.confidence,
        classes=parse_classes(args.classes),
        imgsz=args.imgsz,
        track=args.track,
        track_high_thresh=args.track_high_thresh,
        track_low_thresh=args.track_low_thresh,
        new_track_thresh=args.new_track_thresh,
        track_buffer=args.track_buffer,
        match_thresh=args.match_thresh,
        show_lost=args.show_lost,
        zones=args.zones,
        events_log=args.events_log,
        output=args.output,
        headless=args.headless,
        max_frames=args.max_frames,
    )
