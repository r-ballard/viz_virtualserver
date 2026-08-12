from __future__ import annotations

import math
import random
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from .models import CanvasSpec

Point = tuple[float, float]


class CanvasError(ValueError):
    """Raised when an intrinsic canvas definition is geometrically invalid."""


@dataclass(frozen=True)
class CanvasGeometry:
    """Resolved polygonal drawing domain and semantic reading direction."""

    shape: str
    width: float
    height: float
    polygon: tuple[Point, ...]
    up_anchor: str

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise CanvasError("canvas width and height must be positive")
        if len(self.polygon) < 3:
            raise CanvasError("canvas polygon requires at least three vertices")

        polygon = self.as_polygon()
        if polygon.is_empty or polygon.area <= 0:
            raise CanvasError("canvas polygon must have positive area")
        if not polygon.is_valid:
            raise CanvasError("canvas polygon is invalid or self-intersecting")

        _anchor_target(self.polygon, self.up_anchor)
        _normalized_vector(self.centroid, self.anchor_point)

    def as_polygon(self) -> Polygon:
        return Polygon(self.polygon)

    @property
    def centroid(self) -> Point:
        center = self.as_polygon().centroid
        return (float(center.x), float(center.y))

    @property
    def anchor_point(self) -> Point:
        return _anchor_target(self.polygon, self.up_anchor)

    @property
    def up_vector(self) -> Point:
        """Unit vector from the polygon centroid toward the declared up anchor."""

        return _normalized_vector(self.centroid, self.anchor_point)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        min_x, min_y, max_x, max_y = self.as_polygon().bounds
        return (float(min_x), float(min_y), float(max_x), float(max_y))

    def contains(self, point: Point, *, include_boundary: bool = True) -> bool:
        candidate = ShapelyPoint(float(point[0]), float(point[1]))
        polygon = self.as_polygon()
        return bool(polygon.covers(candidate) if include_boundary else polygon.contains(candidate))

    def distance_to_boundary(self, point: Point) -> float:
        candidate = ShapelyPoint(float(point[0]), float(point[1]))
        return float(self.as_polygon().boundary.distance(candidate))

    def random_point(
        self,
        rng: random.Random | None = None,
        *,
        max_attempts: int = 100_000,
    ) -> Point:
        """Return a uniformly sampled point by rejection sampling the polygon bounds."""

        if max_attempts <= 0:
            raise CanvasError("max_attempts must be positive")
        rng = rng or random.Random()
        min_x, min_y, max_x, max_y = self.bounds
        for _ in range(max_attempts):
            point = (rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))
            if self.contains(point):
                return point
        raise CanvasError("unable to sample a point inside canvas polygon")

    def to_payload(self) -> dict:
        min_x, min_y, max_x, max_y = self.bounds
        return {
            "schema_version": 1,
            "shape": self.shape,
            "width": self.width,
            "height": self.height,
            "polygon": [[x, y] for x, y in self.polygon],
            "centroid": list(self.centroid),
            "up_anchor": self.up_anchor,
            "up_vector": list(self.up_vector),
            "bounds": {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
                "width": max_x - min_x,
                "height": max_y - min_y,
            },
        }


def build_canvas(spec: CanvasSpec) -> CanvasGeometry:
    """Resolve a validated API specification into canonical polygon geometry."""

    width = float(spec.width)
    height = float(spec.height)

    if spec.shape in {"rectangle", "square"}:
        polygon: tuple[Point, ...] = (
            (0.0, 0.0),
            (width, 0.0),
            (width, height),
            (0.0, height),
        )
        default_anchor = "edge:0"
    elif spec.shape == "triangle":
        # Vertex 0 is the canonical apex. This makes ``vertex:0`` the native
        # corner/apex-up convention needed by triangular cootie-catcher panels.
        polygon = (
            (width / 2.0, 0.0),
            (width, height),
            (0.0, height),
        )
        default_anchor = "vertex:0"
    elif spec.shape == "polygon":
        if spec.points is None:  # guarded by CanvasSpec; retained for direct callers
            raise CanvasError("polygon canvas requires points")
        polygon = tuple((float(x), float(y)) for x, y in spec.points)
        default_anchor = "edge:0"
    else:  # pragma: no cover - Literal/Pydantic validation prevents this
        raise CanvasError(f"unsupported canvas shape: {spec.shape}")

    return CanvasGeometry(
        shape=spec.shape,
        width=width,
        height=height,
        polygon=polygon,
        up_anchor=spec.up_anchor or default_anchor,
    )


def _anchor_target(polygon: tuple[Point, ...], up_anchor: str) -> Point:
    try:
        kind, raw_index = up_anchor.split(":", 1)
        index = int(raw_index)
    except (ValueError, AttributeError) as exc:
        raise CanvasError("up_anchor must have the form 'vertex:N' or 'edge:N'") from exc

    count = len(polygon)
    if not 0 <= index < count:
        raise CanvasError(f"up_anchor index {index} is outside polygon vertex range 0..{count - 1}")

    if kind == "vertex":
        return polygon[index]
    if kind == "edge":
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    raise CanvasError("up_anchor must use 'vertex' or 'edge'")


def _normalized_vector(origin: Point, target: Point) -> Point:
    dx = float(target[0]) - float(origin[0])
    dy = float(target[1]) - float(origin[1])
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        raise CanvasError("up_anchor does not define a direction away from the canvas centroid")
    return (dx / length, dy / length)
