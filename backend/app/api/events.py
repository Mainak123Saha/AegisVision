from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..analytics.events import EventType, Severity
from ..database.db import get_db
from ..database.repository import EventRepository
from ..schemas.event import EventOut, EventPage

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventPage)
def list_events(
    event_type: Optional[EventType] = None,
    severity: Optional[Severity] = None,
    camera_id: Optional[int] = None,
    start: Optional[datetime] = Query(None, description="created_at >= start (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="created_at <= end (ISO 8601)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if start and end and start > end:
        raise HTTPException(422, "start must be before end")
    items, total = EventRepository(db).list(
        event_type=event_type.value if event_type else None,
        severity=severity.value if severity else None,
        camera_id=camera_id, start=start, end=end, limit=limit, offset=offset,
    )
    return EventPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    ev = EventRepository(db).get(event_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Event {event_id} not found")
    return ev
