from shapely.geometry import LineString, Polygon

from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.generators.topographic.geometry import (
    clip_contours,
    prepare_contours,
    simplify_contours,
)
from viz_virtualserver.scalar_fields.models import Contour


def line(c):
    return LineString(c.points+(c.points[:1] if c.closed else ()))


def test_zero_tolerance_preserves_contours():
    cs = (Contour(.5, ((0, 0), (1, .1), (2, 0)), False),)
    assert simplify_contours(cs, tolerance=0) == cs


def test_safe_simplification_respects_error_and_closedness():
    cs = (Contour(.2, ((0, 0), (1, .01), (2, 0)), False),
          Contour(.8, ((4, 0), (6, 0), (6, 2), (4, 2)), True))
    out = simplify_contours(cs, tolerance=.02)
    assert len(out[0].points) == 2
    for a, b in zip(cs, out, strict=True):
        assert a.closed == b.closed
        assert line(a).hausdorff_distance(line(b)) <= .02
    assert simplify_contours((cs[1],), tolerance=100)[0].closed


def test_close_contours_revert_unsafe_simplification():
    cs = (Contour(.2, ((0, 0), (1, 2), (2, 0)), False),
          Contour(.8, ((1, -.5), (1, .5)), False))
    assert not line(cs[0]).intersects(line(cs[1]))
    out = simplify_contours(cs, tolerance=3)
    assert out[0] == cs[0]
    assert not line(out[0]).intersects(line(out[1]))


def test_clipping_concave_closed_open_and_winding():
    vertices = ((0, 0), (4, 0), (4, 4), (2, 1), (0, 4))
    polygon = PolygonDomain('a', vertices)
    cs = (Contour(.2, ((-.5, 2), (4.5, 2)), False),
          Contour(.4, ((.2, .2), (1, .2), (1, .7), (.2, .7)), True),
          Contour(.6, ((-1, -1), (5, -1), (5, 2), (-1, 2)), True))
    out = prepare_contours(cs, polygon, tolerance=.02)
    # GEOS boundary interpolation at 8/3 can differ by one ulp; use the
    # repository's existing whole-segment containment tolerance.
    assert all(Polygon(vertices).buffer(1e-9).covers(line(c)) for c in out)
    assert len([c for c in out if c.level == .2]) == 2
    assert next(c for c in out if c.level == .4).closed
    assert all(not c.closed for c in out if c.level == .6)
    assert out == prepare_contours(cs, PolygonDomain('a', vertices[::-1]), tolerance=.02)


def test_boundary_tangency_point_is_omitted():
    polygon = PolygonDomain('a', ((0, 0), (2, 0), (2, 2), (0, 2)))
    cs = (Contour(.5, ((-1, 1), (1, -1)), False),)
    assert clip_contours(cs, polygon) == ()


def test_self_intersection_is_not_introduced():
    c = Contour(.5, ((0, 0), (1, 3), (2, 0), (3, 3), (4, 0)), False)
    assert line(simplify_contours((c,), tolerance=2)[0]).is_simple


def test_clipped_loop_rejoins_its_arbitrary_starting_vertex():
    c = Contour(.5, ((-1, 0), (0, -1), (1, 0), (0, 1)), True)
    d = PolygonDomain('p', ((-2, -2), (.5, -2), (.5, 2), (-2, 2)))
    out = clip_contours((c,), d)
    assert len(out) == 1 and not out[0].closed
    assert {out[0].points[0], out[0].points[-1]} == {(.5, -.5), (.5, .5)}
    assert line(out[0]).length == line(c).intersection(Polygon(d.vertices)).length


def test_simplification_preserves_clipped_components():
    small = Contour(.5, ((-1, -.1), (0, .01), (1, -.1)), False)
    p = PolygonDomain('p', ((-2, 0), (2, 0), (2, 2), (-2, 2)))
    assert prepare_contours((small,), p, tolerance=.2) == clip_contours((small,), p)


def test_simplification_preserves_clipped_closedness():
    p = PolygonDomain('p', ((0, 0), (4, 0), (4, 4), (3, 4), (3, 1),
                            (1, 1), (1, 4), (0, 4)))
    ring = Contour(.5, ((.2, .2), (3.8, .2), (3.8, 3.8), (3.2, 3.8),
                       (3.2, .8), (.8, .8), (.8, 3.8), (.2, 3.8)), True)
    out = prepare_contours((ring,), p, tolerance=2)
    assert len(out) == 1 and out[0].closed
    assert out == clip_contours((ring,), p)
