import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.db import get_db
from ..database.models import Camera
from ..database.repository import CameraRepository
from ..schemas.camera import CameraCreate, CameraOut, CameraStatus, CameraUpdate, LiveInfo, OverlaySettings, OverlayUpdate, _check_source
from ..services.vision_service import (
    CameraAlreadyRunning, CameraNotRunning, CameraSourceError, VisionService,
)
from .deps import get_vision

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _get_or_404(repo: CameraRepository, camera_id: int) -> Camera:
    cam = repo.get(camera_id)
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Camera {camera_id} not found")
    return cam


def _duplicate_name() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "A camera with this name already exists")


@router.get("", response_model=List[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    return CameraRepository(db).list()


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)):
    repo = CameraRepository(db)
    if repo.get_by_name(body.name):
        raise _duplicate_name()
    try:
        return repo.create(**body.model_dump())
    except IntegrityError:
        raise _duplicate_name()


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    return _get_or_404(CameraRepository(db), camera_id)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, body: CameraUpdate, db: Session = Depends(get_db),
                  vision: VisionService = Depends(get_vision)):
    repo = CameraRepository(db)
    cam = _get_or_404(repo, camera_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None or "source_type" in changes and changes["source_type"] is None \
            or "source_uri" in changes and changes["source_uri"] is None:
        raise HTTPException(422, "name, source_type and source_uri cannot be null")
    if ("source_type" in changes or "source_uri" in changes) and vision.is_running(camera_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stop the camera before changing its source")
    try:
        _check_source(changes.get("source_type", cam.source_type), changes.get("source_uri", cam.source_uri))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if "source_type" in changes:
        changes["source_type"] = changes["source_type"].value if hasattr(changes["source_type"], "value") else changes["source_type"]
    if "name" in changes:
        other = repo.get_by_name(changes["name"])
        if other and other.id != camera_id:
            raise _duplicate_name()
    try:
        return repo.update(cam, **changes)
    except IntegrityError:
        raise _duplicate_name()


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    repo = CameraRepository(db)
    cam = _get_or_404(repo, camera_id)
    try:
        vision.stop(camera_id)
    except CameraNotRunning:
        pass
    repo.delete(cam)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{camera_id}/start", response_model=CameraStatus)
def start_camera(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    repo = CameraRepository(db)
    cam = _get_or_404(repo, camera_id)
    try:
        vision.start(cam)
    except CameraAlreadyRunning:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Camera {camera_id} is already running")
    except CameraSourceError as exc:
        raise HTTPException(422, str(exc))
    try:
        repo.set_active(camera_id, True)
    except Exception:
        vision.stop(camera_id)  # don't leave an untracked worker running
        raise
    return vision.status(camera_id)


@router.post("/{camera_id}/stop", response_model=CameraStatus)
def stop_camera(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    repo = CameraRepository(db)
    _get_or_404(repo, camera_id)
    try:
        vision.stop(camera_id)
    except CameraNotRunning:
        repo.set_active(camera_id, False)  # heal a stale flag
        raise HTTPException(status.HTTP_409_CONFLICT, f"Camera {camera_id} is not running")
    return vision.status(camera_id)


@router.get("/{camera_id}/status", response_model=CameraStatus)
def camera_status(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    _get_or_404(CameraRepository(db), camera_id)
    return vision.status(camera_id)


# --- live view -----------------------------------------------------------------------------

@router.get("/{camera_id}/overlay", response_model=OverlaySettings)
def get_overlay(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    _get_or_404(CameraRepository(db), camera_id)
    return vision.get_overlay(camera_id)


@router.patch("/{camera_id}/overlay", response_model=OverlaySettings)
def update_overlay(camera_id: int, body: OverlayUpdate, db: Session = Depends(get_db),
                   vision: VisionService = Depends(get_vision)):
    """Turn overlays on/off (boxes, ids, confidence, zones, events, trails, stats, fps). Applies live."""
    _get_or_404(CameraRepository(db), camera_id)
    return vision.set_overlay(camera_id, body.model_dump(exclude_none=True))


@router.get("/{camera_id}/live", response_model=LiveInfo)
def live_info(camera_id: int, db: Session = Depends(get_db), vision: VisionService = Depends(get_vision)):
    """Details of the latest streamed frame: tracked people (id, confidence, alert) and running totals."""
    _get_or_404(CameraRepository(db), camera_id)
    running = vision.is_running(camera_id)
    if running:
        vision.touch_view(camera_id)
    frame = vision.latest_frame(camera_id) if running else None
    return LiveInfo(running=running, seq=frame[0] if frame else 0, meta=frame[2] if frame else None)


@router.get("/{camera_id}/stream")
async def stream_camera(camera_id: int, request: Request, db: Session = Depends(get_db),
                        vision: VisionService = Depends(get_vision)):
    """MJPEG live view (use as <img src>). Frames are rendered by the worker only while this is open."""
    _get_or_404(CameraRepository(db), camera_id)
    db.close()  # don't hold a DB connection for the lifetime of the stream
    if not vision.is_running(camera_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Camera {camera_id} is not running")

    async def frames():
        last_seq = 0
        while vision.is_running(camera_id) and not await request.is_disconnected():
            vision.touch_view(camera_id)
            frame = vision.latest_frame(camera_id)
            if frame and frame[0] != last_seq:
                last_seq, jpg = frame[0], frame[1]
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            else:
                await asyncio.sleep(0.03)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})
