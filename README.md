# AegisVision

Real-time video analytics. Current state (Weeks 1–2): a video pipeline that reads frames from any source, runs YOLO object detection on every frame, and displays boxes with live performance numbers. No tracking or intrusion logic yet.

## Pipeline

```
 MP4 ─────┐
 Webcam ──┼──► VideoSource.read() ─► resize ─► FrameProcessor ─► YOLODetector ─► draw boxes ─► overlay ─► cv2.imshow
 RTSP ────┘
```

The detector never knows where a frame came from: every source implements the same `VideoSource` interface.

## Project layout

```
backend/
├── requirements.txt
├── assets/videos/surveillance_clip.mp4
└── app/
    ├── video/
    │   ├── source.py           VideoSource ABC: read(), release()
    │   ├── mp4_source.py       MP4Source(path)
    │   ├── webcam_source.py    WebcamSource(camera_id=0)
    │   ├── rtsp_source.py      RTSPSource(url) – IP cameras / network streams
    │   ├── frame_processor.py  FrameProcessor.process(frame) – hook for future preprocessing (currently identity)
    │   ├── demo.py             Live demo (the main entry point)
    │   └── benchmark.py        Headless FPS benchmark of several YOLO configs
    └── detection/
        ├── detector.py         Detector ABC: detect(frame)
        ├── yolo_detector.py    YOLODetector (Ultralytics YOLO)
        ├── visualizer.py       draw_detections(frame, result) -> count
        └── test_yolo.py        Run YOLO on a single image
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
- **Security default is person-only**, set in `add_common_args` in `demo.py`.
- **Swappable detector.** Anything implementing `Detector.detect(frame)` can replace `YOLODetector`. Note that `draw_detections` currently expects an Ultralytics `Results` object; generalise it when a second backend is added.
- **Swappable sources.** Add a new source by subclassing `VideoSource` and exposing an `fps` attribute (`<= 0` falls back to 30).

## Testing the sources

```bash
python -m app.video.demo --path assets/videos/surveillance_clip.mp4   # Test A (MP4)
python -m app.video.demo --webcam                                     # Test B (webcam)
python -m app.detection.test_yolo path/to/image.jpg                   # single image
```

Verified so far: MP4 detection runs headlessly; the webcam opens and returns frames. `store.mp4` is not in the repo – add your own file to run Test A with it. RTSP code is implemented but has not been tested against a real stream.

## Baseline performance

Measure with:

```bash
python -m app.video.benchmark --frames 100
```

It loads the same frames once, then times resize-free detection + drawing per configuration (5 warmup frames discarded).

**Machine:** AMD Ryzen 5 5500U (6 cores / 12 threads), CPU only, no GPU. **Model:** `yolo11n.pt`. **Clip:** `surveillance_clip.mp4`, 768×432, 60 frames, confidence 0.25.

| Configuration | Processing FPS | Avg detections/frame |
|---|---|---|
| All classes, imgsz 640 (baseline) | 17.5 | 6.0 |
| Person-only, imgsz 640 | 16.9 | 3.9 |
| All classes, imgsz 480 | 29.6 | 3.0 |
| All classes, imgsz 320 | 42.6 | 4.0 |
| Person-only, imgsz 320 | 47.9 | 3.9 |

Takeaways:

- Class filtering barely changes speed (≈ the same at 640; the noise is within run-to-run variation). The cost is in the network forward pass, not in post-processing. Its value is cleaner output, not speed.
- **Input size is the real lever**: 640 → 320 gives ~2.5× throughput on CPU.
- Smaller inputs can miss small or distant people (the "All classes" detection count drops at 480), so check accuracy on your footage before picking a size.
- Numbers vary between runs and with CPU load/boost; rerun on the target machine before quoting them.

## Next steps

Tracking, intrusion zones, other optimisations (ONNX/OpenVINO export, frame skipping), GPU comparison, and a real RTSP test.
