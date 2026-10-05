"""Crosshatch geometry, shared budgets, and catalogue contracts."""

import math

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon, box


def crosshatch(region, **parameters):
    from viz_virtualserver.fill_effects import render_fill_effect

    return render_fill_effect(region, effect="crosshatch", parameters=parameters)


def test_crosshatch_has_literal_perpendicular_rows():
    result = crosshatch(box(1, 1, 9, 9), spacing=2, angle=0)
    assert tuple(p.points for p in result) == (
        ((1., 2.), (9., 2.)), ((1., 4.), (9., 4.)),
        ((1., 6.), (9., 6.)), ((1., 8.), (9., 8.)),
        ((2., 1.), (2., 9.)), ((4., 1.), (4., 9.)),
        ((6., 1.), (6., 9.)), ((8., 1.), (8., 9.)),
    )
    assert all(not p.closed and len(p.points) == 2 for p in result)


def test_crosshatch_catalogue_defaults_render_and_angles_repeat():
    from viz_virtualserver.fill_effects import list_fill_effects

    effects = list_fill_effects()
    assert [effect.id for effect in effects] == ["parallel-hatch", "crosshatch"]
    assert [(p.name, p.default, p.unit) for p in effects[1].parameters] == [
        ("spacing", 2, "input-units"), ("angle", 45, "degrees"),
    ]
    region = box(1, 1, 9, 9)
    assert crosshatch(region) == crosshatch(region, spacing=2, angle=45)
    assert crosshatch(region, angle=0) == crosshatch(region, angle=90)
    assert crosshatch(region, angle=45) == crosshatch(region, angle=225)
    assert crosshatch(region, angle=1e308) == crosshatch(region, angle=1e308 % 180)


def test_crosshatch_splits_both_families_at_holes():
    region = Polygon(((0, 0), (10, 0), (10, 10), (0, 10)),
                     holes=[((4, 4), (6, 4), (6, 6), (4, 6))])
    paths = crosshatch(region, spacing=5, angle=0)
    assert {p.points for p in paths if any(5 in point for point in p.points)} == {
        ((0., 5.), (4., 5.)), ((6., 5.), (10., 5.)),
        ((5., 0.), (5., 4.)), ((5., 6.), (5., 10.)),
    }
    assert all(region.covers(LineString(p.points)) for p in paths)
    separated = MultiPolygon([box(1, 1, 3, 3), box(7, 1, 9, 3)])
    assert {p.points for p in crosshatch(separated, spacing=2, angle=0)} == {
        ((1., 2.), (3., 2.)), ((7., 2.), (9., 2.)),
        ((2., 1.), (2., 3.)), ((8., 1.), (8., 3.)),
    }


@pytest.mark.parametrize("parameters", [
    {"unknown": 1}, {"spacing": True}, {"angle": False}, {"spacing": "2"},
    {"spacing": 0}, {"spacing": -1}, {"spacing": math.inf}, {"angle": math.nan},
])
def test_crosshatch_validates_controls_before_empty_region(parameters):
    with pytest.raises(ValueError, match="parameter"):
        crosshatch(Polygon(), **parameters)


def test_crosshatch_empty_and_tangent_contacts():
    assert crosshatch(GeometryCollection()) == ()
    triangle = Polygon(((0, 0), (10, 0), (5, 10)))
    paths = crosshatch(triangle, spacing=5, angle=0)
    assert paths and all(p.points[0] != p.points[1] for p in paths)
    assert all(triangle.covers(LineString(p.points)) for p in paths)


def test_crosshatch_checks_total_rows_before_clipping(monkeypatch):
    from viz_virtualserver.fill_effects import parallel_hatch

    monkeypatch.setattr(parallel_hatch, "MAX_HATCH_ROWS", 7)

    def forbidden_scan(*args, **kwargs):
        pytest.fail("row budget must be rejected before clipping starts")

    with monkeypatch.context() as patch:
        patch.setattr(parallel_hatch, "LineString", forbidden_scan)
        with pytest.raises(ValueError, match="scan rows"):
            crosshatch(box(1, 1, 9, 9), spacing=2, angle=0)
    monkeypatch.setattr(parallel_hatch, "MAX_HATCH_ROWS", 8)
    assert len(crosshatch(box(1, 1, 9, 9), spacing=2, angle=0)) == 8


def test_crosshatch_enforces_combined_point_budget(monkeypatch):
    from viz_virtualserver.fill_effects import parallel_hatch

    monkeypatch.setattr(parallel_hatch, "MAX_HATCH_POINTS", 10)
    with pytest.raises(ValueError, match="points"):
        crosshatch(box(1, 1, 9, 9), spacing=2, angle=0)
    monkeypatch.setattr(parallel_hatch, "MAX_HATCH_POINTS", 16)
    assert len(crosshatch(box(1, 1, 9, 9), spacing=2, angle=0)) == 8


def test_crosshatch_retains_coordinate_precision_checks():
    with pytest.raises(ValueError, match="represent"):
        crosshatch(box(1e10, 1, 1e10 + 10, 1.001), spacing=1e-6, angle=0)
