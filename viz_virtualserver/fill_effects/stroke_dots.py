"""Short, nonzero marks on a rotated square lattice, clipped individually."""

from __future__ import annotations

import math

from shapely.errors import GEOSException
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from .models import FillStroke

MAX_DOT_CANDIDATES = 100_000
MAX_DOT_POINTS = 2_000_000


def stroke_dots(
    region: BaseGeometry, *, spacing: float, mark_length: float, angle: float,
) -> tuple[FillStroke, ...]:
    """Return short open strokes; pen width and ink coverage remain downstream."""
    if region.is_empty:
        return ()
    radians = math.radians(angle % 180)
    dx, dy = math.cos(radians), math.sin(radians)
    dx = 0.0 if abs(dx) < 1e-15 else dx
    dy = 0.0 if abs(dy) < 1e-15 else dy
    left, bottom, right, top = region.bounds
    corners = ((left, bottom), (left, top), (right, bottom), (right, top))
    along = tuple(x * dx + y * dy for x, y in corners)
    across = tuple(-x * dy + y * dx for x, y in corners)
    half = mark_length / 2
    # Marks extend along the first lattice axis only. Include outside centres
    # that can contribute clipped fragments; no padding is needed across rows.
    padded = (min(along) - half, max(along) + half, min(across), max(across))
    coordinates = (*along, *across, *padded, left, bottom, right, top)
    if (half <= 0 or any(not math.isfinite(value) for value in coordinates)
            or any(math.ulp(value) * 8 > min(spacing, mark_length) for value in coordinates)):
        raise ValueError("dot spacing or mark length cannot be represented reliably")
    limits = tuple(value / spacing for value in padded)
    if any(not math.isfinite(value) for value in limits):
        raise ValueError("dot lattice cannot be represented reliably")
    first_column, last_column = math.ceil(limits[0]), math.floor(limits[1])
    first_row, last_row = math.ceil(limits[2]), math.floor(limits[3])
    candidates = max(0, last_column - first_column + 1) * max(0, last_row - first_row + 1)
    if candidates > MAX_DOT_CANDIDATES:
        raise ValueError("dot lattice exceeds 100,000 candidate marks")
    if candidates == 0:
        return ()
    if candidates * 2 > MAX_DOT_POINTS:
        raise ValueError("dot sampling exceeds 2,000,000 points")
    paths = []
    try:
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                x = column * spacing * dx - row * spacing * dy
                y = column * spacing * dy + row * spacing * dx
                points = ((x - half * dx, y - half * dy), (x + half * dx, y + half * dy))
                if (any(not math.isfinite(c) for point in points for c in point)
                        or points[0] == points[1]):
                    raise ValueError("dot mark coordinates cannot be represented reliably")
                pending = [LineString(points).intersection(region)]
                while pending:
                    part = pending.pop()
                    if part.is_empty:
                        continue
                    if part.geom_type == "LineString":
                        a, b = tuple(part.coords[0]), tuple(part.coords[-1])
                        if a != b:
                            paths.append(FillStroke(tuple(sorted((a, b))), False))
                            if len(paths) * 2 > MAX_DOT_POINTS:
                                raise ValueError("clipped dots exceed 2,000,000 points")
                    elif hasattr(part, "geoms"):
                        pending.extend(part.geoms)
    except GEOSException as exc:
        raise ValueError("dot region clipping failed") from exc
    return tuple(sorted(paths, key=lambda p: p.points))
