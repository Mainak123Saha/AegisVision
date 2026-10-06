"""ByteTrack integration (uses Ultralytics' BYTETracker implementation).

We do not re-implement the algorithm. This adapter converts our `Detection`
objects into what BYTETracker expects, and converts its output into `Track`
objects with an explicit NEW / ACTIVE / LOST / REMOVED lifecycle.
"""
from typing import Dict, List, Sequence

import numpy as np
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import IterableSimpleNamespace

from ..detection.models import Detection
from .tracker import Track, Tracker, TrackState


class ByteTracker(Tracker):
    """
    track_high_thresh: detections above this are matched first (and can start tracks).
    track_low_thresh:  detections between low and high are used in the 2nd matching
                       stage to recover occluded tracks (ByteTrack's key idea).
                       Only helps if the detector actually outputs boxes that low;
                       the detector's own confidence threshold filters first.
    new_track_thresh:  minimum score to start a brand-new track.
    track_buffer:      frames a LOST track is kept before being REMOVED
                       (higher = survives longer occlusions, more ID-switch risk).
    match_thresh:      association threshold for matching boxes to tracks.
    frame_rate:        source FPS (kept for API completeness; BYTETracker counts frames).
    """

    def __init__(
        self,
        track_high_thresh=0.25,
        track_low_thresh=0.1,
        new_track_thresh=0.25,
        track_buffer=30,
        match_thresh=0.8,
    ):
        self._args = IterableSimpleNamespace(
            track_high_thresh=track_high_thresh,
            track_low_thresh=track_low_thresh,
            new_track_thresh=new_track_thresh,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            fuse_score=True,
        )
        self._class_names: Dict[int, str] = {}
        self.reset()

    def reset(self):
        self._tracker = BYTETracker(self._args)
        # id -> age (frames since first confirmed) for every track currently alive.
        self._alive: Dict[int, int] = {}

    def update(self, detections: Sequence[Detection], frame) -> List[Track]:
        h, w = frame.shape[:2]

        # Our Detection list -> (N, 6) array [x1, y1, x2, y2, conf, cls] -> Boxes,
        # the structure BYTETracker reads (.conf, .cls, .xywh).
        rows = np.array(
            [[d.x1, d.y1, d.x2, d.y2, d.confidence, d.class_id] for d in detections],
            dtype=np.float32,
        ).reshape(-1, 6)
        for d in detections:
            self._class_names[d.class_id] = d.class_name

        # Output rows: [x1, y1, x2, y2, track_id, score, cls, detection_index]
        output = self._tracker.update(Boxes(rows, (h, w)), frame)

        tracks: List[Track] = []
        current_ids = set()

        # Visible tracks: NEW on their first frame, ACTIVE afterwards.
        for x1, y1, x2, y2, tid, score, cls, _ in output:
            tid, cls = int(tid), int(cls)
            current_ids.add(tid)
            is_new = tid not in self._alive
            self._alive[tid] = 0 if is_new else self._alive[tid] + 1
            tracks.append(Track(
                track_id=tid, class_id=cls, class_name=self._name(cls),
                confidence=float(score),
                x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2),
                state=TrackState.NEW if is_new else TrackState.ACTIVE,
                age=self._alive[tid],
            ))

        # Lost tracks: still remembered by the tracker, but unmatched this frame.
        for st in self._tracker.lost_stracks:
            if st.track_id in current_ids:
                continue
            current_ids.add(st.track_id)
            self._alive[st.track_id] = self._alive.get(st.track_id, 0) + 1
            x1, y1, x2, y2 = st.xyxy
            cls = int(st.cls)
            tracks.append(Track(
                track_id=st.track_id, class_id=cls, class_name=self._name(cls),
                confidence=float(st.score),
                x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2),
                state=TrackState.LOST,
                age=self._alive[st.track_id],
                frames_lost=self._tracker.frame_id - st.end_frame,
            ))

        # Removed: alive last frame, neither visible nor lost now -> retired. Report once.
        for tid in [i for i in self._alive if i not in current_ids]:
            age = self._alive.pop(tid)
            tracks.append(Track(
                track_id=tid, class_id=-1, class_name="unknown", confidence=0.0,
                x1=0.0, y1=0.0, x2=0.0, y2=0.0,
                state=TrackState.REMOVED, age=age,
            ))

        return tracks

    def _name(self, class_id: int) -> str:
        return self._class_names.get(class_id, str(class_id))
