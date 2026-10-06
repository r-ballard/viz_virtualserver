"""Circle outlines, clipping topology, sampling accuracy, and bounded work."""

import math

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon, box


def rings(region, **parameters):
    from viz_virtualserver.fill_effects import render_fill_effect

    return render_fill_effect(region, effect="circle-rings", parameters=parameters)


def test_single_ring_is_closed_with_literal_cardinal_vertices():
    result = rings(box(-2, -2, 2, 2), spacing=10, radius=1, curve_tolerance=.1)
    assert len(result) == 1
    ring = result[0]
    assert ring.closed and len(ring.points) == 8
    assert {(-1., 0.), (0., -1.), (1., 0.), (0., 1.)} <= set(ring.points)
    assert ring.points[0] != ring.points[-1]


def test_circle_catalogue_defaults_match_explicit_rendering():
    from viz_virtualserver.fill_effects import list_fill_effects

    effect = next(e for e in list_fill_effects() if e.id == "circle-rings")
    assert [(p.name, p.default, p.unit) for p in effect.parameters] == [
        ("spacing", 8, "input-units"), ("radius", 2, "input-units"),
        ("angle", 0, "degrees"), ("curve_tolerance", .02, "input-units"),
    ]
    region = box(-12, -12, 12, 12)
    assert rings(region) == rings(region, spacing=8, radius=2, angle=0, curve_tolerance=.02)


def test_circle_chords_obey_tolerance():
    region = box(-2, -2, 2, 2)
    coarse = rings(region, spacing=10, radius=1, curve_tolerance=.1)[0]
    for tolerance in (.01, .001):
        ring = rings(region, spacing=10, radius=1, curve_tolerance=tolerance)[0]
        assert ring.closed and len(ring.points) > len(coarse.points)
        assert all(math.hypot(x, y) == pytest.approx(1, abs=1e-12) for x, y in ring.points)
        for a, b in zip(ring.points, ring.points[1:] + ring.points[:1], strict=True):
            midpoint_radius = math.hypot((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            assert 1 - midpoint_radius <= tolerance + 1e-12


def test_angle_rotates_zero_anchored_lattice():
    region = box(-12, -12, 12, 12)

    def centres(strokes):
        return [((min(x for x, _ in s.points) + max(x for x, _ in s.points)) / 2,
                 (min(y for _, y in s.points) + max(y for _, y in s.points)) / 2)
                for s in strokes if s.closed]

    assert (8., 0.) in centres(rings(region, spacing=8, radius=1))
    rotated = centres(rings(region, spacing=8, radius=1, angle=45))
    assert any(x == pytest.approx(math.sqrt(32)) and y == pytest.approx(math.sqrt(32))
               for x, y in rotated)
    assert not any(abs(x - 8) < 1e-9 and abs(y) < 1e-9 for x, y in rotated)
    assert rings(region, angle=45) == rings(region, angle=405)


def test_clipped_half_ring_is_one_open_arc_across_sampling_seam():
    region = box(0, -2, 2, 2)
    result = rings(region, spacing=10, radius=1, curve_tolerance=.1)
    assert len(result) == 1
    arc = result[0]
    assert not arc.closed
    assert arc.points[0] == (0., -1.) and arc.points[-1] == (0., 1.)
    assert len(arc.points) == 5 and (1., 0.) in arc.points
    assert region.covers(LineString(arc.points))


def split_region():
    return Polygon(((-2, -2), (2, -2), (2, 2), (-2, 2)),
                   holes=[[(-.25, -1.5), (.25, -1.5), (.25, 1.5), (-.25, 1.5)]])


def test_rings_never_bridge_holes_or_disconnected_regions():
    for region in (split_region(), MultiPolygon([box(-2, -2, -.2, 2), box(.2, -2, 2, 2)])):
        arcs = rings(region, spacing=10, radius=1, curve_tolerance=.1)
        assert len(arcs) == 2 and all(not arc.closed for arc in arcs)
        assert all(region.covers(LineString(arc.points)) for arc in arcs)
        assert all(all(x < 0 for x, _ in arc.points) or all(x > 0 for x, _ in arc.points)
                   for arc in arcs)


def test_centres_outside_region_can_contribute_arcs_and_tangents_are_omitted():
    region = box(.5, -.5, 1.5, .5)
    arcs = rings(region, spacing=10, radius=1)
    assert arcs and all(not arc.closed and region.covers(LineString(arc.points)) for arc in arcs)
    assert rings(box(1, -.5, 2, .5), spacing=10, radius=1) == ()
    assert rings(GeometryCollection()) == ()


@pytest.mark.parametrize("parameters", [
    {"radius": 0}, {"radius": -1}, {"radius": math.inf}, {"radius": True},
    {"curve_tolerance": 0}, {"curve_tolerance": math.nan}, {"curve_tolerance": "0.02"},
    {"spacing": 0}, {"angle": math.inf}, {"unknown": 1},
])
def test_ring_controls_validate_even_for_empty_region(parameters):
    with pytest.raises(ValueError, match="parameter"):
        rings(Polygon(), **parameters)


def test_ring_candidate_and_sampling_budgets_preflight(monkeypatch):
    from viz_virtualserver.fill_effects import circle_rings

    def forbidden_scan(*args, **kwargs):
        pytest.fail("budget must fail before geometry is allocated")

    monkeypatch.setattr(circle_rings, "LineString", forbidden_scan)
    monkeypatch.setattr(circle_rings, "MAX_RING_CANDIDATES", 8)
    with pytest.raises(ValueError, match="candidate rings"):
        rings(box(-9, -9, 9, 9), spacing=8, radius=1)
    monkeypatch.setattr(circle_rings, "MAX_RING_POINTS", 7)
    with pytest.raises(ValueError, match="points"):
        rings(box(-2, -2, 2, 2), spacing=10, radius=1, curve_tolerance=.1)


def test_clipped_vertices_have_an_output_budget(monkeypatch):
    from viz_virtualserver.fill_effects import circle_rings

    monkeypatch.setattr(circle_rings, "MAX_RING_POINTS", 8)
    with pytest.raises(ValueError, match="points"):
        rings(split_region(), spacing=10, radius=1, curve_tolerance=.1)


def test_unrepresentable_radius_or_tolerance_rejects():
    with pytest.raises(ValueError, match="represent"):
        rings(box(1e10, 1e10, 1e10 + 10, 1e10 + 10), radius=1e-6)
    with pytest.raises(ValueError, match="points|represent"):
        rings(box(-2, -2, 2, 2), radius=1, curve_tolerance=1e-300)


def test_translated_rounding_budget_cannot_consume_requested_tolerance():
    centre = 1e14
    with pytest.raises(ValueError, match="represent"):
        rings(box(centre - 2, centre - 2, centre + 2, centre + 2),
              spacing=centre, radius=1, curve_tolerance=.077)
