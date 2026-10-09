import numpy as np
import pytest
from shapely.geometry import LineString

from viz_virtualserver.scalar_fields.contours import extract_contours
from viz_virtualserver.scalar_fields.models import SampledField


def grid(values):
    return SampledField((0, 0), 1, 1, np.array(values, dtype=float))


def test_plane_contour_is_one_open_chain():
    cs = extract_contours(grid([[0, 1, 2]]*3), (.5,))
    assert len(cs) == 1 and not cs[0].closed
    assert cs[0].points == ((.5, 0), (.5, 1), (.5, 2))


def test_radial_hill_produces_closed_loops():
    y, x = np.mgrid[-4:5, -4:5]
    cs = extract_contours(grid(16-x*x-y*y), (5.5, 10.5))
    assert len(cs) == 2
    for c in cs:
        assert c.closed and len(set(c.points)) >= 3
        assert c.points[0] != c.points[-1]
        assert LineString(c.points+(c.points[0],)).is_simple


def test_constant_field_has_no_contours():
    assert extract_contours(grid([[1]*3]*3), (0, 1, 2)) == ()


@pytest.mark.parametrize('values,expected', [
    ([[2, -1], [-1, 2]], {frozenset(('top', 'right')), frozenset(('left', 'bottom'))}),
    ([[1, -2], [-2, 1]], {frozenset(('top', 'left')), frozenset(('right', 'bottom'))}),
    ([[1, -1], [-1, 1]], {frozenset(('top', 'right')), frozenset(('left', 'bottom'))}),
])
def test_saddle_connectivity_and_tie(values, expected):
    def side(p):
        x, y = p
        return 'top' if y == 0 else 'bottom' if y == 1 else 'left' if x == 0 else 'right'
    cs = extract_contours(grid(values), (0,))
    assert {frozenset(map(side, c.points)) for c in cs} == expected
    assert cs == extract_contours(grid(values), (0,))


def test_exact_level_vertices_plateaus_and_two_hills():
    for values, levels in (([[0, 1, 2]]*3, (1,)),
                           ([[0, 0, 1], [0, 0, 1], [1, 1, 1]], (0,)),
                           ([[0, 0, 0, 0, 0], [0, 3, 1, 3, 0], [0, 0, 0, 0, 0]], (.5, 2))):
        cs = extract_contours(grid(values), levels)
        edges = []
        for c in cs:
            pts = c.points+(c.points[:1] if c.closed else ())
            edges.extend(tuple(sorted((a, b))) for a, b in zip(pts, pts[1:]))
        assert all(a != b for a, b in edges)
        assert len(edges) == len(set(edges))


def test_contour_budget_aborts_and_levels_are_validated():
    with pytest.raises(ValueError, match='segment'):
        extract_contours(grid([[0, 1, 2]]*3), (.5,), max_segments=1)
    for levels in ((1, 0), (0, 0), (float('nan'),)):
        with pytest.raises(ValueError):
            extract_contours(grid([[0, 1], [0, 1]]), levels)
