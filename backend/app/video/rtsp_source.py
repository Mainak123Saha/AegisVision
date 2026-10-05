import cv2

from .source import VideoSource


class RTSPSource(VideoSource):
    """IP camera / network stream (rtsp://, http://). Same interface as every other source."""

    def __init__(self, url: str):
        self.video = cv2.VideoCapture(url)

        if not self.video.isOpened():
            raise ValueError(f"Could not open stream: {url}")

        self.fps = self.video.get(cv2.CAP_PROP_FPS)

    def read(self):
        return self.video.read()

    def release(self):
        self.video.release()
