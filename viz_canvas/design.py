from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, Protocol

from .geometry import CanvasGeometry as IntrinsicCanvas
from .json_values import freeze_json_object
from .models import Point, PolygonDomain

if TYPE_CHECKING:
    from .runner import AlgorithmContext


@dataclass(frozen=True, slots=True)
class LogicalLayer:
    id: str
    label: str | None = None


@dataclass(frozen=True, slots=True)
class VectorPath:
    points: tuple[Point, ...]
    closed: bool
    layer_id: str
    domain_id: str
    coordinate_frame: Literal["domain", "composition"] = "domain"
    producing_pass_id: str | None = None

    def __post_init__(self) -> None:
        if not self.domain_id:
            raise ValueError("vector path domain id must not be empty")
        if self.coordinate_frame not in {"domain", "composition"}:
            raise ValueError("unknown vector path coordinate frame")
        if self.producing_pass_id is not None:
            if not isinstance(self.producing_pass_id, str):
                raise ValueError("vector path producing pass id must be a string")
            if not self.producing_pass_id.strip():
                raise ValueError("vector path producing pass id must not be empty")
        points = tuple(tuple(point) for point in self.points)
        if any(len(point) != 2 for point in points):
            raise ValueError("vector path points require exactly two coordinates")
        try:
            finite = all(
                math.isfinite(coordinate)
                for point in points
                for coordinate in point
            )
        except TypeError as exc:
            raise ValueError("vector path coordinates must be numeric") from exc
        if not finite:
            raise ValueError("vector path coordinates must be finite")
        minimum = 3 if self.closed else 2
        if len(points) < minimum:
            kind = "closed" if self.closed else "open"
            count = "three" if self.closed else "two"
            raise ValueError(f"{kind} vector path requires at least {count} points")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True, slots=True)
class AlgorithmCapabilities:
    supports_simple_polygon: bool = True
    supports_concave_polygon: bool = True


@dataclass(frozen=True, slots=True)
class DesignResult:
    paths: tuple[VectorPath, ...]
    derived_domains: tuple[PolygonDomain, ...]
    producing_pass_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.producing_pass_id, str):
            raise ValueError("design result producing pass id must be a string")
        if not self.producing_pass_id.strip():
            raise ValueError("design result producing pass id must not be empty")
        paths = tuple(
            replace(path, producing_pass_id=self.producing_pass_id)
            if path.producing_pass_id is None
            else path
            for path in self.paths
        )
        if any(path.producing_pass_id != self.producing_pass_id for path in paths):
            raise ValueError("vector path producing pass does not match design result")
        derived_domains = tuple(self.derived_domains)
        domain_ids = [domain.id for domain in derived_domains]
        if len(domain_ids) != len(set(domain_ids)):
            raise ValueError("duplicate derived domain id in design result")
        if any(domain.provenance is None for domain in derived_domains):
            raise ValueError("derived domain requires provenance")
        if any(
            domain.provenance is not None
            and domain.provenance.generating_pass_id != self.producing_pass_id
            for domain in derived_domains
        ):
            raise ValueError(
                "derived domain provenance does not match result producing pass"
            )
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "derived_domains", derived_domains)


@dataclass(frozen=True, slots=True)
class DesignPass:
    id: str
    algorithm: str
    target_domain_ids: tuple[str, ...]
    parameters: Mapping[str, object] = field(default_factory=dict)
    logical_layers: tuple[LogicalLayer, ...] = ()
    group_context_ids: tuple[str, ...] = ()
    relation_context_ids: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("design pass id must not be empty")
        if not self.algorithm:
            raise ValueError("design pass algorithm must not be empty")
        target_domain_ids = tuple(self.target_domain_ids)
        if not target_domain_ids:
            raise ValueError("design pass requires at least one target domain")
        if any(not domain_id for domain_id in target_domain_ids):
            raise ValueError("design pass target domain ids must not be empty")
        object.__setattr__(self, "target_domain_ids", target_domain_ids)
        object.__setattr__(
            self,
            "parameters",
            freeze_json_object(self.parameters, context=f"design pass {self.id} parameters"),
        )
        object.__setattr__(self, "logical_layers", tuple(self.logical_layers))
        object.__setattr__(self, "group_context_ids", tuple(self.group_context_ids))
        object.__setattr__(self, "relation_context_ids", tuple(self.relation_context_ids))
        object.__setattr__(self, "depends_on", tuple(self.depends_on))


class DomainAlgorithm(Protocol):
    name: str
    capabilities: AlgorithmCapabilities

    def generate(
        self,
        *,
        canvas: IntrinsicCanvas,
        domains: tuple[PolygonDomain, ...],
        design_pass: DesignPass,
        context: AlgorithmContext,
    ) -> DesignResult: ...


@dataclass(frozen=True, slots=True)
class DesignState:
    source_domains: tuple[PolygonDomain, ...]
    derived_domains: tuple[PolygonDomain, ...] = ()
    results: tuple[DesignResult, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_domains", tuple(self.source_domains))
        object.__setattr__(self, "derived_domains", tuple(self.derived_domains))
        object.__setattr__(self, "results", tuple(self.results))

    def resolve_domain(self, domain_id: str) -> PolygonDomain:
        matches = tuple(
            domain
            for domain in (*self.source_domains, *self.derived_domains)
            if domain.id == domain_id
        )
        if not matches:
            raise ValueError(f"unknown domain: {domain_id}")
        if len(matches) != 1:
            raise ValueError(f"ambiguous domain id: {domain_id}")
        return matches[0]


def _validate_pass_graph(
    passes: Sequence[DesignPass], *, completed_external_ids: set[str]
) -> tuple[DesignPass, ...]:
    passes = tuple(passes)
    pass_ids = [design_pass.id for design_pass in passes]
    if len(pass_ids) != len(set(pass_ids)):
        raise ValueError("duplicate design pass id")

    known_ids = set(pass_ids)
    for design_pass in passes:
        for dependency in design_pass.depends_on:
            if dependency == design_pass.id:
                raise ValueError(f"design pass {design_pass.id} has a self-dependency")
            if dependency not in known_ids and dependency not in completed_external_ids:
                raise ValueError(f"unknown dependency: {dependency}")

    dependencies = {design_pass.id: design_pass.depends_on for design_pass in passes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(pass_id: str) -> None:
        if pass_id in visiting:
            raise ValueError("design pass dependency cycle detected")
        if pass_id in visited:
            return
        visiting.add(pass_id)
        for dependency in dependencies[pass_id]:
            if dependency in known_ids:
                visit(dependency)
        visiting.remove(pass_id)
        visited.add(pass_id)

    for pass_id in pass_ids:
        visit(pass_id)
    return passes


def validate_pass_graph(passes: Sequence[DesignPass]) -> tuple[DesignPass, ...]:
    return _validate_pass_graph(passes, completed_external_ids=set())


def execute_design_pass(
    *,
    canvas: IntrinsicCanvas,
    state: DesignState,
    design_pass: DesignPass,
    algorithms: Mapping[str, DomainAlgorithm],
    context: AlgorithmContext | None = None,
) -> DesignState:
    algorithm = algorithms.get(design_pass.algorithm)
    if algorithm is None:
        raise ValueError(f"unknown algorithm: {design_pass.algorithm}")

    domains = tuple(state.resolve_domain(domain_id) for domain_id in design_pass.target_domain_ids)
    if not algorithm.capabilities.supports_simple_polygon:
        raise ValueError("algorithm does not support simple polygon domains")
    if not algorithm.capabilities.supports_concave_polygon:
        concave = [domain.id for domain in domains if not domain.is_convex]
        if concave:
            raise ValueError(f"algorithm does not support concave domains: {concave}")

    if context is None:
        from .runner import AlgorithmContext

        context = AlgorithmContext(
            job_seed=0,
            pass_seed=0,
            domain_seeds={domain.id: 0 for domain in domains},
            surfaces=(),
            groups=(),
            relations=(),
            composition_transforms={},
        )
    result = algorithm.generate(
        canvas=canvas,
        domains=domains,
        design_pass=design_pass,
        context=context,
    )
    if result.producing_pass_id != design_pass.id:
        raise ValueError("result pass id does not match design pass")

    allowed_path_domains = {
        *design_pass.target_domain_ids,
        *(domain.id for domain in result.derived_domains),
    }
    for path in result.paths:
        if path.domain_id not in allowed_path_domains:
            raise ValueError(f"undeclared domain: {path.domain_id}")

    existing_ids = {
        domain.id for domain in (*state.source_domains, *state.derived_domains)
    }
    for domain in result.derived_domains:
        provenance = domain.provenance
        if provenance is None:  # pragma: no cover - DesignResult validates this
            raise ValueError("derived domain requires provenance")
        for source_domain_id in provenance.source_domain_ids:
            if source_domain_id not in design_pass.target_domain_ids:
                raise ValueError(
                    f"derived domain {domain.id} provenance source is not a pass "
                    f"target: {source_domain_id}"
                )
        if domain.id in existing_ids:
            raise ValueError(f"duplicate derived domain id: {domain.id}")
        existing_ids.add(domain.id)

    return DesignState(
        source_domains=state.source_domains,
        derived_domains=(*state.derived_domains, *result.derived_domains),
        results=(*state.results, result),
    )


def execute_design_passes(
    *,
    canvas: IntrinsicCanvas,
    state: DesignState,
    passes: Sequence[DesignPass],
    algorithms: Mapping[str, DomainAlgorithm],
) -> DesignState:
    completed = {result.producing_pass_id for result in state.results}
    passes = _validate_pass_graph(passes, completed_external_ids=completed)
    current = state
    for design_pass in passes:
        missing = tuple(
            dependency for dependency in design_pass.depends_on if dependency not in completed
        )
        if missing:
            raise ValueError(
                f"design pass {design_pass.id} dependency not completed: {missing}"
            )
        current = execute_design_pass(
            canvas=canvas,
            state=current,
            design_pass=design_pass,
            algorithms=algorithms,
        )
        completed.add(current.results[-1].producing_pass_id)
    return current
