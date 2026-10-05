import cv2

from .source import VideoSource


class MP4Source(VideoSource):
    """Reads frames from a video file on disk."""

    def __init__(self, path: str):
        self.video = cv2.VideoCapture(path)

        # VideoCapture fails silently on bad paths, so check explicitly.
        if not self.video.isOpened():
            raise ValueError(f"Could not open video: {path}")

        # Native frame rate stored in the file; used to pace playback.
        self.fps = self.video.get(cv2.CAP_PROP_FPS)

    def read(self):
        """Return `(success, frame)`; success is False at end of file."""
        return self.video.read()

    def release(self):
        self.video.release()