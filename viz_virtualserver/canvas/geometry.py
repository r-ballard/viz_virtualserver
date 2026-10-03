from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from .models import CanvasSpec, Edge, Point, PolygonDomain

EPSILON = 1e-9


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
    domains: tuple[PolygonDomain, ...] = ()

    def __post_init__(self) -> None:
        domains = tuple(self.domains)
        domain_ids = [domain.id for domain in domains]
        if len(domain_ids) != len(set(domain_ids)):
            raise CanvasError("duplicate domain id in intrinsic canvas")
        object.__setattr__(self, "domains", domains)

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


def polygon_edges(vertices: Sequence[Point]) -> tuple[Edge, ...]:
    return tuple(
        (vertices[index], vertices[(index + 1) % len(vertices)])
        for index in range(len(vertices))
    )


def polygon_signed_area(vertices: Sequence[Point]) -> float:
    return 0.5 * sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in polygon_edges(vertices)
    )


def polygon_winding(vertices: Sequence[Point]) -> str:
    return "counterclockwise" if polygon_signed_area(vertices) > 0 else "clockwise"


def polygon_centroid(vertices: Sequence[Point]) -> Point:
    signed_area = polygon_signed_area(vertices)
    if abs(signed_area) <= EPSILON:
        raise ValueError("polygon must have non-zero area")

    scale = 1.0 / (6.0 * signed_area)
    x = 0.0
    y = 0.0
    for (x0, y0), (x1, y1) in polygon_edges(vertices):
        cross = x0 * y1 - x1 * y0
        x += (x0 + x1) * cross
        y += (y0 + y1) * cross
    return x * scale, y * scale


def is_convex_polygon(vertices: Sequence[Point]) -> bool:
    turn_sign = 0
    count = len(vertices)
    for index in range(count):
        first = vertices[index]
        second = vertices[(index + 1) % count]
        third = vertices[(index + 2) % count]
        cross = _cross(first, second, third)
        if abs(cross) <= EPSILON:
            continue
        current_sign = 1 if cross > 0 else -1
        if turn_sign and current_sign != turn_sign:
            return False
        turn_sign = current_sign
    return True


def validate_simple_polygon(vertices: Sequence[Point]) -> None:
    if len(vertices) < 3:
        raise ValueError("polygon requires at least three vertices")

    for x, y in vertices:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("polygon coordinates must be finite")

    edges = polygon_edges(vertices)
    for start, end in edges:
        if _points_equal(start, end):
            raise ValueError("polygon must not contain a zero-length edge")

    if abs(polygon_signed_area(vertices)) <= EPSILON:
        raise ValueError("polygon must have non-zero area")

    edge_count = len(edges)
    for first_index, first in enumerate(edges):
        for second_index in range(first_index + 1, edge_count):
            if second_index == first_index + 1:
                continue
            if first_index == 0 and second_index == edge_count - 1:
                continue
            if _segments_intersect(first, edges[second_index]):
                raise ValueError("polygon must not self-intersect")


def _segments_intersect(first: Edge, second: Edge) -> bool:
    a, b = first
    c, d = second
    orientations = (
        _cross(a, b, c),
        _cross(a, b, d),
        _cross(c, d, a),
        _cross(c, d, b),
    )
    ab_c, ab_d, cd_a, cd_b = orientations

    if _opposite_signs(ab_c, ab_d) and _opposite_signs(cd_a, cd_b):
        return True
    return (
        (abs(ab_c) <= EPSILON and _on_segment(a, b, c))
        or (abs(ab_d) <= EPSILON and _on_segment(a, b, d))
        or (abs(cd_a) <= EPSILON and _on_segment(c, d, a))
        or (abs(cd_b) <= EPSILON and _on_segment(c, d, b))
    )


def _cross(origin: Point, first: Point, second: Point) -> float:
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (
        first[1] - origin[1]
    ) * (second[0] - origin[0])


def _opposite_signs(first: float, second: float) -> bool:
    return (first > EPSILON and second < -EPSILON) or (
        first < -EPSILON and second > EPSILON
    )


def _on_segment(start: Point, end: Point, point: Point) -> bool:
    return (
        min(start[0], end[0]) - EPSILON <= point[0] <= max(start[0], end[0]) + EPSILON
        and min(start[1], end[1]) - EPSILON
        <= point[1]
        <= max(start[1], end[1]) + EPSILON
    )


def _points_equal(first: Point, second: Point) -> bool:
    return abs(first[0] - second[0]) <= EPSILON and abs(first[1] - second[1]) <= EPSILON


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
