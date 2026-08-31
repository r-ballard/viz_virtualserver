"""Versioned JSON loading for immutable polygon artwork jobs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from .design import DesignPass, LogicalLayer
from .frames import AffineTransform, CompositionTransform
from .jobs import DomainArtworkJob
from .models import PolygonDomain
from .semantics import (
    DomainRef,
    DomainRelation,
    FeatureRef,
    FeatureType,
    PolygonGroup,
    PolygonSurface,
    RelationEndpoint,
    RelationType,
)


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _DomainRequest(_RequestModel):
    id: str
    vertices: list[tuple[float, float]]


class _FeatureRefRequest(_RequestModel):
    domain_id: str
    feature_type: FeatureType
    index: int


class _RelationEndpointRequest(_RequestModel):
    domain_id: str
    feature_type: FeatureType | None = None
    index: int | None = None

    @model_validator(mode="before")
    @classmethod
    def require_complete_feature_reference(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        feature_fields = {"feature_type", "index"}
        if feature_fields & value.keys() and not feature_fields <= value.keys():
            raise ValueError("feature relation endpoints require feature_type and index")
        if feature_fields <= value.keys() and (
            value["feature_type"] is None or value["index"] is None
        ):
            raise ValueError("feature relation endpoint feature_type and index must not be null")
        return value

    def to_endpoint(self) -> RelationEndpoint:
        if self.feature_type is None:
            return DomainRef(self.domain_id)
        if self.index is None:
            raise ValueError("feature relation endpoints require feature_type and index")
        return FeatureRef(self.domain_id, self.feature_type, self.index)


class _SurfaceRequest(_RequestModel):
    id: str
    domain_id: str
    feature_aliases: dict[str, _FeatureRefRequest] = Field(default_factory=dict)


class _GroupRequest(_RequestModel):
    id: str
    surface_ids: list[str]
    seed: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class _RelationRequest(_RequestModel):
    id: str
    relation_type: RelationType
    source: _RelationEndpointRequest
    target: _RelationEndpointRequest
    metadata: dict[str, object] = Field(default_factory=dict)


class _CompositionTransformRequest(_RequestModel):
    domain_id: str
    matrix: tuple[float, float, float, float, float, float]

    @field_validator("matrix", mode="before")
    @classmethod
    def reject_boolean_entries(cls, value: object) -> object:
        if isinstance(value, (list, tuple)) and any(
            isinstance(entry, bool) for entry in value
        ):
            raise ValueError("matrix entries must be numeric and cannot be boolean")
        return value


class _LogicalLayerRequest(_RequestModel):
    id: str
    label: str | None = None


class _PassRequest(_RequestModel):
    id: str
    algorithm: str
    target_domain_ids: list[str]
    parameters: dict[str, object] = Field(default_factory=dict)
    logical_layers: list[_LogicalLayerRequest] = Field(default_factory=list)
    group_context_ids: list[str] = Field(default_factory=list)
    relation_context_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class _JobRequest(_RequestModel):
    schema_version: StrictInt
    seed: int
    domains: list[_DomainRequest]
    surfaces: list[_SurfaceRequest] | None = None
    groups: list[_GroupRequest]
    relations: list[_RelationRequest]
    composition_transforms: list[_CompositionTransformRequest]
    passes: list[_PassRequest]

    @model_validator(mode="after")
    def require_supported_schema_version(self) -> Self:
        if self.schema_version != 1:
            raise ValueError(f"unsupported schema version: {self.schema_version}")
        return self


def _to_feature_ref(request: _FeatureRefRequest) -> FeatureRef:
    return FeatureRef(request.domain_id, request.feature_type, request.index)


def load_domain_artwork_job(payload: Mapping[str, object]) -> DomainArtworkJob:
    """Parse a schema-versioned JSON-compatible payload into an immutable job."""

    request = _JobRequest.model_validate(payload)
    surfaces = (
        None
        if request.surfaces is None
        else tuple(
            PolygonSurface(
                id=surface.id,
                domain_id=surface.domain_id,
                feature_aliases={
                    alias: _to_feature_ref(reference)
                    for alias, reference in surface.feature_aliases.items()
                },
            )
            for surface in request.surfaces
        )
    )
    return DomainArtworkJob(
        schema_version=request.schema_version,
        seed=request.seed,
        domains=tuple(
            PolygonDomain(id=domain.id, vertices=domain.vertices)
            for domain in request.domains
        ),
        surfaces=surfaces,
        groups=tuple(
            PolygonGroup(
                id=group.id,
                surface_ids=group.surface_ids,
                seed=group.seed,
                metadata=group.metadata,
            )
            for group in request.groups
        ),
        relations=tuple(
            DomainRelation(
                id=relation.id,
                relation_type=relation.relation_type,
                source=relation.source.to_endpoint(),
                target=relation.target.to_endpoint(),
                metadata=relation.metadata,
            )
            for relation in request.relations
        ),
        composition_transforms=tuple(
            CompositionTransform(
                domain_id=transform.domain_id,
                transform=AffineTransform(*transform.matrix),
            )
            for transform in request.composition_transforms
        ),
        passes=tuple(
            DesignPass(
                id=design_pass.id,
                algorithm=design_pass.algorithm,
                target_domain_ids=design_pass.target_domain_ids,
                parameters=design_pass.parameters,
                logical_layers=tuple(
                    LogicalLayer(id=layer.id, label=layer.label)
                    for layer in design_pass.logical_layers
                ),
                group_context_ids=design_pass.group_context_ids,
                relation_context_ids=design_pass.relation_context_ids,
                depends_on=design_pass.depends_on,
            )
            for design_pass in request.passes
        ),
    )


def read_domain_artwork_job(path: Path) -> DomainArtworkJob:
    """Read a JSON file and load its polygon artwork job."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return load_domain_artwork_job(payload)
