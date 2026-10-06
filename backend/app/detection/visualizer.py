"""Drawing helpers: turn Detection objects into boxes on a frame."""
from typing import Iterable

import cv2

from .models import Detection


def draw_box(frame, bbox, label, color, thickness=2):
    """Draw one rectangle plus a filled label tag above it (in place)."""
    # Box corners in pixels: top-left (x1, y1), bottom-right (x2, y2).
    x1, y1, x2, y2 = map(int, bbox)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    # Filled background behind the label so the text stays readable.
    (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

    # Place the label above the box, clamped so it never leaves the top of the image.
    top = max(y1 - th - baseline, 0)
    # filled rectangle for the label background
    cv2.rectangle(frame, (x1, top), (x1 + tw, top + th + baseline), color, -1)
    cv2.putText(
        frame, label, (x1, top + th),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1
    )


def draw_detections(frame, detections: Iterable[Detection]):
    """Draw boxes with 'class conf' labels onto frame (in place). Returns detection count."""
    count = 0
    for det in detections:
        draw_box(frame, det.bbox, f"{det.class_name} {det.confidence:.2f}", (0, 255, 0))
        count += 1
    return count
