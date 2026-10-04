from dataclasses import replace

import pytest
from shapely import affinity, set_precision
from shapely.geometry import LineString, Point, Polygon

from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.generators.truchet.multiscale_composition import (
    compose_regions,
    render_multiscale,
)
from viz_virtualserver.generators.truchet.multiscale_models import (
    MultiscaleArrangement,
    MultiscaleLeaf,
    MultiscaleParameters,
    TileAddress,
)
from viz_virtualserver.generators.truchet.multiscale_motifs import build_motif
from viz_virtualserver.generators.truchet.multiscale_subdivision import assemble_multiscale


def neighbors(depth, orientation, parity=0, extent=2):
    # All roots right of x=1 are fine; left roots coarse. Includes a full halo.
    leaves = []
    for col in range(-extent, 2 + extent):
        for row in range(-extent, 1 + extent):
            n = 2**depth if col >= 1 else 1
            for x in range(n):
                for y in range(n):
                    address = TileAddress(col, row, (x, y))
                    leaves.append(MultiscaleLeaf(address, None,
                        (col + x/n, row + y/n, col + (x+1)/n, row + (y+1)/n),
                        (depth if col >= 1 else 0) + parity, (col + row + orientation) % 2))
    return MultiscaleArrangement((0, 0), 40, tuple(leaves))


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
@pytest.mark.parametrize("orientation", [0, 1])
@pytest.mark.parametrize("parity", [0, 1])
def test_scale_transitions_have_no_interior_ends_or_grid_seams(depth, orientation, parity):
    a = neighbors(depth, orientation, parity)
    domain = PolygonDomain("p", ((0, 0), (80, 0), (80, 40), (0, 40)))
    paths = render_multiscale(a, domain, curve_tolerance=0.02)
    assert paths
    target = Polygon(domain.vertices)
    for path in paths:
        points = path.points + (path.points[:1] if path.closed else ())
        assert target.buffer(1e-8).covers(LineString(points))
        if not path.closed:
            assert target.boundary.distance(Point(path.points[0])) < 1e-8
            assert target.boundary.distance(Point(path.points[-1])) < 1e-8
        for p, q in zip(points, points[1:]):
            assert p != q
            assert not (abs(p[0] - 40) < 1e-8 and abs(q[0] - 40) < 1e-8
                        and abs(p[1] - q[1]) > 1e-6)


def test_same_depth_paint_order_and_halo_are_equivalent():
    a = neighbors(0, 0, extent=1)
    # Reverse addresses, not input sequence: force a different stable paint order.
    shuffled = replace(a, leaves=tuple(replace(leaf, address=TileAddress(-i, 0))
                                        for i, leaf in enumerate(a.leaves)))
    domain = Polygon(((0, 0), (2, 0), (2, 1), (0, 1)))
    result = compose_regions(a, curve_tolerance=0.02).intersection(domain)
    alternate = compose_regions(shuffled, curve_tolerance=0.02).intersection(domain)
    bigger = compose_regions(neighbors(0, 0, extent=2), curve_tolerance=0.02).intersection(
        domain)
    assert result.symmetric_difference(alternate).area < 1e-10
    assert result.symmetric_difference(bigger).area < 1e-10


def test_batched_composition_matches_sequential_painting_at_mixed_depths():
    a = assemble_multiscale((0, 0, 40, 40),
                           parameters=MultiscaleParameters(max_depth=2), seed=31)
    effective = min(0.02/40, min(v.bounds[2]-v.bounds[0] for v in a.leaves)/100)
    from shapely.geometry import GeometryCollection
    sequential = GeometryCollection()
    for leaf in sorted(a.leaves, key=lambda v: (v.depth, v.address)):
        side = leaf.bounds[2]-leaf.bounds[0]
        motif = build_motif(orientation=leaf.orientation, tolerance=effective*.75/side)
        r = [set_precision(affinity.translate(affinity.scale(g, side, side, origin=(0, 0)),
                           leaf.bounds[0], leaf.bounds[1]), effective/16)
             for g in (motif.region_zero, motif.region_one)]
        sequential = sequential.difference(r[0].union(r[1])).union(r[1-leaf.depth % 2])
    result = compose_regions(a, curve_tolerance=0.02)
    assert result.symmetric_difference(sequential).area < 1e-10


@pytest.mark.parametrize("vertices", [
    ((-20, -30), (60, -30), (20, 30)),
    ((0, 0), (80, 0), (80, 80), (40, 25), (0, 80)),
    ((0, 80), (80, 80), (80, 0), (0, 0)),
])
def test_polygon_clipping_is_canonical_and_does_not_add_perimeter(vertices):
    domain = PolygonDomain("p", vertices)
    xs, ys = zip(*vertices)
    a = assemble_multiscale((min(xs), min(ys), max(xs), max(ys)),
                           parameters=MultiscaleParameters(), seed=31)
    paths = render_multiscale(a, domain, curve_tolerance=0.02)
    assert paths == render_multiscale(a, domain, curve_tolerance=0.02)
    assert paths and len(set(paths)) == len(paths)
    polygon = Polygon(vertices)
    for p in paths:
        line = LineString(p.points + (p.points[:1] if p.closed else ()))
        assert polygon.buffer(1e-8).covers(line)
        assert line.intersection(polygon.boundary).length < 1e-7


def test_translation_preserves_relative_curves_and_coarse_tolerance_keeps_topology():
    p = MultiscaleParameters()
    points = ((0.1, 0.2), (80.1, 0.2), (80.1, 80.2), (0.1, 80.2))
    shift = (1000, -400)
    moved = tuple((x + shift[0], y + shift[1]) for x, y in points)
    a = assemble_multiscale((0.1, 0.2, 80.1, 80.2), parameters=p, seed=31)
    b = assemble_multiscale((1000.1, -399.8, 1080.1, -319.8), parameters=p, seed=31)
    original = render_multiscale(a, PolygonDomain("p", points), curve_tolerance=0.02)
    translated = render_multiscale(b, PolygonDomain("p", moved), curve_tolerance=0.02)
    assert len(original) == len(translated)
    for x, y in zip(original, translated):
        assert x.closed == y.closed and len(x.points) == len(y.points)
        for q, r in zip(x.points, y.points):
            assert (q[0] + 1000, q[1] - 400) == pytest.approx(r, abs=1e-8)
    coarse = render_multiscale(a, PolygonDomain("p", points), curve_tolerance=1e9)
    assert coarse


def test_unrepresentable_precision_and_excessive_sampling_reject():
    a = neighbors(0, 0)
    with pytest.raises(ValueError, match="precision|2,000,000 points"):
        compose_regions(a, curve_tolerance=1e-310)
    large = replace(a, origin=(1e8, 1e8))
    domain = PolygonDomain("p", ((1e8, 1e8), (1e8+80, 1e8),
                                  (1e8+80, 1e8+40), (1e8, 1e8+40)))
    with pytest.raises(ValueError, match="precision"):
        render_multiscale(large, domain, curve_tolerance=1e-9)


def test_total_sampling_limit_rejects_before_any_motif_allocation(monkeypatch):
    import viz_virtualserver.generators.truchet.multiscale_composition as composition
    a = assemble_multiscale((0, 0, 40, 40), parameters=MultiscaleParameters(
        max_depth=3, split_probability=1), seed=31)

    def allocation_not_allowed(**kwargs):
        pytest.fail("motif allocation ran before resource rejection")

    monkeypatch.setattr(composition, "build_motif", allocation_not_allowed)
    with pytest.raises(ValueError, match="2,000,000 points"):
        compose_regions(a, curve_tolerance=0.000001)
