import math

import pytest

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.models import TopographicParameters


def style(**updates):
    return {
        "bands": [0, 2],
        "effect": "stroke-dots",
        "layer_id": "fill",
        "density_source": {"type": "elevation"},
        **updates,
    }


def test_valid_defaults_immutable_and_component_reuse():
    p = TopographicParameters.model_validate({"band_fills": [style()]})
    source = p.band_fills[0].density_source
    assert (source.type, source.minimum, source.maximum, source.invert) == (
        "elevation",
        0,
        1,
        False,
    )
    with pytest.raises(ValueError):
        source.minimum = 0.2
    choice = {k: v for k, v in style().items() if k != "bands"}
    choice.update(id="dots", weight=1)
    q = TopographicParameters.model_validate(
        {"band_fills": [{"bands": [0, 2], "component_choices": [choice]}]}
    )
    assert q.band_fills[0].component_choices[0].density_source == source


@pytest.mark.parametrize(
    "source",
    [
        None,
        {},
        {"type": "other"},
        {"type": "elevation", "minimum": True},
        {"type": "elevation", "maximum": "1"},
        {"type": "elevation", "minimum": 0.8, "maximum": 0.2},
        {"type": "elevation", "minimum": -0.1},
        {"type": "elevation", "maximum": 1.1},
        {"type": "elevation", "maximum": math.inf},
        {"type": "elevation", "minimum": math.nan},
        {"type": "elevation", "invert": 1},
        {"type": "elevation", "extra": 0},
    ],
)
def test_invalid_source_before_sampling(source, monkeypatch):
    from viz_virtualserver.generators.topographic import service

    monkeypatch.setattr(service, "sample_field", lambda *args: pytest.fail("sampled"))
    with pytest.raises(ValueError):
        generate(
            (SQUARE,),
            params={**PARAMS, "band_fills": [style(density_source=source)]},
            layers=("contours", "index", "fill"),
        )


def test_unsupported_blank_and_wrong_placement():
    blank = {"id": "b", "weight": 1, "effect": None, "density_source": {"type": "elevation"}}
    for r in (
        style(effect="parallel-hatch"),
        {"bands": [0], "component_choices": [blank]},
        style(parameters={"density_source": 0}),
        {
            "bands": [0],
            "component_choices": [{"id": "b", "weight": 1, "effect": None}],
            "density_source": {"type": "elevation"},
        },
    ):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate({"band_fills": [r]})


@pytest.mark.parametrize("effect", ["stroke-dots", "vortex-marks", "field-marks"])
def test_supported_effects_equal_inverted_bounds(effect):
    r = style(
        effect=effect,
        density_source={"type": "elevation", "minimum": 0.4, "maximum": 0.4, "invert": True},
    )
    if effect == "field-marks":
        r["field_direction"] = "contour"
    assert (
        TopographicParameters.model_validate({"band_fills": [r]})
        .band_fills[0]
        .density_source.minimum
        == 0.4
    )
