from datetime import datetime
from enum import Enum
from typing import Optional

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
