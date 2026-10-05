from abc import ABC, abstractmethod


class Detector(ABC):
    """Interface for any object detector, so the model can be swapped later."""

    @abstractmethod
    def detect(self, frame):
        pass
