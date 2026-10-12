from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.db import get_db
from ..database.models import Camera
from ..database.repository import CameraRepository
from ..schemas.camera import CameraCreate, CameraOut, CameraStatus, CameraUpdate, _check_source
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
