from typing import List

from ultralytics import YOLO

from .detector import Detector
from .models import Detection


class YOLODetector(Detector):
    """YOLO wrapper.

    confidence: minimum score to keep a detection.
    classes:    None = all classes, otherwise a list of class names (e.g. ["person"]).
                Filtering happens inside YOLO, so no other class is lost permanently:
                pass classes=None (or --classes all) to get everything again.
    imgsz:      inference input size (smaller = faster, less accurate).
    """

    def __init__(self, model_path="yolo11n.pt", confidence=0.25, classes=None, imgsz=640):
        # Weights are downloaded automatically on first use if not found locally.
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.imgsz = imgsz
        self.class_ids = self._resolve_classes(classes)

    def _resolve_classes(self, classes):
        """Convert class names to the numeric IDs YOLO expects; None means 'no filter'."""
        if not classes:
            return None

        # model.names maps id -> name (e.g. 0 -> 'person'); invert it, case-insensitively.
        name_to_id = {name.lower(): i for i, name in self.model.names.items()}
        ids = []
        for name in classes:
            key = name.strip().lower()
            if key not in name_to_id:
                raise ValueError(
                    f"Unknown class '{name}'. Available: {', '.join(sorted(name_to_id))}"
                )
            ids.append(name_to_id[key])
        return ids

    def detect(self, frame) -> List[Detection]:
        """Run YOLO on `frame` and return its detections as `Detection` objects."""
        results = self.model(
            frame,
            conf=self.confidence,
            classes=self.class_ids,
            imgsz=self.imgsz,
            verbose=False,  # silence Ultralytics' per-frame console output
        )
        # One image in -> one Results object out.
        result = results[0]
        names = result.names  # id -> class name

        detections = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=names[class_id],
                    confidence=float(box.conf[0]),
                    x1=x1, y1=y1, x2=x2, y2=y2,
                )
            )
        return detections
