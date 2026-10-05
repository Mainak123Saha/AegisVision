import cv2

from .source import VideoSource


class MP4Source(VideoSource):

    def __init__(self, path: str):
        self.video = cv2.VideoCapture(path)

        if not self.video.isOpened():
            raise ValueError(f"Could not open video: {path}")

        self.fps = self.video.get(cv2.CAP_PROP_FPS)

    def read(self):
        return self.video.read()

    def release(self):
        self.video.release()