"""Bounded fixed-length mark placement consumes any raw-vector evaluator."""

from __future__ import annotations

import math

from shapely.errors import GEOSException
from shapely.geometry import LineString
from shapely.geometry.base import BaseGeometry

from .models import FillStroke
from .region_validation import validate_region
from .vector_fields import VectorField, VectorSample, _finite_number

MAX_MARK_CANDIDATES = 100_000
MAX_MARK_POINTS = 2_000_000


def render_field_marks(
    region: BaseGeometry, *, spacing: float, mark_length: float,
    angle: float, field: VectorField,
) -> tuple[FillStroke, ...]:
    """Use direction only; zero vectors omit marks and magnitude does not size them."""
    spacing = _finite_number(spacing, "mark spacing")
    mark_length = _finite_number(mark_length, "mark length")
    angle = _finite_number(angle, "lattice angle")
    if spacing <= 0 or mark_length <= 0:
        raise ValueError("mark spacing and length must be positive")
    if not callable(getattr(field, "sample", None)):
        raise ValueError("field must implement sample(x, y)")
    validate_region(region)
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
    # A local vector can point in any direction, so pad both lattice axes.
    padded = (min(along) - half, max(along) + half,
              min(across) - half, max(across) + half)
    coordinates = (*along, *across, *padded, left, bottom, right, top)
    if (half <= 0 or any(not math.isfinite(value) for value in coordinates)
            or any(math.ulp(value) * 8 > min(spacing, mark_length) for value in coordinates)):
        raise ValueError("field mark spacing or length cannot be represented reliably")
    limits = tuple(value / spacing for value in padded)
    if any(not math.isfinite(value) for value in limits):
        raise ValueError("field mark lattice cannot be represented reliably")
    first_column, last_column = math.ceil(limits[0]), math.floor(limits[1])
    first_row, last_row = math.ceil(limits[2]), math.floor(limits[3])
    candidates = max(0, last_column - first_column + 1) * max(0, last_row - first_row + 1)
    if candidates > MAX_MARK_CANDIDATES:
        raise ValueError("field lattice exceeds 100,000 candidate marks")
    if candidates == 0:
        return ()
    if candidates * 2 > MAX_MARK_POINTS:
        raise ValueError("field mark sampling exceeds 2,000,000 points")
    paths = []
    try:
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                x = column * spacing * dx - row * spacing * dy
                y = column * spacing * dy + row * spacing * dx
                if not math.isfinite(x) or not math.isfinite(y):
                    raise ValueError("field mark centre cannot be represented reliably")
                sample = field.sample(x, y)
                if not isinstance(sample, VectorSample):
                    raise ValueError("field sample must return a VectorSample")
                ux, uy = sample.direction
                if ux == 0 and uy == 0:
                    continue
                points = ((x - half * ux, y - half * uy), (x + half * ux, y + half * uy))
                if (any(not math.isfinite(c) for point in points for c in point)
                        or points[0] == points[1]):
                    raise ValueError("field mark endpoints cannot be represented reliably")
                pending = [LineString(points).intersection(region)]
                while pending:
                    part = pending.pop()
                    if part.is_empty:
                        continue
                    if part.geom_type == "LineString":
                        a, b = tuple(part.coords[0]), tuple(part.coords[-1])
                        if a != b:
                            paths.append(FillStroke(tuple(sorted((a, b))), False))
                            if len(paths) * 2 > MAX_MARK_POINTS:
                                raise ValueError("clipped field marks exceed 2,000,000 points")
                    elif hasattr(part, "geoms"):
                        pending.extend(part.geoms)
    except GEOSException as exc:
        raise ValueError("field mark clipping failed") from exc
    return tuple(sorted(paths, key=lambda p: p.points))
