<div align="center">

# 🛡️ AegisVision

**Real-Time Multi-Camera Video Analytics, Object Tracking & Intrusion Detection Platform**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![YOLO11](https://img.shields.io/badge/YOLO11-Ultralytics-00FFFF?logo=yolo&logoColor=black)](https://github.com/ultralytics/ultralytics)
[![OpenCV](https://img.shields.io/badge/OpenCV-5.x-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy%202-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

[Features](#-key-features) • [Architecture](#-system-architecture) • [Quickstart](#-getting-started) • [CLI Usage](#-standalone-cli-pipeline) • [API Reference](#-api-reference) • [Benchmarks](#-performance--benchmarks)

</div>

---

## 📖 Overview

**AegisVision** is an end-to-end computer vision and real-time video surveillance analytics platform. It ingests video streams from local files (`MP4`), USB webcams, or network IP cameras (`RTSP`), performs real-time object detection with **YOLO11**, maintains persistent object identities across frames using **ByteTrack**, and evaluates spatial-temporal rules to detect **Line Crossings**, **Restricted-Zone Intrusions**, and **Loitering**.

Built for production-style reliability, AegisVision isolates each camera's computer vision pipeline in its own **dedicated OS worker process**, streaming structured security events to **PostgreSQL** via a **FastAPI** backend and serving a responsive **React + TypeScript** command center with live MJPEG video, real-time overlay toggles, and an interactive browser-based zone editor.

---

## ✨ Key Features

- **🔌 Source-Agnostic Video Pipeline**
  - Unified `VideoSource` interface supporting `MP4Source`, `WebcamSource`, and `RTSPSource`.
  - Downstream detection, tracking, and analytics stages remain completely decoupled from the video input mechanism.
- **🎯 Real-Time Detection & Stateful Tracking**
  - **Ultralytics YOLO11** inference with runtime class filtering and configurable resolution scaling.
  - **ByteTrack** multi-object tracking adapter with explicit track lifecycle states (`NEW` → `ACTIVE` → `LOST` → `REMOVED`), preserving identities across temporary occlusions.
- **📐 Spatial-Temporal Analytics Engine**
  - **Line Crossing (`INFO`)**: Directed finite-segment intersection detection (`IN` / `OUT` directional counting) with per-track cooldowns to prevent boundary bounce.
  - **Restricted-Zone Intrusion (`CRITICAL`)**: Polygon point-in-zone evaluation anchored to each subject's ground contact point (bottom-center of bounding box) with configurable exit grace periods.
  - **Loitering Detection (`WARNING`)**: Tracks per-zone dwell duration and triggers alerts when presence exceeds configurable time thresholds, surviving brief occlusion gaps.
- **⚙️ Fault-Isolated Multiprocess Backend**
  - Starting a camera spawns an isolated worker process (`vision_worker.py`). Worker crashes or heavy CV inference loads never block FastAPI request handling.
  - Asynchronous writer threads batch-persist events into PostgreSQL with exponential backoff retry and idempotent `event_id` deduplication.
- **🎥 Zero-Overhead Live View & Hot-Reloading Zone Editor**
  - **On-Demand MJPEG Streaming**: Worker processes only render overlays and JPEG-encode frames while a client browser is actively watching `/api/cameras/{id}/stream`.
  - **Live Overlay Controls**: Toggle bounding boxes, track IDs, confidence scores, polygon zones, event banners, motion trails, and FPS counters in real time without affecting underlying detection or database logging.
  - **Interactive Zone & Line Editor**: Draw, edit, and save custom intrusion/loitering polygons and counting lines directly over the live camera feed, hot-reloading rules into running worker processes with zero downtime.
- **📊 Real-Time Operations Dashboard**
  - Dark-mode React 19 + TypeScript interface powered by TanStack Query and Recharts.
  - Live camera health monitoring, paginated and filterable event feeds, and 24h / 7d / 30d analytics breakdowns (hourly trends, visitor flow, severity distribution).

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Sources["Video Sources"]
        MP4["MP4 File"]
        CAM["USB Webcam"]
        RTSP["RTSP Stream"]
    end

    subgraph Worker["Per-Camera Worker Process (vision_worker.py)"]
        VS["VideoSource"] --> FP["Resize & Preprocess"]
        FP --> YOLO["YOLO11 Detector"]
        YOLO --> BT["ByteTracker"]
        BT --> AE["AnalyticsEngine\n(Line / Intrusion / Loiter)"]
    end

    subgraph Backend["FastAPI Server (vision_service.py)"]
        Q["Multiprocessing\nEvent Queue"] --> WT["DB Writer Thread\n(Batched + Retry)"]
        SHM["On-Demand Frame Buffer\n(MJPEG + Live Meta)"]
        API["REST API & Stream Router"]
    end

    subgraph Storage["Persistence"]
        PG[("PostgreSQL\n(cameras, events)")]
    end

    subgraph Frontend["React + TypeScript Dashboard"]
        UI["Dashboard / Analytics / Events"]
        LIVE["Live View + Interactive Zone Editor"]
    end

    MP4 & CAM & RTSP --> VS
    AE -- "Event Dicts" --> Q
    AE -. "When Viewed" .-> SHM
    WT --> PG
    PG <--> API
    SHM --> API
    API <--> UI & LIVE
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Computer Vision & ML** | Python 3.10+, OpenCV (`opencv-python`), Ultralytics YOLO11, ByteTrack, PyTorch, NumPy |
| **Backend & API** | FastAPI, Uvicorn, Pydantic v2, Python `multiprocessing` |
| **Database & ORM** | PostgreSQL, SQLAlchemy 2.0, Alembic (migrations), `psycopg` (v3) |
| **Frontend Dashboard** | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack React Query, React Router v7, Recharts, Lucide Icons |
| **Testing & Tooling** | Pytest, HTTPX, Synthetic Track & Rule Test Suites, Headless FPS Benchmark |

---

## 📂 Project Structure

```text
AegisVision/
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI routers: cameras.py, events.py, analytics.py
│   │   ├── analytics/          # Geometry (Zone/Line), intrusion, loitering, line_crossing, engine
│   │   ├── database/           # SQLAlchemy models (Camera, Event), session management, repositories
│   │   ├── detection/          # Detector ABC, YOLODetector, Detection dataclass, visualizers
│   │   ├── schemas/            # Pydantic request/response schemas (Camera, Event, Overlay, Zones)
│   │   ├── services/           # VisionService (process manager) & vision_worker (per-camera loop)
│   │   ├── tracking/           # Tracker ABC, ByteTracker lifecycle adapter, track visualizers
│   │   ├── video/              # VideoSource ABC (MP4, Webcam, RTSP), CLI demo.py, benchmark.py
│   │   ├── config.py           # Unified CLI & environment configuration
│   │   └── main.py             # FastAPI application entrypoint, CORS, exception handlers, /health
│   ├── alembic/                # Database schema migrations
│   ├── assets/videos/          # Sample surveillance video clips
│   ├── config/                 # Default and per-camera zone/line JSON configurations
│   ├── tests/                  # Automated API and overlay integration tests (Pytest)
│   └── requirements.txt        # Python dependencies
└── frontend/
    └── src/
        ├── api/                # Typed REST API clients (cameras, events, analytics)
        ├── components/         # Reusable UI primitives, layout, charts, camera & event views
        ├── hooks/              # TanStack Query hooks with live polling
        ├── pages/              # Dashboard, Cameras, CameraLive (stream + zone editor), Events, Analytics
        └── types/              # TypeScript interfaces matching backend Pydantic schemas
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10 or higher
- **PostgreSQL** 14+ running locally or via Docker
- **Node.js** 18+ and `npm`

### 1. Backend & Database Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and set DATABASE_URL, e.g.:
# DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/aegisvision

# Run database migrations
alembic upgrade head

# Start the FastAPI server (Interactive Swagger docs at http://localhost:8000/docs)
uvicorn app.main:app --reload
```

> **Note:** On first execution, Ultralytics automatically downloads `yolo11n.pt` (~5 MB) if not already present.

### 2. Frontend Dashboard Setup

Open a second terminal:

```bash
cd frontend

# Install packages
npm install

# Start the Vite development server (http://localhost:5173)
npm run dev
```

To configure a custom backend URL, set `VITE_API_BASE_URL` in `frontend/.env` (defaults to `http://localhost:8000`).

---

## 💻 Standalone CLI Pipeline

You can run the computer vision, tracking, and analytics pipeline directly from the command line without PostgreSQL or the web stack. Run all CLI commands from the `backend/` directory:

```bash
cd backend

# Run detection + ByteTrack + zone analytics on the default surveillance clip
python -m app.video.demo --track --zones config/zones.json

# Run on a USB webcam with a custom track buffer
python -m app.video.demo --webcam --track --track-buffer 60

# Run on an RTSP network stream
python -m app.video.demo --rtsp rtsp://user:pass@192.168.1.50:554/stream --track --zones config/zones.json

# Headless batch processing: export annotated MP4 and JSONL event log
python -m app.video.demo \
  --path assets/videos/surveillance_clip.mp4 \
  --track \
  --zones config/zones.json \
  --events-log events.jsonl \
  --output annotated.mp4 \
  --headless
```

### Key CLI Flags

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--path FILE` | `assets/videos/surveillance_clip.mp4` | Path to input MP4 video file |
| `--webcam` | `off` | Capture live frames from default webcam (`0`) |
| `--rtsp URL` | — | Connect to an RTSP network camera stream |
| `--model FILE` | `yolo11n.pt` | Ultralytics YOLO weights (`yolo11n.pt`, `yolo11s.pt`, etc.) |
| `--confidence FLOAT` | `0.25` | Minimum detection confidence threshold |
| `--classes LIST` | `person` | Comma-separated COCO classes (e.g., `person,car`) or `all` |
| `--imgsz INT` | `640` | YOLO inference resolution (`320`, `480`, `640`) |
| `--track` | `off` | Enable ByteTrack multi-object tracking |
| `--zones FILE` | — | Enable spatial-temporal analytics using a JSON zones config |
| `--events-log FILE` | — | Append structured events to a `.jsonl` file |
| `--output FILE` | — | Save annotated video output to disk |
| `--headless` | `off` | Disable GUI window and process at maximum hardware speed |

---

## 🔌 API Reference

### Cameras & Live Processing

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/cameras` | List all registered cameras |
| `POST` | `/api/cameras` | Register a new camera (`mp4`, `webcam`, or `rtsp`) |
| `GET / PATCH / DELETE` | `/api/cameras/{id}` | Retrieve, update, or remove a camera |
| `POST` | `/api/cameras/{id}/start` | Spawn the camera's background vision worker process |
| `POST` | `/api/cameras/{id}/stop` | Gracefully stop and terminate the camera's worker process |
| `GET` | `/api/cameras/{id}/status` | Worker state (`running`, `pid`, `events_persisted`, `last_error`) |
| `GET` | `/api/cameras/{id}/stream` | Live `multipart/x-mixed-replace` MJPEG video stream |
| `GET` | `/api/cameras/{id}/live` | Current frame metadata: active tracks, alerts, FPS, counters |
| `GET / PATCH` | `/api/cameras/{id}/overlay` | Get or toggle live stream overlays (`boxes`, `ids`, `zones`, `trails`, etc.) |
| `GET / PUT` | `/api/cameras/{id}/zones` | Fetch or hot-reload custom intrusion/loitering zones and counting lines |

### Events, Analytics & Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/events` | Paginated events with filters (`event_type`, `severity`, `camera_id`, `start`, `end`) |
| `GET` | `/api/events/{event_id}` | Fetch details for a single event |
| `GET` | `/api/analytics/summary` | Aggregated counts by type, severity, camera, and `visitors_in` / `visitors_out` |
| `GET` | `/api/analytics/hourly` | Hourly time-series buckets by event type (up to 31 days) |
| `GET` | `/health` | Service liveness and PostgreSQL connectivity status |

---

## 🗺️ Zone & Rule Configuration

Zones and counting lines are defined using normalized coordinates (`0.0`–`1.0`) so configurations remain resolution-independent:

```json
{
  "camera_id": "store_cam_1",
  "coords": "normalized",
  "lines": [
    {
      "id": "entrance_aisle",
      "name": "Entrance",
      "points": [[0.06, 0.42], [0.42, 0.42]],
      "cooldown": 1.0
    }
  ],
  "zones": [
    {
      "id": "staff_area",
      "name": "Staff Area",
      "points": [[0.55, 0.12], [0.95, 0.12], [0.95, 0.40], [0.58, 0.52]],
      "rules": ["intrusion"]
    },
    {
      "id": "waiting_area",
      "name": "Waiting Area",
      "points": [[0.18, 0.50], [0.50, 0.50], [0.55, 0.95], [0.08, 0.95]],
      "rules": ["loitering"],
      "loiter_seconds": 5
    }
  ]
}
```

---

## 🧪 Testing & Benchmarks

### Running the Test Suites

```bash
cd backend

# 1. Synthetic unit tests for geometry, line crossing, intrusion, and loitering rules
python -m app.analytics.test_analytics

# 2. Synthetic & video-based ByteTrack lifecycle verification
python -m app.tracking.test_tracking

# 3. Backend REST API, database persistence & live overlay tests (requires PostgreSQL)
pytest
```

### Performance Benchmarks

Measure raw processing throughput across inference resolutions and pipeline stages:

```bash
cd backend
python -m app.video.benchmark --frames 100
```

**Baseline CPU Results (`yolo11n.pt`, `768×432` clip, confidence `0.25`):**

| Pipeline Configuration | Processing FPS | Avg Detections / Frame |
| :--- | :---: | :---: |
| All classes, `imgsz 640` (Baseline) | 17.2 FPS | 6.0 |
| Person-only, `imgsz 640` | 17.0 FPS | 3.9 |
| All classes, `imgsz 480` | 29.6 FPS | 3.0 |
| All classes, `imgsz 320` | 42.2 FPS | 4.0 |
| Person-only, `imgsz 320` | **45.3 FPS** | 3.9 |
| Person-only, `imgsz 640` + ByteTrack | 16.5 FPS | 3.9 |
| Person-only, `imgsz 320` + ByteTrack | **42.5 FPS** | 3.9 |

- **Inference resolution (`--imgsz`)** is the primary throughput lever on CPU (`640 → 320` yields ~2.5× speedup).
- **ByteTrack overhead is minimal** (~0.5 ms/frame, or ~3–6% FPS impact).
