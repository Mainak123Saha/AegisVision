"""ORM models: Camera and Event (Event mirrors the analytics `Event` dataclass)."""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # mp4 | webcam | rtsp
    # File path (mp4), device index (webcam) or stream URL (rtsp). Needed to start processing.
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Events are kept when their camera is deleted.
    camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)  # stream seconds
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # "metadata" is reserved by SQLAlchemy's declarative API, so the attribute has another name.
    event_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_camera_id", "camera_id"),
        Index("ix_events_type_severity", "event_type", "severity"),
    )
