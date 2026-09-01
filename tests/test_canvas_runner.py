from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from viz_canvas.design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    VectorPath,
)
from viz_canvas.frames import AffineTransform, CompositionTransform
from viz_canvas.jobs import DomainArtworkJob
from viz_canvas.models import PolygonDomain
from viz_canvas.runner import AlgorithmContext, run_domain_artwork_job
from viz_canvas.semantics import (
    DomainRef,
    DomainRelation,
    PolygonGroup,
    PolygonSurface,
    RelationType,
)


def _domain(domain_id: str, offset: float = 0.0) -> PolygonDomain:
    return PolygonDomain(
        domain_id,
        (
            (offset, offset),
            (offset + 10.0, offset),
            (offset, offset + 10.0),
        ),
    )


def _path(domain_id: str, seed: int, *, frame: str = "domain") -> VectorPath:
    value = float(seed % 10_000)
    return VectorPath(
        points=((value, value), (value + 1.0, value + 1.0)),
        closed=False,
        layer_id="ink",
        domain_id=domain_id,
        coordinate_frame=frame,  # type: ignore[arg-type]
    )


@dataclass
class RecordingAlgorithm:
    name: str = "record"
    capabilities: AlgorithmCapabilities = field(default_factory=AlgorithmCapabilities)
    contexts: list[AlgorithmContext] = field(default_factory=list)
    calls: list[tuple[object, tuple[PolygonDomain, ...], DesignPass]] = field(
        default_factory=list
    )
    returned_frame: str = "domain"
    producing_pass_id: str | None = None
    path_domain_id: str | None = None

    def generate(self, *, canvas, domains, design_pass, context):
        self.contexts.append(context)
        self.calls.append((canvas, domains, design_pass))
        return DesignResult(
            paths=tuple(
                _path(
                    self.path_domain_id or domain.id,
                    context.domain_seeds[domain.id],
                    frame=self.returned_frame,
                )
                for domain in domains
            ),
            derived_domains=(),
            producing_pass_id=self.producing_pass_id or design_pass.id,
        )


def _job(
    domains: tuple[PolygonDomain, ...],
    design_passes: tuple[DesignPass, ...],
    *,
    transforms: tuple[CompositionTransform, ...] = (),
    surfaces: tuple[PolygonSurface, ...] | None = None,
    groups: tuple[PolygonGroup, ...] = (),
    relations: tuple[DomainRelation, ...] = (),
) -> DomainArtworkJob:
    return DomainArtworkJob(
        schema_version=1,
        seed=42,
        domains=domains,
        surfaces=surfaces,
        groups=groups,
        relations=relations,
        composition_transforms=transforms,
        passes=design_passes,
    )


def _paths_for(state, domain_id: str) -> tuple[VectorPath, ...]:
    return tuple(
        path
        for result in state.results
        for path in result.paths
        if path.domain_id == domain_id
    )


def test_independent_results_survive_unrelated_domain_reordering() -> None:
    a = _domain("a")
    b = _domain("b", 20.0)
    extra = _domain("extra", -100.0)
    design_pass = DesignPass("draw", "record", ("a", "b"))

    first = run_domain_artwork_job(_job((a, b), (design_pass,)), {"record": RecordingAlgorithm()})
    second = run_domain_artwork_job(
        _job((extra, b, a), (design_pass,)), {"record": RecordingAlgorithm()}
    )

    assert _paths_for(first, "a") == _paths_for(second, "a")
    assert _paths_for(first, "b") == _paths_for(second, "b")


def test_runner_canvas_is_numeric_source_bounds_carrier() -> None:
    a = _domain("a", -5.0)
    b = _domain("b", 20.0)
    algorithm = RecordingAlgorithm()

    run_domain_artwork_job(
        _job((a, b), (DesignPass("draw", "record", ("a",)),)),
        {"record": algorithm},
    )

    canvas = algorithm.calls[0][0]
    assert canvas.bounds == (-5.0, -5.0, 30.0, 30.0)
    assert canvas.width == 35.0
    assert canvas.height == 35.0
    assert canvas.domains == (a, b)


def test_coordinated_pass_requires_requested_composition_transforms() -> None:
    a = _domain("a")
    b = _domain("b", 20.0)
    coordinated = DesignPass(
        "join",
        "record",
        ("a", "b"),
        parameters={"coordinate_frame": "composition"},
    )

    with pytest.raises(
        ValueError, match="composition transform required for domain: b"
    ):
        run_domain_artwork_job(
            _job(
                (a, b),
                (coordinated,),
                transforms=(CompositionTransform("a", AffineTransform.identity()),),
            ),
            {"record": RecordingAlgorithm(returned_frame="composition")},
        )


def test_coordinated_seed_depends_on_ordered_target_ids() -> None:
    a = _domain("a")
    b = _domain("b", 20.0)
    transforms = tuple(
        CompositionTransform(domain_id, AffineTransform.identity())
        for domain_id in ("a", "b")
    )
    first_algorithm = RecordingAlgorithm(returned_frame="composition")
    second_algorithm = RecordingAlgorithm(returned_frame="composition")

    run_domain_artwork_job(
        _job(
            (a, b),
            (
                DesignPass(
                    "join",
                    "record",
                    ("a", "b"),
                    parameters={"coordinate_frame": "composition"},
                ),
            ),
            transforms=transforms,
        ),
        {"record": first_algorithm},
    )
    run_domain_artwork_job(
        _job(
            (a, b),
            (
                DesignPass(
                    "join",
                    "record",
                    ("b", "a"),
                    parameters={"coordinate_frame": "composition"},
                ),
            ),
            transforms=transforms,
        ),
        {"record": second_algorithm},
    )

    assert first_algorithm.contexts[0].pass_seed != second_algorithm.contexts[0].pass_seed


def test_runner_filters_requested_semantic_context_and_reserved_parameters() -> None:
    a = _domain("a")
    b = _domain("b", 20.0)
    surfaces = (PolygonSurface("surface-a", "a"), PolygonSurface("surface-b", "b"))
    groups = (
        PolygonGroup("first", ("surface-a",)),
        PolygonGroup("second", ("surface-b",)),
    )
    relations = (
        DomainRelation("left", RelationType.ADJACENT, DomainRef("a"), DomainRef("b")),
        DomainRelation("right", RelationType.MIRRORS, DomainRef("b"), DomainRef("a")),
    )
    algorithm = RecordingAlgorithm(returned_frame="composition")
    design_pass = DesignPass(
        "join",
        "record",
        ("b", "a"),
        parameters={"coordinate_frame": "composition", "custom": 7},
        group_context_ids=("second",),
        relation_context_ids=("right",),
    )

    run_domain_artwork_job(
        _job(
            (a, b),
            (design_pass,),
            transforms=(
                CompositionTransform("a", AffineTransform.identity()),
                CompositionTransform("b", AffineTransform.identity()),
            ),
            surfaces=surfaces,
            groups=groups,
            relations=relations,
        ),
        {"record": algorithm},
    )

    context = algorithm.contexts[0]
    received_pass = algorithm.calls[0][2]
    assert context.surfaces == surfaces
    assert [group.id for group in context.groups] == ["second"]
    assert [relation.id for relation in context.relations] == ["right"]
    assert list(context.composition_transforms) == ["b", "a"]
    assert dict(received_pass.parameters) == {"custom": 7}
    assert dict(design_pass.parameters) == {
        "coordinate_frame": "composition",
        "custom": 7,
    }


def test_runner_requires_declared_semantic_context_ids() -> None:
    domain = _domain("a")
    design_pass = DesignPass(
        "draw", "record", ("a",), group_context_ids=("missing",)
    )

    with pytest.raises(ValueError, match="unknown group context: missing"):
        run_domain_artwork_job(
            _job((domain,), (design_pass,)), {"record": RecordingAlgorithm()}
        )


def test_runner_requires_passes_to_follow_dependency_order() -> None:
    domain = _domain("a")
    passes = (
        DesignPass("second", "record", ("a",), depends_on=("first",)),
        DesignPass("first", "record", ("a",)),
    )

    with pytest.raises(ValueError, match="dependency.*first"):
        run_domain_artwork_job(_job((domain,), passes), {"record": RecordingAlgorithm()})


@pytest.mark.parametrize(
    ("parameters", "returned_frame", "expected"),
    [
        ({}, "composition", "domain-local pass returned non-domain path"),
        (
            {"coordinate_frame": "composition"},
            "domain",
            "composition pass returned non-composition path",
        ),
    ],
)
def test_runner_rejects_paths_in_the_wrong_coordinate_frame(
    parameters: dict[str, str], returned_frame: str, expected: str
) -> None:
    domain = _domain("a")
    transforms = (
        (CompositionTransform("a", AffineTransform.identity()),)
        if parameters
        else ()
    )

    with pytest.raises(ValueError, match=expected):
        run_domain_artwork_job(
            _job(
                (domain,),
                (DesignPass("draw", "record", ("a",), parameters=parameters),),
                transforms=transforms,
            ),
            {"record": RecordingAlgorithm(returned_frame=returned_frame)},
        )


@pytest.mark.parametrize(
    ("algorithm", "expected"),
    [
        (RecordingAlgorithm(producing_pass_id="other"), "result pass id does not match"),
        (RecordingAlgorithm(path_domain_id="other"), "undeclared domain: other"),
    ],
)
def test_runner_rejects_result_contract_mismatches(
    algorithm: RecordingAlgorithm, expected: str
) -> None:
    domain = _domain("a")

    with pytest.raises(ValueError, match=expected):
        run_domain_artwork_job(
            _job((domain,), (DesignPass("draw", "record", ("a",)),)),
            {"record": algorithm},
        )
