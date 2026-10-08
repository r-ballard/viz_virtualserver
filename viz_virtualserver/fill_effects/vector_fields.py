"""Pure field evaluators without geometry, region masks, or plotting ownership."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Protocol


def _finite_number(value: object, label: str) -> float:
    try:
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"{label} must be a finite real number")
        return float(value)
    except (OverflowError, TypeError) as exc:
        raise ValueError(f"{label} must be a finite real number") from exc


@dataclass(frozen=True)
class VectorSample:
    """Raw components support blending before direction normalization."""

    dx: float
    dy: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "dx", _finite_number(self.dx, "field component"))
        object.__setattr__(self, "dy", _finite_number(self.dy, "field component"))

    @property
    def magnitude(self) -> float:
        magnitude = math.hypot(self.dx, self.dy)
        if not math.isfinite(magnitude):
            raise ValueError("field magnitude cannot be represented reliably")
        return magnitude

    @property
    def direction(self) -> tuple[float, float]:
        scale = max(abs(self.dx), abs(self.dy))
        if scale == 0:
            return (0.0, 0.0)
        x, y = self.dx / scale, self.dy / scale
        norm = math.hypot(x, y)
        return (x / norm, y / norm)


class VectorField(Protocol):
    """Evaluate raw vectors in the caller's input coordinate frame."""

    def sample(self, x: float, y: float) -> VectorSample: ...


@dataclass(frozen=True)
class VortexField:
    """Clockwise tangential vectors in SVG coordinates, zero at the centre."""

    center_x: float = 0.0
    center_y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "center_x", _finite_number(self.center_x, "field centre"))
        object.__setattr__(self, "center_y", _finite_number(self.center_y, "field centre"))

    def sample(self, x: float, y: float) -> VectorSample:
        return VectorSample(-(y - self.center_y), x - self.center_x)
