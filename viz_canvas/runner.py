"""Deterministic execution of artwork jobs over polygon domains."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .design import DesignPass, DesignState, DomainAlgorithm, execute_design_pass
from .frames import AffineTransform, resolve_composition_transforms
from .geometry import CanvasGeometry
from .jobs import DomainArtworkJob, derive_domain_seed
from .semantics import DomainRelation, PolygonGroup, PolygonSurface


@dataclass(frozen=True, slots=True)
class AlgorithmContext:
    job_seed: int
    pass_seed: int
    domain_seeds: Mapping[str, int]
    surfaces: tuple[PolygonSurface, ...]
    groups: tuple[PolygonGroup, ...]
    relations: tuple[DomainRelation, ...]
    composition_transforms: Mapping[str, AffineTransform]

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain_seeds", MappingProxyType(dict(self.domain_seeds)))
        object.__setattr__(self, "surfaces", tuple(self.surfaces))
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(
            self,
            "composition_transforms",
            MappingProxyType(dict(self.composition_transforms)),
        )


def run_domain_artwork_job(
    job: DomainArtworkJob,
    algorithms: Mapping[str, DomainAlgorithm],
) -> DesignState:
    canvas = _source_bounds_canvas(job)
    all_transforms = resolve_composition_transforms(
        job.domains, job.composition_transforms
    )
    state = DesignState(source_domains=job.domains)
    completed: set[str] = set()

    for design_pass in job.passes:
        missing = tuple(
            dependency
            for dependency in design_pass.depends_on
            if dependency not in completed
        )
        if missing:
            raise ValueError(
                f"design pass {design_pass.id} dependency not completed: {missing}"
            )

        algorithm_pass, coordinated = _algorithm_pass(design_pass)
        if coordinated:
            derived_ids = {domain.id for domain in state.derived_domains}
            for domain_id in design_pass.target_domain_ids:
                if domain_id in derived_ids:
                    raise ValueError(
                        "composition frame is unavailable for derived target domain: "
                        f"{domain_id}"
                    )
        context = _algorithm_context(
            job=job,
            design_pass=design_pass,
            coordinated=coordinated,
            all_transforms=all_transforms,
        )
        state = execute_design_pass(
            canvas=canvas,
            state=state,
            design_pass=algorithm_pass,
            algorithms=algorithms,
            context=context,
        )
        result = state.results[-1]
        if coordinated:
            new_derived_ids = {domain.id for domain in result.derived_domains}
            for path in result.paths:
                if path.domain_id in new_derived_ids:
                    raise ValueError(
                        "coordinated pass cannot return a path owned by derived "
                        f"domain without a declared composition transform: {path.domain_id}"
                    )
        expected_frame = "composition" if coordinated else "domain"
        for path in result.paths:
            if path.coordinate_frame != expected_frame:
                pass_kind = "composition" if coordinated else "domain-local"
                raise ValueError(
                    f"{pass_kind} pass returned non-{expected_frame} path: "
                    f"{path.domain_id}"
                )
        completed.add(design_pass.id)

    return state


def _source_bounds_canvas(job: DomainArtworkJob) -> CanvasGeometry:
    vertices = tuple(vertex for domain in job.domains for vertex in domain.vertices)
    min_x = min(vertex[0] for vertex in vertices)
    min_y = min(vertex[1] for vertex in vertices)
    max_x = max(vertex[0] for vertex in vertices)
    max_y = max(vertex[1] for vertex in vertices)
    return CanvasGeometry(
        shape="rectangle",
        width=max_x - min_x,
        height=max_y - min_y,
        polygon=(
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
        ),
        up_anchor="edge:0",
        domains=job.domains,
    )


def _algorithm_pass(design_pass: DesignPass) -> tuple[DesignPass, bool]:
    parameters = dict(design_pass.parameters)
    coordinate_frame = parameters.pop("coordinate_frame", "domain")
    if coordinate_frame not in {"domain", "composition"}:
        raise ValueError(
            "coordinate_frame must be exactly 'domain' or 'composition'"
        )
    return dataclasses.replace(design_pass, parameters=parameters), (
        coordinate_frame == "composition"
    )


def _algorithm_context(
    *,
    job: DomainArtworkJob,
    design_pass: DesignPass,
    coordinated: bool,
    all_transforms: Mapping[str, AffineTransform],
) -> AlgorithmContext:
    groups = _requested_by_id(
        job.groups,
        design_pass.group_context_ids,
        kind="group",
    )
    relations = _requested_by_id(
        job.relations,
        design_pass.relation_context_ids,
        kind="relation",
    )
    transforms: dict[str, AffineTransform] = {}
    if coordinated:
        for domain_id in design_pass.target_domain_ids:
            transform = all_transforms.get(domain_id)
            if transform is None:
                raise ValueError(
                    f"composition transform required for domain: {domain_id}"
                )
            transforms[domain_id] = transform

    domain_seeds = {
        domain_id: derive_domain_seed(
            job.seed,
            design_pass.id,
            design_pass.algorithm,
            domain_id,
        )
        for domain_id in design_pass.target_domain_ids
    }
    return AlgorithmContext(
        job_seed=job.seed,
        pass_seed=_derive_pass_seed(job.seed, design_pass),
        domain_seeds=domain_seeds,
        surfaces=job.resolved_surfaces,
        groups=groups,
        relations=relations,
        composition_transforms=transforms,
    )


def _requested_by_id(items, requested_ids: tuple[str, ...], *, kind: str):
    by_id = {item.id: item for item in items}
    requested = []
    for item_id in requested_ids:
        item = by_id.get(item_id)
        if item is None:
            raise ValueError(f"unknown {kind} context: {item_id}")
        requested.append(item)
    return tuple(requested)


def _derive_pass_seed(job_seed: int, design_pass: DesignPass) -> int:
    parts = (
        str(job_seed),
        design_pass.id,
        design_pass.algorithm,
        *design_pass.target_domain_ids,
    )
    payload = b"".join(
        len(encoded).to_bytes(8, byteorder="big", signed=False) + encoded
        for part in parts
        for encoded in (part.encode("utf-8"),)
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big")
