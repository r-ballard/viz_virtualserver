import math

import pytest

from viz_virtualserver.generators.truchet.assembly import assemble_grid
from viz_virtualserver.generators.truchet.geometry import render_arrangement, sample_connection
from viz_virtualserver.generators.truchet.grammar import compile_states
from viz_virtualserver.generators.truchet.models import (
    TileArrangement,
    TilePlacement,
    TruchetParameters,
)


def test_clipping_preserves_loops_and_splits_exterior_gaps():
    from viz_virtualserver.canvas.models import PolygonDomain
    from viz_virtualserver.generators.truchet.geometry import clip_paths
    from viz_virtualserver.generators.truchet.models import CurvePath

    square = PolygonDomain("s", ((0, 0), (10, 0), (10, 10), (0, 10)))
    loop = CurvePath(((2, 2), (8, 2), (8, 8), (2, 8)), True)
    result = clip_paths((loop,), square)
    assert len(result) == 1 and result[0].closed
    concave = PolygonDomain(
        "c", ((0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10))
    )
    pieces = clip_paths((CurvePath(((-1, 5), (11, 5)), False),), concave)
    assert len(pieces) == 2
    assert {p.points for p in pieces} == {((0.0, 5.0), (3.0, 5.0)), ((7.0, 5.0), (10.0, 5.0))}
    assert not any(p.closed for p in clip_paths((loop,), concave))
    assert clip_paths((CurvePath(((-1, 1), (1, -1)), False),), square) == ()


def test_classic_arc_radius_endpoints_and_error_bound():
    points = sample_connection((5, 0), (0, 5), sagitta_ratio=math.sqrt(2) / 2 - 0.5, tolerance=0.02)
    assert points[0] == (5, 0) and points[-1] == (0, 5)
    assert len(points) > 2
    for x, y in points:
        assert math.hypot(x, y) == pytest.approx(5)
    for a, b in zip(points, points[1:]):
        assert 5 - math.hypot((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) <= 0.020000001


@pytest.mark.parametrize("ratio", [0, 1e-18, -1e-18, 0.5 - math.sqrt(2) / 2, 0.45])
def test_arcs_are_stable_and_inside_square(ratio):
    p = sample_connection((5, 0), (0, 5), sagitta_ratio=ratio, tolerance=0.001)
    assert all(math.isfinite(v) and -1e-12 <= v <= 10 + 1e-12 for xy in p for v in xy)
    if abs(ratio) < 1e-10:
        assert p == ((5, 0), (0, 5))


def test_tracing_consumes_connections_once_and_keeps_loops():
    grid = assemble_grid((0, 0, 50, 50), tile_size=10, seed=7)
    paths = render_arrangement(grid, TruchetParameters(arc_a=0, arc_b=0))
    assert any(p.closed for p in paths)
    assert any(not p.closed for p in paths)
    assert sum(len(p.points) if p.closed else len(p.points) - 1 for p in paths) == 50
    assert all(a != b for p in paths for a, b in zip(p.points, p.points[1:]))
    assert render_arrangement(grid, TruchetParameters()) == render_arrangement(
        grid, TruchetParameters()
    )


def test_complement_changes_regions_without_changing_curves():
    states = compile_states()

    def render(state):
        grid = TileArrangement((0, 0), 10, 1, 1, (TilePlacement(0, 0, state),))
        return render_arrangement(grid, TruchetParameters(arc_a=0.08, arc_b=0.35))

    assert render(states[0]) == render(states[1])
    assert render(states[0]) != render(states[2])


def test_both_classic_corners_have_correct_circle_centers():
    states = compile_states()
    grid = TileArrangement((0, 0), 10, 1, 1, (TilePlacement(0, 0, states[0]),))
    paths = render_arrangement(grid, TruchetParameters())
    for path in paths:
        center = (0, 0) if (5, 0) in path.points else (10, 10)
        assert all(
            math.hypot(x - center[0], y - center[1]) == pytest.approx(5) for x, y in path.points
        )


def test_all_rotated_extreme_arcs_stay_inside_their_tile():
    for state in compile_states():
        grid = TileArrangement((0, 0), 10, 1, 1, (TilePlacement(0, 0, state),))
        paths = render_arrangement(grid, TruchetParameters(arc_a=0.45, arc_b=0.45))
        assert all(
            -1e-12 <= coordinate <= 10 + 1e-12
            for path in paths
            for point in path.points
            for coordinate in point
        )


def test_sample_limit_precedes_allocation():
    grid = assemble_grid((0, 0, 10, 10), tile_size=10, seed=7)
    with pytest.raises(ValueError, match="2,000,000"):
        render_arrangement(grid, TruchetParameters(curve_tolerance=1e-20))
