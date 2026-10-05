"""Perpendicular hatch families clipped with shared resource budgets."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry

from .models import FillStroke
from .parallel_hatch import _hatch_families


def crosshatches(
    region: BaseGeometry, *, spacing: float, angle: float,
) -> tuple[FillStroke, ...]:
    # Reduce first: adding 90 to a very large angle can lose the rotation entirely.
    primary = angle % 180
    return _hatch_families(region, spacing=spacing, angles=(primary, (primary + 90) % 180))
