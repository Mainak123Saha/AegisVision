# AegisVision

Real-time video analytics. Current state (Weeks 1–5): a video pipeline that reads frames from any source, runs YOLO detection, tracks objects with ByteTrack (persistent IDs + lifecycle), and turns tracked behaviour into events (line crossing, restricted-zone intrusion, loitering) shown live on the video. Week 5 adds a FastAPI + PostgreSQL backend that stores events and controls camera processing.

## Pipeline

```
 MP4 ─────┐
 Webcam ──┼──► VideoSource ─► resize ─► FrameProcessor ─► YOLODetector ─► ByteTracker ─► AnalyticsEngine ─► draw ─► overlay ─► cv2.imshow
 RTSP ────┘                                                (Detections)    (Tracks)       (Events)
                                                                           --track        --zones
```

The detector never knows where a frame came from: every source implements the same `VideoSource` interface. Tracking and analytics are optional stages.

## Project layout

```
backend/
├── requirements.txt
├── .env.example                Template for DATABASE_URL etc. (copy to .env, which is gitignored)
├── alembic.ini, alembic/       Database migrations
├── tests/test_api.py           API tests (PostgreSQL)
├── config/zones.json           Sample lines/zones for analytics
├── assets/videos/              Test videos
└── app/
    ├── main.py                 FastAPI app, error handlers, /health
    ├── config.py               Config dataclass + CLI arguments + backend Settings (env vars)
    ├── api/                    cameras.py, events.py, analytics.py routers (+ deps.py)
    ├── database/               db.py (engine/session), models.py (Camera, Event), repository.py
    ├── schemas/                Pydantic models: camera.py, event.py
    ├── services/
    │   ├── vision_service.py   Starts/stops camera worker processes, persists their events
    │   └── vision_worker.py    The per-camera pipeline (runs in its own process)
    ├── video/
    │   ├── source.py           VideoSource ABC: read(), release()
    │   ├── mp4_source.py       MP4Source(path)
    │   ├── webcam_source.py    WebcamSource(camera_id=0)
    │   ├── rtsp_source.py      RTSPSource(url) – IP cameras / network streams
    │   ├── frame_processor.py  FrameProcessor.process(frame) – hook for future preprocessing (currently identity)
    │   ├── demo.py             Live demo (the main entry point)
    │   └── benchmark.py        Headless FPS benchmark of several configs
    ├── detection/
    │   ├── models.py           Detection dataclass (class, confidence, box)
    │   ├── detector.py         Detector ABC: detect(frame) -> list[Detection]
    │   ├── yolo_detector.py    YOLODetector (Ultralytics YOLO)
    │   ├── visualizer.py       draw_box / draw_detections
    │   └── test_yolo.py        Run YOLO on a single image
    ├── tracking/
    │   ├── tracker.py          Track, TrackState, Tracker ABC
    │   ├── bytetrack.py        ByteTracker (adapter over Ultralytics BYTETracker)
    │   ├── visualizer.py       draw_tracks ("Person #7")
    │   └── test_tracking.py    Synthetic lifecycle test + video ID statistics
    └── analytics/
        ├── zones.py            Zone (polygon) and Line geometry
        ├── line_crossing.py    LINE_CROSSED events with IN/OUT direction
        ├── intrusion.py        INTRUSION_DETECTED events
        ├── loitering.py        LOITERING events
        ├── events.py           Event model, EventType, Severity, rule interface
        ├── engine.py           AnalyticsEngine + JSON config loader
        ├── visualizer.py       Zones, lines, event banners, statistics
        └── test_analytics.py   Independent tests for every rule
```

## Setup

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python -c "from ultralytics import YOLO; print('YOLO OK')"
```

The first run downloads `yolo11n.pt` (~5 MB) into the current directory. **Run all commands from `backend/`**, since default paths are relative to it.

## Running the demo

```bash
python -m app.video.demo                                   # default MP4, person-only
python -m app.video.demo --path assets/videos/store.mp4    # another file
python -m app.video.demo --webcam                          # webcam 0
python -m app.video.demo --rtsp rtsp://user:pass@host/stream
python -m app.video.demo --confidence 0.5                  # stricter threshold
python -m app.video.demo --classes all                     # every COCO class
python -m app.video.demo --classes person,car,dog          # selected classes
python -m app.video.demo --imgsz 320 --width 640           # faster, less accurate
python -m app.video.demo --no-detect                       # plain video player
```

| Option | Default | Meaning |
|---|---|---|
| `--path` | `assets/videos/surveillance_clip.mp4` | MP4 file |
| `--webcam` | off | Use webcam instead of file |
| `--rtsp URL` | – | Use a network stream (takes priority over `--webcam`/`--path`) |
| `--width` | 960 | Frames wider than this are downscaled (aspect ratio kept) before detection |
| `--model` | `yolo11n.pt` | YOLO weights; swap for `yolo11s.pt` etc. |
| `--confidence` | 0.25 | Detections below this score are dropped |
| `--classes` | `person` | Comma-separated class names, or `all` |
| `--imgsz` | 640 | YOLO inference resolution |
| `--no-detect` | off | Disable YOLO |

Keys: **Space** pause/resume, **q** quit.

### On-screen overlay

- **FPS** – the source video's native FPS (playback delay is derived from it).
- **Processing FPS** – real throughput of resize + processor + YOLO + box drawing (smoothed). Excludes display and the playback wait, so it reflects what the hardware can sustain.
- **Detections** – number of boxes in the current frame.

## Design notes

- **Class filtering is configuration, not deletion.** The model still knows all 80 COCO classes. `YOLODetector(classes=["person"])` converts names to IDs and YOLO filters inside inference; `classes=None` (CLI: `--classes all`) restores everything. Future retail/traffic/safety use cases only change this setting. Unknown names raise an error listing valid classes.
- **Security default is person-only**, set in `add_common_args` in `app/config.py`.
- **Swappable detector.** Anything implementing `Detector.detect(frame) -> list[Detection]` can replace `YOLODetector`. `Detection` (`detection/models.py`) is a plain dataclass, so nothing downstream depends on Ultralytics.
- **Swappable sources.** Add a new source by subclassing `VideoSource` and exposing an `fps` attribute (`<= 0` falls back to 30).
- **Central config.** All settings live in the `Config` dataclass (`app/config.py`); the CLI just fills it in. `demo.py` and `benchmark.py` share it.

## Tracking (Week 3)

```
YOLODetector ──► list[Detection] ──► ByteTracker ──► list[Track] ──► draw / (future) analytics
```

`detection/` knows nothing about tracking, and `tracking/` only consumes `Detection` objects. ByteTrack itself is Ultralytics' `BYTETracker`; `tracking/bytetrack.py` is a thin adapter that converts types and adds an explicit lifecycle.

```bash
python -m app.video.demo --path assets/videos/surveillance_clip.mp4 --track
python -m app.video.demo --track --show-lost          # also draw LOST tracks in grey
python -m app.video.demo --webcam --track --track-buffer 60
```

**Data model**

```
Detection: class_id, class_name, confidence, x1, y1, x2, y2
Track:     track_id, class_id, class_name, confidence, x1, y1, x2, y2, state, age, frames_lost
```

**Lifecycle (`TrackState`)**

| State | Meaning |
|---|---|
| `NEW` | First frame the track is confirmed |
| `ACTIVE` | Matched to a detection on following frames |
| `LOST` | Temporarily unmatched; kept for `--track-buffer` frames in case the person reappears (box = predicted position) |
| `REMOVED` | Lost for too long; the ID is retired. Reported exactly once |

`tracker.update(detections, frame)` returns every relevant track for the frame with its state, so later rules (zones, line crossing) can tell whether "Person #7" is still the same person.

**Overlay with `--track`:** FPS, Processing FPS, **Detections** (YOLO boxes this frame), **Active Tracks** (NEW + ACTIVE; not necessarily equal to detections) and **Lost Tracks**.

| Tracking option | Default | Meaning |
|---|---|---|
| `--track` | off | Enable ByteTrack |
| `--track-high-thresh` | 0.25 | Score for first-stage matching |
| `--track-low-thresh` | 0.1 | Score for second-stage recovery of occluded tracks |
| `--new-track-thresh` | 0.25 | Minimum score to start a new track (raise to suppress flicker/false IDs) |
| `--track-buffer` | 30 | Frames a LOST track survives (more = survives longer occlusions, more ID-switch risk) |
| `--match-thresh` | 0.8 | Box-association threshold |
| `--show-lost` | off | Draw LOST tracks |

> The detector's `--confidence` (default 0.25) filters boxes *before* the tracker. ByteTrack's low-score recovery stage (`--track-low-thresh`) only has an effect if you lower `--confidence` to around 0.1, at the cost of more false boxes.

## Analytics (Week 4)

```
Tracks ──┬─► LineCrossingDetector ─┐
         ├─► IntrusionDetector ────┼─► Event ─► AnalyticsEngine ─► overlay / events log / (later) API + DB
         └─► LoiteringDetector ────┘
```

YOLO is computer vision, ByteTrack is temporal tracking, and `analytics/` is the application logic that decides what tracked behaviour *means*. Rules only consume `Track` objects, never detections or pixels.

| Module | Purpose |
|---|---|
| `zones.py` | `Zone` (polygon, `contains(point)`), `Line` (directed segment, `side()`, `crosses()`), `anchor_point()` |
| `line_crossing.py` | `LineCrossingDetector` → `LINE_CROSSED` with `direction` `IN`/`OUT` |
| `intrusion.py` | `IntrusionDetector` → `INTRUSION_DETECTED` once per entry into a zone |
| `loitering.py` | `LoiteringDetector` → `LOITERING` once a track has stayed in a zone ≥ N seconds |
| `events.py` | `Event`, `EventType`, `Severity`, `AnalyticsRule` base class |
| `engine.py` | `AnalyticsEngine` (runs all rules, keeps history + statistics), `build_engine` / `load_engine` from JSON |
| `visualizer.py` | Zones, lines (with an IN arrow), event banners, statistics |

**Event model** – every rule returns the same structure (`Event.to_dict()` gives JSON ready for an API/DB):

```
Event: event_type, track_id, timestamp, camera_id, metadata, severity, event_id, created_at
```

e.g. `LINE_CROSSED, track_id=7, camera_id=store_cam_1, metadata={line_id, direction: "IN", ...}, severity=INFO`.
Severity: line crossing = INFO, loitering = WARNING, intrusion = CRITICAL.

**How each rule works**

- **Position:** a track is located by the *bottom-centre* of its box (the feet). Use `anchor="center"` in code for other cases.
- **Line crossing:** remembers each track's previous position and side of the line. An event fires when the move from the previous to the current position actually crosses the *finite* segment (walking around the end of a line does not count). For a line drawn left → right, moving top → bottom is `IN`, bottom → top is `OUT`; swap the two points to flip it (the arrow on screen shows the IN side). A 1 s per-track `cooldown` prevents jitter on the line from firing repeatedly.
- **Intrusion:** fires on outside → inside. Staying inside does not re-fire. A track must be outside for `exit_grace` (1 s) before leaving counts, so boundary jitter does not create new intrusions.
- **Loitering:** stores `entered_at` per track and zone; when `now - entered_at ≥ loiter_seconds` it fires once for that visit. The same grace period protects the timer against boundary jitter.
- **Track lifecycle:** `LOST` tracks keep their state (a person briefly hidden does not restart timers or re-fire events); `REMOVED` tracks are forgotten.
- **Time:** rules use *stream time*: `frame_index / fps` for files (correct even when processing is slower than real time) and elapsed wall-clock time for webcam/RTSP.

**Configuration** (`config/zones.json`, coordinates are normalized 0–1 so they work at any resolution; use `"coords": "pixel"` for pixels):

```json
{
  "camera_id": "store_cam_1",
  "coords": "normalized",
  "lines": [{"id": "entrance_aisle", "name": "Entrance", "points": [[0.06, 0.42], [0.42, 0.42]], "cooldown": 1.0}],
  "zones": [
    {"id": "staff_area", "name": "Staff area", "points": [[0.55,0.12],[0.95,0.12],[0.95,0.40],[0.58,0.52]], "rules": ["intrusion"]},
    {"id": "waiting_area", "name": "Waiting area", "points": [[0.18,0.5],[0.5,0.5],[0.55,0.95],[0.08,0.95]], "rules": ["loitering"], "loiter_seconds": 5}
  ]
}
```

A zone can have `"rules": ["intrusion", "loitering"]` at the same time. **The sample coordinates were drawn by eye for the current default clip; redraw them for your own camera.**

```bash
python -m app.video.demo --track --zones config/zones.json                       # live window
python -m app.video.demo --track --zones config/zones.json --events-log events.jsonl   # also log events (JSON lines)
python -m app.video.demo --track --zones config/zones.json --headless --output annotated.mp4 --max-frames 900
```

On screen: zones (red = intrusion, orange = loitering), the line with its IN arrow, boxes of people currently in an alert state drawn in red with `!`, event banners at the bottom-left (`! LINE CROSSING / Person #7 / Direction: IN`), and running totals at the top-right. Events are also printed to the console, and `--zones` requires `--track`.

| New option | Meaning |
|---|---|
| `--zones FILE` | Enable analytics with this JSON config (requires `--track`) |
| `--events-log FILE` | Append every event as one JSON line |
| `--output FILE` | Save the annotated video |
| `--headless` | No window, run as fast as possible (for batch runs/tests) |
| `--max-frames N` | Stop after N frames |

**Tests** – each module is tested independently with synthetic tracks (no video, no YOLO):

```bash
python -m app.analytics.test_analytics
```

It checks zones (4.1), line crossing incl. direction, two people with different IDs, walking around a line end and jitter (4.2), intrusion incl. re-entry and edge jitter (4.3), loitering incl. quick pass-through and boundary jitter (4.4), and the event model plus engine statistics (4.5).

> **Known limitation:** analytics are only as good as the tracker. On the crowded sample clip ByteTrack still fragments some identities, so one person can appear as several IDs and produce several events. Tuning `--confidence`, `--new-track-thresh` and `--track-buffer` improves this.

## Backend API (Week 5)

FastAPI + PostgreSQL turn the pipeline into an application that stores and serves events. **The vision engine is kept separate from FastAPI**: the API never runs the video loop inside a request handler.

```
Camera (MP4/webcam/RTSP) → worker process: OpenCV → YOLO → ByteTrack → AnalyticsEngine
                                   │  event dicts over a multiprocessing queue
                                   ▼
                     API process (writer thread) → PostgreSQL ← FastAPI REST API
```

`POST /api/cameras/{id}/start` spawns a worker process (`services/vision_worker.py`); `stop` signals it, waits, then terminates it if it hangs. A worker crash cannot take the API down. The API process saves events in batches, retries on database errors (5 attempts with backoff), and ignores duplicate `event_id`s.

**Run**

```bash
cd backend
cp .env.example .env              # set DATABASE_URL, e.g. postgresql+psycopg://user:pass@localhost:5432/aegisvision
alembic upgrade head              # create the tables
uvicorn app.main:app --reload     # docs at http://localhost:8000/docs
pytest                            # uses TEST_DATABASE_URL (default: aegisvision_test)
```

Credentials come from environment variables / `backend/.env` (never committed). Optional: `ZONES_PATH`, `YOLO_MODEL`, `CORS_ORIGINS`, `DB_ECHO`.

**Database** (PostgreSQL, SQLAlchemy 2, Alembic)

| Table | Fields |
|---|---|
| `cameras` | id, name (unique), source_type (`mp4`/`webcam`/`rtsp`), source_uri, location, is_active, created_at |
| `events` | event_id (PK), event_type, track_id, camera_id (FK, `SET NULL` on delete), timestamp (stream seconds), severity, metadata (JSONB), created_at |

`events` mirrors the analytics `Event` dataclass, so the rules are unchanged. `source_uri` was added to `cameras` (file path, device index or stream URL) because the API needs it to start processing. The analytics `camera_id` string is replaced with the integer camera id by the worker. Video frames are never stored.

**Endpoints**

| Endpoint | Purpose |
|---|---|
| `GET /health` | Always 200 while FastAPI is up; reports `database: up/down` |
| `GET /api/events` | Filters `event_type`, `severity`, `camera_id`, `start`, `end`; pagination `limit` (1–500), `offset`; returns `{items, total, limit, offset}` |
| `GET /api/events/{event_id}` | One event |
| `GET/POST /api/cameras` | List / create |
| `GET/PATCH/DELETE /api/cameras/{id}` | Read / update (source locked while running) / delete (stops it first) |
| `POST /api/cameras/{id}/start`, `/stop` | Start / stop processing (409 if already running / not running) |
| `GET /api/cameras/{id}/status` | running, pid, started_at, events_persisted, last_error |
| `GET /api/analytics/summary` | `total_events`, `intrusion_events`, `loitering_events`, `line_crossed_events`, `by_type`, `by_severity`, `by_camera` for `start`/`end` (default: last 24 h) and optional `camera_id` |

**Error handling:** 404 unknown camera/event, 409 duplicate name or wrong start/stop state, 422 invalid input or a missing video file, 503 when the database is unreachable, and 500 with a generic message for anything else (details go to the log, not the client).

**Verified:** `/health` responds with no camera running; a real clip run produced `INTRUSION_DETECTED` and `LINE_CROSSED` rows that were still returned after restarting the server; start/stop (including double start/stop) behaves correctly and leaves no stray processes; summary counts and filters match the stored data (6 automated tests in `tests/test_api.py`).

**Limitations:** all cameras use the same `config/zones.json`; cameras do not resume after an API restart (all are marked inactive at startup); there is no authentication yet; RTSP and webcam start paths were not exercised through the API.

## Testing the sources

```bash
python -m app.video.demo --path assets/videos/surveillance_clip.mp4   # Test A (MP4)
python -m app.video.demo --webcam                                     # Test B (webcam)
python -m app.detection.test_yolo path/to/image.jpg                   # single image
python -m app.tracking.test_tracking                                  # synthetic lifecycle test
python -m app.tracking.test_tracking --video assets/videos/surveillance_clip.mp4 --frames 300
```

Verified so far: MP4 detection runs headlessly; the webcam opens and returns frames. `store.mp4` is not in the repo – add your own file to run Test A with it. RTSP code is implemented but has not been tested against a real stream.

**Tracking results.** The synthetic test (box moves, disappears 5 frames, reappears, then vanishes) confirms: one ID throughout, `NEW` once, `LOST` during the gap, `REMOVED` once after the buffer expires. On the real clip (300 frames, person-only, default settings) the tracker produced 24 IDs; a few long-lived tracks (e.g. 296, 158, 131 frames) are stable, but several IDs live only 1–3 frames, i.e. flickering detections or ID fragmentation in the crowded scenes. Tune `--new-track-thresh`, `--confidence` and `--track-buffer` on your own footage; crossing/occlusion behaviour should be checked visually with the demo window.

## Baseline performance

Measure with:

```bash
python -m app.video.benchmark --frames 100
```

It loads the same frames once, then times resize-free detection + drawing per configuration (5 warmup frames discarded).

`yolo11n.pt`. **Clip:** `surveillance_clip.mp4`, 768×432, 60 frames, confidence 0.25.

| Configuration | Processing FPS | Avg detections/frame |
|---|---|---|
| All classes, imgsz 640 (baseline) | 17.2 | 6.0 |
| Person-only, imgsz 640 | 17.0 | 3.9 |
| All classes, imgsz 480 | 29.6 | 3.0 |
| All classes, imgsz 320 | 42.2 | 4.0 |
| Person-only, imgsz 320 | 45.3 | 3.9 |
| Person-only, imgsz 640 + ByteTrack | 16.5 | 3.9 |
| Person-only, imgsz 320 + ByteTrack | 42.5 | 3.9 |

Takeaways:

- Class filtering barely changes speed (≈ the same at 640; the noise is within run-to-run variation). The cost is in the network forward pass, not in post-processing. Its value is cleaner output, not speed.
- **Input size is the real lever**: 640 → 320 gives ~2.5× throughput on CPU.
- **ByteTrack is cheap**: about 0.5 ms/frame (≈3–6% FPS) on top of detection. Tracking will not be the bottleneck; YOLO is.
- Smaller inputs can miss small or distant people (the "All classes" detection count drops at 480), so check accuracy on your footage before picking a size.
- Numbers vary between runs and with CPU load/boost; rerun on the target machine before quoting them.

## Next steps

Week 6: React + TypeScript dashboard (camera controls, events, analytics) on top of this API. Later: per-camera zone configuration, authentication, tracker tuning on your own footage, other optimisations (ONNX/OpenVINO export, frame skipping), GPU comparison, and a real RTSP test.
