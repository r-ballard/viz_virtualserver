import pytest
from shapely.geometry import box

from viz_virtualserver.fill_effects import render_fill_effect
from viz_virtualserver.fill_effects.mark_selection import MarkSelection
from viz_virtualserver.fill_effects.vector_fields import VectorSample


class Field:
    def sample(self, x, y):
        return VectorSample(1, 0)


@pytest.mark.parametrize("effect", ["stroke-dots", "vortex-marks", "field-marks"])
def test_full_zero_nested_and_unchanged_surviving_geometry(effect):
    context = {"field": Field()} if effect == "field-marks" else {}

    def render(density):
        return render_fill_effect(
            box(-15, -15, 15, 15),
            effect=effect,
            parameters={"spacing": 3, "mark_length": 1, "density": density},
            density_seed=-7,
            **context,
        )

    original = render_fill_effect(
        box(-15, -15, 15, 15), effect=effect, parameters={"spacing": 3, "mark_length": 1}, **context
    )
    assert original == render(1)
    sets = [set(render(d)) for d in (0, 0.25, 0.5, 0.75, 1)]
    assert not sets[0] and all(a <= b for a, b in zip(sets, sets[1:]))
    assert 0 < len(sets[2]) < len(sets[-1])


def test_fragment_ownership_and_rejected_field_not_sampled():
    region = box(-3, -1, 3, 1).difference(box(-0.5, -0.5, 0.5, 0.5))
    for seed in range(6):
        strokes = render_fill_effect(
            region,
            effect="stroke-dots",
            parameters={"spacing": 8, "mark_length": 6, "density": 0.5},
            density_seed=seed,
        )
        assert len(strokes) == (2 if MarkSelection(0.5, seed).accepts(0, 0) else 0)

    class Spy:
        def sample(self, x, y):
            pytest.fail("sampled rejected mark")

    assert (
        render_fill_effect(region, effect="field-marks", parameters={"density": 0}, field=Spy())
        == ()
    )


def test_candidate_caps_remain_at_zero(monkeypatch):
    from viz_virtualserver.fill_effects import stroke_dots

    monkeypatch.setattr(stroke_dots, "MAX_DOT_CANDIDATES", 1)
    with pytest.raises(ValueError, match="candidate"):
        render_fill_effect(
            box(-10, -10, 10, 10), effect="stroke-dots", parameters={"spacing": 2, "density": 0}
        )
