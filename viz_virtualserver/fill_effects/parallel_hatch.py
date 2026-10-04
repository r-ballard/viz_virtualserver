"""Parallel plotter strokes clipped to already-composed regions."""

from __future__ import annotations

import math

from shapely.errors import GEOSException
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from .models import FillStroke

MAX_HATCH_ROWS = 100_000
MAX_HATCH_POINTS = 2_000_000


def parallel_hatches(
    region: BaseGeometry, *, spacing: float, angle: float,
) -> tuple[FillStroke, ...]:
    if not math.isfinite(spacing) or spacing <= 0 or not math.isfinite(angle):
        raise ValueError("hatch spacing must be positive and hatch angle finite")
    if region.is_empty:
        return ()
    radians = math.radians(angle % 180)
    dx, dy = math.cos(radians), math.sin(radians)
    # Exact cardinal directions avoid tiny gaps at axis-aligned edges.
    dx = 0.0 if abs(dx) < 1e-15 else dx
    dy = 0.0 if abs(dy) < 1e-15 else dy
    left, bottom, right, top = region.bounds
    corners = ((left, bottom), (left, top), (right, bottom), (right, top))
    along = tuple(x * dx + y * dy for x, y in corners)
    across = tuple(-x * dy + y * dx for x, y in corners)
    low, high = min(across), max(across)
    span = (high - low) / spacing
    if not math.isfinite(span) or span > MAX_HATCH_ROWS:
        raise ValueError("hatching exceeds 100,000 scan rows")
    if any(math.ulp(value) * 4 > spacing for value in (*along, *across)):
        raise ValueError("hatch spacing cannot be represented reliably")
    first, last = math.ceil(low / spacing), math.floor(high / spacing)
    if last - first + 1 > MAX_HATCH_ROWS:
        raise ValueError("hatching exceeds 100,000 scan rows")
    start, end = min(along) - spacing, max(along) + spacing
    paths = []
    try:
        for row in range(first, last + 1):
            offset = row * spacing
            stroke = LineString(((start * dx - offset * dy, start * dy + offset * dx),
                                 (end * dx - offset * dy, end * dy + offset * dx)))
            pending = [stroke.intersection(region)]
            while pending:
                part = pending.pop()
                if part.is_empty:
                    continue
                if part.geom_type == "LineString":
                    a, b = tuple(part.coords[0]), tuple(part.coords[-1])
                    if a != b:
                        paths.append(FillStroke(tuple(sorted((a, b))), False))
                        if len(paths) * 2 > MAX_HATCH_POINTS:
                            raise ValueError("hatching exceeds 2,000,000 points")
                elif hasattr(part, "geoms"):
                    pending.extend(part.geoms)
    except GEOSException as exc:
        raise ValueError("hatch region clipping failed") from exc
    return tuple(sorted(paths, key=lambda p: p.points))
