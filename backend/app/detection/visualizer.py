import cv2


def draw_detections(frame, result):
    """Draw boxes with 'class conf' labels onto frame (in place). Returns detection count."""
    names = result.names
    boxes = result.boxes

    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf[0])
        label = f"{names[int(box.cls[0])]} {conf:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(y1 - th - baseline, 0)
        cv2.rectangle(frame, (x1, top), (x1 + tw, top + th + baseline), (0, 255, 0), -1)
        cv2.putText(
            frame, label, (x1, top + th),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1
        )

    return len(boxes)
