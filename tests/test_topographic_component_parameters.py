import pytest

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.models import TopographicParameters


def rule(**updates):
    return {
        "bands": [0, 2],
        "component_choices": [
            {"id": "blank", "weight": 2, "effect": None},
            {"id": "dots", "weight": 1, "effect": "stroke-dots", "layer_id": "dots"},
        ],
        **updates,
    }


def test_canonical_frozen_palette_and_all_blank_channels():
    p = TopographicParameters.model_validate({"band_fills": [rule()]})
    assert [v.id for v in p.band_fills[0].component_choices] == ["blank", "dots"]
    assert p.band_fills[0].component_seed == 0
    with pytest.raises(ValueError):
        p.band_fills[0].component_seed = 2
    from viz_virtualserver.generators.topographic.component_models import iter_rule_styles

    blank = TopographicParameters.model_validate(
        {"band_fills": [rule(component_choices=[{"id": "b", "weight": 1, "effect": None}])]}
    )
    assert list(iter_rule_styles(blank.band_fills[0])) == []


@pytest.mark.parametrize(
    "update",
    [
        {"weight": True},
        {"weight": 0},
        {"weight": 1.0},
        {"weight": 1_000_001},
        {"id": ""},
        {"effect": "missing"},
        {"parameters": None},
        {"field_direction": "slope"},
    ],
)
def test_invalid_unused_choice_before_sampling(update, monkeypatch):
    from viz_virtualserver.generators.topographic import service

    monkeypatch.setattr(service, "sample_field", lambda *a: pytest.fail("sampled"))
    r = rule()
    r["component_choices"][1].update(update)
    with pytest.raises(ValueError):
        generate(
            (SQUARE,), params={**PARAMS, "band_fills": [r]}, layers=("contours", "index", "dots")
        )


@pytest.mark.parametrize(
    "update",
    [
        {"component_seed": True},
        {"component_choices": None},
        {"component_choices": []},
        {"effect": "stroke-dots"},
        {"layer_id": "dots"},
        {"parameters": {}},
        {"field_direction": None},
    ],
)
def test_ambiguous_rules_fail(update):
    with pytest.raises(ValueError):
        TopographicParameters.model_validate({"band_fills": [rule(**update)]})


def test_blank_rejects_render_fields_duplicates_caps_overlap():
    for choices in (
        [{"id": "b", "weight": 1, "effect": None, "layer_id": None}],
        [{"id": "b", "weight": 1, "effect": None}] * 2,
        [{"id": str(i), "weight": 1, "effect": None} for i in range(33)],
    ):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate({"band_fills": [rule(component_choices=choices)]})
    with pytest.raises(ValueError):
        TopographicParameters.model_validate({"band_fills": [rule(), rule()]})


@pytest.mark.parametrize(
    "effect",
    ["parallel-hatch", "crosshatch", "circle-rings", "stroke-dots", "vortex-marks", "field-marks"],
)
def test_every_effect_is_valid_in_choice(effect):
    choice = {"id": "effect", "weight": 1, "effect": effect, "layer_id": "fill"}
    if effect == "field-marks":
        choice["field_direction"] = "slope"
    p = TopographicParameters.model_validate({"band_fills": [rule(component_choices=[choice])]})
    assert p.band_fills[0].component_choices[0].parameters["spacing"] > 0
