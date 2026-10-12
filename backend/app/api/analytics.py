from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..analytics.events import EventType
from ..database.db import get_db
from ..database.repository import EventRepository
from typing import List

from ..schemas.event import AnalyticsSummary, HourlyBucket

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(
    start: Optional[datetime] = Query(None, description="Default: 24 hours before end"),
    end: Optional[datetime] = Query(None, description="Default: now"),
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(hours=24)
    if start > end:
        raise HTTPException(422, "start must be before end")
    agg = EventRepository(db).summary(start=start, end=end, camera_id=camera_id)
    by_type = agg["by_type"]
    return AnalyticsSummary(
        start=start, end=end, camera_id=camera_id,
        total_events=sum(by_type.values()),
        intrusion_events=by_type.get(EventType.INTRUSION_DETECTED.value, 0),
        loitering_events=by_type.get(EventType.LOITERING.value, 0),
        line_crossed_events=by_type.get(EventType.LINE_CROSSED.value, 0),
        visitors_in=agg["by_direction"].get("IN", 0),
        visitors_out=agg["by_direction"].get("OUT", 0),
        by_type=by_type,
        by_severity=agg["by_severity"],
        by_camera={str(k) if k is not None else "unassigned": v for k, v in agg["by_camera"].items()},
    )


@router.get("/hourly", response_model=List[HourlyBucket])
def hourly(
    start: Optional[datetime] = Query(None, description="Default: 24 hours before end"),
    end: Optional[datetime] = Query(None, description="Default: now"),
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Events per hour (UTC) for the period, with empty hours included as zero."""
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(hours=24)
    if start > end:
        raise HTTPException(422, "start must be before end")
    if end - start > timedelta(days=31):
        raise HTTPException(422, "period must be at most 31 days")
    buckets = {}
    t = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    while t <= end:
        buckets[t] = {}
        t += timedelta(hours=1)
    for hour, etype, count in EventRepository(db).hourly(start=start, end=end, camera_id=camera_id):
        buckets.setdefault(hour.replace(tzinfo=timezone.utc), {})[etype] = count
    return [HourlyBucket(hour=h, total=sum(v.values()), by_type=v) for h, v in sorted(buckets.items())]
