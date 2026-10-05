"""Manual check: run YOLO on a single image.

Usage (from backend/):  python -m app.detection.test_yolo [image_path]
Prints each detection, then shows the image with boxes until a key is pressed.
"""
import sys

import cv2

from .yolo_detector import YOLODetector
from .visualizer import draw_detections


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/test.jpg"

    image = cv2.imread(path)
    # imread returns None instead of raising when the file is missing/unreadable.
    if image is None:
        raise SystemExit(f"Could not read image: {path}")

    detector = YOLODetector()
    result = detector.detect(image)

    # Detection 1: raw detections
    for box in result.boxes:
        print(
            result.names[int(box.cls[0])],
            f"confidence={float(box.conf[0]):.2f}",
            f"box={tuple(int(v) for v in box.xyxy[0].tolist())}",
        )

    # Detection 2: display the boxes
    draw_detections(image, result)
    cv2.imshow("YOLO test", image)
    cv2.waitKey(0)  # wait for any key
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
