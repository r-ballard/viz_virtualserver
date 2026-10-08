"""Raw vectors remain independent of their eventual plotting representation."""

import math
from dataclasses import FrozenInstanceError

import pytest


def test_vortex_cardinal_vectors_magnitude_and_stagnation():
    from viz_virtualserver.fill_effects.vector_fields import VortexField

    field = VortexField(2., 3.)
    expected = [((4., 3.), (0., 2.)), ((2., 5.), (-2., 0.)),
                ((0., 3.), (0., -2.)), ((2., 1.), (2., 0.))]
    for point, vector in expected:
        sample = field.sample(*point)
        assert (sample.dx, sample.dy) == vector
        assert sample.magnitude == 2
        assert sample.direction == tuple(value / 2 for value in vector)
    zero = field.sample(2., 3.)
    assert zero.magnitude == 0 and zero.direction == (0., 0.)
    with pytest.raises(FrozenInstanceError):
        field.center_x = 8


def test_vector_direction_is_stable_for_large_and_subnormal_components():
    from viz_virtualserver.fill_effects.vector_fields import VectorSample

    for size in (1e308, 5e-324):
        sample = VectorSample(size, size)
        assert sample.direction == pytest.approx((math.sqrt(.5), math.sqrt(.5)))
    sample = VectorSample(1.7e308, 1.7e308)
    assert sample.direction == pytest.approx((math.sqrt(.5), math.sqrt(.5)))
    with pytest.raises(ValueError, match="magnitude"):
        _ = sample.magnitude


@pytest.mark.parametrize("bad", [True, "1", math.inf, math.nan])
def test_vector_values_and_field_centres_are_strict_finite_numbers(bad):
    from viz_virtualserver.fill_effects.vector_fields import VectorSample, VortexField

    with pytest.raises(ValueError):
        VectorSample(bad, 0.)
    with pytest.raises(ValueError):
        VortexField(0., bad)
