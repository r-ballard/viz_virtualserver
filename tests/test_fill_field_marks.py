from dataclasses import FrozenInstanceError

import pytest
from shapely.geometry import Polygon, box

from viz_virtualserver.fill_effects import (
    list_fill_effects,
    render_fill_effect,
    validate_fill_parameters,
)
from viz_virtualserver.fill_effects.field_marks import render_field_marks
from viz_virtualserver.fill_effects.vector_fields import VectorSample


class PlaneField:
    def sample(self, x, y):
        return VectorSample(2, 3)


def test_contextual_effect_descriptor_controls_and_rendering():
    effects = list_fill_effects()
    assert [e.id for e in effects] == [
        "parallel-hatch",
        "crosshatch",
        "circle-rings",
        "stroke-dots",
        "vortex-marks",
        "field-marks",
    ]
    assert [e.requires_field for e in effects] == [False] * 5 + [True]
    with pytest.raises(FrozenInstanceError):
        effects[-1].requires_field = False
    assert validate_fill_parameters(effect="field-marks") == {
        "spacing": 8,
        "mark_length": 0.5,
        "angle": 0,
    }
    region = box(-10, -10, 10, 10)
    field = PlaneField()
    assert render_fill_effect(region, effect="field-marks", field=field) == render_field_marks(
        region, spacing=8, mark_length=0.5, angle=0, field=field
    )


@pytest.mark.parametrize("region", [Polygon(), box(0, 0, 10, 10)])
@pytest.mark.parametrize("field", [None, object(), {"sample": 1}])
def test_missing_or_invalid_field_context_rejected_even_when_empty(region, field):
    with pytest.raises(ValueError, match="field"):
        render_fill_effect(region, effect="field-marks", field=field)


@pytest.mark.parametrize(
    "effect", ["parallel-hatch", "crosshatch", "circle-rings", "stroke-dots", "vortex-marks"]
)
def test_unexpected_context_on_ordinary_effect_rejected(effect):
    with pytest.raises(ValueError, match="field"):
        render_fill_effect(Polygon(), effect=effect, field=PlaneField())


def test_invalid_sample_and_controls_fail():
    class BadField:
        def sample(self, x, y):
            return (2, 3)

    with pytest.raises(ValueError, match="VectorSample"):
        render_fill_effect(box(-1, -1, 1, 1), effect="field-marks", field=BadField())
    with pytest.raises(ValueError, match="spacing"):
        render_fill_effect(Polygon(), effect="field-marks", parameters={"spacing": 0})


def test_truchet_models_reject_field_marks_without_a_source():
    from viz_virtualserver.generators.truchet.models import TruchetParameters
    from viz_virtualserver.generators.truchet.multiscale_models import MultiscaleParameters

    for model in (TruchetParameters, MultiscaleParameters):
        with pytest.raises(ValueError, match="hatch_effect"):
            model.model_validate({"hatch_effect": "field-marks"})
