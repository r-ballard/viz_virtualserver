"""Catalogue adapter combining the vortex evaluator and fixed mark renderer."""

from shapely.geometry.base import BaseGeometry

from .field_marks import render_field_marks
from .models import FillStroke
from .vector_fields import VortexField


def vortex_marks(
    region: BaseGeometry, *, spacing: float, mark_length: float, angle: float,
    center_x: float, center_y: float,
) -> tuple[FillStroke, ...]:
    return render_field_marks(region, spacing=spacing, mark_length=mark_length, angle=angle,
                              field=VortexField(center_x, center_y))
