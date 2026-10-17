import math

import numpy as np
import pytest

from viz_virtualserver.scalar_fields.densities import SampledSlopeDensity
from viz_virtualserver.scalar_fields.gradients import SampledGradient
from viz_virtualserver.scalar_fields.models import SampledField


def plane(dx=0.03, dy=0.04):
    yy, xx = np.indices((4, 5))
    return SampledGradient(SampledField((-3, 7), 2, 4, dx * xx * 2 + dy * yy * 4))


def test_planar_magnitude_anisotropic_mapping_inversion_bounds_and_immutability():
    gradient = plane()
    a = SampledSlopeDensity(gradient, reference_slope=0.1, minimum=0.1, maximum=0.9)
    b = SampledSlopeDensity(gradient, reference_slope=0.1, minimum=0.1, maximum=0.9, invert=True)
    assert a.gradient is gradient
    for point in ((-3, 7), (5, 19), (-1.5, 10.5)):
        assert a.sample(*point) == pytest.approx(0.5)
        assert b.sample(*point) == pytest.approx(0.5)
    assert SampledSlopeDensity(gradient, reference_slope=0.01).sample(0, 10) == 1
    assert SampledSlopeDensity(gradient, reference_slope=0.01, invert=True).sample(0, 10) == 0
    assert SampledSlopeDensity(gradient, reference_slope=0.2, minimum=0.1, maximum=0.9).sample(
        0, 10
    ) == pytest.approx(0.3)
    assert SampledSlopeDensity(
        gradient, reference_slope=0.2, minimum=0.1, maximum=0.9, invert=True
    ).sample(0, 10) == pytest.approx(0.7)
    for point in ((-3.1, 7), (5.1, 7), (0, 6.9), (0, 19.1)):
        assert a.sample(*point) == b.sample(*point) == 0
    with pytest.raises(AttributeError):
        a.reference_slope = 2


def test_flat_field_and_interpolate_components_before_magnitude():
    flat = plane(0, 0)
    assert SampledSlopeDensity(flat, reference_slope=0.1, minimum=0.2).sample(0, 9) == 0.2
    assert SampledSlopeDensity(flat, reference_slope=0.1, invert=True).sample(0, 9) == 1
    # Opposite derivatives cancel at the midpoint; interpolating magnitudes would not.
    gradient = SampledGradient(SampledField((0, 0), 1, 1, np.array([[0, 1, 0]] * 3)))
    source = SampledSlopeDensity(gradient, reference_slope=1)
    assert source.sample(1, 1) == 0
    assert source.sample(0.25, 1) == pytest.approx(0.75)


@pytest.mark.parametrize("reference", [0, -1, True, "0.1", None, math.inf, math.nan])
def test_invalid_reference(reference):
    with pytest.raises(ValueError):
        SampledSlopeDensity(plane(), reference_slope=reference)


@pytest.mark.parametrize(
    "controls",
    [
        {"minimum": -0.1},
        {"minimum": 0.8, "maximum": 0.2},
        {"maximum": math.inf},
        {"invert": 1},
        {"minimum": True},
    ],
)
def test_invalid_mapping(controls):
    with pytest.raises(ValueError):
        SampledSlopeDensity(plane(), reference_slope=0.1, **controls)


def test_bad_context_queries_and_tiny_reference_saturation():
    with pytest.raises(ValueError):
        SampledSlopeDensity(object(), reference_slope=0.1)
    source = SampledSlopeDensity(plane(), reference_slope=5e-324)
    assert source.sample(0, 9) == 1
    for x in (True, "0", math.nan, math.inf):
        with pytest.raises(ValueError):
            source.sample(x, 9)


def test_small_raw_slopes_remain_relative_to_reference_below_direction_cutoff():
    gradient = plane(1e-15, 0)
    assert gradient.vector_field("slope").sample(0, 9).magnitude == 0
    assert SampledSlopeDensity(gradient, reference_slope=1e-15).sample(0, 9) == pytest.approx(1)
