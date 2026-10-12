"""FastAPI entry point (run from backend/: uvicorn app.main:app --reload).

The API manages and exposes the system. Video processing never runs inside a
request handler - cameras are started as separate worker processes by
`VisionService`, so the API starts and answers /health even with no cameras
running (and even if PostgreSQL is down).
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from .api import analytics, cameras, events
from .config import load_settings
from .database import db as dbmod
from .services.vision_service import VisionService

log = logging.getLogger("aegis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.vision = VisionService(settings)
    app.state.vision.startup()
    try:
        yield
    finally:
        app.state.vision.shutdown()


app = FastAPI(title="AegisVision", lifespan=lifespan)

try:
    _origins = load_settings().cors_origins
except RuntimeError:
    _origins = []
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(cameras.router)
app.include_router(events.router)
app.include_router(analytics.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    """Database failures become a clean 503 instead of a stack trace."""
    log.error("database error on %s %s: %s", request.method, request.url.path, exc)
    unavailable = isinstance(exc, DBAPIError) and exc.connection_invalidated or "OperationalError" in type(exc).__name__
    return JSONResponse(
        status_code=503 if unavailable else 500,
        content={"detail": "Database unavailable" if unavailable else "Database error"},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
def root():
    """Basic liveness message."""
    return {"message": "AegisVision API is running"}


@app.get("/health")
def health():
    """Liveness probe. Always 200 if FastAPI is up; reports DB reachability separately."""
    return {"status": "ok", "database": "up" if dbmod.check_connection() else "down"}