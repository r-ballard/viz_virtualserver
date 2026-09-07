"""Immutable one-to-many artwork jobs for intrinsic polygon domains."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .design import DesignPass, validate_pass_graph
from .frames import CompositionTransform, resolve_composition_transforms
from .models import PolygonDomain
from .semantics import (
    DomainRelation,
    PolygonGroup,
    PolygonSurface,
    validate_semantics,
)


def derive_domain_seed(job_seed: int, pass_id: str, algorithm: str, domain_id: str) -> int:
    """Derive a stable per-domain seed without depending on collection order."""

    encoded_parts = (
        str(job_seed).encode("utf-8"),
        pass_id.encode("utf-8"),
        algorithm.encode("utf-8"),
        domain_id.encode("utf-8"),
    )
    payload = b"".join(
        len(part).to_bytes(8, byteorder="big", signed=False) + part
        for part in encoded_parts
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big")


@dataclass(frozen=True, slots=True)
class DomainArtworkJob:
    """A validated, immutable declaration of artwork over multiple domains."""

    schema_version: int
    seed: int
    domains: tuple[PolygonDomain, ...]
    surfaces: tuple[PolygonSurface, ...] | None
    groups: tuple[PolygonGroup, ...]
    relations: tuple[DomainRelation, ...]
    composition_transforms: tuple[CompositionTransform, ...]
    passes: tuple[DesignPass, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError(f"unsupported schema version: {self.schema_version!r}")
        domains = tuple(self.domains)
        surfaces = None if self.surfaces is None else tuple(self.surfaces)
        groups = tuple(self.groups)
        relations = tuple(self.relations)
        composition_transforms = tuple(self.composition_transforms)
        passes = tuple(self.passes)

        if not domains:
            raise ValueError("domains collection must not be empty")
        if surfaces is not None and not surfaces:
            raise ValueError("explicit surfaces collection must not be empty")

        resolved_surfaces = (
            tuple(PolygonSurface(domain.id, domain.id) for domain in domains)
            if surfaces is None
            else surfaces
        )
        validate_semantics(
            domains=domains,
            surfaces=resolved_surfaces,
            groups=groups,
            relations=relations,
        )
        validate_pass_graph(passes)
        resolve_composition_transforms(domains, composition_transforms)

        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "surfaces", surfaces)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "composition_transforms", composition_transforms)
        object.__setattr__(self, "passes", passes)

    @property
    def resolved_surfaces(self) -> tuple[PolygonSurface, ...]:
        """Return explicit surfaces or one implicit surface per declared domain."""

        if self.surfaces is not None:
            return self.surfaces
        return tuple(PolygonSurface(domain.id, domain.id) for domain in self.domains)
