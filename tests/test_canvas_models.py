import dataclasses

import pytest
from pydantic import ValidationError

from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import CanvasSpec, DomainProvenance, PolygonDomain


def test_square_requires_equal_dimensions() -> None:
    with pytest.raises(ValidationError, match="width == height"):
        CanvasSpec(shape="square", width=100, height=80)


def test_polygon_requires_points() -> None:
    with pytest.raises(ValidationError, match="at least three points"):
        CanvasSpec(shape="polygon")


def test_polygon_points_must_fit_declared_viewbox() -> None:
    with pytest.raises(ValidationError, match="inside the declared"):
        CanvasSpec(
            shape="polygon",
            width=100,
            height=100,
            points=[(0, 0), (101, 0), (0, 100)],
        )


def test_named_shape_rejects_custom_points() -> None:
    with pytest.raises(ValidationError, match="only be supplied"):
        CanvasSpec(shape="triangle", points=[(0, 0), (1, 0), (0, 1)])


def test_polygon_domain_preserves_declared_vertex_order() -> None:
    vertices = ((10.0, 10.0), (90.0, 10.0), (50.0, 80.0))

    domain = PolygonDomain(id="triangle", vertices=vertices)

    assert domain.vertices == vertices
    assert domain.edge(0) == (vertices[0], vertices[1])
    assert domain.edge(1) == (vertices[1], vertices[2])
    assert domain.edge(2) == (vertices[2], vertices[0])


def test_polygon_domain_is_immutable() -> None:
    domain = PolygonDomain(
        id="triangle",
        vertices=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
    )

    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        domain.id = "changed"


def test_polygon_domain_copies_mutable_vertex_inputs() -> None:
    vertices = [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]]
    domain = PolygonDomain(id="triangle", vertices=vertices)

    vertices[0][0] = 99.0

    assert domain.vertices == ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))
    with pytest.raises(TypeError):
        domain.vertices[0][0] = 99.0


def test_domain_provenance_copies_mutable_source_ids() -> None:
    source_domain_ids = ["source"]
    provenance = DomainProvenance(
        source_domain_ids=source_domain_ids,
        generating_pass_id="pass-a",
        operation="copy",
    )

    source_domain_ids.append("changed")

    assert provenance.source_domain_ids == ("source",)


@pytest.mark.parametrize(
    ("source_domain_ids", "generating_pass_id", "operation", "message"),
    [
        ((), "pass-a", "copy", "at least one source"),
        (("",), "pass-a", "copy", "source domain ids"),
        (("source", "source"), "pass-a", "copy", "duplicate source"),
        (("source",), "", "copy", "generating pass"),
        (("source",), "pass-a", "   ", "operation"),
    ],
)
def test_domain_provenance_rejects_incomplete_identity(
    source_domain_ids: tuple[str, ...],
    generating_pass_id: str,
    operation: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        DomainProvenance(source_domain_ids, generating_pass_id, operation)


@pytest.mark.parametrize(
    ("source_domain_ids", "generating_pass_id", "operation"),
    [
        ((1,), "pass-a", "copy"),
        (("source",), 1, "copy"),
        (("source",), "pass-a", 1),
    ],
)
def test_domain_provenance_rejects_non_string_identity_parts(
    source_domain_ids: object,
    generating_pass_id: object,
    operation: object,
) -> None:
    with pytest.raises(ValueError, match="provenance.*string"):
        DomainProvenance(  # type: ignore[arg-type]
            source_domain_ids,
            generating_pass_id,
            operation,
        )


def test_polygon_domain_accepts_clockwise_and_counterclockwise_order() -> None:
    ccw = PolygonDomain(
        id="ccw",
        vertices=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
    )
    cw = PolygonDomain(
        id="cw",
        vertices=((0.0, 0.0), (0.0, 10.0), (10.0, 0.0)),
    )

    assert ccw.vertices[0] == cw.vertices[0]
    assert ccw.winding != cw.winding


def test_intrinsic_canvas_accepts_overlapping_domains() -> None:
    a = PolygonDomain(
        id="a",
        vertices=((0.0, 0.0), (8.0, 0.0), (0.0, 8.0)),
    )
    b = PolygonDomain(
        id="b",
        vertices=((2.0, 2.0), (10.0, 2.0), (2.0, 10.0)),
    )

    canvas = CanvasGeometry(
        shape="rectangle",
        width=100.0,
        height=100.0,
        polygon=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        up_anchor="edge:0",
        domains=(a, b),
    )

    assert canvas.domains == (a, b)


def test_intrinsic_canvas_rejects_duplicate_domain_ids() -> None:
    a = PolygonDomain(
        id="same",
        vertices=((0.0, 0.0), (8.0, 0.0), (0.0, 8.0)),
    )
    b = PolygonDomain(
        id="same",
        vertices=((2.0, 2.0), (10.0, 2.0), (2.0, 10.0)),
    )

    with pytest.raises(ValueError, match="duplicate domain id"):
        CanvasGeometry(
            shape="rectangle",
            width=100.0,
            height=100.0,
            polygon=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            up_anchor="edge:0",
            domains=(a, b),
        )
