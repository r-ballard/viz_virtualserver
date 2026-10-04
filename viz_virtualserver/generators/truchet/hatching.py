"""Compatibility adapter for Truchet callers of the shared hatch engine."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry

from viz_virtualserver.fill_effects import render_fill_effect
from viz_virtualserver.fill_effects.parallel_hatch import MAX_HATCH_POINTS, MAX_HATCH_ROWS

from .models import CurvePath

__all__ = ["MAX_HATCH_POINTS", "MAX_HATCH_ROWS", "parallel_hatches"]


def parallel_hatches(
    region: BaseGeometry, *, spacing: float, angle: float,
) -> tuple[CurvePath, ...]:
    """Return shared hatch geometry in the historical Truchet value type."""
    strokes = render_fill_effect(region, effect="parallel-hatch",
                                 parameters={"spacing": spacing, "angle": angle})
    return tuple(CurvePath(stroke.points, stroke.closed) for stroke in strokes)
