import pytest

from viz_virtualserver.fill_effects import validate_fill_parameters
from viz_virtualserver.generators.topographic.models import TopographicParameters


def rule(**updates):
    return dict(
        bands=[2, 0],
        effect="stroke-dots",
        parameters={"spacing": 3, "mark_length": 0.5},
        layer_id="dots",
        **updates,
    )


def test_rules_are_canonical_and_parameters_immutable():
    p = TopographicParameters.model_validate(
        {
            "contour_count": 4,
            "band_fills": [{"bands": [3], "effect": "parallel-hatch", "layer_id": "hatch"}, rule()],
        }
    )
    assert [r.bands for r in p.band_fills] == [(0, 2), (3,)]
    assert p.band_fills[0].parameters["angle"] == 0
    with pytest.raises(TypeError):
        p.band_fills[0].parameters["spacing"] = 1
    assert TopographicParameters().band_fills == ()


@pytest.mark.parametrize(
    "update",
    [
        {"bands": []},
        {"bands": [True]},
        {"bands": ["1"]},
        {"bands": [1.0]},
        {"bands": [-1]},
        {"bands": [5]},
        {"bands": [0, 0]},
        {"parameters": None},
        {"parameters": {"spacing": 0}},
        {"parameters": {"unknown": 1}},
        {"effect": "missing"},
        {"layer_id": ""},
        {"extra": 0},
    ],
)
def test_invalid_rules_fail(update):
    payload = rule()
    payload.update(update)
    with pytest.raises(ValueError):
        TopographicParameters.model_validate({"contour_count": 4, "band_fills": [payload]})


def test_overlapping_rules_are_not_double_filled():
    with pytest.raises(ValueError, match="overlap"):
        TopographicParameters.model_validate({"band_fills": [rule(), rule()]})


@pytest.mark.parametrize(
    "effect", ["parallel-hatch", "crosshatch", "circle-rings", "stroke-dots", "vortex-marks"]
)
def test_catalogue_validation_is_available_without_geometry(effect):
    controls = validate_fill_parameters(effect=effect)
    assert controls["spacing"] > 0
    with pytest.raises(ValueError):
        validate_fill_parameters(effect=effect, parameters={"spacing": True})
