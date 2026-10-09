import numpy as np
import pytest

from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.sampling import plan_grid, sample_field, smooth_normalize


class Field:
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def sample(self, x, y):
        self.calls += 1
        return self.fn(x, y)


def test_parameter_defaults_and_strict_rejections():
    assert TopographicParameters().model_dump() == dict(
        terrain_scale=30.0, octaves=5, roughness=.45, warp_strength=.35,
        terrain_smoothing=1.0, sample_spacing=.5, contour_count=30,
        index_every=5, simplify_tolerance=.02)
    for params in ({'unknown': 1}, {'octaves': True}, {'octaves': 1.2},
                   {'sample_spacing': '1'}, {'sample_spacing': False},
                   {'sample_spacing': 0}, {'roughness': 2},
                   {'terrain_smoothing': -1}, {'terrain_scale': float('inf')},
                   {'contour_count': 121}, {'index_every': 0}):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate(params)


def test_grid_anchors_bounds_and_accounts_for_halo():
    p = plan_grid((2, 3, 12, 10), spacing=.7, smoothing=1, contour_count=30)
    assert p.dx <= .7 and p.dy <= .7
    assert p.origin[0] + p.interior_columns.start*p.dx == pytest.approx(2)
    assert p.origin[1] + (p.interior_rows.stop-1)*p.dy == pytest.approx(10)
    assert p.interior_rows.start >= np.ceil(4/p.dy)+1
    assert p.interior_columns.start >= np.ceil(4/p.dx)+1


def test_cost_rejected_before_sampling():
    for spacing, smoothing in ((1e-300, 1), (.1, 1e300), (.001, 0)):
        with pytest.raises(ValueError, match='spacing|cost|sample|smoothing'):
            plan_grid((0, 0, 100, 100), spacing=spacing, smoothing=smoothing,
                      contour_count=120)


def test_smoothing_zero_identity_and_constant_empty():
    p = plan_grid((0, 0, 4, 4), spacing=1, smoothing=0, contour_count=3)
    raw = sample_field(Field(lambda x, y: x), p)
    normalized = smooth_normalize(raw, p)
    np.testing.assert_array_equal(normalized.values, raw.values/4)
    assert not normalized.values.flags.writeable
    assert smooth_normalize(sample_field(Field(lambda x, y: 7), p), p) is None
    with pytest.raises(ValueError, match='finite'):
        sample_field(Field(lambda x, y: float('nan')), p)


def test_normalization_uses_interior_not_halo():
    p = plan_grid((0, 0, 4, 4), spacing=1, smoothing=0, contour_count=3)
    f = smooth_normalize(sample_field(Field(lambda x, y: x), p), p)
    assert f.values.min() < 0 and f.values.max() > 1


def test_smoothing_reduces_high_frequency_variation_and_halo_artifacts():
    f = Field(lambda x, y: x + .5*np.sin(5*x)*np.cos(5*y))
    p = plan_grid((0, 0, 10, 10), spacing=.2, smoothing=.6, contour_count=3)
    raw = sample_field(f, p)
    filtered = smooth_normalize(raw, p)
    row = filtered.values[p.interior_rows, p.interior_columns][10]
    assert np.std(np.diff(row, n=2)) < .01
    # A linear field stays linear away from the padded grid boundary.
    linear = smooth_normalize(sample_field(Field(lambda x, y: x), p), p)
    np.testing.assert_allclose(linear.values[p.interior_rows, p.interior_columns][10],
                               np.linspace(0, 1, 51), atol=1e-12)
