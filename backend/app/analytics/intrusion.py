"""Restricted-zone intrusion: emits INTRUSION_DETECTED when a track enters a zone."""
from typing import Dict, List, Sequence, Set

from ..tracking.tracker import Track, TrackState
from .events import AnalyticsRule, Event, EventType, Severity
from .zones import Zone, anchor_point


class IntrusionDetector(AnalyticsRule):
    """One event per *entry*: fires when a track goes from outside to inside.

    A track that stays inside does not re-fire every frame. If it leaves and
    enters again, that is a new intrusion.

    exit_grace: seconds a track must stay outside before it counts as having
                left. Without this, a person standing on the zone edge (or a
                jittery box) would generate a new intrusion every few frames.
    """

    def __init__(self, zone: Zone, camera_id="cam0", anchor="bottom", exit_grace=1.0):
        self.zone = zone
        self.camera_id = camera_id
        self.anchor = anchor
        self.exit_grace = exit_grace
        self._inside: Set[int] = set()
        self._outside_since: Dict[int, float] = {}

    def _forget(self, track_id: int):
        self._inside.discard(track_id)
        self._outside_since.pop(track_id, None)

    def update(self, tracks: Sequence[Track], timestamp: float) -> List[Event]:
        events: List[Event] = []

        for t in tracks:
            if t.state == TrackState.REMOVED:
                self._forget(t.track_id)
                continue
            if t.state == TrackState.LOST:
                continue  # keep its inside/outside status until it is seen again

            point = anchor_point(t.bbox, self.anchor)
            if self.zone.contains(point):
                self._outside_since.pop(t.track_id, None)
                if t.track_id not in self._inside:
                    self._inside.add(t.track_id)
                    events.append(Event(
                        event_type=EventType.INTRUSION_DETECTED,
                        track_id=t.track_id,
                        timestamp=timestamp,
                        camera_id=self.camera_id,
                        severity=Severity.CRITICAL,
                        metadata={
                            "zone_id": self.zone.zone_id,
                            "zone_name": self.zone.name,
                            "class_name": t.class_name,
                            "position": [round(point[0], 1), round(point[1], 1)],
                        },
                    ))
            elif t.track_id in self._inside:
                # Stepped outside: only counts as "left" after the grace period.
                since = self._outside_since.setdefault(t.track_id, timestamp)
                if timestamp - since > self.exit_grace:
                    self._forget(t.track_id)

        return events

    def active_ids(self) -> Set[int]:
        return set(self._inside)
