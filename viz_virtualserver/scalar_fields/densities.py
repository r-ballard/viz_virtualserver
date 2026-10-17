"""Immutable elevation and slope density sampling without terrain resampling."""

import math
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from viz_virtualserver.fill_effects.vector_fields import _finite_number

from .gradients import SampledGradient
from .models import MAX_SAMPLES, SampledField


@dataclass(frozen=True, slots=True)
class SampledElevationDensity:
    field: SampledField
    minimum: float = dataclass_field(default=0, kw_only=True)
    maximum: float = dataclass_field(default=1, kw_only=True)
    invert: bool = dataclass_field(default=False, kw_only=True)
    bounds: tuple[float, float, float, float] = dataclass_field(init=False)

    def __post_init__(self):
        if not isinstance(self.field, SampledField):
            raise ValueError("elevation density requires a SampledField")
        minimum = _finite_number(self.minimum, "density minimum")
        maximum = _finite_number(self.maximum, "density maximum")
        if not 0 <= minimum <= maximum <= 1 or type(self.invert) is not bool:
            raise ValueError(
                "density mapping requires 0 <= minimum <= maximum <= 1 and boolean invert"
            )
        if self.field.values.size > MAX_SAMPLES:
            raise ValueError("elevation density sample cost limit exceeded")
        ny, nx = self.field.values.shape
        x0, y0 = self.field.origin
        bounds = (x0, y0, x0 + (nx - 1) * self.field.dx, y0 + (ny - 1) * self.field.dy)
        if not all(math.isfinite(v) for v in bounds) or any(
            8 * math.ulp(v) > step
            for v, step in zip(bounds, (self.field.dx, self.field.dy) * 2, strict=True)
        ):
            raise ValueError("density grid coordinates cannot be represented reliably")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "bounds", bounds)

    def sample(self, x: float, y: float) -> float:
        x, y = _finite_number(x, "density position"), _finite_number(y, "density position")
        x0, y0, x1, y1 = self.bounds
        if not x0 <= x <= x1 or not y0 <= y <= y1:
            return 0.0
        ny, nx = self.field.values.shape
        column, row = (x - x0) / self.field.dx, (y - y0) / self.field.dy
        i, j = min(math.floor(column), nx - 2), min(math.floor(row), ny - 2)
        u, v = min(1.0, column - i), min(1.0, row - j)
        values = self.field.values
        lower = (1 - u) * float(values[j, i]) + u * float(values[j, i + 1])
        upper = (1 - u) * float(values[j + 1, i]) + u * float(values[j + 1, i + 1])
        height = (1 - v) * lower + v * upper
        if not math.isfinite(height):
            raise ValueError("interpolated elevation must be finite")
        t = min(1.0, max(0.0, height))
        if self.invert:
            t = 1 - t
        density = self.minimum + (self.maximum - self.minimum) * t
        return min(self.maximum, max(self.minimum, density))


@dataclass(frozen=True, slots=True)
class SampledSlopeDensity:
    """Map gradient magnitude to density using an explicit height/unit reference."""

    gradient: SampledGradient
    reference_slope: float = dataclass_field(kw_only=True)
    minimum: float = dataclass_field(default=0, kw_only=True)
    maximum: float = dataclass_field(default=1, kw_only=True)
    invert: bool = dataclass_field(default=False, kw_only=True)

    def __post_init__(self):
        if not isinstance(self.gradient, SampledGradient):
            raise ValueError("slope density requires a SampledGradient")
        reference = _finite_number(self.reference_slope, "reference slope")
        minimum = _finite_number(self.minimum, "density minimum")
        maximum = _finite_number(self.maximum, "density maximum")
        if reference <= 0:
            raise ValueError("reference slope must be positive")
        if not 0 <= minimum <= maximum <= 1 or type(self.invert) is not bool:
            raise ValueError("density mapping requires ordered bounds in [0,1] and boolean invert")
        object.__setattr__(self, "reference_slope", reference)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    def sample(self, x: float, y: float) -> float:
        x, y = _finite_number(x, "density position"), _finite_number(y, "density position")
        x0, y0, x1, y1 = self.gradient.bounds
        if not x0 <= x <= x1 or not y0 <= y <= y1:
            return 0.0
        magnitude = self.gradient.sample_raw(x, y).magnitude
        t = 1.0 if magnitude >= self.reference_slope else magnitude / self.reference_slope
        if self.invert:
            t = 1 - t
        return min(
            self.maximum, max(self.minimum, self.minimum + (self.maximum - self.minimum) * t)
        )
