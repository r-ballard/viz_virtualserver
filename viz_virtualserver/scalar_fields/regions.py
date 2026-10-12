"""Indexed polygonal regions of the shared marching-square height field."""

import math
from dataclasses import dataclass

import numpy as np
from shapely import get_num_coordinates
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from viz_virtualserver.canvas.models import PolygonDomain

from .cells import cell_segments
from .models import SampledField

MAX_REGION_WORK = 12_000_000
MAX_REGION_COORDINATES = 1_000_000


@dataclass(frozen=True, slots=True)
class BandRegion:
    index: int
    lower: float | None
    upper: float | None
    geometry: BaseGeometry


class _Budget:
    def __init__(self):
        self.used = 0

    def check(self, geometry):
        self.used += get_num_coordinates(geometry)
        if self.used > MAX_REGION_COORDINATES:
            raise ValueError("region coordinate budget exceeded; increase spacing or reduce levels")
        if not geometry.is_valid:
            raise ValueError("invalid region topology; increase spacing or reduce levels")
        return geometry


def _polygonal(geometry):
    if geometry.is_empty:
        return Polygon()
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    parts = []
    pending = [geometry]
    while pending:
        part = pending.pop()
        if part.geom_type == "Polygon":
            parts.append(part)
        elif hasattr(part, "geoms"):
            pending.extend(part.geoms)
    return unary_union(parts) if parts else Polygon()


def _superlevel(field, level, budget):
    values = field.values
    ny, nx = values.shape
    above = values > level
    codes = above[:-1, :-1] * 8 + above[:-1, 1:] * 4 + above[1:, 1:] * 2 + above[1:, :-1]
    pieces = []
    x0, y0 = field.origin
    for row in range(ny - 1):
        # Fully high cells form row runs, avoiding per-cell rectangles.
        transitions = np.diff(np.pad((codes[row] == 15).astype(np.int8), (1, 1)))
        starts, ends = np.flatnonzero(transitions == 1), np.flatnonzero(transitions == -1)
        for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
            pieces.append(
                budget.check(
                    box(
                        x0 + start * field.dx,
                        y0 + row * field.dy,
                        x0 + end * field.dx,
                        y0 + (row + 1) * field.dy,
                    )
                )
            )
        for column in np.flatnonzero((codes[row] != 0) & (codes[row] != 15)).tolist():
            corners = ((column, row), (column + 1, row), (column + 1, row + 1), (column, row + 1))
            points = tuple((x0 + i * field.dx, y0 + j * field.dy) for i, j in corners)
            cuts = cell_segments(field, column, row, level, reject_precision_loss=True)
            boundary = LineString(points + (points[0],))
            graph = unary_union([boundary, *[LineString((a.point, b.point)) for a, b in cuts]])
            high = [Point(p) for p, (i, j) in zip(points, corners, strict=True) if above[j, i]]
            for face in polygonize(graph):
                budget.check(face)
                if face.area > 0 and any(face.covers(p) for p in high):
                    pieces.append(face)
    return budget.check(unary_union(pieces) if pieces else Polygon())


def extract_band_regions(
    field: SampledField, levels: tuple[float, ...], polygon: PolygonDomain
) -> tuple[BandRegion, ...]:
    if any(not math.isfinite(v) for v in levels) or any(a >= b for a, b in zip(levels, levels[1:])):
        raise ValueError("band levels must be finite and strictly increasing")
    ny, nx = field.values.shape
    if (nx - 1) * (ny - 1) * len(levels) > MAX_REGION_WORK:
        raise ValueError("region work budget exceeded; increase spacing or reduce levels")
    target = Polygon(polygon.vertices)
    x0, y0 = field.origin
    x1, y1 = x0 + (nx - 1) * field.dx, y0 + (ny - 1) * field.dy
    if not all(math.isfinite(v) for v in (x1, y1)) or not box(x0, y0, x1, y1).covers(target):
        raise ValueError("target must lie inside the sampled field rectangle")
    minx, miny, maxx, maxy = target.bounds
    tolerance = 64 * np.finfo(float).eps * max(1, target.area, (maxx - minx) * (maxy - miny))
    budget = _Budget()
    try:
        thresholds = [
            budget.check(_polygonal(_superlevel(field, level, budget).intersection(target)))
            for level in levels
        ]
        for lower, higher in zip(thresholds, thresholds[1:]):
            if higher.difference(lower).area > tolerance:
                raise ValueError("non-nested scalar regions; increase spacing or reduce levels")
        partitions = []
        bounds = (target, *thresholds, Polygon())
        for i, (lower, higher) in enumerate(zip(bounds, bounds[1:])):
            geometry = budget.check(_polygonal(lower.difference(higher)))
            partitions.append(
                BandRegion(
                    i,
                    None if i == 0 else levels[i - 1],
                    None if i == len(levels) else levels[i],
                    geometry,
                )
            )
        combined = unary_union([r.geometry for r in partitions])
        if combined.symmetric_difference(target).area > tolerance:
            raise ValueError("scalar band partition does not cover target")
        if sum(r.geometry.area for r in partitions) - combined.area > tolerance:
            raise ValueError("scalar band interiors overlap")
        return tuple(partitions)
    except GEOSException as error:
        raise ValueError(
            "scalar region topology failed; increase spacing or reduce levels"
        ) from error
