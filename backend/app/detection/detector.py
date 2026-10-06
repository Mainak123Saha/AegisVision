from abc import ABC, abstractmethod
from typing import List

from .models import Detection


class Detector(ABC):
    """Interface for any object detector, so the model can be swapped later."""

    @abstractmethod
    def detect(self, frame) -> List[Detection]:
        """Run detection on one BGR frame and return a list of `Detection`s.

        Implementations must translate their model's native output into
        `Detection` objects; nothing model-specific should leak out.
        """
        pass
