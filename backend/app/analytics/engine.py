"""AnalyticsEngine: runs all rules on each frame's tracks and collects the events.

                Tracks
                  |
      +-----------+-----------+
      v           v           v
  LineCrossing  Intrusion  Loitering
      +-----------+-----------+
                  v
               Events  -> overlay / log / (later) API + database
"""
import json
from collections import Counter, deque
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..tracking.tracker import Track
from .events import AnalyticsRule, Event, EventType
from .intrusion import IntrusionDetector
from .line_crossing import LineCrossingDetector
from .loitering import LoiteringDetector
from .zones import Line, Zone


class AnalyticsEngine:
    """Owns the rules, the event history and running statistics."""

    def __init__(self, rules: Iterable[AnalyticsRule], history_size=1000):
        self.rules: List[AnalyticsRule] = list(rules)
        self.history: Deque[Event] = deque(maxlen=history_size)
        self.counts: Counter = Counter()      # event_type value -> total
        self.line_counts: Counter = Counter()  # "IN" / "OUT" -> total

    # --- processing ---------------------------------------------------
    def update(self, tracks: Sequence[Track], timestamp: float) -> List[Event]:
        """Run every rule on this frame; returns only the *new* events."""
        new_events: List[Event] = []
        for rule in self.rules:
            new_events.extend(rule.update(tracks, timestamp))

        for ev in new_events:
            self.history.append(ev)
            self.counts[ev.event_type.value] += 1
            if ev.event_type == EventType.LINE_CROSSED:
                self.line_counts[ev.metadata.get("direction", "?")] += 1
        return new_events

    # --- queries (for visualisation / statistics) --------------------
    def recent(self, timestamp: float, ttl: float = 4.0) -> List[Event]:
        """Events from the last `ttl` stream-seconds (for on-screen banners)."""
        return [e for e in self.history if timestamp - e.timestamp <= ttl]

    def alert_ids(self) -> Set[int]:
        """Track IDs currently in an alert state (inside a restricted zone, loitering)."""
        ids: Set[int] = set()
        for rule in self.rules:
            ids |= rule.active_ids()
        return ids

    @property
    def zones(self) -> List[Tuple[Zone, str]]:
        """(zone, kind) pairs for drawing; kind is 'intrusion' or 'loitering'."""
        out = []
        for r in self.rules:
            if isinstance(r, IntrusionDetector):
                out.append((r.zone, "intrusion"))
            elif isinstance(r, LoiteringDetector):
                out.append((r.zone, "loitering"))
        return out

    @property
    def lines(self) -> List[Line]:
        return [r.line for r in self.rules if isinstance(r, LineCrossingDetector)]

    def stats(self) -> Dict[str, int]:
        return {
            "line_in": self.line_counts["IN"],
            "line_out": self.line_counts["OUT"],
            "intrusions": self.counts[EventType.INTRUSION_DETECTED.value],
            "loitering": self.counts[EventType.LOITERING.value],
            "total_events": sum(self.counts.values()),
        }


def build_engine(spec: dict, frame_size: Tuple[int, int]) -> AnalyticsEngine:
    """Create an engine from a config dict (see `config/zones.json`).

    spec = {
      "camera_id": "cam0",
      "coords": "normalized" | "pixel",     # normalized = 0..1 fractions of the frame
      "lines": [{"id", "points": [[x,y],[x,y]], "cooldown"}],
      "zones": [{"id", "name", "points": [[x,y],...], "rules": ["intrusion", "loitering"],
                 "loiter_seconds": 10}]
    }
    `frame_size` is (width, height) of the frames the pipeline will process, so
    normalized coordinates work at any resolution.
    """
    w, h = frame_size
    camera_id = spec.get("camera_id", "cam0")
    normalized = spec.get("coords", "pixel") == "normalized"

    def conv(p):
        return (p[0] * w, p[1] * h) if normalized else (p[0], p[1])

    rules: List[AnalyticsRule] = []

    for ln in spec.get("lines", []):
        p1, p2 = (conv(p) for p in ln["points"])
        rules.append(LineCrossingDetector(
            Line(ln["id"], p1, p2, ln.get("name", "")),
            camera_id=camera_id,
            cooldown=ln.get("cooldown", 1.0),
        ))

    for z in spec.get("zones", []):
        zone = Zone(z["id"], [conv(p) for p in z["points"]], z.get("name", ""))
        kinds = z.get("rules", ["intrusion"])
        if "intrusion" in kinds:
            rules.append(IntrusionDetector(zone, camera_id=camera_id))
        if "loitering" in kinds:
            rules.append(LoiteringDetector(
                zone,
                threshold_seconds=z.get("loiter_seconds", 10.0),
                camera_id=camera_id,
            ))

    return AnalyticsEngine(rules)


def load_engine(path: str, frame_size: Tuple[int, int]) -> AnalyticsEngine:
    """Read a JSON config file and build the engine for the given frame size."""
    with open(path) as f:
        return build_engine(json.load(f), frame_size)
