"""Loitering: emits LOITERING when a track stays inside a zone too long."""
from typing import Dict, List, Sequence, Set

from ..tracking.tracker import Track, TrackState
from .events import AnalyticsRule, Event, EventType, Severity
from .zones import Zone, anchor_point


class LoiteringDetector(AnalyticsRule):
    """Tracks how long each track has been inside a zone.

    entered_at is recorded when a track first appears inside the zone; once
    `timestamp - entered_at >= threshold_seconds` a single LOITERING event is
    emitted for that visit.

    exit_grace: seconds a track may be outside the zone before its timer is
                reset. Stops boundary jitter from restarting the clock.
    """

    def __init__(self, zone: Zone, threshold_seconds=10.0, camera_id="cam0",
                 exit_grace=1.0, anchor="bottom"):
        self.zone = zone
        self.threshold = threshold_seconds
        self.camera_id = camera_id
        self.exit_grace = exit_grace
        self.anchor = anchor
        self._entered_at: Dict[int, float] = {}
        self._outside_since: Dict[int, float] = {}
        self._alerted: Set[int] = set()

    def _forget(self, track_id: int):
        self._entered_at.pop(track_id, None)
        self._outside_since.pop(track_id, None)
        self._alerted.discard(track_id)

    def update(self, tracks: Sequence[Track], timestamp: float) -> List[Event]:
        events: List[Event] = []

        for t in tracks:
            tid = t.track_id
            if t.state == TrackState.REMOVED:
                self._forget(tid)
                continue
            if t.state == TrackState.LOST:
                continue  # timer keeps running; removal (not loss) ends the visit

            point = anchor_point(t.bbox, self.anchor)

            if self.zone.contains(point):
                self._outside_since.pop(tid, None)
                entered = self._entered_at.setdefault(tid, timestamp)
                duration = timestamp - entered
                if duration >= self.threshold and tid not in self._alerted:
                    self._alerted.add(tid)
                    events.append(Event(
                        event_type=EventType.LOITERING,
                        track_id=tid,
                        timestamp=timestamp,
                        camera_id=self.camera_id,
                        severity=Severity.WARNING,
                        metadata={
                            "zone_id": self.zone.zone_id,
                            "zone_name": self.zone.name,
                            "entered_at": round(entered, 3),
                            "duration_seconds": round(duration, 2),
                            "class_name": t.class_name,
                        },
                    ))
            elif tid in self._entered_at:
                # Just stepped outside: only forget after the grace period.
                since = self._outside_since.setdefault(tid, timestamp)
                if timestamp - since > self.exit_grace:
                    self._forget(tid)

        return events

    def dwell_time(self, track_id: int, timestamp: float) -> float:
        """Seconds the track has currently been inside the zone (0 if not inside)."""
        entered = self._entered_at.get(track_id)
        return 0.0 if entered is None else timestamp - entered

    def active_ids(self) -> Set[int]:
        return set(self._alerted)
