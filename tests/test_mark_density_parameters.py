import math

import pytest
from shapely.geometry import Polygon, box

from viz_virtualserver.fill_effects import (
    estimate_fill_candidates,
    list_fill_effects,
    render_fill_effect,
    validate_fill_parameters,
)


@pytest.mark.parametrize("effect", ["stroke-dots", "vortex-marks", "field-marks"])
def test_density_descriptor_and_controls(effect):
    descriptor = next(v for v in list_fill_effects() if v.id == effect)
    p = descriptor.parameters[-1]
    assert (p.name, p.default, p.minimum, p.maximum) == ("density", 1, 0, 1)
    assert validate_fill_parameters(effect=effect)["density"] == 1
    for density in (0, 0.2, 1):
        assert estimate_fill_candidates(
            box(0, 0, 10, 10), effect=effect, parameters={"density": density}
        ) == estimate_fill_candidates(box(0, 0, 10, 10), effect=effect)


@pytest.mark.parametrize("value", [True, "0", None, -0.01, 1.01, math.nan, math.inf])
def test_invalid_density_even_empty(value):
    with pytest.raises(ValueError):
        render_fill_effect(Polygon(), effect="stroke-dots", parameters={"density": value})


@pytest.mark.parametrize("seed", [True, 1.0, "0", None, -(2**63) - 1, 2**63])
def test_invalid_seed_at_zero_and_full_even_empty(seed):
    for density in (0, 1):
        with pytest.raises(ValueError):
            render_fill_effect(
                Polygon(), effect="stroke-dots", parameters={"density": density}, density_seed=seed
            )


def test_unsupported_controls_and_missing_context():
    for effect in ("parallel-hatch", "crosshatch", "circle-rings"):
        with pytest.raises(ValueError):
            render_fill_effect(Polygon(), effect=effect, parameters={"density": 1})
        with pytest.raises(ValueError):
            render_fill_effect(Polygon(), effect=effect, density_seed=1)
    with pytest.raises(ValueError, match="field"):
        render_fill_effect(Polygon(), effect="field-marks", parameters={"density": 0})
