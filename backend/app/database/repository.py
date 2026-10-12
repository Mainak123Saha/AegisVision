"""Data-access layer: all SQL lives here so API routes and services stay thin."""
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Camera, Event


def _camera_id_to_int(value: Any) -> Optional[int]:
    """The analytics Event carries camera_id as str; the DB uses the integer camera PK."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def event_dict_to_row(d: Dict[str, Any]) -> Dict[str, Any]:
    """Convert `analytics.events.Event.to_dict()` output into column values."""
    row: Dict[str, Any] = {
        "event_id": d["event_id"],
        "event_type": d["event_type"],
        "track_id": int(d["track_id"]),
        "camera_id": _camera_id_to_int(d.get("camera_id")),
        "timestamp": float(d["timestamp"]),
        "severity": d["severity"],
        "metadata": d.get("metadata") or {},
    }
    if d.get("created_at"):
        row["created_at"] = datetime.fromisoformat(d["created_at"])
    return row


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_many(self, events: Iterable[Dict[str, Any]]) -> int:
        """Persist event dicts; duplicates (same event_id) are ignored so retries are safe."""
        rows = [event_dict_to_row(e) for e in events]
        if not rows:
            return 0
        # Drop references to cameras that no longer exist instead of failing the batch.
        ids = {r["camera_id"] for r in rows if r["camera_id"] is not None}
        if ids:
            existing = set(self.db.scalars(select(Camera.id).where(Camera.id.in_(ids))))
            for r in rows:
                if r["camera_id"] not in existing:
                    r["camera_id"] = None
        stmt = pg_insert(Event).values(rows).on_conflict_do_nothing(index_elements=["event_id"])
        try:
            result = self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result.rowcount or 0

    @staticmethod
    def _filters(event_type, severity, camera_id, start, end) -> list:
        conds = []
        if event_type:
            conds.append(Event.event_type == event_type)
        if severity:
            conds.append(Event.severity == severity)
        if camera_id is not None:
            conds.append(Event.camera_id == camera_id)
        if start:
            conds.append(Event.created_at >= start)
        if end:
            conds.append(Event.created_at <= end)
        return conds

    def list(self, *, event_type=None, severity=None, camera_id=None, start=None, end=None,
             limit: int = 50, offset: int = 0) -> Tuple[List[Event], int]:
        conds = self._filters(event_type, severity, camera_id, start, end)
        total = self.db.scalar(select(func.count()).select_from(Event).where(*conds)) or 0
        items = self.db.scalars(
            select(Event).where(*conds).order_by(Event.created_at.desc(), Event.event_id)
            .limit(limit).offset(offset)
        ).all()
        return list(items), total

    def get(self, event_id: str) -> Optional[Event]:
        return self.db.get(Event, event_id)

    def summary(self, *, start=None, end=None, camera_id=None) -> Dict[str, Any]:
        conds = self._filters(None, None, camera_id, start, end)
        by_type = dict(self.db.execute(
            select(Event.event_type, func.count()).where(*conds).group_by(Event.event_type)).all())
        by_sev = dict(self.db.execute(
            select(Event.severity, func.count()).where(*conds).group_by(Event.severity)).all())
        by_cam = dict(self.db.execute(
            select(Event.camera_id, func.count()).where(*conds).group_by(Event.camera_id)).all())
        return {"by_type": by_type, "by_severity": by_sev, "by_camera": by_cam}


class CameraRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> Sequence[Camera]:
        return self.db.scalars(select(Camera).order_by(Camera.id)).all()

    def get(self, camera_id: int) -> Optional[Camera]:
        return self.db.get(Camera, camera_id)

    def get_by_name(self, name: str) -> Optional[Camera]:
        return self.db.scalar(select(Camera).where(Camera.name == name))

    def create(self, **fields) -> Camera:
        cam = Camera(**fields)
        self.db.add(cam)
        self._commit()
        self.db.refresh(cam)
        return cam

    def update(self, cam: Camera, **fields) -> Camera:
        for k, v in fields.items():
            setattr(cam, k, v)
        self._commit()
        self.db.refresh(cam)
        return cam

    def delete(self, cam: Camera) -> None:
        self.db.delete(cam)
        self._commit()

    def set_active(self, camera_id: int, active: bool) -> None:
        self.db.execute(update(Camera).where(Camera.id == camera_id).values(is_active=active))
        self._commit()

    def deactivate_all(self) -> None:
        self.db.execute(update(Camera).where(Camera.is_active.is_(True)).values(is_active=False))
        self._commit()

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
