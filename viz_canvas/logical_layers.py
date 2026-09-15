"""Immutable semantic path records used by logical-layer producers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .models import Point

type SemanticScalar = bool | int | float | str


@dataclass(frozen=True, slots=True)
class PathGeometry:
    """The geometry portion of a semantic path, independent of its layer."""

    points: tuple[Point, ...]
    closed: bool
    coordinate_frame: Literal["domain", "composition"] = "domain"

    def __post_init__(self) -> None:
        if not isinstance(self.closed, bool):
            raise ValueError("path geometry closed must be a bool")
        if self.coordinate_frame not in {"domain", "composition"}:
            raise ValueError("unknown path geometry coordinate frame")
        points = tuple(tuple(point) for point in self.points)
        if any(len(point) != 2 for point in points):
            raise ValueError("path geometry points require exactly two coordinates")
        if any(
            isinstance(coordinate, bool)
            for point in points
            for coordinate in point
        ):
            raise ValueError("path geometry coordinates must be numeric")
        try:
            finite = all(
                math.isfinite(coordinate)
                for point in points
                for coordinate in point
            )
        except TypeError as exc:
            raise ValueError("path geometry coordinates must be numeric") from exc
        if not finite:
            raise ValueError("path geometry coordinates must be finite")
        minimum = 3 if self.closed else 2
        if len(points) < minimum:
            kind = "closed" if self.closed else "open"
            count = "three" if self.closed else "two"
            raise ValueError(f"{kind} path geometry requires at least {count} points")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class SemanticAttributeSchema:
    """The ordered, immutable set of attribute keys a semantic path may expose."""

    keys: tuple[str, ...]

    def __post_init__(self) -> None:
        keys = tuple(self.keys)
        if any(not isinstance(key, str) or not key.strip() for key in keys):
            raise ValueError("semantic attribute keys must be non-empty strings")
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate semantic attribute key")
        object.__setattr__(self, "keys", keys)


@dataclass(frozen=True, slots=True)
class SemanticPath:
    """An immutable path with stable semantic identity and scalar attributes."""

    path_id: str
    domain_id: str
    geometry: PathGeometry
    feature_role: str
    attributes: Mapping[str, SemanticScalar]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("path id", self.path_id),
            ("domain id", self.domain_id),
            ("feature role", self.feature_role),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"semantic path {field_name} must not be empty")
        if not isinstance(self.geometry, PathGeometry):
            raise TypeError("semantic path geometry must be a PathGeometry")
        if not isinstance(self.attributes, Mapping):
            raise TypeError("semantic path attributes must be a mapping")
        frozen: dict[str, SemanticScalar] = {}
        for key, value in self.attributes.items():
            if not isinstance(key, str):
                raise ValueError("semantic attribute keys must be strings")
            if value is None or isinstance(value, (list, tuple, dict, set, Mapping)):
                raise ValueError(f"semantic attribute {key!r} must be scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"semantic attribute {key!r} must be finite")
            if not isinstance(value, (bool, int, float, str)):
                raise ValueError(f"semantic attribute {key!r} must be scalar")
            frozen[key] = value
        object.__setattr__(self, "attributes", MappingProxyType(frozen))
