from abc import ABC, abstractmethod


class VideoSource(ABC):
    """Common interface for anything that produces video frames.

    Implementations (MP4, webcam, RTSP, ...) must also expose an `fps`
    attribute (float; <= 0 means unknown). The detection code depends only
    on this interface, so it never cares where a frame came from.
    """

    @abstractmethod
    def read(self):
        """Return `(success, frame)` like cv2.VideoCapture.read().

        `success` is False when the source has no more frames.
        `frame` is a BGR numpy array (H x W x 3).
        """
        pass

    @abstractmethod
    def release(self):
        """Free the underlying device/file handle."""
        pass