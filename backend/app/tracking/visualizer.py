"""Drawing helper for tracked objects."""
from typing import List

import cv2
import numpy as np

from ..detection.visualizer import draw_box
from .tracker import Track, TrackState


def color_for_id(track_id: int):
    """Deterministic, well-separated BGR colour per track ID (same ID -> same colour)."""
    hue = (track_id * 47) % 180  # OpenCV hue range is 0-179; 47 spreads neighbours apart
    bgr = cv2.cvtColor(np.uint8([[[hue, 220, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def draw_tracks(frame, tracks: List[Track], show_lost=False, highlight_ids=None):
    """Draw tracked objects as '<Class> #<id>' boxes (in place).

    NEW / ACTIVE tracks are drawn in a per-ID colour. LOST tracks (temporarily
    unmatched; box is the last known/predicted position) are only drawn when
    `show_lost` is True, in grey. REMOVED tracks are never drawn.
    Tracks whose ID is in `highlight_ids` (e.g. inside a restricted zone) are
    drawn in red with a "!" prefix.
    Returns the number of NEW + ACTIVE tracks drawn.
    """
    highlight_ids = highlight_ids or ()
    active = 0
    for t in tracks:
        if t.state in (TrackState.NEW, TrackState.ACTIVE):
            label = f"{t.class_name.capitalize()} #{t.track_id}"
            if t.track_id in highlight_ids:
                draw_box(frame, t.bbox, "! " + label, (0, 0, 255), thickness=3)
            else:
                draw_box(frame, t.bbox, label, color_for_id(t.track_id))
            active += 1
        elif t.state == TrackState.LOST and show_lost:
            draw_box(frame, t.bbox, f"#{t.track_id} lost", (160, 160, 160), thickness=1)
    return active
