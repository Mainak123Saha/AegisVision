from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    event_id: str
    event_type: str
    track_id: int
    camera_id: Optional[int]
    timestamp: float
    severity: str
    # ORM attribute is `event_metadata`; exposed to clients as `metadata`.
    metadata: Dict[str, Any] = Field(validation_alias="event_metadata")
    created_at: datetime


class EventPage(BaseModel):
    items: List[EventOut]
    total: int
    limit: int
    offset: int


class AnalyticsSummary(BaseModel):
    start: datetime
    end: datetime
    camera_id: Optional[int] = None
    total_events: int
    intrusion_events: int
    loitering_events: int
    line_crossed_events: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    by_camera: Dict[str, int]
