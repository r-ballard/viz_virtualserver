import numpy as np
import pytest
from shapely.geometry import LineString, Polygon, box

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.fill_effects import FillStroke
from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.models import SampledField
from viz_virtualserver.scalar_fields.regions import BandRegion


def rule(direction="slope", **updates):
    return {
        "bands": list(range(9)),
        "effect": "field-marks",
        "field_direction": direction,
        "parameters": {"spacing": 3, "mark_length": 1.5},
        "layer_id": "fill",
        **updates,
    }


def fills(result):
    return tuple(p for p in result.paths if p.layer_id == "fill")


def test_plane_orientation_and_single_adapter_shared_for_both_rules(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module
    from viz_virtualserver.generators.topographic import service
    from viz_virtualserver.scalar_fields.gradients import SampledGradient

    field = SampledField((0, 0), 1, 1, np.tile(np.linspace(0, 1, 21), (21, 1)))
    captured = []

    def construct(actual):
        assert actual is field
        captured.append(actual)
        return SampledGradient(actual)

    monkeypatch.setattr(module, "SampledGradient", construct)
    monkeypatch.setattr(service, "smooth_normalize", lambda *args: field)
    original_sample = service.sample_field
    sampled_calls = []

    def sample_once(*args):
        sampled_calls.append(args)
        return original_sample(*args)

    monkeypatch.setattr(service, "sample_field", sample_once)
    rules = [rule(bands=[0, 1, 2, 3]), rule("contour", bands=[4, 5, 6, 7, 8], layer_id="tangent")]
    result = generate(
        (SQUARE,),
        params={**PARAMS, "band_fills": rules},
        layers=("contours", "index", "fill", "tangent"),
    )
    assert len(captured) == 1
    assert len(sampled_calls) == 1
    assert fills(result) and any(p.layer_id == "tangent" for p in result.paths)
    for path in result.paths:
        if path.layer_id == "fill":
            assert path.points[0][1] == pytest.approx(path.points[-1][1])
        elif path.layer_id == "tangent":
            assert path.points[0][0] == pytest.approx(path.points[-1][0])


def test_gradient_marks_preserve_simplification_winding_and_rule_domain_order():
    rules = [rule(bands=[0, 2, 4]), rule("contour", bands=[6, 8])]
    other = PolygonDomain("other", ((0, 0), (12, 0), (12, 12), (0, 12)))
    params = {**PARAMS, "band_fills": rules}
    a = generate((SQUARE, other), params=params, layers=("contours", "index", "fill"))
    b = generate(
        (other, PolygonDomain(SQUARE.id, tuple(reversed(SQUARE.vertices)))),
        params={**params, "band_fills": rules[::-1], "simplify_tolerance": 0.5},
        layers=("contours", "index", "fill"),
    )

    def key(p):
        return (p.domain_id, p.points)

    assert fills(a) and sorted(fills(a), key=key) == sorted(fills(b), key=key)
    shifted = PolygonDomain(SQUARE.id, tuple((x - 30, y - 20) for x, y in SQUARE.vertices))
    c = generate((shifted,), params=params, layers=("contours", "index", "fill"))
    original = [p for p in fills(a) if p.domain_id == SQUARE.id]
    assert len(original) == len(fills(c))
    for p, q in zip(original, fills(c), strict=True):
        assert np.array(q.points) == pytest.approx(np.array(p.points) - (30, 20))


def test_marks_respect_band_union_hole_concavity_and_lattice_angle():
    region = Polygon(
        ((0, 0), (20, 0), (20, 20), (10, 12), (0, 20)), holes=[((2, 2), (8, 2), (8, 8), (2, 8))]
    )
    sampled = SampledField((0, 0), 1, 1, np.tile(np.arange(21), (21, 1)))
    regions = (BandRegion(0, None, None, region),)
    result = []
    for angle in (0, 45):
        rules = TopographicParameters.model_validate(
            {
                "band_fills": [
                    rule(bands=[0], parameters={"spacing": 3, "mark_length": 1.5, "angle": angle})
                ]
            }
        ).band_fills
        strokes = render_band_fills(regions, rules, sampled_field=sampled)
        assert strokes
        assert all(region.buffer(1e-10).covers(LineString(s.points)) for _, s in strokes)
        assert all(s.points[0][1] == pytest.approx(s.points[-1][1]) for _, s in strokes)
        result.append(strokes)
    assert result[0] != result[1]


def test_remaining_vertex_budget_stops_before_next_rule(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    calls = []

    def render(region, **kwargs):
        calls.append(kwargs["effect"])
        return (FillStroke(((0, 0), (1, 1))), FillStroke(((1, 0), (0, 1))))

    monkeypatch.setattr(module, "render_fill_effect", render)
    regions = (BandRegion(0, None, 0.5, box(0, 0, 1, 1)), BandRegion(1, 0.5, None, box(1, 0, 2, 1)))
    rules = TopographicParameters.model_validate(
        {
            "band_fills": [
                {"bands": [0], "effect": "stroke-dots", "layer_id": "fill"},
                {"bands": [1], "effect": "parallel-hatch", "layer_id": "fill"},
            ]
        }
    ).band_fills
    with pytest.raises(ValueError, match="vertex"):
        render_band_fills(regions, rules, max_vertices=3)
    assert calls == ["stroke-dots"]


def test_old_effects_do_not_allocate_gradients_and_constant_normalization_skips(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module
    from viz_virtualserver.generators.topographic import service

    monkeypatch.setattr(module, "SampledGradient", lambda *args: pytest.fail("gradient allocated"))
    ordinary = {"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots", "layer_id": "fill"}
    assert generate(
        (SQUARE,), params={**PARAMS, "band_fills": [ordinary]}, layers=("contours", "index", "fill")
    ).paths
    monkeypatch.setattr(service, "smooth_normalize", lambda *args: None)
    assert not generate(
        (SQUARE,), params={**PARAMS, "band_fills": [rule()]}, layers=("contours", "index", "fill")
    ).paths


def test_missing_field_fails_with_rule_context():
    rules = TopographicParameters.model_validate({"band_fills": [rule(bands=[0])]}).band_fills
    with pytest.raises(ValueError, match="band fill.*field"):
        render_band_fills((BandRegion(0, None, None, box(0, 0, 1, 1)),), rules)


def test_invalid_gradient_fails_with_rule_context_and_empty_region_keeps_selection():
    rules = TopographicParameters.model_validate({"band_fills": [rule(bands=[0])]}).band_fills
    sampled = SampledField((0, 0), 1e-300, 1, np.array([[-1e300, 1e300]] * 2))
    with pytest.raises(ValueError, match="band fill.*finite"):
        render_band_fills(
            (BandRegion(0, None, None, box(0, 0, 1, 1)),), rules, sampled_field=sampled
        )
    flat = SampledField((0, 0), 1, 1, np.ones((2, 2)))
    assert (
        render_band_fills((BandRegion(0, None, None, Polygon()),), rules, sampled_field=flat) == ()
    )
