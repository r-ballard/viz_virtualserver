"""Immutable semantic path records used by logical-layer producers."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal
from urllib.parse import quote

from .design import LogicalLayer, VectorPath
from .models import Point

type SemanticScalar = bool | int | float | str


class ProjectionError(ValueError):
    """Raised when a semantic path cannot be projected into a logical layer."""


def _validate_scalar(value: object, *, context: str) -> None:
    if value is None or isinstance(value, (list, tuple, dict, set, Mapping)):
        raise ValueError(f"{context} must be scalar")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{context} must be finite")
    if not isinstance(value, (bool, int, float, str)):
        raise ValueError(f"{context} must be scalar")


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


@dataclass(frozen=True, slots=True)
class MatchSpec:
    """Semantic selectors used to choose a fixed logical layer."""

    feature_role: str | None = None
    attributes: Mapping[str, tuple[SemanticScalar, ...]] = MappingProxyType({})

    def __post_init__(self) -> None:
        if self.feature_role is not None and (
            not isinstance(self.feature_role, str) or not self.feature_role.strip()
        ):
            raise ValueError("match feature role must be a non-empty string")
        if not isinstance(self.attributes, Mapping):
            raise TypeError("match attributes must be a mapping")
        frozen: dict[str, tuple[SemanticScalar, ...]] = {}
        for key, values in self.attributes.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("match attribute keys must be non-empty strings")
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"match attribute {key!r} requires at least one value")
            for value in values:
                _validate_scalar(value, context=f"match attribute {key!r} value")
            frozen[key] = values
        object.__setattr__(self, "attributes", MappingProxyType(frozen))


@dataclass(frozen=True, slots=True)
class FixedLayerSpec:
    """The logical layer to assign when a projection rule matches."""

    id: str
    label: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("fixed layer id must be a non-empty string")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("fixed layer label must be a non-empty string")


@dataclass(frozen=True, slots=True)
class DynamicLayerSpec:
    """A logical layer derived from an ordered tuple of semantic values."""

    id_prefix: str
    label_prefix: str
    group_by: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id_prefix, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9._-]*", self.id_prefix
        ):
            raise ValueError("dynamic layer id prefix must be a safe identifier")
        if not isinstance(self.label_prefix, str) or not self.label_prefix.strip():
            raise ValueError("dynamic layer label prefix must be a non-empty string")
        group_by = tuple(self.group_by)
        if not group_by:
            raise ValueError("dynamic layer group by requires at least one key")
        if any(not isinstance(key, str) or not key.strip() for key in group_by):
            raise ValueError("dynamic layer group by keys must be non-empty strings")
        if len(group_by) != len(set(group_by)):
            raise ValueError("duplicate dynamic layer group by key")
        object.__setattr__(self, "group_by", group_by)


@dataclass(frozen=True, slots=True)
class ProjectionRule:
    """A semantic selector and the fixed or dynamic layer it produces."""

    match: MatchSpec
    fixed: FixedLayerSpec | None = None
    dynamic: DynamicLayerSpec | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.match, MatchSpec):
            raise TypeError("projection rule match must be a MatchSpec")
        if (self.fixed is None) == (self.dynamic is None):
            raise ValueError("projection rule requires exactly one layer specification")
        if self.fixed is not None and not isinstance(self.fixed, FixedLayerSpec):
            raise TypeError("projection rule fixed layer must be a FixedLayerSpec")
        if self.dynamic is not None and not isinstance(self.dynamic, DynamicLayerSpec):
            raise TypeError("projection rule dynamic layer must be a DynamicLayerSpec")


@dataclass(frozen=True, slots=True)
class ProjectionSpec:
    """The named, ordered rules for projecting semantic paths."""

    id: str
    rules: tuple[ProjectionRule, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("projection id must be a non-empty string")
        rules = tuple(self.rules)
        if not rules:
            raise ValueError("projection requires at least one rule")
        if any(not isinstance(rule, ProjectionRule) for rule in rules):
            raise TypeError("projection rules must be ProjectionRule values")
        fixed_layers: dict[str, FixedLayerSpec] = {}
        for rule in rules:
            if rule.fixed is None:
                continue
            previous = fixed_layers.get(rule.fixed.id)
            if previous is not None and previous != rule.fixed:
                raise ValueError(
                    f"{rule.fixed.id!r} has conflicting fixed layer definitions"
                )
            fixed_layers[rule.fixed.id] = rule.fixed
        object.__setattr__(self, "rules", rules)


@dataclass(frozen=True, slots=True)
class ProjectedDesign:
    """Paths and their used fixed logical layers after semantic projection."""

    paths: tuple[VectorPath, ...]
    layers: tuple[LogicalLayer, ...]

    def __post_init__(self) -> None:
        paths = tuple(self.paths)
        layers = tuple(self.layers)
        if any(not isinstance(path, VectorPath) for path in paths):
            raise TypeError("projected design paths must be VectorPath values")
        if any(not isinstance(layer, LogicalLayer) for layer in layers):
            raise TypeError("projected design layers must be LogicalLayer values")
        layer_ids = [layer.id for layer in layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("projected design layers must have unique ids")
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "layers", layers)


def project_paths(
    paths: tuple[SemanticPath, ...],
    schema: SemanticAttributeSchema,
    projection: ProjectionSpec,
) -> ProjectedDesign:
    """Project semantic paths into the first matching fixed or dynamic layer."""

    paths = tuple(paths)
    if any(not isinstance(path, SemanticPath) for path in paths):
        raise TypeError("paths must be SemanticPath values")
    if not isinstance(schema, SemanticAttributeSchema):
        raise TypeError("schema must be a SemanticAttributeSchema")
    if not isinstance(projection, ProjectionSpec):
        raise TypeError("projection must be a ProjectionSpec")

    declared_keys = set(schema.keys)
    for rule_index, rule in enumerate(projection.rules):
        for key in rule.match.attributes:
            if key not in declared_keys:
                raise ProjectionError(
                    f"projection {projection.id} selects undeclared attribute "
                    f"{key!r} in rule {rule_index}"
                )
        if rule.dynamic is not None:
            for key in rule.dynamic.group_by:
                if key != "domain_id" and key not in declared_keys:
                    raise ProjectionError(
                        f"projection {projection.id} groups by undeclared attribute "
                        f"{key!r} in rule {rule_index}"
                    )

    projected_paths: list[VectorPath] = []
    layer_definitions: dict[str, tuple[object, ...]] = {}
    matched_rule_layers: dict[int, dict[str, tuple[tuple[object, ...], LogicalLayer]]] = {}
    for path in paths:
        for rule_index, rule in enumerate(projection.rules):
            if not _matches(path, rule.match):
                continue
            if rule.fixed is not None:
                layer = LogicalLayer(rule.fixed.id, rule.fixed.label)
                definition = ("fixed", rule.fixed.label)
                sort_key = ()
            else:
                assert rule.dynamic is not None
                group_values = _group_values(path, rule.dynamic, projection.id, rule_index)
                encoded_values = tuple(canonical_scalar(value) for value in group_values)
                layer = LogicalLayer(
                    "-".join((rule.dynamic.id_prefix, *encoded_values)),
                    _dynamic_layer_label(rule.dynamic, group_values),
                )
                definition = (
                    "dynamic",
                    rule.dynamic.group_by,
                    tuple(_scalar_identity(value) for value in group_values),
                    layer.label,
                )
                sort_key = tuple(_scalar_sort_key(value) for value in group_values)
            previous = layer_definitions.get(layer.id)
            if previous is not None and previous != definition:
                raise ProjectionError(
                    f"logical layer id {layer.id!r} has conflicting dynamic group metadata"
                )
            layer_definitions[layer.id] = definition
            projected_paths.append(
                VectorPath(
                    points=path.geometry.points,
                    closed=path.geometry.closed,
                    layer_id=layer.id,
                    domain_id=path.domain_id,
                    coordinate_frame=path.geometry.coordinate_frame,
                )
            )
            matched_rule_layers.setdefault(rule_index, {})[layer.id] = (sort_key, layer)
            break
        else:
            raise ProjectionError(
                f"path ID {path.path_id} did not match any rule (0 through "
                f"{len(projection.rules) - 1}) in projection {projection.id}"
            )

    layers: list[LogicalLayer] = []
    emitted_layer_ids: set[str] = set()
    for rule_index, _rule in enumerate(projection.rules):
        rule_layers = matched_rule_layers.get(rule_index, {})
        for _, layer in sorted(rule_layers.values(), key=lambda entry: entry[0]):
            if layer.id not in emitted_layer_ids:
                layers.append(layer)
                emitted_layer_ids.add(layer.id)
    return ProjectedDesign(tuple(projected_paths), tuple(layers))


def canonical_scalar(value: SemanticScalar) -> str:
    """Encode a scalar into a typed, SVG-safe identifier component."""

    tag, content = _scalar_identity(value)
    return f"{tag}-{quote(content, safe='-._~')}"


def _scalar_identity(value: SemanticScalar) -> tuple[str, str]:
    if type(value) is bool:
        return "b", "true" if value else "false"
    if type(value) is int:
        return "i", str(value)
    if type(value) is float:
        return "n", repr(value)
    return "s", value


def _scalar_sort_key(value: SemanticScalar) -> tuple[object, ...]:
    if type(value) is bool:
        return 0, value
    if type(value) is int:
        return 1, value
    if type(value) is float:
        return 2, value, repr(value)
    return 3, value


def _group_values(
    path: SemanticPath,
    dynamic: DynamicLayerSpec,
    projection_id: str,
    rule_index: int,
) -> tuple[SemanticScalar, ...]:
    values: list[SemanticScalar] = []
    for key in dynamic.group_by:
        value = path.domain_id if key == "domain_id" else path.attributes.get(key)
        if value is None:
            raise ProjectionError(
                f"path ID {path.path_id} lacks group attribute {key!r} in rule "
                f"{rule_index} of projection {projection_id}"
            )
        values.append(value)
    return tuple(values)


def _dynamic_layer_label(dynamic: DynamicLayerSpec, values: tuple[SemanticScalar, ...]) -> str:
    return " ".join((dynamic.label_prefix, *(str(value) for value in values)))


def _matches(path: SemanticPath, match: MatchSpec) -> bool:
    if match.feature_role is not None and path.feature_role != match.feature_role:
        return False
    for key, allowed_values in match.attributes.items():
        actual = path.attributes.get(key)
        if not any(type(actual) is type(value) and actual == value for value in allowed_values):
            return False
    return True
