import math

import pytest

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.models import TopographicParameters


def rule(reference=0.05, **updates):
    return {
        "bands": list(range(9)),
        "effect": "stroke-dots",
        "layer_id": "fill",
        "parameters": {"spacing": 2, "mark_length": 0.5},
        "density_source": {"type": "slope", "reference_slope": reference},
        **updates,
    }


@pytest.mark.parametrize(
    "source",
    [
        {"type": "slope"},
        *({"type": "slope", "reference_slope": v} for v in (0, -1, True, "0.1", None, math.inf)),
        {"type": "elevation", "reference_slope": 0.1},
        {"type": "slope", "reference_slope": 0.1, "minimum": 0.8, "maximum": 0.2},
    ],
)
def test_strict_sources_rejected_before_sampling(source, monkeypatch):
    from viz_virtualserver.generators.topographic import service

    monkeypatch.setattr(service, "sample_field", lambda *a: pytest.fail("sampled"))
    with pytest.raises(ValueError):
        generate(
            (SQUARE,),
            params={**PARAMS, "band_fills": [rule(density_source=source)]},
            layers=("contours", "index", "fill"),
        )


def test_nested_reference_and_multiplier_preserve_terrain_and_seed_positions():
    results = [
        generate(
            (SQUARE,), params={**PARAMS, "band_fills": [r]}, layers=("contours", "index", "fill")
        )
        for r in (
            rule(0.15),
            rule(0.05),
            rule(0.05, parameters={"spacing": 2, "mark_length": 0.5, "density": 0.5}),
        )
    ]
    marks = [{p.points for p in result.paths if p.layer_id == "fill"} for result in results]
    assert marks[0] < marks[1]
    assert marks[2] < marks[1]
    contours = [tuple(p for p in r.paths if p.layer_id != "fill") for r in results]
    assert contours[0] == contours[1] == contours[2]


def test_density_and_directions_share_one_gradient_and_no_terrain_resampling(monkeypatch):
    from viz_virtualserver.generators.topographic import fills, service

    gradients, samples = [], []
    original_gradient, original_sample = fills.SampledGradient, service.sample_field

    def gradient(field):
        gradients.append(field)
        return original_gradient(field)

    def sample(*args):
        samples.append(args)
        return original_sample(*args)

    monkeypatch.setattr(fills, "SampledGradient", gradient)
    monkeypatch.setattr(service, "sample_field", sample)
    a = rule(effect="field-marks", field_direction="contour")
    result = generate(
        (SQUARE,), params={**PARAMS, "band_fills": [a]}, layers=("contours", "index", "fill")
    )
    assert any(p.layer_id == "fill" for p in result.paths)
    assert len(gradients) == len(samples) == 1


def test_component_source_reuse_and_blank_rejection():
    style = {k: v for k, v in rule().items() if k != "bands"}
    choice = {"id": "dots", "weight": 1, **style}
    p = TopographicParameters.model_validate(
        {"band_fills": [{"bands": [0], "component_choices": [choice]}]}
    )
    assert p.band_fills[0].component_choices[0].density_source.reference_slope == 0.05
    with pytest.raises(ValueError):
        TopographicParameters.model_validate(
            {"band_fills": [{"bands": [0], "component_choices": [{**choice, "effect": None}]}]}
        )


@pytest.mark.parametrize("effect", ["stroke-dots", "vortex-marks", "field-marks"])
def test_planar_mask_matches_static_density_with_holes_and_components(effect):
    import numpy as np
    from shapely.geometry import LineString, Polygon

    from viz_virtualserver.generators.topographic.fills import render_band_fills
    from viz_virtualserver.scalar_fields.models import SampledField
    from viz_virtualserver.scalar_fields.regions import BandRegion

    sampled = SampledField((0, 0), 1, 1, np.tile(np.arange(21) / 16, (21, 1)))
    region = Polygon(
        [(0, 0), (20, 0), (20, 20), (10, 9), (0, 20)], holes=[[(3, 3), (7, 3), (7, 7), (3, 7)]]
    )
    style = rule(0.125, bands=[0], effect=effect, pen_width=0.4, boundary_margin=0.2)
    if effect == "field-marks":
        style["field_direction"] = "contour"

    def render(style, component=False):
        if component:
            choice = {k: v for k, v in style.items() if k != "bands"}
            style = {"bands": [0], "component_choices": [{"id": "only", "weight": 1, **choice}]}
        rules = TopographicParameters.model_validate({"band_fills": [style]}).band_fills
        return render_band_fills(
            (BandRegion(0, None, None, region),), rules, sampled_field=sampled, domain_seed=31
        )

    a = render(style)
    b = render(style, True)
    static = {k: v for k, v in style.items() if k != "density_source"}
    static["parameters"] = {**style["parameters"], "density": 0.5}
    assert a and set(a) == set(b) == set(render(static))
    for _, stroke in a:
        assert LineString(stroke.points).distance(region.boundary) >= 0.4 - 1e-9


@pytest.mark.parametrize("zero_source", [False, True])
def test_zero_density_does_not_build_gradients_but_still_reserves_candidates(
    zero_source, monkeypatch
):
    import numpy as np
    from shapely.geometry import box

    from viz_virtualserver.generators.topographic import fills
    from viz_virtualserver.scalar_fields.models import SampledField
    from viz_virtualserver.scalar_fields.regions import BandRegion

    monkeypatch.setattr(fills, "SampledGradient", lambda *a: pytest.fail("gradient allocated"))
    style = rule(bands=[0], effect="field-marks", field_direction="contour")
    if zero_source:
        style["density_source"]["maximum"] = 0
    else:
        style["parameters"]["density"] = 0
    choice = {k: v for k, v in style.items() if k != "bands"}
    parsed = TopographicParameters.model_validate(
        {
            "band_fills": [
                {"bands": [0], "component_choices": [{"id": "only", "weight": 1, **choice}]}
            ]
        }
    ).band_fills
    context = dict(
        sampled_field=SampledField((0, 0), 1, 1, np.ones((21, 21))), domain_seed=31, max_vertices=0
    )
    regions = (BandRegion(0, None, None, box(0, 0, 20, 20)),)
    assert fills.render_band_fills(regions, parsed, **context) == ()
    monkeypatch.setattr(fills, "MAX_COMPONENT_CANDIDATES", 1)
    with pytest.raises(ValueError, match="candidate"):
        fills.render_band_fills(regions, parsed, **context)


def test_mixed_elevation_and_slope_sources_use_distinct_cached_adapters(monkeypatch):
    from viz_virtualserver.generators.topographic import fills

    records = []
    original = fills.render_fill_effect

    def render(region, **kwargs):
        records.append(kwargs["density_field"].sample(10, 10))
        return original(region, **kwargs)

    monkeypatch.setattr(fills, "render_fill_effect", render)
    styles = [
        rule(bands=[0]),
        rule(bands=[1], density_source={"type": "elevation"}),
        rule(0.5, bands=[2]),
    ]
    generate(
        (SQUARE,), params={**PARAMS, "band_fills": styles}, layers=("contours", "index", "fill")
    )
    assert len(records) == 3
    assert records[0] != records[1]
    assert records[2] == pytest.approx(records[0] / 10)
