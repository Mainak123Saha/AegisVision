import sys

import cv2

from .yolo_detector import YOLODetector
from .visualizer import draw_detections


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/test.jpg"

    image = cv2.imread(path)
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
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
