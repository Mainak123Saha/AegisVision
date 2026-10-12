"""Draw zones, lines, event banners and statistics on the video."""
from typing import Iterable, Sequence

import cv2
import numpy as np

from .engine import AnalyticsEngine
from .events import Event, EventType

FONT = cv2.FONT_HERSHEY_SIMPLEX

# BGR colours per zone kind / event type.
ZONE_COLORS = {"intrusion": (0, 0, 255), "loitering": (0, 165, 255)}
LINE_COLOR = (255, 255, 0)
EVENT_COLORS = {
    EventType.LINE_CROSSED: (255, 255, 0),
    EventType.INTRUSION_DETECTED: (0, 0, 255),
    EventType.LOITERING: (0, 165, 255),
}


def draw_zones(frame, engine: AnalyticsEngine):
    """Semi-transparent filled polygons with an outline and a name tag."""
    overlay = frame.copy()
    for zone, kind in engine.zones:
        pts = np.array(zone.polygon, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], ZONE_COLORS[kind])
    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

    for zone, kind in engine.zones:
        pts = np.array(zone.polygon, dtype=np.int32)
        color = ZONE_COLORS[kind]
        cv2.polylines(frame, [pts], True, color, 2)
        x, y = pts[0]
        cv2.putText(frame, f"{zone.name} ({kind})", (int(x) + 4, int(y) + 18), FONT, 0.5, color, 1)


def draw_lines(frame, engine: AnalyticsEngine):
    """Each line, plus a small arrow from its midpoint pointing to the IN side."""
    for line in engine.lines:
        p1 = tuple(int(v) for v in line.p1)
        p2 = tuple(int(v) for v in line.p2)
        cv2.line(frame, p1, p2, LINE_COLOR, 2)

        # Normal pointing toward the positive side (the side people move toward when going IN).
        dx, dy = line.p2[0] - line.p1[0], line.p2[1] - line.p1[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        nx, ny = -dy / length, dx / length
        mx, my = (line.p1[0] + line.p2[0]) / 2, (line.p1[1] + line.p2[1]) / 2
        cv2.arrowedLine(frame, (int(mx), int(my)), (int(mx + nx * 30), int(my + ny * 30)),
                        LINE_COLOR, 2, tipLength=0.4)
        cv2.putText(frame, f"{line.name} (IN)", (int(mx + nx * 36), int(my + ny * 36)), FONT, 0.5, LINE_COLOR, 1)


def _event_lines(ev: Event):
    """Banner text for one event."""
    who = f"{ev.metadata.get('class_name', 'object').capitalize()} #{ev.track_id}"
    if ev.event_type == EventType.LINE_CROSSED:
        return ["! LINE CROSSING", who, f"Direction: {ev.metadata.get('direction', '?')}"]
    if ev.event_type == EventType.INTRUSION_DETECTED:
        return ["! INTRUSION DETECTED", who, f"Zone: {ev.metadata.get('zone_name', '')}"]
    if ev.event_type == EventType.LOITERING:
        return ["! LOITERING", who,
                f"Zone: {ev.metadata.get('zone_name', '')}  ({ev.metadata.get('duration_seconds', 0):.0f}s)"]
    return [ev.event_type.value, who]


def draw_event_banners(frame, events: Sequence[Event], max_events=3):
    """Stack the most recent events at the bottom-left, newest at the bottom."""
    h = frame.shape[0]
    y = h - 12
    for ev in list(events)[-max_events:][::-1]:
        lines = _event_lines(ev)
        color = EVENT_COLORS.get(ev.event_type, (255, 255, 255))
        box_h = 20 * len(lines) + 8
        box_w = max(cv2.getTextSize(t, FONT, 0.55, 1)[0][0] for t in lines) + 16
        top = y - box_h
        sub = frame[max(top, 0):y, 8:8 + box_w]
        if sub.size:
            frame[max(top, 0):y, 8:8 + box_w] = (sub * 0.35).astype(np.uint8)
        cv2.rectangle(frame, (8, top), (8 + box_w, y), color, 1)
        for i, text in enumerate(lines):
            cv2.putText(frame, text, (16, top + 20 * (i + 1)), FONT, 0.55,
                        color if i == 0 else (255, 255, 255), 1)
        y = top - 8


def draw_stats(frame, engine: AnalyticsEngine):
    """Running totals, top-right corner."""
    s = engine.stats()
    rows = [
        f"Line IN: {s['line_in']}  OUT: {s['line_out']}",
        f"Intrusions: {s['intrusions']}",
        f"Loitering: {s['loitering']}",
        f"Total events: {s['total_events']}",
    ]
    w = frame.shape[1]
    for i, text in enumerate(rows):
        (tw, _), _ = cv2.getTextSize(text, FONT, 0.6, 2)
        cv2.putText(frame, text, (w - tw - 12, 28 + 26 * i), FONT, 0.6, (255, 255, 255), 2)
