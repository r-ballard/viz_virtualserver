import math

import numpy as np
import pytest

from viz_virtualserver.scalar_fields.densities import SampledElevationDensity
from viz_virtualserver.scalar_fields.models import SampledField


def test_planes_anisotropic_origin_boundaries_and_shared_storage():
    field = SampledField((-3, 7), 2, 4, np.array([[0, 1], [0, 1]]))
    source = SampledElevationDensity(field, minimum=0.2, maximum=0.8)
    assert source.field is field
    for point, expected in [((-3, 7), 0.2), ((-1, 11), 0.8), ((-2, 9), 0.5), ((-2.5, 8), 0.35)]:
        assert source.sample(*point) == pytest.approx(expected)
    with pytest.raises(AttributeError):
        source.minimum = 0
    for point in ((-3.1, 8), (-0.9, 8), (-2, 6.9), (-2, 11.1)):
        assert source.sample(*point) == 0


def test_independent_bilinear_mapping_inverse_constant_and_halo():
    field = SampledField((0, 0), 1, 1, np.array([[0, 0], [0, 1]]))
    assert SampledElevationDensity(field, minimum=0.1, maximum=0.9).sample(
        0.25, 0.75
    ) == pytest.approx(0.25)
    assert SampledElevationDensity(field, minimum=0.1, maximum=0.9, invert=True).sample(
        0.25, 0.75
    ) == pytest.approx(0.75)
    assert SampledElevationDensity(field, minimum=0.4, maximum=0.4).sample(0.3, 0.6) == 0.4
    halo = SampledField((0, 0), 1, 1, np.array([[-1, 2], [-1, 2]]))
    source = SampledElevationDensity(halo, minimum=0.2, maximum=0.8)
    assert source.sample(0, 0) == 0.2
    assert source.sample(1, 1) == 0.8
    assert source.sample(0.5, 0.5) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "controls",
    [
        {"minimum": True},
        {"maximum": "1"},
        {"minimum": -0.1},
        {"maximum": 1.1},
        {"minimum": 0.8, "maximum": 0.2},
        {"invert": 1},
        {"minimum": math.nan},
        {"maximum": math.inf},
    ],
)
def test_invalid_controls(controls):
    with pytest.raises(ValueError):
        SampledElevationDensity(SampledField((0, 0), 1, 1, np.zeros((2, 2))), **controls)


def test_invalid_context_queries_precision_and_cap(monkeypatch):
    from viz_virtualserver.scalar_fields import densities

    with pytest.raises(ValueError):
        SampledElevationDensity(object())
    with pytest.raises(ValueError, match="represent"):
        SampledElevationDensity(SampledField((1e16, 0), 1, 1, np.zeros((2, 2))))
    field = SampledField((0, 0), 1, 1, np.zeros((2, 2)))
    source = SampledElevationDensity(field)
    for x in (True, "0", math.nan, math.inf):
        with pytest.raises(ValueError):
            source.sample(x, 0)
    monkeypatch.setattr(densities, "MAX_SAMPLES", 3)
    with pytest.raises(ValueError, match="sample"):
        SampledElevationDensity(field)
