"""Immutable sampled derivatives supplying raw vectors to field-mark renderers."""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from viz_virtualserver.fill_effects.vector_fields import VectorSample, _finite_number

from .models import MAX_SAMPLES, SampledField

Direction = Literal["slope", "contour"]


@dataclass(frozen=True, slots=True, init=False, eq=False)
class SampledGradient:
    field: SampledField
    dx_values: np.ndarray
    dy_values: np.ndarray
    threshold: float
    bounds: tuple[float, float, float, float]

    def __init__(self, field: SampledField):
        if not isinstance(field, SampledField):
            raise ValueError("gradient requires a SampledField")
        ny, nx = field.values.shape
        if field.values.size > MAX_SAMPLES:
            raise ValueError("gradient sample cost limit exceeded; increase spacing")
        x0, y0 = field.origin
        bounds = (x0, y0, x0 + (nx - 1) * field.dx, y0 + (ny - 1) * field.dy)
        if not all(math.isfinite(v) for v in bounds) or any(
            8 * math.ulp(v) > step for v, step in zip(bounds, (field.dx, field.dy) * 2, strict=True)
        ):
            raise ValueError("gradient grid coordinates cannot be represented reliably")
        threshold = (
            64
            * float(np.finfo(float).eps)
            * max(1, float(np.max(np.abs(field.values))))
            / min(field.dx, field.dy)
        )
        if not math.isfinite(threshold):
            raise ValueError("gradient threshold must be finite")
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            dy_values, dx_values = np.gradient(field.values, field.dy, field.dx, edge_order=1)
        if not np.isfinite(dx_values).all() or not np.isfinite(dy_values).all():
            raise ValueError("gradient derivatives must be finite")
        object.__setattr__(self, "field", field)
        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "threshold", float(threshold))
        for name, values in (("dx_values", dx_values), ("dy_values", dy_values)):
            immutable = np.frombuffer(values.tobytes(), dtype=np.float64).reshape(values.shape)
            object.__setattr__(self, name, immutable)

    def vector_field(self, direction: Direction) -> "GradientField":
        return GradientField(self, direction)


@dataclass(frozen=True, slots=True)
class GradientField:
    gradient: SampledGradient
    direction: Direction

    def __post_init__(self):
        if not isinstance(self.gradient, SampledGradient) or self.direction not in (
            "slope",
            "contour",
        ):
            raise ValueError("gradient direction must be slope or contour")

    def sample(self, x: float, y: float) -> VectorSample:
        x, y = _finite_number(x, "gradient position"), _finite_number(y, "gradient position")
        g = self.gradient
        x0, y0, x1, y1 = g.bounds
        if not x0 <= x <= x1 or not y0 <= y <= y1:
            return VectorSample(0, 0)
        ny, nx = g.field.values.shape
        column, row = (x - x0) / g.field.dx, (y - y0) / g.field.dy
        i, j = min(math.floor(column), nx - 2), min(math.floor(row), ny - 2)
        # Upper endpoint arithmetic can differ by an ulp from the integer index.
        u, v = min(1.0, column - i), min(1.0, row - j)

        def interpolate(values):
            lower = (1 - u) * float(values[j, i]) + u * float(values[j, i + 1])
            upper = (1 - u) * float(values[j + 1, i]) + u * float(values[j + 1, i + 1])
            return (1 - v) * lower + v * upper

        dx, dy = interpolate(g.dx_values), interpolate(g.dy_values)
        raw = VectorSample(dx, dy)
        if raw.magnitude <= g.threshold:
            return VectorSample(0, 0)
        return raw if self.direction == "slope" else VectorSample(-dy, dx)
