"""Recursive clipped Voronoi contours in neutral domain coordinates."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from viz_canvas.design import AlgorithmCapabilities, DesignPass, DesignResult, VectorPath
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import Point, PolygonDomain

if TYPE_CHECKING:
    from viz_canvas.runner import AlgorithmContext

Polygon = list[Point]
EPSILON = 1e-10


class VoronoiCellsParameters(BaseModel):
    """Inset and radius ratios use the domain's smaller bounding-box dimension."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    branch: int = Field(default=3, ge=2, le=5)
    depth: int = Field(default=4, ge=1, le=7)
    inset_ratio: float = Field(default=0.0035, ge=0, le=0.05)
    corner_radius_ratio: float = Field(default=0.0065, ge=0, le=0.05)
    curve_segments: int = Field(default=6, ge=2, le=12)
    max_cells: int = Field(default=2000, ge=1, le=5000)
    max_path_length_ratio: float = Field(default=100, gt=0, le=1000)


class VoronoiCellsDomainAlgorithm:
    name = "voronoi-cells"
    capabilities = AlgorithmCapabilities(supports_concave_polygon=False)

    def generate(
        self,
        *,
        canvas: CanvasGeometry,
        domains: tuple[PolygonDomain, ...],
        design_pass: DesignPass,
        context: AlgorithmContext,
    ) -> DesignResult:
        del canvas
        if tuple(layer.id for layer in design_pass.logical_layers) != ("cell-contours",):
            raise ValueError("voronoi-cells requires one cell-contours logical layer")
        settings = VoronoiCellsParameters.model_validate(dict(design_pass.parameters))
        if settings.branch**settings.depth > settings.max_cells:
            raise ValueError("requested recursion exceeds max_cells")
        paths: list[VectorPath] = []
        for domain in domains:
            if not domain.is_convex:
                raise ValueError(f"voronoi-cells requires a convex domain: {domain.id}")
            vertices = domain.vertices
            scale = min(
                max(p[0] for p in vertices) - min(p[0] for p in vertices),
                max(p[1] for p in vertices) - min(p[1] for p in vertices),
            )
            root = list(vertices)
            if signed_area(root) < 0:
                root.reverse()
            leaves = subdivide(root, random.Random(context.domain_seeds[domain.id]), settings)
            error = abs(sum(signed_area(cell) for cell in leaves) - signed_area(root))
            if error > max(1e-8, signed_area(root) * 1e-8):
                raise ValueError(f"Voronoi partition does not cover domain: {domain.id}")
            contours = [inset(cell, scale * settings.inset_ratio) for cell in leaves]
            contours = [cell for cell in contours if len(cell) >= 3 and signed_area(cell) > EPSILON]
            if not contours:
                raise ValueError(f"inset removed every cell in domain: {domain.id}")
            total_length = sum(perimeter(cell) for cell in contours)
            if total_length > scale * settings.max_path_length_ratio:
                raise ValueError(f"source path length exceeds max_path_length_ratio: {domain.id}")
            paths.extend(
                VectorPath(
                    points=tuple(
                        rounded(cell, scale * settings.corner_radius_ratio, settings.curve_segments)
                    ),
                    closed=True,
                    layer_id="cell-contours",
                    domain_id=domain.id,
                )
                for cell in contours
            )
        return DesignResult(
            paths=tuple(paths), derived_domains=(), producing_pass_id=design_pass.id
        )


def signed_area(polygon: Polygon) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1])) / 2


def perimeter(polygon: Polygon) -> float:
    return sum(math.dist(a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def sample(polygon: Polygon, rng: random.Random) -> Point:
    triangles = [(polygon[0], polygon[i], polygon[i + 1]) for i in range(1, len(polygon) - 1)]
    target = rng.random() * signed_area(polygon)
    chosen = triangles[-1]
    for triangle in triangles:
        target -= signed_area(list(triangle))
        if target <= 0:
            chosen = triangle
            break
    a, b, c = chosen
    u, v = math.sqrt(rng.random()), rng.random()
    return (
        (1 - u) * a[0] + u * (1 - v) * b[0] + u * v * c[0],
        (1 - u) * a[1] + u * (1 - v) * b[1] + u * v * c[1],
    )


def clip(polygon: Polygon, dx: float, dy: float, threshold: float) -> Polygon:
    if not polygon:
        return []
    output: Polygon = []
    previous = polygon[-1]
    previous_side = dx * previous[0] + dy * previous[1] - threshold
    for current in polygon:
        current_side = dx * current[0] + dy * current[1] - threshold
        if (previous_side <= EPSILON) != (current_side <= EPSILON):
            fraction = previous_side / (previous_side - current_side)
            output.append(
                (
                    previous[0] + fraction * (current[0] - previous[0]),
                    previous[1] + fraction * (current[1] - previous[1]),
                )
            )
        if current_side <= EPSILON:
            output.append(current)
        previous, previous_side = current, current_side
    clean: Polygon = []
    for point in output:
        if not clean or math.dist(point, clean[-1]) > EPSILON:
            clean.append(point)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= EPSILON:
        clean.pop()
    return clean


def subdivide(root: Polygon, rng: random.Random, settings: VoronoiCellsParameters) -> list[Polygon]:
    leaves: list[Polygon] = []

    def visit(parent: Polygon, remaining: int) -> None:
        if remaining == 0:
            leaves.append(parent)
            return
        sites = [sample(parent, rng) for _ in range(settings.branch)]
        for index, site in enumerate(sites):
            cell = parent[:]
            for other_index, other in enumerate(sites):
                if index == other_index:
                    continue
                dx, dy = other[0] - site[0], other[1] - site[1]
                threshold = (other[0] ** 2 + other[1] ** 2 - site[0] ** 2 - site[1] ** 2) / 2
                cell = clip(cell, dx, dy, threshold)
                if len(cell) < 3:
                    raise ValueError("Voronoi partition produced a degenerate cell")
            visit(cell, remaining - 1)

    visit(root, settings.depth)
    return leaves


def inset(polygon: Polygon, distance: float) -> Polygon:
    result = polygon[:]
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        threshold = dy * start[0] - dx * start[1] - distance * math.hypot(dx, dy)
        result = clip(result, dy, -dx, threshold)
        if len(result) < 3:
            return []
    return result


def rounded(polygon: Polygon, radius: float, segments: int) -> Polygon:
    if radius == 0:
        return polygon[:]
    points: Polygon = []
    for i, vertex in enumerate(polygon):
        before, after = polygon[i - 1], polygon[(i + 1) % len(polygon)]
        before_length, after_length = math.dist(before, vertex), math.dist(after, vertex)
        trim = min(radius, before_length / 3, after_length / 3)
        incoming = (
            vertex[0] + trim * (before[0] - vertex[0]) / before_length,
            vertex[1] + trim * (before[1] - vertex[1]) / before_length,
        )
        outgoing = (
            vertex[0] + trim * (after[0] - vertex[0]) / after_length,
            vertex[1] + trim * (after[1] - vertex[1]) / after_length,
        )
        points.append(incoming)
        for step in range(1, segments + 1):
            t = step / segments
            points.append(
                (
                    (1 - t) ** 2 * incoming[0] + 2 * (1 - t) * t * vertex[0] + t * t * outgoing[0],
                    (1 - t) ** 2 * incoming[1] + 2 * (1 - t) * t * vertex[1] + t * t * outgoing[1],
                )
            )
    return points
