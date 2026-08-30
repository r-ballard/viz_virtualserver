"""Immutable SVG affine transforms for intrinsic polygon domains."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .geometry import EPSILON
from .models import Point, PolygonDomain


@dataclass(frozen=True, slots=True)
class AffineTransform:
    """An invertible SVG affine transform: ``(x, y) -> (ax + cy + e, bx + dy + f)``."""

    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in (self.a, self.b, self.c, self.d, self.e, self.f))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("affine transform matrix values must be finite")
        determinant = values[0] * values[3] - values[1] * values[2]
        if not math.isfinite(determinant) or abs(determinant) <= EPSILON:
            raise ValueError("affine transform matrix must be invertible")
        for name, value in zip(("a", "b", "c", "d", "e", "f"), values, strict=True):
            object.__setattr__(self, name, value)

    @property
    def determinant(self) -> float:
        """Return the determinant of the transform's linear portion."""

        return self.a * self.d - self.b * self.c

    @classmethod
    def identity(cls) -> AffineTransform:
        """Return the identity transform."""

        return cls(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0)

    def apply(self, point: Point) -> Point:
        """Apply this transform to a point in SVG coordinate order."""

        x, y = point
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def inverse(self) -> AffineTransform:
        """Return the inverse transform."""

        determinant = self.determinant
        return AffineTransform(
            a=self.d / determinant,
            b=-self.b / determinant,
            c=-self.c / determinant,
            d=self.a / determinant,
            e=(self.c * self.f - self.d * self.e) / determinant,
            f=(self.b * self.e - self.a * self.f) / determinant,
        )

    def compose(self, other: AffineTransform) -> AffineTransform:
        """Return this transform applied after ``other``."""

        return AffineTransform(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )


@dataclass(frozen=True, slots=True)
class CompositionTransform:
    """A declared intrinsic transform for one polygon domain."""

    domain_id: str
    transform: AffineTransform

    def __post_init__(self) -> None:
        if not isinstance(self.transform, AffineTransform):
            raise ValueError("composition transform must be an AffineTransform")


def resolve_composition_transforms(
    domains: Iterable[PolygonDomain],
    transforms: Iterable[CompositionTransform],
) -> Mapping[str, AffineTransform]:
    """Resolve explicitly declared transforms by domain without creating defaults."""

    domain_ids = {domain.id for domain in tuple(domains)}
    resolved: dict[str, AffineTransform] = {}
    for composition in tuple(transforms):
        if composition.domain_id not in domain_ids:
            raise ValueError(f"unknown domain: {composition.domain_id}")
        if composition.domain_id in resolved:
            raise ValueError(f"duplicate transform domain id: {composition.domain_id}")
        resolved[composition.domain_id] = composition.transform
    return MappingProxyType(resolved)
