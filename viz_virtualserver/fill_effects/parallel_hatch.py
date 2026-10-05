"""Parallel plotter strokes clipped to already-composed regions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.errors import GEOSException
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from .models import FillStroke

MAX_HATCH_ROWS = 100_000
MAX_HATCH_POINTS = 2_000_000


@dataclass(frozen=True)
class _ScanFrame:
    dx: float
    dy: float
    first: int
    last: int
    start: float
    end: float


def parallel_hatches(
    region: BaseGeometry, *, spacing: float, angle: float,
) -> tuple[FillStroke, ...]:
    return _hatch_families(region, spacing=spacing, angles=(angle,))


def _scan_frame(region: BaseGeometry, *, spacing: float, angle: float) -> _ScanFrame:
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
    return _ScanFrame(dx, dy, first, last, start, end)


def _hatch_families(
    region: BaseGeometry, *, spacing: float, angles: tuple[float, ...],
) -> tuple[FillStroke, ...]:
    """Clip all families with one preflight row budget and one point budget."""
    if (not math.isfinite(spacing) or spacing <= 0
            or any(not math.isfinite(angle) for angle in angles)):
        raise ValueError("hatch spacing must be positive and hatch angle finite")
    if region.is_empty:
        return ()
    frames = tuple(_scan_frame(region, spacing=spacing, angle=angle) for angle in angles)
    if sum(max(0, frame.last - frame.first + 1) for frame in frames) > MAX_HATCH_ROWS:
        raise ValueError("hatching exceeds 100,000 scan rows")
    paths = []
    try:
        for frame in frames:
            dx, dy, start, end = frame.dx, frame.dy, frame.start, frame.end
            for row in range(frame.first, frame.last + 1):
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
