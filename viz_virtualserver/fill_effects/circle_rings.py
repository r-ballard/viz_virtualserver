"""Sampled circle outlines on a rotated square lattice, clipped to regions."""

from __future__ import annotations

import math

from shapely.errors import GEOSException
from shapely.geometry import LineString, MultiLineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

from .models import FillStroke

MAX_RING_CANDIDATES = 100_000
MAX_RING_POINTS = 2_000_000


def _segments(radius: float, tolerance: float) -> int:
    fraction = min(1.0, tolerance / radius / 2)
    if fraction <= 0:
        raise ValueError("circle sampling exceeds 2,000,000 points")
    count = math.pi / (2 * math.asin(math.sqrt(fraction)))
    if not math.isfinite(count) or count > MAX_RING_POINTS:
        raise ValueError("circle sampling exceeds 2,000,000 points")
    # Cardinal samples provide exact extrema and a stable closure seam.
    return max(8, 4 * math.ceil(count / 4))


def _canonical_stroke(line: BaseGeometry) -> FillStroke | None:
    source = tuple(line.coords)
    points = tuple(point for index, point in enumerate(source)
                   if index == 0 or point != source[index - 1])
    if len(points) < 2:
        return None
    closed = points[0] == points[-1]
    if closed:
        points = points[:-1]
        if len(set(points)) < 3:
            return None
        start = min(range(len(points)), key=points.__getitem__)
        points = points[start:] + points[:start]
        reverse = points[:1] + points[:0:-1]
    else:
        reverse = points[::-1]
    return FillStroke(min(points, reverse), closed)


def _clipped_strokes(line: BaseGeometry, region: BaseGeometry) -> tuple[FillStroke, ...]:
    pending = [line.intersection(region)]
    parts = []
    while pending:
        part = pending.pop()
        if part.is_empty:
            continue
        if part.geom_type == "LineString":
            parts.append(part)
        elif hasattr(part, "geoms"):
            pending.extend(part.geoms)
    if not parts:
        return ()
    # A clipped arc may cross the arbitrary sampling seam. Join only contiguous
    # fragments from this single ring, never across separate rings or gaps.
    merged = linemerge(MultiLineString(parts)) if len(parts) > 1 else parts[0]
    lines = merged.geoms if hasattr(merged, "geoms") else (merged,)
    return tuple(stroke for part in lines if (stroke := _canonical_stroke(part)) is not None)


def circle_rings(
    region: BaseGeometry, *, spacing: float, radius: float, angle: float,
    curve_tolerance: float,
) -> tuple[FillStroke, ...]:
    """Return complete closed rings and separate open arcs in input units."""
    if region.is_empty:
        return ()
    radians = math.radians(angle % 360)
    dx, dy = math.cos(radians), math.sin(radians)
    dx = 0.0 if abs(dx) < 1e-15 else dx
    dy = 0.0 if abs(dy) < 1e-15 else dy
    left, bottom, right, top = region.bounds
    corners = ((left, bottom), (left, top), (right, bottom), (right, top))
    along = tuple(x * dx + y * dy for x, y in corners)
    across = tuple(-x * dy + y * dx for x, y in corners)
    padded = (min(along) - radius, max(along) + radius,
              min(across) - radius, max(across) + radius)
    if (any(not math.isfinite(value) for value in (*along, *across, *padded))
            or any(math.ulp(value) * 4 > min(spacing, radius, curve_tolerance)
                   for value in (*along, *across, *padded, left, bottom, right, top))):
        raise ValueError("ring spacing, radius or tolerance cannot be represented reliably")
    limits = tuple(value / spacing for value in padded)
    if any(not math.isfinite(value) for value in limits):
        raise ValueError("ring lattice cannot be represented reliably")
    first_column, last_column = math.ceil(limits[0]), math.floor(limits[1])
    first_row, last_row = math.ceil(limits[2]), math.floor(limits[3])
    candidates = max(0, last_column - first_column + 1) * max(0, last_row - first_row + 1)
    if candidates > MAX_RING_CANDIDATES:
        raise ValueError("circle lattice exceeds 100,000 candidate rings")
    if candidates == 0:
        return ()
    # Reserve arithmetic error at the emitted coordinates instead of spending
    # the entire deviation budget on an ideal, untranslated polygon.
    rounding = 8 * max(math.ulp(value) for value in
                       (*along, *across, *padded, left, bottom, right, top, radius))
    sampling_tolerance = curve_tolerance - rounding
    if sampling_tolerance <= 0:
        raise ValueError("ring tolerance cannot be represented reliably at these coordinates")
    count = _segments(radius, sampling_tolerance)
    if candidates * count > MAX_RING_POINTS:
        raise ValueError("circle sampling exceeds 2,000,000 points")
    offsets = []
    cardinal = ((radius, 0.0), (0.0, radius), (-radius, 0.0), (0.0, -radius))
    quarter = count // 4
    for index in range(count):
        if index % quarter == 0:
            offsets.append(cardinal[index // quarter])
        else:
            phase = 2 * math.pi * index / count
            offsets.append((radius * math.cos(phase), radius * math.sin(phase)))
    paths = []
    point_count = 0
    try:
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                x = column * spacing * dx - row * spacing * dy
                y = column * spacing * dy + row * spacing * dx
                points = tuple((x + ox, y + oy) for ox, oy in offsets)
                if any(not math.isfinite(c) for point in points for c in point):
                    raise ValueError("ring coordinates cannot be represented reliably")
                line = LineString(points + points[:1])
                for stroke in _clipped_strokes(line, region):
                    point_count += len(stroke.points)
                    if point_count > MAX_RING_POINTS:
                        raise ValueError("clipped rings exceed 2,000,000 points")
                    paths.append(stroke)
    except GEOSException as exc:
        raise ValueError("ring region clipping failed") from exc
    return tuple(sorted(paths, key=lambda p: (p.points, p.closed)))
