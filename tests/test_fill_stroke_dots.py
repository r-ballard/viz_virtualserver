"""Short mark geometry, zero-anchored placement, clipping, and bounded work."""

import math

import pytest
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box


def dots(region, **parameters):
    from viz_virtualserver.fill_effects import render_fill_effect

    return render_fill_effect(region, effect="stroke-dots", parameters=parameters)


def test_dot_catalogue_defaults_and_literal_lattice_marks():
    from viz_virtualserver.fill_effects import list_fill_effects

    descriptor = next(e for e in list_fill_effects() if e.id == "stroke-dots")
    assert [(p.name, p.default, p.unit) for p in descriptor.parameters] == [
        ("spacing", 8, "input-units"), ("mark_length", .5, "input-units"),
        ("angle", 0, "degrees"),
    ]
    region = box(-1, -1, 9, 9)
    result = dots(region)
    assert result == dots(region, spacing=8, mark_length=.5, angle=0)
    assert tuple(p.points for p in result) == (
        ((-.25, 0.), (.25, 0.)), ((-.25, 8.), (.25, 8.)),
        ((7.75, 0.), (8.25, 0.)), ((7.75, 8.), (8.25, 8.)),
    )
    assert all(not p.closed and len(p.points) == 2 for p in result)


def test_rotation_changes_lattice_and_mark_direction():
    vertical = dots(box(-1, -1, 9, 9), angle=90)
    assert {p.points for p in vertical} == {
        ((0., -.25), (0., .25)), ((0., 7.75), (0., 8.25)),
        ((8., -.25), (8., .25)), ((8., 7.75), (8., 8.25)),
    }
    region = box(-1, -1, 7, 7)
    rotated = dots(region, spacing=8, mark_length=.5, angle=45)
    assert len(rotated) == 2
    centres = [tuple((a + b) / 2 for a, b in zip(p.points[0], p.points[1], strict=True))
               for p in rotated]
    assert centres[0] == pytest.approx((0., 0.))
    assert centres[1] == pytest.approx((math.sqrt(32), math.sqrt(32)))
    for p in rotated:
        (x0, y0), (x1, y1) = p.points
        assert x1 - x0 == pytest.approx(y1 - y0, abs=1e-12)
        assert math.hypot(x1 - x0, y1 - y0) == pytest.approx(.5, abs=1e-12)
    assert rotated == dots(region, spacing=8, mark_length=.5, angle=225)
    assert dots(region, angle=1e308) == dots(region, angle=1e308 % 180)


def split_region():
    return Polygon(((-1, -1), (1, -1), (1, 1), (-1, 1)),
                   holes=[[(-.1, -.2), (.1, -.2), (.1, .2), (-.1, .2)]])


def test_marks_split_at_holes_and_disconnected_regions():
    separated = MultiPolygon([box(-1, -1, -.1, 1), box(.1, -1, 1, 1)])
    for region in (split_region(), separated):
        assert tuple(p.points for p in dots(region, mark_length=1)) == (
            ((-.5, 0.), (-.1, 0.)), ((.1, 0.), (.5, 0.)),
        )


def test_outside_centres_contribute_clipped_marks_and_tangents_are_omitted():
    assert tuple(p.points for p in dots(box(.2, -.2, .8, .2), mark_length=1)) == (
        ((.2, 0.), (.5, 0.)),
    )
    assert dots(box(.5, -.2, .8, .2), mark_length=1) == ()
    assert dots(GeometryCollection()) == ()


def test_overlapping_marks_remain_independent_strokes():
    result = dots(box(-2, -1, 3, 1), spacing=2, mark_length=3)
    assert tuple(p.points for p in result) == (
        ((-2., 0.), (-.5, 0.)), ((-1.5, 0.), (1.5, 0.)),
        ((.5, 0.), (3., 0.)), ((2.5, 0.), (3., 0.)),
    )


@pytest.mark.parametrize("parameters", [
    {"mark_length": 0}, {"mark_length": -1}, {"mark_length": math.inf},
    {"mark_length": math.nan}, {"mark_length": True}, {"mark_length": "0.5"},
    {"spacing": 0}, {"spacing": math.inf}, {"angle": math.nan}, {"unknown": 1},
])
def test_dot_controls_validate_even_for_empty_region(parameters):
    with pytest.raises(ValueError, match="parameter"):
        dots(Polygon(), **parameters)


def test_dot_candidate_and_source_point_budgets_preflight(monkeypatch):
    from viz_virtualserver.fill_effects import stroke_dots

    def forbidden_geometry(*args, **kwargs):
        pytest.fail("preflight must reject before allocating marks")

    monkeypatch.setattr(stroke_dots, "LineString", forbidden_geometry)
    monkeypatch.setattr(stroke_dots, "MAX_DOT_CANDIDATES", 8)
    with pytest.raises(ValueError, match="candidate marks"):
        dots(box(-9, -9, 9, 9))
    monkeypatch.setattr(stroke_dots, "MAX_DOT_POINTS", 1)
    with pytest.raises(ValueError, match="points"):
        dots(box(-1, -1, 1, 1))


def test_dot_clipped_endpoint_budget_and_exact_limit(monkeypatch):
    from viz_virtualserver.fill_effects import stroke_dots

    monkeypatch.setattr(stroke_dots, "MAX_DOT_POINTS", 2)
    assert len(dots(box(-1, -1, 1, 1), mark_length=1)) == 1
    with pytest.raises(ValueError, match="points"):
        dots(split_region(), mark_length=1)
    monkeypatch.setattr(stroke_dots, "MAX_DOT_POINTS", 4)
    assert len(dots(split_region(), mark_length=1)) == 2


def test_dot_length_and_spacing_require_representable_coordinates():
    region = box(1e10, 1, 1e10 + 10, 9)
    for controls in ({"mark_length": 1e-6}, {"spacing": 1e-6}):
        with pytest.raises(ValueError, match="represent"):
            dots(region, **controls)


def test_empty_lattice_dimension_never_iterates_unbounded_other_dimension(monkeypatch):
    from viz_virtualserver.fill_effects import stroke_dots

    def forbidden_iteration(*args):
        pytest.fail("an empty mark lattice must return before iterating rows or columns")

    monkeypatch.setattr(stroke_dots, "range", forbidden_iteration, raising=False)
    # No column centre can reach this thin region, but its height would otherwise
    # trigger 125,000,001 empty outer-loop iterations despite zero candidates.
    assert dots(box(3, 0, 4, 1e9)) == ()
    assert dots(box(0, 3, 1e9, 4)) == ()
