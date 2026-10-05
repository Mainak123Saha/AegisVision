from ultralytics import YOLO

from .detector import Detector


class YOLODetector(Detector):
    """YOLO wrapper.

    confidence: minimum score to keep a detection.
    classes:    None = all classes, otherwise a list of class names (e.g. ["person"]).
                Filtering happens inside YOLO, so no other class is lost permanently:
                pass classes=None (or --classes all) to get everything again.
    imgsz:      inference input size (smaller = faster, less accurate).
    """

    def __init__(self, model_path="yolo11n.pt", confidence=0.25, classes=None, imgsz=640):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.imgsz = imgsz
        self.class_ids = self._resolve_classes(classes)

    def _resolve_classes(self, classes):
        if not classes:
            return None

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

    def detect(self, frame):
        results = self.model(
            frame,
            conf=self.confidence,
            classes=self.class_ids,
            imgsz=self.imgsz,
            verbose=False,
        )
        return results[0]
