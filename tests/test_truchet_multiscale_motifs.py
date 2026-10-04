import math

import pytest
from shapely import affinity
from shapely.geometry import box

from viz_virtualserver.generators.truchet.multiscale_motifs import (
    build_motif,
    estimate_motif_points,
)


@pytest.mark.parametrize("orientation", [0, 1])
@pytest.mark.parametrize("tolerance", [0.001, 0.0001])
def test_winged_regions_cover_square_without_overlapping_interiors(orientation, tolerance):
    motif = build_motif(orientation=orientation, tolerance=tolerance)
    a, b = motif.region_zero, motif.region_one
    assert a.is_valid and b.is_valid and not a.is_empty and not b.is_empty
    assert a.intersection(b).area < 1e-12
    assert box(0, 0, 1, 1).difference(a.union(b)).area < 1e-12
    assert box(-1/3 - 1e-12, -1/3 - 1e-12, 4/3 + 1e-12, 4/3 + 1e-12).covers(a.union(b))
    ports = ((1/3, 0), (2/3, 0), (1, 1/3), (1, 2/3),
             (2/3, 1), (1/3, 1), (0, 2/3), (0, 1/3))
    for p in ports:
        from shapely.geometry import Point
        assert a.boundary.distance(Point(p)) < 1e-12
        assert b.boundary.distance(Point(p)) < 1e-12
    assert motif.sampled_points == estimate_motif_points(
        orientation=orientation, tolerance=tolerance)


def test_orientation_is_quarter_rotation_and_arcs_are_smooth():
    a = build_motif(orientation=0, tolerance=0.0001)
    b = build_motif(orientation=1, tolerance=0.0001)
    assert affinity.rotate(a.region_zero, 90, origin=(0.5, 0.5)).symmetric_difference(
        b.region_zero).area < 1e-10
    # Base motif interior boundaries are circles at opposing corners, radii 1/3 and 2/3.
    interface = a.region_zero.boundary.intersection(a.region_one.boundary)
    points = []
    for line in interface.geoms:
        points.extend(line.coords)
    for x, y in points:
        if 0 < x < 1 and 0 < y < 1:
            assert min(abs(math.hypot(x, y) - r) for r in (1/3, 2/3)) < 1e-12 or min(
                abs(math.hypot(x - 1, y - 1) - r) for r in (1/3, 2/3)) < 1e-12


def test_tiny_tolerance_rejects_before_sampling():
    with pytest.raises(ValueError, match="2,000,000 points"):
        estimate_motif_points(orientation=0, tolerance=1e-310)
