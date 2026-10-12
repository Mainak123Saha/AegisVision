"""API tests against a throwaway PostgreSQL database (default: aegisvision_test).

Run from backend/:  .venv/bin/pytest tests
"""
import os

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://aegis:aegis_dev_password@localhost:5432/aegisvision_test",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.analytics.events import Event, EventType, Severity  # noqa: E402
from app.database import db as dbmod  # noqa: E402
from app.database.db import Base  # noqa: E402
from app.database.repository import EventRepository  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    engine = dbmod.get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def _cam(client, name="c1", **kw):
    body = {"name": name, "source_type": "mp4", "source_uri": "assets/videos/surveillance_clip.mp4", **kw}
    return client.post("/api/cameras", json=body)


def _save(*events):
    with dbmod.SessionLocal() as db:
        EventRepository(db).add_many([e.to_dict() for e in events])


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "up"}


def test_camera_crud(client):
    r = _cam(client, location="door")
    assert r.status_code == 201
    cid = r.json()["id"]
    assert _cam(client).status_code == 409                       # duplicate name
    assert client.post("/api/cameras", json={"name": "w", "source_type": "webcam",
                                             "source_uri": "x"}).status_code == 422
    assert [c["id"] for c in client.get("/api/cameras").json()] == [cid]
    assert client.patch(f"/api/cameras/{cid}", json={"location": "gate"}).json()["location"] == "gate"
    assert client.get("/api/cameras/999").status_code == 404
    assert client.delete(f"/api/cameras/{cid}").status_code == 204
    assert client.get(f"/api/cameras/{cid}").status_code == 404


def test_start_stop_errors(client):
    cid = _cam(client, name="missing", source_uri="assets/videos/nope.mp4").json()["id"]
    assert client.post(f"/api/cameras/{cid}/start").status_code == 422   # file missing
    assert client.post(f"/api/cameras/{cid}/stop").status_code == 409    # not running
    assert client.post("/api/cameras/999/start").status_code == 404


def test_events_filters_pagination_and_summary(client):
    cid = _cam(client).json()["id"]
    other = _cam(client, name="c2").json()["id"]
    cam = str(cid)
    _save(
        Event(EventType.INTRUSION_DETECTED, 1, 1.0, cam, severity=Severity.CRITICAL),
        Event(EventType.INTRUSION_DETECTED, 2, 2.0, cam, severity=Severity.CRITICAL),
        Event(EventType.LOITERING, 3, 3.0, cam, {"duration": 6}, Severity.WARNING),
        Event(EventType.LINE_CROSSED, 4, 4.0, str(other), {"direction": "IN"}),
    )
    page = client.get("/api/events", params={"limit": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert len(client.get("/api/events", params={"limit": 2, "offset": 2}).json()["items"]) == 2
    assert client.get("/api/events", params={"event_type": "LOITERING"}).json()["items"][0]["metadata"] == {"duration": 6}
    assert client.get("/api/events", params={"severity": "CRITICAL"}).json()["total"] == 2
    assert client.get("/api/events", params={"camera_id": other}).json()["total"] == 1
    assert client.get("/api/events", params={"limit": 0}).status_code == 422

    s = client.get("/api/analytics/summary").json()
    assert (s["total_events"], s["intrusion_events"], s["loitering_events"], s["line_crossed_events"]) == (4, 2, 1, 1)
    assert client.get("/api/analytics/summary", params={"camera_id": cid}).json()["total_events"] == 3
    assert client.get("/api/analytics/summary", params={"start": "2999-01-01T00:00:00Z"}).status_code == 422
    assert client.get("/api/analytics/summary", params={"start": "2000-01-01T00:00:00Z", "end": "2000-01-02T00:00:00Z"}).json()["total_events"] == 0


def test_duplicate_event_ids_are_ignored(client):
    e = Event(EventType.LOITERING, 1, 1.0, "none")
    _save(e, e)
    assert client.get("/api/events").json()["total"] == 1


def test_database_failure_returns_503(client):
    def broken():
        class Broken:
            def __getattr__(self, name):
                raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield Broken()

    app.dependency_overrides[dbmod.get_db] = broken
    try:
        r = client.get("/api/events")
        assert r.status_code == 503 and r.json() == {"detail": "Database unavailable"}
    finally:
        app.dependency_overrides.clear()
