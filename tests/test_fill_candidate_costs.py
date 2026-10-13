import pytest
from shapely.geometry import Polygon, box

from viz_virtualserver.fill_effects import estimate_fill_candidates, render_fill_effect
from viz_virtualserver.fill_effects.vector_fields import VectorSample


@pytest.mark.parametrize(
    "effect,count",
    [
        ("parallel-hatch", 6),
        ("crosshatch", 12),
        ("stroke-dots", 36),
        ("circle-rings", 36),
        ("field-marks", 36),
        ("vortex-marks", 36),
    ],
)
def test_literal_candidate_counts(effect, count):
    controls = {"spacing": 2, "angle": 0}
    if effect == "circle-rings":
        controls.update(radius=0.5)
    assert estimate_fill_candidates(box(0, 0, 10, 10), effect=effect, parameters=controls) == count
    assert estimate_fill_candidates(Polygon(), effect=effect) == 0


def test_estimator_counts_actual_field_samples_and_padding():
    samples = []

    class Field:
        def sample(self, x, y):
            samples.append((x, y))
            return VectorSample(1, 0)

    for angle in (0, 45, 1e100):
        controls = {"spacing": 2, "mark_length": 5, "angle": angle}
        expected = estimate_fill_candidates(
            box(0, 0, 10, 10), effect="field-marks", parameters=controls
        )
        samples.clear()
        render_fill_effect(
            box(0, 0, 10, 10), effect="field-marks", parameters=controls, field=Field()
        )
        assert len(samples) == expected
    assert (
        estimate_fill_candidates(
            box(0, 0, 10, 10), effect="stroke-dots", parameters={"spacing": 2, "mark_length": 5}
        )
        == 48
    )
    assert (
        estimate_fill_candidates(
            box(0, 0, 10, 10), effect="field-marks", parameters={"spacing": 2, "mark_length": 5}
        )
        == 64
    )
