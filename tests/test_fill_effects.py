"""Literal geometry and public boundary checks for reusable fill effects."""

import math
from dataclasses import FrozenInstanceError

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box


def render(region, **parameters):
    from viz_virtualserver.fill_effects import render_fill_effect

    return render_fill_effect(region, effect="parallel-hatch", parameters=parameters)


def test_catalogue_defaults_and_immutability():
    from viz_virtualserver.fill_effects import list_fill_effects

    effects = list_fill_effects()
    assert isinstance(effects, tuple)
    assert [e.id for e in effects] == ["parallel-hatch"]
    controls = effects[0].parameters
    assert [(p.name, p.default, p.unit, p.exclusive_minimum) for p in controls] == [
        ("spacing", 2, "input-units", 0), ("angle", 45, "degrees", None),
    ]
    with pytest.raises(FrozenInstanceError):
        controls[0].default = 9
    with pytest.raises(FrozenInstanceError):
        effects[0].id = "changed"
    assert list_fill_effects() == effects


def test_default_parameters_match_explicit_controls():
    from viz_virtualserver.fill_effects import render_fill_effect

    region = box(1, 1, 9, 9)
    assert render_fill_effect(region, effect="parallel-hatch") == render(
        region, spacing=2, angle=45)
    parameters = {"spacing": 2, "angle": 0}
    strokes = render_fill_effect(region, effect="parallel-hatch", parameters=parameters)
    parameters["spacing"] = 8
    assert len(strokes) == 4


@pytest.mark.parametrize("parameters", [
    {"unknown": 1}, {"spacing": True}, {"angle": False}, {"spacing": "2"},
    {"angle": "45"}, {"spacing": 0}, {"spacing": -1},
    {"spacing": math.nan}, {"spacing": math.inf}, {"angle": math.nan},
    {"angle": math.inf}, {"spacing": None},
])
def test_invalid_controls_fail(parameters):
    with pytest.raises(ValueError):
        render(Polygon(), **parameters)


def test_unknown_effect_fails():
    from viz_virtualserver.fill_effects import render_fill_effect

    with pytest.raises(ValueError, match="effect"):
        render_fill_effect(Polygon(), effect="missing")


def test_horizontal_literal_endpoints():
    strokes = render(box(1, 1, 9, 9), spacing=2, angle=0)
    assert tuple(s.points for s in strokes) == (
        ((1., 2.), (9., 2.)), ((1., 4.), (9., 4.)),
        ((1., 6.), (9., 6.)), ((1., 8.), (9., 8.)),
    )
    assert all(not s.closed for s in strokes)


def test_holes_and_disconnected_regions_never_bridge():
    region = Polygon(((0, 0), (10, 0), (10, 10), (0, 10)),
                     holes=[((4, 2), (6, 2), (6, 8), (4, 8))])
    assert [s.points for s in render(region, spacing=5, angle=0)
            if s.points[0][1] == 5] == [
        ((0., 5.), (4., 5.)), ((6., 5.), (10., 5.)),
    ]
    separated = MultiPolygon([box(1, 1, 3, 3), box(7, 1, 9, 3)])
    assert [s.points for s in render(separated, spacing=2, angle=0)] == [
        ((1., 2.), (3., 2.)), ((7., 2.), (9., 2.)),
    ]
    triangle = Polygon(((0, 0), (10, 0), (5, 10)))
    assert not any(s.points[0][1] == 10 for s in render(triangle, spacing=5, angle=0))


def test_angles_and_zero_phase():
    region = box(1, 1, 9, 9)
    assert render(region, spacing=2, angle=0) == render(region, spacing=2, angle=180)
    assert [s.points for s in render(region, spacing=2, angle=90)] == [
        ((2., 1.), (2., 9.)), ((4., 1.), (4., 9.)),
        ((6., 1.), (6., 9.)), ((8., 1.), (8., 9.)),
    ]
    diagonal = render(region, spacing=2, angle=45)
    assert diagonal
    for stroke in diagonal:
        (x0, y0), (x1, y1) = stroke.points
        assert x1 - x0 == pytest.approx(y1 - y0, abs=1e-12)


@pytest.mark.parametrize("region", [Polygon(), MultiPolygon(), GeometryCollection()])
def test_empty_region_returns_tuple(region):
    assert render(region) == ()


@pytest.mark.parametrize("region", [
    Point(0, 0), LineString([(0, 0), (1, 1)]),
    GeometryCollection([box(0, 0, 2, 2), Point(8, 8)]),
    Polygon([(0, 0), (2, 2), (0, 2), (2, 0)]),
])
def test_region_contract_rejects_non_polygonal_and_invalid_geometry(region):
    with pytest.raises(ValueError, match="region"):
        render(region)


def test_polygonal_collection_is_supported():
    assert render(GeometryCollection([box(1, 1, 9, 9)]), angle=0) == render(
        box(1, 1, 9, 9), angle=0)


def test_stroke_values_snapshot_and_validate():
    from viz_virtualserver.fill_effects import FillStroke

    points = [[0, 0], [1, 1]]
    stroke = FillStroke(points)
    points[0][0] = 99
    assert stroke.points == ((0., 0.), (1., 1.))
    with pytest.raises(FrozenInstanceError):
        stroke.closed = True
    for invalid, closed in [
        ([(0, math.nan), (1, 1)], False), ([(0, 0, 0), (1, 1)], False),
        ([(0, 0), (0, 0)], False), ([(0, 0), (1, 1)], True),
    ]:
        with pytest.raises(ValueError):
            FillStroke(invalid, closed)
    assert FillStroke(((0, 0), (1, 0), (0, 1)), True).closed


def test_hatch_limits_and_precision(monkeypatch):
    from viz_virtualserver.fill_effects import parallel_hatch

    with pytest.raises(ValueError, match="100,000"):
        render(box(0, 0, 1, 100_000), spacing=1, angle=0)
    with pytest.raises(ValueError, match="represent"):
        render(box(0, 1e10, 80, 1e10 + .001), spacing=1e-6, angle=0)
    monkeypatch.setattr(parallel_hatch, "MAX_HATCH_POINTS", 4)
    with pytest.raises(ValueError, match="points"):
        render(box(0, 0, 10, 10), spacing=2, angle=0)
