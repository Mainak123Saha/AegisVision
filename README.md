# AegisVision

Real-time video analytics. Current state (Weeks 1–3): a video pipeline that reads frames from any source, runs YOLO object detection on every frame, optionally tracks objects with ByteTrack (persistent IDs + lifecycle), and displays boxes with live performance numbers. No intrusion/analytics rules yet.

## Pipeline

```
 MP4 ─────┐
 Webcam ──┼──► VideoSource.read() ─► resize ─► FrameProcessor ─► YOLODetector ─► [ByteTracker] ─► draw ─► overlay ─► cv2.imshow
 RTSP ────┘                                                        (Detections)    (Tracks, --track)
```

The detector never knows where a frame came from: every source implements the same `VideoSource` interface.

## Project layout

```
backend/
├── requirements.txt
├── assets/videos/surveillance_clip.mp4
└── app/
    ├── config.py               Config dataclass + CLI argument definitions
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
    └── tracking/
        ├── tracker.py          Track, TrackState, Tracker ABC
        ├── bytetrack.py        ByteTracker (adapter over Ultralytics BYTETracker)
        ├── visualizer.py       draw_tracks ("Person #7")
        └── test_tracking.py    Synthetic lifecycle test + video ID statistics
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

Week 4 analytics (line crossing, restricted zones, loitering) built on `Track` objects, tracker tuning on your own footage, other optimisations (ONNX/OpenVINO export, frame skipping), GPU comparison, and a real RTSP test.
