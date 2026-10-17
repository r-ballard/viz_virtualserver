import numpy as np
import pytest
from shapely.geometry import MultiPolygon, box

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.models import SampledField
from viz_virtualserver.scalar_fields.regions import BandRegion


def rule(minimum=0, maximum=1, **updates):
    return {
        "bands": list(range(9)),
        "effect": "stroke-dots",
        "parameters": {"spacing": 3},
        "density_source": {"type": "elevation", "minimum": minimum, "maximum": maximum},
        "layer_id": "fill",
        **updates,
    }


def fills(result):
    return {p.points for p in result.paths if p.layer_id == "fill"}


def test_same_raw_field_no_resampling_or_gradients(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module
    from viz_virtualserver.generators.topographic import service
    from viz_virtualserver.scalar_fields.densities import SampledElevationDensity

    captured = []
    samples = []
    original = service.sample_field

    def sample(*args):
        samples.append(args)
        return original(*args)

    def source(field, **controls):
        captured.append(field)
        return SampledElevationDensity(field, **controls)

    monkeypatch.setattr(service, "sample_field", sample)
    monkeypatch.setattr(module, "SampledElevationDensity", source)
    monkeypatch.setattr(module, "SampledGradient", lambda *args: pytest.fail("gradient"))
    a = generate(
        (SQUARE,), params={**PARAMS, "band_fills": [rule()]}, layers=("contours", "index", "fill")
    )
    assert fills(a) and len(samples) == 1 and len(captured) == 1


def test_mapping_retention_nested_without_contour_changes_and_simplification():
    params = {**PARAMS, "band_fills": [rule(0, 0.5)]}
    a = generate((SQUARE,), params=params, layers=("contours", "index", "fill"))
    b = generate(
        (SQUARE,),
        params={**PARAMS, "band_fills": [rule(0.25, 1)]},
        layers=("contours", "index", "fill"),
    )
    full = generate(
        (SQUARE,),
        params={**PARAMS, "band_fills": [rule(1, 1)]},
        layers=("contours", "index", "fill"),
    )
    assert fills(a) < fills(b) <= fills(full)
    assert tuple(p for p in a.paths if p.layer_id != "fill") == tuple(
        p for p in full.paths if p.layer_id != "fill"
    )
    c = generate(
        (SQUARE,),
        params={**params, "simplify_tolerance": 0.5},
        layers=("contours", "index", "fill"),
    )
    assert fills(c) == fills(a)
    reversed_domain = type(SQUARE)(SQUARE.id, SQUARE.vertices[::-1])
    assert generate((reversed_domain,), params=params, layers=("contours", "index", "fill")) == a


def test_ordinary_component_agreement_and_zero_source_allowance(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    sampled = SampledField((0, 0), 1, 1, np.tile(np.linspace(0, 1, 21), (21, 1)))
    region = MultiPolygon([box(0, 0, 5, 5), box(10, 0, 15, 5)])
    ordinary = rule(bands=[0])
    choice = {k: v for k, v in ordinary.items() if k != "bands"}
    choice.update(id="dots", weight=1)
    palette = {"bands": [0], "component_choices": [choice]}

    def render(r, **kwargs):
        rules = TopographicParameters.model_validate({"band_fills": [r]}).band_fills
        return render_band_fills(
            (BandRegion(0, None, None, region),),
            rules,
            domain_seed=31,
            sampled_field=sampled,
            **kwargs,
        )

    assert {s.points for _, s in render(ordinary)} == {s.points for _, s in render(palette)}
    choice["density_source"] = {"type": "elevation", "maximum": 0}
    assert render(palette, max_vertices=0) == ()
    monkeypatch.setattr(module, "MAX_COMPONENT_CANDIDATES", 1)
    with pytest.raises(ValueError, match="candidate"):
        render(palette, max_vertices=0)


def test_zero_field_avoids_gradients_omitted_source_avoids_adapter_and_bad_context_fails(
    monkeypatch,
):
    from viz_virtualserver.generators.topographic import fills as module

    monkeypatch.setattr(module, "SampledGradient", lambda *args: pytest.fail("gradient"))
    r = rule(0, 0, effect="field-marks", field_direction="contour")
    assert not fills(
        generate(
            (SQUARE,), params={**PARAMS, "band_fills": [r]}, layers=("contours", "index", "fill")
        )
    )
    rules = TopographicParameters.model_validate({"band_fills": [{**r, "bands": [0]}]}).band_fills
    with pytest.raises(ValueError, match="terrain|SampledField"):
        render_band_fills(
            (BandRegion(0, None, None, box(0, 0, 20, 20)),),
            rules,
            domain_seed=31,
            sampled_field=object(),
        )
    monkeypatch.setattr(
        module, "SampledElevationDensity", lambda *args, **kw: pytest.fail("density adapter")
    )
    assert generate((SQUARE,), params=PARAMS).paths


def test_source_mapping_preserves_component_assignments_and_local_translation(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    decisions = []
    original = module.choose_components

    def choose(*args, **kwargs):
        result = original(*args, **kwargs)
        decisions.append(tuple((d.component.id, d.choice_id) for d in result))
        return result

    monkeypatch.setattr(module, "choose_components", choose)
    choice = {k: v for k, v in rule(0, 0.5).items() if k != "bands"}
    choice.update(id="dots", weight=3)
    palette = {
        "bands": [0, 2, 4, 6, 8],
        "component_choices": [{"id": "blank", "weight": 1, "effect": None}, choice],
    }
    params = {**PARAMS, "band_fills": [palette]}
    a = generate((SQUARE,), params=params, layers=("contours", "index", "fill"))
    choice["density_source"] = {"type": "elevation", "minimum": 0.25, "maximum": 1}
    b = generate((SQUARE,), params=params, layers=("contours", "index", "fill"))
    assert decisions[0] == decisions[1]
    assert fills(a) <= fills(b)
    shifted = type(SQUARE)(SQUARE.id, tuple((x - 30, y - 20) for x, y in SQUARE.vertices))
    moved = generate((shifted,), params=params, layers=("contours", "index", "fill"))
    assert decisions[1] == decisions[2]
    original_paths = [p for p in b.paths if p.layer_id == "fill"]
    moved_paths = [p for p in moved.paths if p.layer_id == "fill"]
    assert len(original_paths) == len(moved_paths)
    for p, q in zip(original_paths, moved_paths, strict=True):
        assert np.array(q.points) == pytest.approx(np.array(p.points) - (30, 20))
