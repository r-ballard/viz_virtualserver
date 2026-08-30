import dataclasses
from types import MappingProxyType

import pytest

from viz_canvas.design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    DesignState,
    LogicalLayer,
    VectorPath,
    execute_design_pass,
    execute_design_passes,
    validate_pass_graph,
)
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import DomainProvenance, PolygonDomain


def make_domain(domain_id: str, *, concave: bool = False) -> PolygonDomain:
    vertices = (
        ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (2.0, 2.0), (0.0, 4.0))
        if concave
        else ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
    )
    return PolygonDomain(id=domain_id, vertices=vertices)


def make_derived_domain(domain_id: str, producing_pass_id: str) -> PolygonDomain:
    return dataclasses.replace(
        make_domain(domain_id),
        provenance=DomainProvenance(("source",), producing_pass_id, "copy-for-test"),
    )


def make_canvas(*domains: PolygonDomain) -> CanvasGeometry:
    return CanvasGeometry(
        shape="rectangle",
        width=10.0,
        height=10.0,
        polygon=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        up_anchor="edge:0",
        domains=domains,
    )


class RecordingAlgorithm:
    name = "record"
    capabilities = AlgorithmCapabilities()

    def __init__(self, result: DesignResult | None = None) -> None:
        self.result = result
        self.calls = []

    def generate(self, *, canvas, domains, design_pass):
        self.calls.append((canvas, domains, design_pass))
        return self.result or DesignResult((), (), design_pass.id)


class DomainAttributionAlgorithm:
    name = "attribute"
    capabilities = AlgorithmCapabilities()

    def generate(self, *, canvas, domains, design_pass):
        del canvas
        return DesignResult(
            paths=tuple(
                VectorPath(
                    points=(domain.vertices[0], domain.vertices[1]),
                    closed=False,
                    layer_id=f"artwork-{domain.id}",
                    domain_id=domain.id,
                )
                for domain in domains
            ),
            derived_domains=(),
            producing_pass_id=design_pass.id,
        )


def test_vector_path_defensively_copies_points() -> None:
    points = [[10.0, 20.0], [30.0, 40.0]]
    path = VectorPath(points=points, closed=False, layer_id="linework", domain_id="source")
    points[0][0] = 99.0
    assert path.points == ((10.0, 20.0), (30.0, 40.0))


def test_vector_path_requires_a_domain_id() -> None:
    with pytest.raises(ValueError, match="domain id must not be empty"):
        VectorPath(
            points=((0, 0), (1, 1)),
            closed=False,
            layer_id="ink",
            domain_id="",
        )


def test_vector_path_rejects_unknown_coordinate_frame() -> None:
    with pytest.raises(ValueError, match="coordinate frame"):
        VectorPath(
            points=((0, 0), (1, 1)),
            closed=False,
            layer_id="ink",
            domain_id="target",
            coordinate_frame="physical",
        )


@pytest.mark.parametrize(
    ("points", "closed", "message"),
    [([[0.0, 0.0]], False, "at least two"), ([[0.0, 0.0], [1.0, 0.0]], True, "at least three")],
)
def test_vector_path_rejects_too_few_points(points, closed, message) -> None:
    with pytest.raises(ValueError, match=message):
        VectorPath(points=points, closed=closed, layer_id="layer", domain_id="source")


@pytest.mark.parametrize("point", [[0.0], [0.0, 1.0, 2.0]])
def test_vector_path_rejects_coordinates_without_exactly_two_values(point) -> None:
    with pytest.raises(ValueError, match="exactly two coordinates"):
        VectorPath(
            points=[point, [3.0, 4.0]],
            closed=False,
            layer_id="layer",
            domain_id="source",
        )


def test_design_result_is_neutral_and_copies_sequences() -> None:
    paths = [VectorPath(((10.0, 20.0), (30.0, 40.0)), False, "linework", "source")]
    result = DesignResult(paths, [], "pass-a")
    paths.clear()
    assert result.paths[0].points == ((10.0, 20.0), (30.0, 40.0))
    assert not hasattr(result, "svg")


def test_multiple_paths_can_share_or_use_different_logical_layers() -> None:
    result = DesignResult(
        paths=(
            VectorPath(((0.0, 0.0), (10.0, 0.0)), False, "shared", "source"),
            VectorPath(((0.0, 1.0), (10.0, 1.0)), False, "shared", "source"),
            VectorPath(((0.0, 2.0), (10.0, 2.0)), False, "accent", "source"),
        ),
        derived_domains=(),
        producing_pass_id="pass-a",
    )
    assert [path.layer_id for path in result.paths] == ["shared", "shared", "accent"]


def test_design_result_requires_unique_derived_domain_ids() -> None:
    with pytest.raises(ValueError, match="duplicate derived domain id"):
        DesignResult((), (make_domain("same"), make_domain("same")), "pass-a")


def test_design_result_requires_provenance_for_derived_domains() -> None:
    with pytest.raises(ValueError, match="derived domain requires provenance"):
        DesignResult((), (make_domain("derived"),), "pass-a")


def test_design_pass_copies_inputs_and_preserves_nested_parameter_types() -> None:
    targets = ["b", "a"]
    weights = [1, 2]
    options = {"weights": weights}
    parameters = {"options": options, "choices": {1, 2}, "span": range(3)}
    design_pass = DesignPass(
        "pass-a",
        "fake",
        targets,
        parameters=parameters,
        logical_layers=[LogicalLayer("ink")],
        group_context_ids=["group"],
        relation_context_ids=["relation"],
        depends_on=["prior"],
    )
    targets.reverse()
    parameters["new"] = True
    assert design_pass.target_domain_ids == ("b", "a")
    assert "new" not in design_pass.parameters
    assert isinstance(design_pass.parameters, MappingProxyType)
    assert design_pass.parameters["options"] is options
    assert isinstance(design_pass.parameters["options"], dict)
    assert design_pass.parameters["options"]["weights"] is weights
    assert isinstance(design_pass.parameters["choices"], set)
    assert isinstance(design_pass.parameters["span"], range)
    with pytest.raises(TypeError):
        design_pass.parameters["new"] = True
    with pytest.raises(dataclasses.FrozenInstanceError):
        design_pass.algorithm = "changed"


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"id": "", "algorithm": "fake", "target_domain_ids": ("a",)}, "id"),
        ({"id": "a", "algorithm": "", "target_domain_ids": ("a",)}, "algorithm"),
        ({"id": "a", "algorithm": "fake", "target_domain_ids": ()}, "at least one"),
        ({"id": "a", "algorithm": "fake", "target_domain_ids": ("",)}, "target"),
    ],
)
def test_design_pass_rejects_invalid_identity_or_targets(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        DesignPass(**kwargs)


def test_validate_pass_graph_preserves_order_and_accepts_explicit_dependencies() -> None:
    passes = (
        DesignPass("second", "fake", ("source",), depends_on=("first",)),
        DesignPass("first", "fake", ("source",)),
    )
    assert validate_pass_graph(passes) == passes


@pytest.mark.parametrize(
    "passes, message",
    [
        ((DesignPass("a", "x", ("d",)), DesignPass("a", "x", ("d",))), "duplicate"),
        ((DesignPass("a", "x", ("d",), depends_on=("missing",)),), "unknown"),
        ((DesignPass("a", "x", ("d",), depends_on=("a",)),), "self"),
        (
            (
                DesignPass("a", "x", ("d",), depends_on=("b",)),
                DesignPass("b", "x", ("d",), depends_on=("a",)),
            ),
            "cycle",
        ),
    ],
)
def test_validate_pass_graph_rejects_invalid_graphs(passes, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_pass_graph(passes)


def test_design_state_copies_inputs_and_resolves_exact_ids() -> None:
    source = make_domain("Source")
    sources = [source]
    state = DesignState(source_domains=sources)
    sources.clear()
    assert state.resolve_domain("Source") is source
    with pytest.raises(ValueError, match="unknown domain"):
        state.resolve_domain("source")


def test_design_state_rejects_ambiguous_resolution() -> None:
    state = DesignState((make_domain("same"),), (make_domain("same"),))
    with pytest.raises(ValueError, match="ambiguous"):
        state.resolve_domain("same")


@pytest.mark.parametrize(
    "capabilities, message",
    [
        (AlgorithmCapabilities(supports_simple_polygon=False), "simple polygon"),
        (AlgorithmCapabilities(supports_concave_polygon=False), "concave"),
    ],
)
def test_execute_pass_rejects_unsupported_capability(capabilities, message) -> None:
    domain = make_domain("target", concave=True)
    algorithm = RecordingAlgorithm()
    algorithm.capabilities = capabilities
    with pytest.raises(ValueError, match=message):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=DesignState((domain,)),
            design_pass=DesignPass("pass-a", "record", ("target",)),
            algorithms={"record": algorithm},
        )
    assert algorithm.calls == []


def test_execute_pass_uses_exact_algorithm_and_domain_ids() -> None:
    domain = make_domain("Target")
    state = DesignState((domain,))
    with pytest.raises(ValueError, match="unknown algorithm"):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=state,
            design_pass=DesignPass("a", "Record", ("Target",)),
            algorithms={"record": RecordingAlgorithm()},
        )
    with pytest.raises(ValueError, match="unknown domain"):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=state,
            design_pass=DesignPass("a", "record", ("target",)),
            algorithms={"record": RecordingAlgorithm()},
        )


def test_execute_pass_delivers_target_domains_in_declared_order() -> None:
    domain_a = make_domain("a")
    domain_b = make_domain("b")
    algorithm = RecordingAlgorithm()
    execute_design_pass(
        canvas=make_canvas(domain_a, domain_b),
        state=DesignState((domain_a, domain_b)),
        design_pass=DesignPass("pass-a", "record", ("b", "a")),
        algorithms={"record": algorithm},
    )
    assert algorithm.calls[0][1] == (domain_b, domain_a)


def test_execute_pass_does_not_union_or_reorder_overlapping_target_domains() -> None:
    domain_a = PolygonDomain(
        "a", ((0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0))
    )
    domain_b = PolygonDomain(
        "b", ((4.0, 2.0), (8.0, 2.0), (8.0, 8.0), (4.0, 8.0))
    )
    before = (domain_a.vertices, domain_b.vertices)

    state = execute_design_pass(
        canvas=make_canvas(domain_a, domain_b),
        state=DesignState((domain_a, domain_b)),
        design_pass=DesignPass("both", "attribute", ("a", "b")),
        algorithms={"attribute": DomainAttributionAlgorithm()},
    )

    assert [path.layer_id for path in state.results[0].paths] == [
        "artwork-a",
        "artwork-b",
    ]
    assert [path.points for path in state.results[0].paths] == [
        ((0.0, 0.0), (6.0, 0.0)),
        ((4.0, 2.0), (8.0, 2.0)),
    ]
    assert (domain_a.vertices, domain_b.vertices) == before


def test_separate_passes_do_not_clip_or_mutate_overlapping_source_domains() -> None:
    domain_a = PolygonDomain(
        "a", ((0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0))
    )
    domain_b = PolygonDomain(
        "b", ((4.0, 2.0), (8.0, 2.0), (8.0, 8.0), (4.0, 8.0))
    )
    before = (domain_a.vertices, domain_b.vertices)

    state = execute_design_passes(
        canvas=make_canvas(domain_a, domain_b),
        state=DesignState((domain_a, domain_b)),
        passes=(
            DesignPass("pass-a", "attribute", ("a",)),
            DesignPass("pass-b", "attribute", ("b",)),
        ),
        algorithms={"attribute": DomainAttributionAlgorithm()},
    )

    assert [result.producing_pass_id for result in state.results] == [
        "pass-a",
        "pass-b",
    ]
    assert [result.paths[0].layer_id for result in state.results] == [
        "artwork-a",
        "artwork-b",
    ]
    assert [result.paths[0].points for result in state.results] == [
        ((0.0, 0.0), (6.0, 0.0)),
        ((4.0, 2.0), (8.0, 2.0)),
    ]
    assert state.source_domains == (domain_a, domain_b)
    assert (domain_a.vertices, domain_b.vertices) == before


def test_execute_pass_requires_matching_result_pass_id() -> None:
    domain = make_domain("source")
    algorithm = RecordingAlgorithm(DesignResult((), (), "other"))
    with pytest.raises(ValueError, match="does not match"):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=DesignState((domain,)),
            design_pass=DesignPass("pass-a", "record", ("source",)),
            algorithms={"record": algorithm},
        )


def test_design_executor_rejects_path_for_undeclared_domain() -> None:
    domain = make_domain("target")
    algorithm = RecordingAlgorithm(
        DesignResult(
            paths=(VectorPath(((0, 0), (1, 1)), False, "ink", "other"),),
            derived_domains=(),
            producing_pass_id="pass-1",
        )
    )

    with pytest.raises(ValueError, match="undeclared domain: other"):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=DesignState((domain,)),
            design_pass=DesignPass("pass-1", "record", ("target",)),
            algorithms={"record": algorithm},
        )


def test_execute_pass_rejects_derived_collision_without_mutating_state_or_domain() -> None:
    domain = make_domain("source")
    state = DesignState((domain,))
    algorithm = RecordingAlgorithm(
        DesignResult((), (make_derived_domain("source", "pass-a"),), "pass-a")
    )
    before = domain.vertices
    with pytest.raises(ValueError, match="duplicate derived domain id"):
        execute_design_pass(
            canvas=make_canvas(domain),
            state=state,
            design_pass=DesignPass("pass-a", "record", ("source",)),
            algorithms={"record": algorithm},
        )
    assert domain.vertices == before
    assert state.derived_domains == ()
    assert state.results == ()


def test_sequential_passes_reject_the_same_derived_domain_id() -> None:
    source = make_domain("source")
    first = RecordingAlgorithm(
        DesignResult((), (make_derived_domain("shared-derived", "first"),), "first")
    )
    second = RecordingAlgorithm(
        DesignResult((), (make_derived_domain("shared-derived", "second"),), "second")
    )

    with pytest.raises(
        ValueError, match="duplicate derived domain id: shared-derived"
    ):
        execute_design_passes(
            canvas=make_canvas(source),
            state=DesignState((source,)),
            passes=(
                DesignPass("first", "first-derive", ("source",)),
                DesignPass(
                    "second",
                    "second-derive",
                    ("source",),
                    depends_on=("first",),
                ),
            ),
            algorithms={"first-derive": first, "second-derive": second},
        )


def test_sequential_execution_requires_list_order_to_satisfy_dependencies() -> None:
    domain = make_domain("source")
    passes = (
        DesignPass("second", "record", ("source",), depends_on=("first",)),
        DesignPass("first", "record", ("source",)),
    )
    with pytest.raises(ValueError, match="dependency.*first"):
        execute_design_passes(
            canvas=make_canvas(domain),
            state=DesignState((domain,)),
            passes=passes,
            algorithms={"record": RecordingAlgorithm()},
        )


def test_unknown_dependency_is_not_satisfied_by_an_earlier_list_item() -> None:
    source = make_domain("source")
    passes = (
        DesignPass("unrelated", "record", ("source",)),
        DesignPass("consumer", "record", ("source",), depends_on=("missing",)),
    )

    with pytest.raises(ValueError, match="unknown dependency: missing"):
        execute_design_passes(
            canvas=make_canvas(source),
            state=DesignState((source,)),
            passes=passes,
            algorithms={"record": RecordingAlgorithm()},
        )


def test_completed_dependencies_come_from_existing_result_pass_ids() -> None:
    source = make_domain("source")
    algorithm = RecordingAlgorithm()
    state = DesignState(
        (source,),
        results=(DesignResult((), (), "producer"),),
    )

    final_state = execute_design_passes(
        canvas=make_canvas(source),
        state=state,
        passes=(
            DesignPass(
                "consumer", "record", ("source",), depends_on=("producer",)
            ),
        ),
        algorithms={"record": algorithm},
    )

    assert [call[2].id for call in algorithm.calls] == ["consumer"]
    assert [result.producing_pass_id for result in final_state.results] == [
        "producer",
        "consumer",
    ]


def test_sequential_execution_resolves_derived_domains_and_preserves_provenance() -> None:
    source = make_domain("source")
    source_vertices = source.vertices
    provenance = DomainProvenance(("source",), "first", "copy")
    derived = PolygonDomain(
        id="derived-from-source",
        vertices=source.vertices,
        provenance=provenance,
    )
    first = RecordingAlgorithm(DesignResult((), (derived,), "first"))
    second = RecordingAlgorithm()
    state = execute_design_passes(
        canvas=make_canvas(source),
        state=DesignState((source,)),
        passes=(
            DesignPass("first", "derive", ("source",)),
            DesignPass(
                "second",
                "record",
                ("derived-from-source",),
                depends_on=("first",),
            ),
        ),
        algorithms={"derive": first, "record": second},
    )
    assert second.calls[0][1] == (derived,)
    assert state.resolve_domain("derived-from-source") is derived
    assert state.resolve_domain("derived-from-source").provenance == DomainProvenance(
        ("source",), "first", "copy"
    )
    assert state.source_domains == (source,)
    assert source.vertices == source_vertices
    assert source.provenance is None
    assert [result.producing_pass_id for result in state.results] == ["first", "second"]
