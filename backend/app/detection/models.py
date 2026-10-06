"""Plain data types produced by the detection layer.

Everything downstream (tracking, analytics, drawing) consumes these instead of
raw Ultralytics objects, so the detector model can be replaced without
touching the rest of the system.
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Detection:
    """One object found by the detector in a single frame.

    Box coordinates are pixels in the frame that was given to the detector:
    (x1, y1) = top-left corner, (x2, y2) = bottom-right corner.
    """

    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """The box as an (x1, y1, x2, y2) tuple."""
        return (self.x1, self.y1, self.x2, self.y2)
