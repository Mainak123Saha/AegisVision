import cv2

from .source import VideoSource


class WebcamSource(VideoSource):

    def __init__(self, camera_id: int = 0):
        self.video = cv2.VideoCapture(camera_id)

        if not self.video.isOpened():
            raise ValueError("Could not open webcam")

        self.fps = self.video.get(cv2.CAP_PROP_FPS)

    def read(self):
        return self.video.read()

    def release(self):
        self.video.release()