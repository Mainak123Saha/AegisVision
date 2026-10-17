"""Live-view overlay: which annotations are drawn on the streamed frame, and the drawing itself.

The flags live in a shared integer (bit mask) so the API can flip them while the
worker process is running; the worker re-reads the mask on every frame.
`cv2` is imported lazily so importing the flag helpers keeps the API process light.
"""
from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Sequence

# name -> (bit, default). Order is the order shown in the UI.
OVERLAY_FLAGS: Dict[str, tuple] = {
    "boxes": (1 << 0, True),        # bounding boxes
    "ids": (1 << 1, True),          # "Person #7"
    "confidence": (1 << 2, True),   # "92%"
    "zones": (1 << 3, True),        # zones + counting lines
    "events": (1 << 4, True),       # event banners (intrusion, loitering, crossing)
    "trails": (1 << 5, False),      # recent path of every person
    "stats": (1 << 6, False),       # running totals
    "fps": (1 << 7, False),         # processing FPS
}

DEFAULT_MASK = sum(bit for bit, on in OVERLAY_FLAGS.values() if on)


def mask_to_dict(mask: int) -> Dict[str, bool]:
    return {name: bool(mask & bit) for name, (bit, _) in OVERLAY_FLAGS.items()}


def apply_changes(mask: int, changes: Dict[str, bool]) -> int:
    for name, value in changes.items():
        bit = OVERLAY_FLAGS[name][0]
        mask = (mask | bit) if value else (mask & ~bit)
    return mask


class TrailBook:
    """Remembers the last N foot positions of each track for the 'trails' overlay."""

    def __init__(self, length: int = 40):
        self.length = length
        self._points: Dict[int, Deque[tuple]] = {}

    def update(self, tracks: Iterable[Any]) -> None:
        seen = set()
        for t in tracks:
            if t.state.value in ("new", "active"):
                seen.add(t.track_id)
                self._points.setdefault(t.track_id, deque(maxlen=self.length)).append(
                    (int((t.x1 + t.x2) / 2), int(t.y2)))
        for tid in [k for k in self._points if k not in seen]:
            del self._points[tid]  # forget tracks as soon as they are not visible

    def get(self, track_id: int):
        return self._points.get(track_id, ())


def _label(cv2, frame, text: str, x: int, y: int, color) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), base = cv2.getTextSize(text, font, 0.5, 1)
    y = max(y, th + base + 2)
    cv2.rectangle(frame, (x, y - th - base - 3), (x + tw + 6, y + 1), color, -1)
    cv2.putText(frame, text, (x + 3, y - base), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def render_frame(frame, *, mask: int, tracks: Sequence[Any], engine, trails: TrailBook,
                 alert_ids: set, recent_events: List[Any], fps: float):
    """Draw the enabled overlays onto `frame` (in place) and return it."""
    import cv2

    from ..analytics.visualizer import draw_event_banners, draw_lines, draw_stats, draw_zones
    from ..tracking.visualizer import color_for_id

    flags = mask_to_dict(mask)

    if flags["zones"] and engine is not None:
        draw_zones(frame, engine)
        draw_lines(frame, engine)

    for t in tracks:
        if t.state.value not in ("new", "active"):
            continue
        alert = t.track_id in alert_ids
        color = (0, 0, 255) if alert else color_for_id(t.track_id)
        x1, y1, x2, y2 = (int(v) for v in t.bbox)

        if flags["trails"]:
            pts = list(trails.get(t.track_id))
            for a, b in zip(pts, pts[1:]):
                cv2.line(frame, a, b, color, 2, cv2.LINE_AA)

        if flags["boxes"]:
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3 if alert else 2)

        parts = []
        if flags["ids"]:
            parts.append(("! " if alert else "") + f"{t.class_name.capitalize()} #{t.track_id}")
        if flags["confidence"]:
            parts.append(f"{t.confidence * 100:.0f}%")
        if parts:
            _label(cv2, frame, " ".join(parts), x1, y1, color)

    if flags["events"]:
        draw_event_banners(frame, recent_events)
    if flags["stats"] and engine is not None:
        draw_stats(frame, engine)
    if flags["fps"]:
        cv2.putText(frame, f"{fps:.1f} FPS", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
    return frame
