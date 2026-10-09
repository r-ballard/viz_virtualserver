import random

import numpy as np
import pytest

from viz_virtualserver.scalar_fields.terrain import TerrainField


def values(field):
    return [field.sample(x, y) for x, y in ((0, 0), (-3.1, 9), (12, 7), (55.6, 31.2))]


def test_terrain_seed_repeatability_and_variation():
    a = values(TerrainField(31))
    assert a == values(TerrainField(31))
    assert a != values(TerrainField(32))
    assert np.isfinite(a).all()


def test_terrain_does_not_mutate_global_rng():
    before = random.getstate()
    numpy_before = np.random.get_state()
    values(TerrainField(99))
    assert before == random.getstate()
    after = np.random.get_state()
    assert numpy_before[0] == after[0]
    np.testing.assert_array_equal(numpy_before[1], after[1])
    assert numpy_before[2:] == after[2:]


def test_zero_warp_and_zero_roughness():
    assert values(TerrainField(31, roughness=0)) == values(TerrainField(31, octaves=1))
    assert values(TerrainField(31, warp_strength=0)) != values(TerrainField(31))
    f = TerrainField(31, warp_strength=0)
    assert f.sample(30-1e-7, 7) == pytest.approx(f.sample(30+1e-7, 7), abs=1e-6)
    assert np.isfinite(f.sample(-1e10, 1e10))
    with pytest.raises(ValueError):
        TerrainField(31, scale=1e-300).sample(1e300, 1e300)
