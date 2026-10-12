"""Common event model and the rule interface shared by all analytics modules.

Every rule (line crossing, intrusion, loitering, ...) returns `Event` objects,
so the rest of the system (overlay, logging, and later FastAPI/DB) deals with a
single structure.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Sequence, Set

from ..tracking.tracker import Track


class EventType(str, Enum):
    LINE_CROSSED = "LINE_CROSSED"
    INTRUSION_DETECTED = "INTRUSION_DETECTED"
    LOITERING = "LOITERING"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Event:
    """Something that happened to a tracked object.

    event_type: what happened (see `EventType`).
    track_id:   which tracked object it happened to (stable ID from the tracker).
    timestamp:  seconds on the stream's clock (video time for files, wall-clock
                elapsed time for live sources). Used by all duration logic.
    camera_id:  which camera produced it.
    metadata:   event-specific details (zone_id, line_id, direction, duration...).
    severity:   INFO / WARNING / CRITICAL.
    """

    event_type: EventType
    track_id: int
    timestamp: float
    camera_id: str = "cam0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable form (what will later be sent to an API / stored in a DB)."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "track_id": self.track_id,
            "timestamp": round(self.timestamp, 3),
            "camera_id": self.camera_id,
            "metadata": self.metadata,
            "severity": self.severity.value,
            "created_at": self.created_at,
        }


class AnalyticsRule(ABC):
    """A rule consumes the tracks of each frame and emits zero or more events."""

    @abstractmethod
    def update(self, tracks: Sequence[Track], timestamp: float) -> List[Event]:
        """Process one frame's tracks. Must be called once per frame, in order."""
        pass

    def active_ids(self) -> Set[int]:
        """Track IDs currently in an alert condition (used to highlight them)."""
        return set()
