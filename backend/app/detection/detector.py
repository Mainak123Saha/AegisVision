from abc import ABC, abstractmethod


class Detector(ABC):
    """Interface for any object detector, so the model can be swapped later."""

    @abstractmethod
    def detect(self, frame):
        """Run detection on one BGR frame and return the model's result object.

        Currently the result is an Ultralytics `Results` (with `.boxes` and
        `.names`), which `visualizer.draw_detections` knows how to draw.
        """
        pass
