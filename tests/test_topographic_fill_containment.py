import math

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon

from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.models import SampledField
from viz_virtualserver.scalar_fields.regions import BandRegion


def rules(**controls):
    return TopographicParameters.model_validate(
        {
            "band_fills": [
                {
                    "bands": [0],
                    "effect": "stroke-dots",
                    "layer_id": "fill",
                    "parameters": {"spacing": 1, "mark_length": 2},
                    **controls,
                }
            ]
        }
    ).band_fills


@pytest.mark.parametrize("component", [False, True])
@pytest.mark.parametrize(
    "effect",
    ["stroke-dots", "vortex-marks", "parallel-hatch", "crosshatch", "circle-rings", "field-marks"],
)
def test_pen_footprints_respect_concavity_and_holes(component, effect):
    region = Polygon(
        [(0, 0), (20, 0), (20, 20), (10, 9), (0, 20)], holes=[[(3, 3), (7, 3), (7, 7), (3, 7)]]
    )
    style = {"effect": effect, "layer_id": "fill", "pen_width": 0.8, "boundary_margin": 0.2}
    if effect == "field-marks":
        style["field_direction"] = "contour"
        style["parameters"] = {"spacing": 2, "mark_length": 3}
    rule = {"bands": [0], **style}
    if component:
        rule = {"bands": [0], "component_choices": [{"id": "only", "weight": 1, **style}]}
    parsed = TopographicParameters.model_validate({"band_fills": [rule]}).band_fills
    sampled = SampledField((0, 0), 1, 1, np.indices((21, 21))[1])
    strokes = render_band_fills(
        (BandRegion(0, None, None, region),), parsed, domain_seed=31, sampled_field=sampled
    )
    assert strokes
    for _, stroke in strokes:
        line = LineString(stroke.points + (stroke.points[:1] if stroke.closed else ()))
        # Independent distance check includes endpoints, every segment, and hole boundaries.
        assert region.covers(line)
        assert line.distance(region.boundary) >= 0.6 - 1e-9
        assert region.covers(line.buffer(0.4))


def test_too_narrow_region_is_empty_and_zero_preserves_geometry():
    region = Polygon([(0, 0), (0.5, 0), (0.5, 10), (0, 10)])
    regions = (BandRegion(0, None, None, region),)
    assert render_band_fills(regions, rules())
    assert render_band_fills(regions, rules()) == render_band_fills(
        regions, rules(pen_width=0, boundary_margin=0)
    )
    assert render_band_fills(regions, rules(pen_width=1)) == ()


@pytest.mark.parametrize("key", ["pen_width", "boundary_margin"])
@pytest.mark.parametrize("value", [-1, True, None, "0.5", float("inf"), float("nan")])
def test_invalid_clearance_rejected(key, value):
    with pytest.raises(ValueError):
        rules(**{key: value})


def test_blank_choice_rejects_clearance_controls():
    with pytest.raises(ValueError, match="blank choice"):
        TopographicParameters.model_validate(
            {
                "band_fills": [
                    {
                        "bands": [0],
                        "component_choices": [
                            {"id": "blank", "weight": 1, "effect": None, "pen_width": 0.5}
                        ],
                    }
                ]
            }
        )


def test_containment_preserves_terrain_and_rejects_unrepresentable_clearance():
    from tests.test_topographic_service import PARAMS, SQUARE, generate
    from viz_virtualserver.canvas.models import PolygonDomain

    payload = {"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots", "layer_id": "fill"}
    results = [
        generate(
            (SQUARE,),
            params={**PARAMS, "band_fills": [{**payload, **controls}]},
            layers=("contours", "index", "fill"),
        )
        for controls in ({}, {"pen_width": 0.4, "boundary_margin": 0.2})
    ]
    assert tuple(p for p in results[0].paths if p.layer_id != "fill") == tuple(
        p for p in results[1].paths if p.layer_id != "fill"
    )
    distant = PolygonDomain("far", tuple((x + 1e12, y) for x, y in SQUARE.vertices))
    with pytest.raises(ValueError, match="represented"):
        generate(
            (distant,),
            params={**PARAMS, "band_fills": [{**payload, "pen_width": 1e-6}]},
            layers=("contours", "index", "fill"),
        )


def test_erased_region_still_requires_field_context():
    region = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    parsed = TopographicParameters.model_validate(
        {
            "band_fills": [
                {
                    "bands": [0],
                    "effect": "field-marks",
                    "field_direction": "contour",
                    "layer_id": "fill",
                    "pen_width": 10,
                }
            ]
        }
    ).band_fills
    with pytest.raises(ValueError, match="sampled terrain"):
        render_band_fills((BandRegion(0, None, None, region),), parsed, domain_seed=31)


def test_translated_concave_pen_footprint_stays_contained():
    from tests.test_topographic_service import PARAMS, generate
    from viz_virtualserver.canvas.models import PolygonDomain

    offset = 1e12
    width = 16 * math.ulp(offset)
    domain = PolygonDomain(
        "far",
        tuple((x + offset, y + offset) for x, y in ((0, 0), (20, 0), (20, 20), (10, 9), (0, 20))),
    )
    result = generate(
        (domain,),
        params={
            **PARAMS,
            "simplify_tolerance": 0,
            "band_fills": [
                {
                    "bands": list(range(9)),
                    "effect": "parallel-hatch",
                    "layer_id": "fill",
                    "parameters": {"spacing": 1, "angle": 17},
                    "pen_width": width,
                }
            ],
        },
        layers=("contours", "index", "fill"),
    )
    region = Polygon(domain.vertices)
    fills = tuple(p for p in result.paths if p.layer_id == "fill")
    assert fills
    assert all(
        region.covers(LineString(p.points))
        and LineString(p.points).distance(region.boundary) >= width / 2
        for p in fills
    )
