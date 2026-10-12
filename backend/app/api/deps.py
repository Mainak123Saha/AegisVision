from fastapi import Request

from ..services.vision_service import VisionService


def get_vision(request: Request) -> VisionService:
    return request.app.state.vision
