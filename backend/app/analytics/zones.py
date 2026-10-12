"""Geometry primitives: polygon zones, lines, and the point used to locate a track."""
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import cv2
import numpy as np

Point = Tuple[float, float]


def anchor_point(bbox: Tuple[float, float, float, float], mode: str = "bottom") -> Point:
    """The single point of a bounding box used for zone/line tests.

    "bottom" = bottom-centre (where the feet touch the ground; best for people
    on a floor plane). "center" = box centre.
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    if mode == "center":
        return (cx, (y1 + y2) / 2)
    if mode == "bottom":
        return (cx, y2)
    raise ValueError(f"Unknown anchor mode '{mode}' (use 'bottom' or 'center')")


@dataclass
class Zone:
    """A polygonal area of the video frame, in pixel coordinates.

    Example: Zone("restricted_1", [(200, 150), (600, 150), (650, 500), (180, 500)])
    """

    zone_id: str
    polygon: Sequence[Point]
    name: str = ""

    def __post_init__(self):
        if len(self.polygon) < 3:
            raise ValueError(f"Zone '{self.zone_id}' needs at least 3 points")
        self.polygon: List[Point] = [(float(x), float(y)) for x, y in self.polygon]
        self.name = self.name or self.zone_id
        # Integer contour in the shape OpenCV expects (N, 1, 2).
        self._contour = np.array(self.polygon, dtype=np.float32).reshape(-1, 1, 2)

    def contains(self, point: Point) -> bool:
        """True if `point` is inside the polygon or exactly on its edge."""
        return cv2.pointPolygonTest(self._contour, (float(point[0]), float(point[1])), False) >= 0


@dataclass
class Line:
    """A directed line segment p1 -> p2 in pixel coordinates.

    Crossing direction: for a line drawn left -> right, moving from above the
    line to below it is "IN", and the reverse is "OUT". (In general: IN means
    moving from the negative to the positive side of `side()`.) Swap p1/p2 to
    flip the meaning.
    """

    line_id: str
    p1: Point
    p2: Point
    name: str = ""

    def __post_init__(self):
        self.p1 = (float(self.p1[0]), float(self.p1[1]))
        self.p2 = (float(self.p2[0]), float(self.p2[1]))
        if self.p1 == self.p2:
            raise ValueError(f"Line '{self.line_id}' has identical end points")
        self.name = self.name or self.line_id

    def side(self, point: Point) -> int:
        """Which side of the (infinite) line the point is on: +1, -1, or 0 (on it)."""
        (x1, y1), (x2, y2) = self.p1, self.p2
        cross = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
        return (cross > 0) - (cross < 0)

    def crosses(self, a: Point, b: Point) -> bool:
        """True if the movement segment a -> b strictly crosses this finite line segment.

        Needed on top of `side()`: walking around the end of a finite line
        changes side without actually crossing it.
        """
        def orient(p, q, r):
            v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            return (v > 0) - (v < 0)

        o1, o2 = orient(a, b, self.p1), orient(a, b, self.p2)
        o3, o4 = orient(self.p1, self.p2, a), orient(self.p1, self.p2, b)
        return o1 * o2 < 0 and o3 * o4 < 0
