import math
from dataclasses import FrozenInstanceError

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from viz_virtualserver.generators.truchet.multiscale_models import MultiscaleParameters
from viz_virtualserver.generators.truchet.multiscale_subdivision import assemble_multiscale


@pytest.mark.parametrize("field,value", [
    ("max_depth", -1), ("max_depth", 7), ("max_depth", 1.0), ("max_depth", True),
    ("base_tile_size", 0), ("base_tile_size", "40"), ("base_tile_size", True),
    ("curve_tolerance", -1), ("curve_tolerance", math.inf), ("curve_tolerance", False),
    ("split_probability", -0.1), ("split_probability", 1.1),
    ("split_probability", math.nan), ("split_probability", "0.5"),
    ("split_probability", True), ("unknown", 1),
])
def test_invalid_controls_rejected(field, value):
    with pytest.raises(ValueError):
        MultiscaleParameters.model_validate({field: value})


@pytest.mark.parametrize("depth,probability,per_root", [(0, 1, 1), (3, 0, 1), (3, 1, 64)])
def test_endpoint_subdivision_partitions_every_root(depth, probability, per_root):
    p = MultiscaleParameters(base_tile_size=40, max_depth=depth, split_probability=probability)
    arrangement = assemble_multiscale((0, 0, 40, 40), parameters=p, seed=7)
    assert len(arrangement.leaves) == 9 * per_root  # one root plus a one-root halo
    assert len({leaf.address for leaf in arrangement.leaves}) == len(arrangement.leaves)
    for col in (-1, 0, 1):
        for row in (-1, 0, 1):
            leaves = [v for v in arrangement.leaves
                      if (v.address.root_column, v.address.root_row) == (col, row)]
            polygons = [box(*v.bounds) for v in leaves]
            assert sum(v.area for v in polygons) == pytest.approx(1)
            assert unary_union(polygons).equals(box(col, row, col + 1, row + 1))
            assert all(v.depth == (depth if probability else 0) for v in leaves)
            assert all(v.orientation in (0, 1) for v in leaves)
            for v in leaves:
                assert v.parent is None if v.depth == 0 else (
                    v.parent.quadrants == v.address.quadrants[:-1])
    with pytest.raises(FrozenInstanceError):
        arrangement.leaves[0].depth = 9


def test_seed_choices_are_stable_and_frame_independent():
    p = MultiscaleParameters()
    a = assemble_multiscale((0.1, 0.2, 80.1, 80.2), parameters=p, seed=31)
    b = assemble_multiscale((1000.1, -399.8, 1080.1, -319.8), parameters=p, seed=31)
    c = assemble_multiscale((0.1, 0.2, 80.1, 80.2),
                            parameters=p.model_copy(update={"curve_tolerance": 0.1}), seed=31)
    assert a.leaves == b.leaves == c.leaves
    assert a == assemble_multiscale((0.1, 0.2, 80.1, 80.2), parameters=p, seed=31)
    assert len({v.depth for v in a.leaves}) > 1
    assert {v.orientation for v in a.leaves} == {0, 1}
    bigger = assemble_multiscale((0.1, 0.2, 120.1, 120.2), parameters=p, seed=31)
    shared_roots = {(v.address.root_column, v.address.root_row) for v in a.leaves}
    assert a.leaves == tuple(v for v in bigger.leaves
                            if (v.address.root_column, v.address.root_row) in shared_roots)


def test_default_controls_produce_bounded_mixed_arrangement():
    p = MultiscaleParameters()
    assert (p.base_tile_size, p.max_depth, p.split_probability, p.curve_tolerance) == (
        40, 3, 0.45, 0.02)
    a = assemble_multiscale((0, 0, 80, 80), parameters=p, seed=31)
    assert 16 < len(a.leaves) < 16 * 64


@pytest.mark.parametrize("bounds,params", [
    ((0, 0, 40000, 40000), {}),
    ((0, 0, 40, 40), {"max_depth": 6, "split_probability": 1}),
])
def test_leaf_budget_rejected(bounds, params):
    with pytest.raises(ValueError, match="10,000 leaves"):
        assemble_multiscale(bounds, parameters=MultiscaleParameters(**params), seed=0)
