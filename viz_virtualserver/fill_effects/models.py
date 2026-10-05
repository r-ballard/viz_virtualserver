"""Immutable geometry and catalogue values without generator ownership."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


@dataclass(frozen=True)
class FillStroke:
    """An open or closed stroke in the input region's coordinate frame."""

    points: tuple[tuple[float, float], ...]
    closed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.closed, bool):
            raise ValueError("stroke closed flag must be boolean")
        try:
            points = tuple(tuple(point) for point in self.points)
            if any(len(point) != 2 or any(
                isinstance(value, bool) or not isinstance(value, Real)
                or not math.isfinite(value) for value in point
            ) for point in points):
                raise ValueError("stroke points must be finite 2D coordinates")
            points = tuple((float(x), float(y)) for x, y in points)
        except (TypeError, OverflowError) as exc:
            raise ValueError("stroke points must be finite 2D coordinates") from exc
        if len(set(points)) < (3 if self.closed else 2):
            raise ValueError("stroke has too few distinct vertices")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True)
class EffectParameter:
    """One numeric control; rendering validates these same declarations."""

    name: str
    default: float
    unit: str
    exclusive_minimum: float | None = None


@dataclass(frozen=True)
class FillEffectDescriptor:
    """An implemented effect and its ordered numeric controls."""

    id: str
    name: str
    description: str
    parameters: tuple[EffectParameter, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(self.parameters))
