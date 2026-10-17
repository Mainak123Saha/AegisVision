from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceType(str, Enum):
    mp4 = "mp4"
    webcam = "webcam"
    rtsp = "rtsp"


def _check_source(source_type: SourceType, uri: str) -> None:
    if source_type == SourceType.webcam and not uri.isdigit():
        raise ValueError("webcam source_uri must be a device index such as '0'")
    if source_type == SourceType.rtsp and not uri.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
        raise ValueError("rtsp source_uri must be an rtsp:// or http(s):// URL")


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source_type: SourceType
    source_uri: str = Field(min_length=1, max_length=500, description="MP4 path, webcam index or RTSP URL")
    location: Optional[str] = Field(default=None, max_length=200)

    @field_validator("name", "source_uri")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def _validate_source(self):
        _check_source(self.source_type, self.source_uri)
        return self


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    source_type: Optional[SourceType] = None
    source_uri: Optional[str] = Field(default=None, min_length=1, max_length=500)
    location: Optional[str] = Field(default=None, max_length=200)


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    source_uri: str
    location: Optional[str]
    is_active: bool
    created_at: datetime


class CameraStatus(BaseModel):
    camera_id: int
    running: bool
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    events_persisted: int = 0
    last_error: Optional[str] = None


class OverlaySettings(BaseModel):
    """What the live view draws on the video. Every flag can be toggled while a camera runs."""
    boxes: bool
    ids: bool
    confidence: bool
    zones: bool
    events: bool
    trails: bool
    stats: bool
    fps: bool


class OverlayUpdate(BaseModel):
    boxes: Optional[bool] = None
    ids: Optional[bool] = None
    confidence: Optional[bool] = None
    zones: Optional[bool] = None
    events: Optional[bool] = None
    trails: Optional[bool] = None
    stats: Optional[bool] = None
    fps: Optional[bool] = None


class LiveInfo(BaseModel):
    running: bool
    seq: int = 0
    # frame, stream_time, fps, tracks [{track_id, class_name, confidence, alert}], stats
    meta: Optional[Dict[str, Any]] = None


class LineSpec(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=100)
    points: List[Tuple[float, float]] = Field(min_length=2, max_length=2)
    cooldown: float = Field(default=1.0, ge=0.0, le=300.0)


class ZoneSpec(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=100)
    points: List[Tuple[float, float]] = Field(min_length=3, max_length=50)
    rules: List[Literal["intrusion", "loitering"]] = Field(min_length=1)
    loiter_seconds: float = Field(default=5.0, ge=1.0, le=3600.0)


class ZonesConfig(BaseModel):
    camera_id: str = "cam0"
    coords: Literal["normalized", "pixel"] = "normalized"
    lines: List[LineSpec] = Field(default_factory=list)
    zones: List[ZoneSpec] = Field(default_factory=list)
