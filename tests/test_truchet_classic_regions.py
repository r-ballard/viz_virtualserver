"""Classic grammar field reconstruction from shared sampled arc geometry."""

import math

import pytest
from shapely import affinity
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from viz_virtualserver.generators.truchet.assembly import assemble_grid
from viz_virtualserver.generators.truchet.geometry import render_arrangement
from viz_virtualserver.generators.truchet.grammar import compile_states
from viz_virtualserver.generators.truchet.models import (
    TileArrangement,
    TilePlacement,
    TruchetParameters,
)


def regions(arrangement, parameters):
    from viz_virtualserver.generators.truchet.classic_regions import compose_regions
    from viz_virtualserver.generators.truchet.geometry import sample_arrangement

    return compose_regions(arrangement, sample_arrangement(arrangement, parameters))


def curves_geometry(paths):
    return unary_union([LineString(p.points + (p.points[:1] if p.closed else ())) for p in paths])


@pytest.mark.parametrize("state", compile_states())
def test_all_states_partition_tile_with_literal_straight_field_areas(state):
    arrangement = TileArrangement((3., 4.), 10., 1, 1, (TilePlacement(0, 0, state),))
    parameters = TruchetParameters(arc_a=0., arc_b=0.)
    zero, one = regions(arrangement, parameters)
    assert zero.is_valid and one.is_valid
    assert zero.intersection(one).area == 0
    assert zero.union(one).symmetric_difference(box(0, 0, 10, 10)).area == 0
    assert one.area == (75 if state.complement else 25)
    assert zero.area == (25 if state.complement else 75)
    expected = affinity.translate(curves_geometry(render_arrangement(arrangement, parameters)),
                                  xoff=-3, yoff=-4)
    assert one.boundary.difference(box(0, 0, 10, 10).boundary).hausdorff_distance(expected) < 1e-10


@pytest.mark.parametrize("arc", [math.sqrt(2) / 2 - .5, .5 - math.sqrt(2) / 2])
def test_quarter_arc_regions_match_independent_analytic_areas(arc):
    arrangement = TileArrangement((0., 0.), 10., 1, 1,
                                  (TilePlacement(0, 0, compile_states()[0]),))
    parameters = TruchetParameters(arc_a=arc, arc_b=arc, curve_tolerance=.001)
    _, painted = regions(arrangement, parameters)
    expected = 12.5 * math.pi if arc > 0 else 50 - 12.5 * math.pi
    assert painted.area == pytest.approx(expected, abs=.02)


@pytest.mark.parametrize("arc_a,arc_b", [(0., .45), (-.2, .3), (.45, .45)])
def test_asymmetric_rotations_and_complements_keep_exact_partition(arc_a, arc_b):
    parameters = TruchetParameters(arc_a=arc_a, arc_b=arc_b)
    for index in range(0, 8, 2):
        normal = TileArrangement((0., 0.), 10., 1, 1,
                                 (TilePlacement(0, 0, compile_states()[index]),))
        inverse = TileArrangement((0., 0.), 10., 1, 1,
                                  (TilePlacement(0, 0, compile_states()[index + 1]),))
        zero, one = regions(normal, parameters)
        inverse_zero, inverse_one = regions(inverse, parameters)
        assert zero.is_valid and one.is_valid
        assert zero.intersection(one).area < 1e-10
        assert zero.union(one).symmetric_difference(box(0, 0, 10, 10)).area < 1e-10
        assert zero.symmetric_difference(inverse_one).area < 1e-10
        assert one.symmetric_difference(inverse_zero).area < 1e-10


def test_field_union_removes_tile_seam_for_literal_hatch_row():
    from viz_virtualserver.fill_effects import render_fill_effect

    arrangement = TileArrangement((0., 0.), 10., 2, 1, (
        TilePlacement(0, 0, compile_states()[0]), TilePlacement(1, 0, compile_states()[1]),
    ))
    _, painted = regions(arrangement, TruchetParameters(arc_a=0., arc_b=0.))
    strokes = render_fill_effect(painted, effect="parallel-hatch",
                                 parameters={"spacing": 7., "angle": 0.})
    assert [p.points for p in strokes if p.points[0][1] == 7] == [((8., 7.), (18., 7.))]


def test_arrangement_internal_field_boundaries_match_original_curves():
    arrangement = assemble_grid((1e8, -1e8, 1e8 + 30, -1e8 + 20), tile_size=10, seed=31)
    parameters = TruchetParameters(arc_a=-.1, arc_b=.3)
    zero, one = regions(arrangement, parameters)
    footprint = box(0, 0, 30, 20)
    assert zero.union(one).symmetric_difference(footprint).area < 1e-8
    expected = affinity.translate(curves_geometry(render_arrangement(arrangement, parameters)),
                                  xoff=-1e8, yoff=1e8)
    actual = one.boundary.difference(footprint.boundary)
    assert actual.hausdorff_distance(expected) < 1e-7
    assert actual.length == pytest.approx(expected.length, abs=1e-6)
