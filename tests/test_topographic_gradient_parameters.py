import pytest

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.models import TopographicParameters


def rule(**kwargs):
    return {
        "bands": [0, 2],
        "effect": "field-marks",
        "field_direction": "slope",
        "layer_id": "fill",
        **kwargs,
    }


@pytest.mark.parametrize("direction", ["slope", "contour"])
def test_explicit_field_orientation_is_valid_and_immutable(direction):
    p = TopographicParameters.model_validate({"band_fills": [rule(field_direction=direction)]})
    r = p.band_fills[0]
    assert r.field_direction == direction
    assert r.parameters == {"spacing": 8, "mark_length": 0.5, "angle": 0, "density": 1}
    with pytest.raises(ValueError):
        r.field_direction = "other"


@pytest.mark.parametrize(
    "update",
    [
        {"field_direction": None},
        {"field_direction": "other"},
        {"field_direction": True},
        {"field_direction": 1},
        {"effect": "stroke-dots"},
    ],
)
def test_invalid_orientation_rejected_before_sampling(update, monkeypatch):
    from viz_virtualserver.generators.topographic import service

    monkeypatch.setattr(service, "sample_field", lambda *args: pytest.fail("sampled"))
    with pytest.raises(ValueError):
        generate(
            (SQUARE,),
            params={**PARAMS, "band_fills": [rule(**update)]},
            layers=("contours", "index", "fill"),
        )


def test_missing_direction_and_null_on_ordinary_effect_rejected():
    missing = rule()
    del missing["field_direction"]
    for payload in (missing, rule(effect="stroke-dots", field_direction=None)):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate({"band_fills": [payload]})
