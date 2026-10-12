"""Line crossing: emits LINE_CROSSED when a tracked object moves across a line."""
from typing import Dict, List, Sequence, Tuple

from ..tracking.tracker import Track, TrackState
from .events import AnalyticsRule, Event, EventType, Severity
from .zones import Line, Point, anchor_point


class LineCrossingDetector(AnalyticsRule):
    """Compares each track's previous and current position against a line.

    previous position + current position -> did the movement cross the line? -> Event

    cooldown: minimum stream-seconds between two events for the same track, so
              jitter right on the line doesn't generate a burst of crossings.
    """

    def __init__(self, line: Line, camera_id="cam0", cooldown=1.0, anchor="bottom"):
        self.line = line
        self.camera_id = camera_id
        self.cooldown = cooldown
        self.anchor = anchor
        # track_id -> (last position, last non-zero side of the line)
        self._prev: Dict[int, Tuple[Point, int]] = {}
        self._last_event: Dict[int, float] = {}

    def update(self, tracks: Sequence[Track], timestamp: float) -> List[Event]:
        events: List[Event] = []

        for t in tracks:
            if t.state == TrackState.REMOVED:
                # The track ended; forget it so a reused/new ID starts fresh.
                self._prev.pop(t.track_id, None)
                self._last_event.pop(t.track_id, None)
                continue
            if t.state == TrackState.LOST:
                continue  # position is only a prediction; keep old state until it reappears

            point = anchor_point(t.bbox, self.anchor)
            side = self.line.side(point)
            if side == 0:
                continue  # exactly on the line: wait for a side to be decided

            prev = self._prev.get(t.track_id)
            if prev is not None:
                prev_point, prev_side = prev
                if (
                    prev_side != side
                    and self.line.crosses(prev_point, point)
                    and timestamp - self._last_event.get(t.track_id, -1e9) >= self.cooldown
                ):
                    self._last_event[t.track_id] = timestamp
                    events.append(Event(
                        event_type=EventType.LINE_CROSSED,
                        track_id=t.track_id,
                        timestamp=timestamp,
                        camera_id=self.camera_id,
                        severity=Severity.INFO,
                        metadata={
                            "line_id": self.line.line_id,
                            "direction": "IN" if prev_side < 0 else "OUT",
                            "class_name": t.class_name,
                            "position": [round(point[0], 1), round(point[1], 1)],
                        },
                    ))

            self._prev[t.track_id] = (point, side)

        return events
