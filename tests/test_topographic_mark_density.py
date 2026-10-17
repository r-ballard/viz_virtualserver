import pytest
from shapely.geometry import MultiPolygon, box

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.regions import BandRegion


def rule(density=0.5, **kwargs):
    return {
        "bands": [0, 2, 4, 6, 8],
        "effect": "stroke-dots",
        "parameters": {"spacing": 3, "density": density},
        "layer_id": "fill",
        **kwargs,
    }


def test_styles_seed_validation_and_unsupported_explicit_fields():
    p = TopographicParameters.model_validate({"band_fills": [rule(density_seed=-7)]})
    assert p.band_fills[0].density_seed == -7
    for seed in (True, 1.0, "0", None, 2**63, -(2**63) - 1):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate({"band_fills": [rule(density_seed=seed)]})
    for payload in (
        rule(effect="parallel-hatch", parameters={}, density_seed=0),
        {
            "bands": [0],
            "component_choices": [{"id": "b", "weight": 1, "effect": None, "density_seed": 0}],
        },
    ):
        with pytest.raises(ValueError):
            TopographicParameters.model_validate({"band_fills": [payload]})


def test_seed_only_changes_marks_not_terrain_and_nested_service_sets():
    results = [
        generate(
            (SQUARE,),
            params={**PARAMS, "band_fills": [rule(d)]},
            layers=("contours", "index", "fill"),
        )
        for d in (0, 0.25, 0.5, 1)
    ]
    contours = [tuple(v for v in r.paths if v.layer_id != "fill") for r in results]
    assert all(c == contours[0] for c in contours)
    paths = [{v.points for v in r.paths if v.layer_id == "fill"} for r in results]
    assert not paths[0] and all(a <= b for a, b in zip(paths, paths[1:]))
    changed = generate(
        (SQUARE,),
        params={**PARAMS, "band_fills": [rule(density_seed=1)]},
        layers=("contours", "index", "fill"),
    )
    assert {v.points for v in changed.paths if v.layer_id == "fill"} != paths[2]
    assert tuple(v for v in changed.paths if v.layer_id != "fill") == contours[0]


def test_zero_field_no_gradient_and_missing_context(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    monkeypatch.setattr(module, "SampledGradient", lambda *a: pytest.fail("gradient allocated"))
    p = rule(0, effect="field-marks", field_direction="contour")
    result = generate(
        (SQUARE,), params={**PARAMS, "band_fills": [p]}, layers=("contours", "index", "fill")
    )
    assert not any(v.layer_id == "fill" for v in result.paths)
    rules = TopographicParameters.model_validate({"band_fills": [{**p, "bands": [0]}]}).band_fills
    with pytest.raises(ValueError, match="terrain"):
        render_band_fills((BandRegion(0, None, None, box(0, 0, 20, 20)),), rules, domain_seed=31)


def test_union_component_mask_agreement_and_zero_exhausted_allowance():
    region = MultiPolygon([box(0, 0, 5, 5), box(10, 0, 15, 5)])
    ordinary = rule(bands=[0])
    choice = {k: v for k, v in ordinary.items() if k != "bands"}
    choice.update(id="dots", weight=1)
    palette = {"bands": [0], "component_choices": [choice]}

    def render(payload, cap=1_000_000):
        r = TopographicParameters.model_validate({"band_fills": [payload]}).band_fills
        return render_band_fills(
            (BandRegion(0, None, None, region),), r, domain_seed=31, max_vertices=cap
        )

    assert {s.points for _, s in render(ordinary)} == {s.points for _, s in render(palette)}
    palette["component_choices"][0]["parameters"] = {"spacing": 3, "density": 0}
    assert render(palette, 0) == ()
    with pytest.raises(ValueError, match="seed"):
        render_band_fills(
            (BandRegion(0, None, None, region),),
            TopographicParameters.model_validate({"band_fills": [ordinary]}).band_fills,
        )
