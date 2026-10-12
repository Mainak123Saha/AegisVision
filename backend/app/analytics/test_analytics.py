"""Independent tests for each Week-4 module (no video / YOLO needed).

    python -m app.analytics.test_analytics

4.1 zones   4.2 line crossing   4.3 intrusion   4.4 loitering   4.5 events/engine
Tracks are synthetic: a person is a 40x100 box whose bottom-centre is the anchor.
"""
from ..tracking.tracker import Track, TrackState
from .engine import AnalyticsEngine, build_engine
from .events import Event, EventType, Severity
from .intrusion import IntrusionDetector
from .line_crossing import LineCrossingDetector
from .loitering import LoiteringDetector
from .zones import Line, Zone, anchor_point


def person(track_id, foot_x, foot_y, state=TrackState.ACTIVE):
    """A person track whose feet (bottom-centre of the box) are at (foot_x, foot_y)."""
    return Track(track_id, 0, "person", 0.9,
                 foot_x - 20, foot_y - 100, foot_x + 20, foot_y, state)


def removed(track_id):
    return Track(track_id, -1, "unknown", 0.0, 0, 0, 0, 0, TrackState.REMOVED)


# ---------------------------------------------------------------- 4.1
def test_zones():
    zone = Zone("restricted", [(200, 150), (600, 150), (650, 500), (180, 500)])
    assert zone.contains((400, 300))
    assert not zone.contains((50, 50))
    assert not zone.contains((620, 160))   # right of the slanted edge near the top
    assert zone.contains((200, 150))       # corner counts as inside
    assert anchor_point((100, 50, 140, 150)) == (120, 150)
    assert anchor_point((100, 50, 140, 150), "center") == (120, 100)
    try:
        Zone("bad", [(0, 0), (1, 1)])
        assert False, "expected ValueError for <3 points"
    except ValueError:
        pass
    print("4.1 zones OK")


# ---------------------------------------------------------------- 4.2
def test_line_crossing():
    line = Line("door", (0, 300), (640, 300))  # left -> right: top->bottom is IN
    det = LineCrossingDetector(line, camera_id="camA")

    # Person #7 walks top -> bottom across the line.
    events = []
    for i, y in enumerate([200, 250, 290, 310, 350]):
        events += det.update([person(7, 320, y)], timestamp=i * 0.1)
    assert len(events) == 1, events
    ev = events[0]
    assert ev.event_type == EventType.LINE_CROSSED
    assert ev.track_id == 7 and ev.camera_id == "camA"
    assert ev.metadata["direction"] == "IN" and ev.metadata["line_id"] == "door"

    # Same person walks back: OUT (after cooldown).
    events = []
    for i, y in enumerate([350, 310, 290, 250]):
        events += det.update([person(7, 320, y)], timestamp=5 + i * 0.1)
    assert [e.metadata["direction"] for e in events] == ["OUT"], events

    # Two people cross in opposite directions: each event carries the right ID.
    det = LineCrossingDetector(line)
    events = []
    for i, (y1, y2) in enumerate([(250, 350), (290, 310), (310, 290), (350, 250)]):
        events += det.update([person(1, 100, y1), person(2, 500, y2)], timestamp=float(i))
    by_id = {e.track_id: e.metadata["direction"] for e in events}
    assert by_id == {1: "IN", 2: "OUT"}, by_id

    # Walking around the end of a finite line is NOT a crossing.
    det = LineCrossingDetector(Line("short", (200, 300), (400, 300)))
    events = []
    for i, (x, y) in enumerate([(100, 200), (100, 320), (450, 320)]):
        events += det.update([person(3, x, y)], timestamp=i)
    events += det.update([person(3, 450, 280)], timestamp=3)
    assert events == [], events

    # Jitter on the line is debounced by the cooldown.
    det = LineCrossingDetector(line, cooldown=1.0)
    events = []
    for i, y in enumerate([290, 310, 290, 310, 290, 310]):
        events += det.update([person(9, 320, y)], timestamp=i * 0.1)
    assert len(events) == 1, f"expected 1 event after debounce, got {len(events)}"

    # Staying on one side never fires.
    det = LineCrossingDetector(line)
    for i in range(10):
        assert det.update([person(4, 100 + i * 10, 100)], timestamp=i) == []
    print("4.2 line crossing OK")


# ---------------------------------------------------------------- 4.3
def test_intrusion():
    zone = Zone("restricted_1", [(200, 150), (600, 150), (650, 500), (180, 500)])
    det = IntrusionDetector(zone)

    assert det.update([person(5, 50, 100)], 0.0) == []           # outside

    events = det.update([person(5, 400, 300)], 1.0)               # enters
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == EventType.INTRUSION_DETECTED
    assert ev.track_id == 5 and ev.metadata["zone_id"] == "restricted_1"
    assert ev.severity == Severity.CRITICAL
    assert det.active_ids() == {5}

    assert det.update([person(5, 410, 310)], 2.0) == []           # still inside: no repeat
    assert det.update([person(5, 50, 100)], 3.0) == []            # steps out (grace running)
    assert det.update([person(5, 50, 100)], 5.0) == []            # outside > grace: has left
    assert det.active_ids() == set()
    assert len(det.update([person(5, 400, 300)], 6.0)) == 1       # re-entry = new intrusion

    # Edge jitter (out for < grace, then back in) is NOT a new intrusion.
    det = IntrusionDetector(zone, exit_grace=1.0)
    n = len(det.update([person(8, 400, 300)], 0.0))
    for i, x in enumerate([50, 400, 50, 400, 50, 400]):
        n += len(det.update([person(8, x, 300 if x == 400 else 100)], 0.3 * (i + 1)))
    assert n == 1, f"jitter produced {n} intrusion events"

    # LOST track keeps its state (no duplicate event on reappearance), REMOVED resets it.
    det = IntrusionDetector(zone)
    det.update([person(6, 400, 300)], 0.0)
    det.update([person(6, 400, 300, TrackState.LOST)], 1.0)
    assert det.update([person(6, 405, 305)], 2.0) == []
    det.update([removed(6)], 3.0)
    assert len(det.update([person(6, 400, 300)], 4.0)) == 1
    print("4.3 intrusion OK")


# ---------------------------------------------------------------- 4.4
def test_loitering():
    zone = Zone("waiting_area", [(100, 100), (500, 100), (500, 400), (100, 400)])
    det = LoiteringDetector(zone, threshold_seconds=10, exit_grace=1.0)

    events = []
    for t in range(0, 31):                 # person #12 stands inside for 30 s
        events += det.update([person(12, 300, 300)], float(t))
    assert len(events) == 1, events        # exactly one event, not one per frame
    ev = events[0]
    assert ev.event_type == EventType.LOITERING and ev.track_id == 12
    assert ev.timestamp == 10.0 and ev.metadata["duration_seconds"] == 10.0
    assert ev.metadata["zone_id"] == "waiting_area"
    assert det.dwell_time(12, 30.0) == 30.0

    # Passing through quickly never triggers.
    det = LoiteringDetector(zone, threshold_seconds=10)
    events = []
    for t in range(0, 5):
        events += det.update([person(13, 300, 300)], float(t))
    events += det.update([person(13, 700, 300)], 5.0)
    events += det.update([person(13, 700, 300)], 8.0)    # outside > grace -> timer reset
    for t in range(9, 15):
        events += det.update([person(13, 300, 300)], float(t))
    assert events == [], events

    # Brief boundary jitter does NOT reset the timer.
    det = LoiteringDetector(zone, threshold_seconds=10, exit_grace=1.0)
    events = []
    for t in range(0, 12):
        x = 700 if t == 5 else 300           # one-frame excursion
        events += det.update([person(14, x, 300)], float(t))
    assert len(events) == 1, events
    print("4.4 loitering OK")


# ---------------------------------------------------------------- 4.5
def test_events_and_engine():
    ev = Event(EventType.LINE_CROSSED, track_id=7, timestamp=1.5, camera_id="cam0",
               metadata={"direction": "IN"})
    d = ev.to_dict()
    assert d["event_type"] == "LINE_CROSSED" and d["track_id"] == 7 and d["severity"] == "INFO"
    assert d["metadata"]["direction"] == "IN" and d["event_id"] and d["created_at"]

    spec = {
        "camera_id": "lobby",
        "coords": "normalized",
        "lines": [{"id": "door", "points": [[0, 0.5], [1, 0.5]]}],
        "zones": [{"id": "vault", "points": [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]],
                   "rules": ["intrusion", "loitering"], "loiter_seconds": 3}],
    }
    engine = build_engine(spec, (1000, 500))
    assert isinstance(engine, AnalyticsEngine) and len(engine.rules) == 3
    assert len(engine.lines) == 1 and len(engine.zones) == 2

    seen = []
    # Person #1 crosses the door line (y=250) heading down, then stands in the vault (x>600,y>300).
    path = [(300, 200), (300, 240), (300, 260), (700, 400), (700, 400), (700, 400), (700, 400), (700, 400)]
    for i, (x, y) in enumerate(path):
        seen += engine.update([person(1, x, y)], float(i))

    types = [e.event_type for e in seen]
    assert EventType.LINE_CROSSED in types
    assert EventType.INTRUSION_DETECTED in types
    assert EventType.LOITERING in types
    assert all(e.camera_id == "lobby" for e in seen)
    s = engine.stats()
    assert s["line_in"] == 1 and s["intrusions"] == 1 and s["loitering"] == 1 and s["total_events"] == 3, s
    assert engine.alert_ids() == {1}
    assert len(engine.recent(timestamp=7.0, ttl=100)) == 3
    print("4.5 events + engine OK")


def main():
    test_zones()
    test_line_crossing()
    test_intrusion()
    test_loitering()
    test_events_and_engine()
    print("\nAll analytics tests passed.")


if __name__ == "__main__":
    main()
