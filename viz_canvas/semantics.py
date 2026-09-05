from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from .json_values import freeze_json_object
from .models import PolygonDomain


class FeatureType(StrEnum):
    VERTEX = "vertex"
    EDGE = "edge"


@dataclass(frozen=True, slots=True)
class DomainRef:
    domain_id: str


@dataclass(frozen=True, slots=True)
class FeatureRef:
    domain_id: str
    feature_type: FeatureType
    index: int


class RelationType(StrEnum):
    ADJACENT = "adjacent"
    CORRESPONDS_TO = "corresponds_to"
    ALIGNED_WITH = "aligned_with"
    MIRRORS = "mirrors"
    CONTINUES_TO = "continues_to"
    CONTAINS = "contains"
    OVERLAPS = "overlaps"


RelationEndpoint = DomainRef | FeatureRef


@dataclass(frozen=True, slots=True)
class PolygonSurface:
    id: str
    domain_id: str
    feature_aliases: Mapping[str, FeatureRef] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "feature_aliases", MappingProxyType(dict(self.feature_aliases))
        )


@dataclass(frozen=True, slots=True)
class PolygonGroup:
    id: str
    surface_ids: tuple[str, ...]
    seed: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_ids", tuple(self.surface_ids))
        object.__setattr__(
            self,
            "metadata",
            freeze_json_object(self.metadata, context=f"group {self.id} metadata"),
        )


@dataclass(frozen=True, slots=True)
class DomainRelation:
    id: str
    relation_type: RelationType
    source: RelationEndpoint
    target: RelationEndpoint
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            freeze_json_object(self.metadata, context=f"relation {self.id} metadata"),
        )


class _HasId(Protocol):
    id: str


def _unique_by_id[T: _HasId](items: Sequence[T], kind: str) -> dict[str, T]:
    by_id: dict[str, T] = {}
    for item in items:
        if not item.id:
            raise ValueError(f"{kind} id must not be empty")
        if item.id in by_id:
            raise ValueError(f"duplicate {kind} id: {item.id}")
        by_id[item.id] = item
    return by_id


def _validate_feature_ref(
    ref: FeatureRef, domain: PolygonDomain, *, context: str
) -> None:
    if not isinstance(ref.feature_type, FeatureType):
        raise ValueError(
            f"{context} has invalid feature type: {ref.feature_type!r}"
        )
    if ref.index < 0 or ref.index >= len(domain.vertices):
        raise ValueError(
            f"{context} has {ref.feature_type.value} index out of range for domain "
            f"{domain.id}: {ref.index}"
        )


def _validate_endpoint(
    endpoint: RelationEndpoint,
    domain_by_id: Mapping[str, PolygonDomain],
    *,
    relation_id: str,
    role: str,
) -> None:
    if not isinstance(endpoint, (DomainRef, FeatureRef)):
        raise ValueError(f"relation {relation_id} has invalid {role} endpoint")
    domain = domain_by_id.get(endpoint.domain_id)
    if domain is None:
        raise ValueError(
            f"relation {relation_id} references unknown domain: {endpoint.domain_id}"
        )
    if isinstance(endpoint, FeatureRef):
        _validate_feature_ref(endpoint, domain, context=f"relation {relation_id}")


def validate_semantics(
    *,
    domains: Sequence[PolygonDomain],
    surfaces: Sequence[PolygonSurface],
    groups: Sequence[PolygonGroup],
    relations: Sequence[DomainRelation],
) -> None:
    domain_by_id = _unique_by_id(domains, "domain")
    surface_by_id = _unique_by_id(surfaces, "surface")
    _unique_by_id(groups, "group")
    _unique_by_id(relations, "relation")

    for surface in surfaces:
        domain = domain_by_id.get(surface.domain_id)
        if domain is None:
            raise ValueError(f"unknown domain: {surface.domain_id}")
        for alias, ref in surface.feature_aliases.items():
            if not isinstance(ref, FeatureRef):
                raise ValueError(
                    f"surface {surface.id} alias {alias!r} is not a FeatureRef"
                )
            if ref.domain_id != surface.domain_id:
                raise ValueError(
                    f"surface {surface.id} alias {alias!r} references another domain"
                )
            _validate_feature_ref(
                ref, domain, context=f"surface {surface.id} alias {alias!r}"
            )

    for group in groups:
        for surface_id in group.surface_ids:
            if surface_id not in surface_by_id:
                raise ValueError(
                    f"group {group.id} references unknown surface: {surface_id}"
                )

    for relation in relations:
        if not isinstance(relation.relation_type, RelationType):
            raise ValueError(
                f"relation {relation.id} has invalid relation type: "
                f"{relation.relation_type!r}"
            )
        _validate_endpoint(
            relation.source,
            domain_by_id,
            relation_id=relation.id,
            role="source",
        )
        _validate_endpoint(
            relation.target,
            domain_by_id,
            relation_id=relation.id,
            role="target",
        )
