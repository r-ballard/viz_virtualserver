import numpy as np
import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon, box

from tests.test_topographic_service import PARAMS, SQUARE, generate
from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.models import SampledField
from viz_virtualserver.scalar_fields.regions import BandRegion


def palette(**updates):
    return {
        "bands": [0],
        "component_choices": [
            {"id": "blank", "weight": 1, "effect": None},
            {
                "id": "dots",
                "weight": 1,
                "effect": "stroke-dots",
                "parameters": {"spacing": 2},
                "layer_id": "fill",
            },
        ],
        **updates,
    }


def rules(payload):
    return TopographicParameters.model_validate({"band_fills": [payload]}).band_fills


def test_components_render_with_blanks_and_own_containment():
    polygons = [box(i * 8, 0, i * 8 + 6, 6) for i in range(12)]
    region = MultiPolygon(polygons)
    r = rules(palette())
    a = render_band_fills((BandRegion(0, None, None, region),), r, domain_seed=31)
    assert a
    filled = {
        i for i, p in enumerate(polygons) if any(p.covers(LineString(s.points)) for _, s in a)
    }
    assert 0 < len(filled) < 12
    assert all(any(p.covers(LineString(s.points)) for p in polygons) for _, s in a)
    assert a == render_band_fills(
        (BandRegion(0, None, None, MultiPolygon(polygons[::-1])),), r, domain_seed=31
    )
    assert a != render_band_fills(
        (BandRegion(0, None, None, region),), rules(palette(component_seed=5)), domain_seed=31
    )


def test_union_before_components_holes_lattice_and_shared_field(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module
    from viz_virtualserver.scalar_fields.gradients import SampledGradient

    captured = []

    def gradient(field):
        captured.append(field)
        return SampledGradient(field)

    monkeypatch.setattr(module, "SampledGradient", gradient)
    left = box(0, 0, 10, 20)
    right = Polygon(
        [(10, 0), (20, 0), (20, 20), (10, 20)], holes=[[(12, 8), (18, 8), (18, 14), (12, 14)]]
    )
    field = SampledField((0, 0), 1, 1, np.tile(np.arange(21), (21, 1)))
    choices = [
        {
            "id": "marks",
            "weight": 1,
            "effect": "field-marks",
            "field_direction": "contour",
            "parameters": {"spacing": 3},
            "layer_id": "fill",
        }
    ]
    a = render_band_fills(
        (BandRegion(0, None, 0.5, left), BandRegion(1, 0.5, None, right)),
        rules(palette(bands=[0, 1], component_choices=choices)),
        domain_seed=31,
        sampled_field=field,
    )
    assert len(captured) == 1 and a
    union = left.union(right)
    assert all(union.buffer(1e-9).covers(LineString(s.points)) for _, s in a)
    assert all(s.points[0][0] == pytest.approx(s.points[-1][0]) for _, s in a)


def test_aggregate_budget_stops_before_second_component_and_vertices(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    calls = []
    original = module.render_fill_effect

    def render(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "render_fill_effect", render)
    monkeypatch.setattr(module, "MAX_COMPONENT_CANDIDATES", 10)
    region = MultiPolygon([box(0, 0, 4, 4), box(8, 0, 12, 4)])
    r = rules(
        palette(
            component_choices=[
                {
                    "id": "dots",
                    "weight": 1,
                    "effect": "stroke-dots",
                    "parameters": {"spacing": 2},
                    "layer_id": "fill",
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="candidate"):
        render_band_fills((BandRegion(0, None, None, region),), r, domain_seed=31)
    assert len(calls) == 1
    calls.clear()
    monkeypatch.setattr(module, "MAX_COMPONENT_CANDIDATES", 100_000)
    with pytest.raises(ValueError, match="vertex"):
        render_band_fills((BandRegion(0, None, None, region),), r, domain_seed=31, max_vertices=1)
    assert len(calls) == 1


def test_blank_no_gradients_potential_channels_and_service_determinism(monkeypatch):
    from viz_virtualserver.generators.topographic import fills as module

    monkeypatch.setattr(module, "SampledGradient", lambda *a: pytest.fail("gradient"))
    blank = palette(
        bands=[0, 2, 4, 6, 8], component_choices=[{"id": "blank", "weight": 1, "effect": None}]
    )
    assert generate((SQUARE,), params={**PARAMS, "band_fills": [blank]}) == generate(
        (SQUARE,), params=PARAMS
    )
    p = palette(bands=[0, 2, 4, 6, 8])
    p["component_choices"][1]["layer_id"] = "fill"
    a = generate(
        (SQUARE,), params={**PARAMS, "band_fills": [p]}, layers=("contours", "index", "fill")
    )
    b = generate(
        (SQUARE,),
        params={**PARAMS, "band_fills": [p], "simplify_tolerance": 0.5},
        layers=("contours", "index", "fill"),
    )
    assert tuple(v for v in a.paths if v.layer_id == "fill") == tuple(
        v for v in b.paths if v.layer_id == "fill"
    )
    with pytest.raises(ValueError):
        generate((SQUARE,), params={**PARAMS, "band_fills": [p]})


def test_service_translation_winding_order_and_missing_seed():
    p = palette(bands=[0, 2, 4, 6, 8])
    a = generate(
        (SQUARE,), params={**PARAMS, "band_fills": [p]}, layers=("contours", "index", "fill")
    )
    reverse = generate(
        (type(SQUARE)(SQUARE.id, SQUARE.vertices[::-1]),),
        params={**PARAMS, "band_fills": [p]},
        layers=("contours", "index", "fill"),
    )
    assert a == reverse
    shifted = type(SQUARE)(SQUARE.id, tuple((x - 30, y - 20) for x, y in SQUARE.vertices))
    b = generate(
        (shifted,), params={**PARAMS, "band_fills": [p]}, layers=("contours", "index", "fill")
    )
    ap = tuple(v for v in a.paths if v.layer_id == "fill")
    bp = tuple(v for v in b.paths if v.layer_id == "fill")
    assert len(ap) == len(bp)
    for original, moved in zip(ap, bp, strict=True):
        assert np.array(moved.points) == pytest.approx(np.array(original.points) - (30, 20))
    with pytest.raises(ValueError, match="seed"):
        render_band_fills((BandRegion(0, None, None, box(0, 0, 4, 4)),), rules(palette()))
