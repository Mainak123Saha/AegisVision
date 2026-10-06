"""Tracker interface and the Track data model.

Boundary:  detection/ -> Detection objects -> tracking/ -> Track objects.
The tracker only ever sees `Detection`s, never YOLO internals.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence, Tuple

from ..detection.models import Detection


class TrackState(Enum):
    """Lifecycle of a track.

    NEW      -> first frame in which the track is confirmed
    ACTIVE   -> matched to a detection on a following frame
    LOST     -> not matched recently; kept alive in case the object reappears
    REMOVED  -> lost for too long; the ID is retired (reported exactly once)
    """

    NEW = "new"
    ACTIVE = "active"
    LOST = "lost"
    REMOVED = "removed"


@dataclass
class Track:
    """One tracked object in the current frame."""

    track_id: int
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    state: TrackState
    age: int = 0          # frames since the track was first confirmed
    frames_lost: int = 0  # consecutive frames without a match (0 unless LOST)

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """The box as an (x1, y1, x2, y2) tuple."""
        return (self.x1, self.y1, self.x2, self.y2)


class Tracker(ABC):
    """Interface for multi-object trackers, so ByteTrack can be swapped later."""

    @abstractmethod
    def update(self, detections: Sequence[Detection], frame) -> List[Track]:
        """Consume this frame's detections and return all relevant tracks.

        The result contains NEW/ACTIVE tracks (currently visible), LOST tracks
        (temporarily unmatched) and REMOVED tracks (ended this frame).
        Must be called once per frame, in order.
        """
        pass

    @abstractmethod
    def reset(self):
        """Forget all tracks (e.g. when switching video source)."""
        pass
