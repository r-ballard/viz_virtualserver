import math
import random

import pytest

from viz_canvas.geometry import (
    CanvasError,
    build_canvas,
    is_convex_polygon,
    polygon_centroid,
    polygon_edges,
    polygon_winding,
    validate_simple_polygon,
)
from viz_canvas.models import CanvasSpec


def test_triangle_defaults_to_apex_up() -> None:
    canvas = build_canvas(CanvasSpec(shape="triangle", width=100, height=80))

    assert canvas.polygon == ((50.0, 0.0), (100.0, 80.0), (0.0, 80.0))
    assert canvas.up_anchor == "vertex:0"
    assert canvas.centroid == pytest.approx((50.0, 160.0 / 3.0))
    assert canvas.up_vector == pytest.approx((0.0, -1.0))


def test_square_can_declare_corner_up() -> None:
    canvas = build_canvas(
        CanvasSpec(shape="square", width=100, height=100, up_anchor="vertex:0")
    )

    expected = -1.0 / math.sqrt(2.0)
    assert canvas.up_vector == pytest.approx((expected, expected))


def test_rectangle_defaults_to_top_side_up() -> None:
    canvas = build_canvas(CanvasSpec(shape="rectangle", width=200, height=100))
    assert canvas.up_anchor == "edge:0"
    assert canvas.anchor_point == pytest.approx((100.0, 0.0))
    assert canvas.up_vector == pytest.approx((0.0, -1.0))


def test_polygon_contains_and_samples_inside_domain() -> None:
    canvas = build_canvas(
        CanvasSpec(
            shape="polygon",
            width=100,
            height=100,
            points=[(0, 0), (100, 0), (80, 100), (20, 100)],
            up_anchor="edge:0",
        )
    )
    assert canvas.contains((50, 50))
    assert not canvas.contains((5, 95))

    rng = random.Random(7)
    for _ in range(20):
        assert canvas.contains(canvas.random_point(rng))


def test_distance_to_boundary_is_available_to_generators() -> None:
    canvas = build_canvas(CanvasSpec(shape="square", width=100, height=100))
    assert canvas.distance_to_boundary((50, 50)) == pytest.approx(50.0)


def test_invalid_up_anchor_index_is_rejected() -> None:
    with pytest.raises(CanvasError, match="outside polygon vertex range"):
        build_canvas(CanvasSpec(shape="triangle", up_anchor="vertex:7"))


def test_polygon_edges_wrap_last_vertex_to_first() -> None:
    vertices = ((0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0))

    assert polygon_edges(vertices) == (
        ((0.0, 0.0), (5.0, 0.0)),
        ((5.0, 0.0), (5.0, 5.0)),
        ((5.0, 5.0), (0.0, 5.0)),
        ((0.0, 5.0), (0.0, 0.0)),
    )


def test_polygon_winding_does_not_reorder_vertices() -> None:
    vertices = ((0.0, 0.0), (0.0, 5.0), (5.0, 0.0))
    before = tuple(vertices)

    winding = polygon_winding(vertices)

    assert winding in {"clockwise", "counterclockwise"}
    assert vertices == before


@pytest.mark.parametrize(
    "vertices",
    [
        ((0.0, 0.0), (1.0, 0.0)),
        ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)),
        ((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)),
    ],
)
def test_validate_simple_polygon_rejects_invalid_geometry(vertices) -> None:
    with pytest.raises(ValueError):
        validate_simple_polygon(vertices)


def test_validate_simple_polygon_rejects_non_finite_coordinates() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_simple_polygon(((0.0, 0.0), (1.0, 0.0), (math.inf, 1.0)))


def test_validate_simple_polygon_rejects_zero_length_closing_edge() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        validate_simple_polygon(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)))


def test_validate_simple_polygon_accepts_concave_polygon() -> None:
    vertices = (
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 4.0),
        (2.0, 2.0),
        (0.0, 4.0),
    )

    validate_simple_polygon(vertices)
    assert is_convex_polygon(vertices) is False


def test_polygon_centroid_for_square() -> None:
    vertices = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))

    assert polygon_centroid(vertices) == pytest.approx((5.0, 5.0))
