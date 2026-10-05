import cv2

from .source import VideoSource


class WebcamSource(VideoSource):
    """Reads frames from a local camera (0 = default device)."""

    def __init__(self, camera_id: int = 0):
        self.video = cv2.VideoCapture(camera_id)

        if not self.video.isOpened():
            raise ValueError("Could not open webcam")

        # Many webcams report 0 here; the demo falls back to 30 FPS in that case.
        self.fps = self.video.get(cv2.CAP_PROP_FPS)

    def read(self):
        """Return `(success, frame)`; blocks until the camera delivers a frame."""
        return self.video.read()

    def release(self):
        self.video.release()