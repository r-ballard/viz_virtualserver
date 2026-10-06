import json
import math
import xml.etree.ElementTree as ET

import pytest
from shapely import affinity, set_precision
from shapely.geometry import GeometryCollection, LineString, Polygon, box
from shapely.ops import unary_union

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.cli.domain_bundle import main
from viz_virtualserver.generators.truchet.multiscale_composition import compose_regions
from viz_virtualserver.generators.truchet.multiscale_models import MultiscaleParameters
from viz_virtualserver.generators.truchet.multiscale_service import TruchetMultiscaleDomainAlgorithm
from viz_virtualserver.generators.truchet.multiscale_subdivision import assemble_multiscale

SQUARE = ((0, 0), (80, 0), (80, 80), (0, 80))
CHANNELS = ("blue", "orange", "green")


def generate(*, parameters=None, layers=CHANNELS, vertices=SQUARE):
    domain = PolygonDomain("panel", vertices)
    return TruchetMultiscaleDomainAlgorithm().generate(
        canvas=CanvasGeometry("square", 80, 80, SQUARE, "edge:0"), domains=(domain,),
        design_pass=DesignPass("tiles", "truchet-multiscale", ("panel",), parameters or {},
                               tuple(LogicalLayer(layer) for layer in layers)),
        context=AlgorithmContext(1, 2, {"panel": 31}, (), (), (), {}),
    )


def lines(paths):
    return unary_union([LineString(p.points + (p.points[:1] if p.closed else ())) for p in paths])


def test_horizontal_hatch_spacing_has_literal_endpoints():
    from viz_virtualserver.generators.truchet.hatching import parallel_hatches

    result = parallel_hatches(box(1, 1, 9, 9), spacing=2.0, angle=0.0)
    assert tuple(p.points for p in result) == (
        ((1.0, 2.0), (9.0, 2.0)), ((1.0, 4.0), (9.0, 4.0)),
        ((1.0, 6.0), (9.0, 6.0)), ((1.0, 8.0), (9.0, 8.0)),
    )
    assert all(not p.closed for p in result)


def test_hatches_do_not_bridge_holes_or_tangent_contacts():
    from viz_virtualserver.generators.truchet.hatching import parallel_hatches

    region = Polygon(((0, 0), (10, 0), (10, 10), (0, 10)),
                     holes=[((4, 2), (6, 2), (6, 8), (4, 8))])
    result = parallel_hatches(region, spacing=5.0, angle=0.0)
    middle = [p.points for p in result if p.points[0][1] == 5]
    assert middle == [((0.0, 5.0), (4.0, 5.0)), ((6.0, 5.0), (10.0, 5.0))]
    triangle = Polygon(((0, 0), (10, 0), (5, 10)))
    assert not any(p.points[0][1] == 10 for p in parallel_hatches(
        triangle, spacing=5.0, angle=0.0))
    assert parallel_hatches(GeometryCollection(), spacing=2.0, angle=0.0) == ()


def test_hatches_cross_union_seams_and_angles_are_periodic():
    from viz_virtualserver.generators.truchet.hatching import parallel_hatches

    region = box(0, 0, 5, 10).union(box(5, 0, 10, 10))
    result = parallel_hatches(region, spacing=5.0, angle=0.0)
    assert ((0.0, 5.0), (10.0, 5.0)) in [p.points for p in result]
    assert result == parallel_hatches(region, spacing=5.0, angle=180.0)
    diagonal = parallel_hatches(box(0, 0, 10, 10), spacing=2.0, angle=45.0)
    assert diagonal
    for path in diagonal:
        (x0, y0), (x1, y1) = path.points
        assert x1 - x0 == pytest.approx(y1 - y0, abs=1e-12)


@pytest.mark.parametrize("region", ["painted", "unpainted"])
def test_selected_region_hatches_match_scanlines_and_preserve_curves(region):
    original = generate()
    parameters = {"hatch_layer_id": "hatch", "hatch_spacing": 3.0,
                  "hatch_angle": 0.0, "hatch_region": region}
    result = generate(parameters=parameters, layers=("hatch", *CHANNELS))
    assert tuple(p for p in result.paths if p.layer_id != "hatch") == original.paths
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert hatches and all(not p.closed and len(p.points) == 2 for p in hatches)
    assert all(p.semantic_path.feature_role == "truchet-hatch" for p in hatches)
    a = assemble_multiscale((0, 0, 80, 80), parameters=MultiscaleParameters(), seed=31)
    painted = affinity.scale(set_precision(compose_regions(a, curve_tolerance=.02), 0),
                             xfact=40, yfact=40, origin=(0, 0))
    target = box(0, 0, 80, 80)
    selected = target.intersection(painted) if region == "painted" else target.difference(painted)
    expected = unary_union([LineString(((0, y), (80, y))).intersection(selected)
                            for y in range(0, 81, 3)])
    actual = lines(hatches)
    assert actual.hausdorff_distance(expected) < 1e-7
    assert actual.length == pytest.approx(expected.length, abs=1e-7)
    assert selected.buffer(1e-8).covers(actual)
    assert result == generate(parameters=parameters, layers=("hatch", *CHANNELS))


def test_hatches_respect_artwork_inset_and_keep_matching_semantic_geometry():
    parameters = {"hatch_layer_id": "hatch", "hatch_spacing": 3.0,
                  "artwork_inset": 5.0, "outline_layer_id": "border"}
    result = generate(parameters=parameters, layers=(*CHANNELS, "hatch", "border"))
    original = generate(parameters={"artwork_inset": 5.0, "outline_layer_id": "border"},
                        layers=(*CHANNELS, "border"))
    assert tuple(p for p in result.paths if p.layer_id in CHANNELS) == tuple(
        p for p in original.paths if p.layer_id in CHANNELS)
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert hatches and box(5, 5, 75, 75).buffer(1e-8).covers(lines(hatches))
    assert all(p.semantic_path.geometry.points == p.points for p in hatches)
    assert [p.points for p in result.paths if p.layer_id == "border"] == [SQUARE]


def test_disabled_hatch_controls_preserve_output():
    assert generate(parameters={"hatch_spacing": 1.0, "hatch_angle": 90.0}) == generate()


def test_translated_thin_polygon_rejects_unrepresentable_hatch_spacing():
    vertices = ((0, 1e10), (80, 1e10), (80, 1e10 + .001), (0, 1e10 + .001))
    with pytest.raises(ValueError, match="hatch spacing.*represent"):
        generate(vertices=vertices, layers=("curves", "hatch"), parameters={
            "hatch_layer_id": "hatch", "hatch_spacing": 1e-6,
            "hatch_angle": 0.0, "hatch_region": "unpainted",
        })


def test_hatch_fragments_collapsed_by_world_conversion_are_discarded():
    result = generate(vertices=((1e10, 0), (1e10 + 80, 0), (1e10 + 40, 80)),
                      layers=("curves", "hatch"), parameters={
                          "hatch_layer_id": "hatch", "hatch_spacing": 80 - 1e-8,
                          "hatch_angle": 0.0,
                      })
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert hatches
    assert all(p.points[0] != p.points[-1] for p in hatches)


@pytest.mark.parametrize("vertices,target", [
    (((0, 0), (30, 0), (30, 14), (50, 14), (50, 0), (80, 0),
      (80, 30), (50, 30), (50, 16), (30, 16), (30, 30), (0, 30)),
     unary_union((box(3, 3, 27, 27), box(53, 3, 77, 27)))),
    (tuple((x + 1e8, y - 1e8) for x, y in SQUARE),
     box(1e8 + 3, -1e8 + 3, 1e8 + 77, -1e8 + 77)),
])
def test_hatches_stay_inside_split_concave_and_translated_insets(vertices, target):
    result = generate(vertices=vertices, layers=("curves", "hatch"), parameters={
        "hatch_layer_id": "hatch", "hatch_spacing": 2.0,
        "hatch_region": "unpainted", "artwork_inset": 3.0,
    })
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert hatches and target.buffer(1e-7).covers(lines(hatches))
    assert all(len(set(p.points)) >= 2 for p in hatches)
    assert all(p.semantic_path.geometry.points == p.points for p in hatches)


@pytest.mark.parametrize("parameters,layers", [
    ({"hatch_layer_id": "hatch"}, CHANNELS),
    ({"hatch_layer_id": "hatch"}, ("hatch",)),
    ({"hatch_layer_id": " "}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "outline_layer_id": "hatch"}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_spacing": 0.0}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_spacing": -1.0}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_spacing": math.inf}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_angle": math.nan}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_region": "both"}, (*CHANNELS, "hatch")),
    ({"hatch_layer_id": "hatch", "hatch_spacing": 1e-9}, (*CHANNELS, "hatch")),
])
def test_invalid_hatching_controls_reject(parameters, layers):
    with pytest.raises(ValueError):
        generate(parameters=parameters, layers=layers)


@pytest.mark.parametrize("effect", ["parallel-hatch", "crosshatch", "circle-rings"])
def test_cli_exports_hatches_curves_and_outline_as_neutral_channels(tmp_path, effect):
    job = {"schema_version": 1, "seed": 31,
           "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": "truchet-multiscale",
                       "target_domain_ids": ["panel"],
                       "parameters": {"hatch_layer_id": "hatch", "hatch_spacing": 3.0,
                                      "hatch_effect": effect,
                                      "artwork_inset": 5.0, "outline_layer_id": "border"},
                       "logical_layers": [{"id": "curves"}, {"id": "hatch"},
                                          {"id": "border"}]}]}
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job), encoding="utf-8")
    outputs = (tmp_path / "first", tmp_path / "second")
    for output in outputs:
        assert main([str(source), "--output-dir", str(output)]) == 0
        for relative in ("design.svg", "surfaces/panel.svg"):
            root = ET.fromstring((output / relative).read_text())
            assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"
            groups = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id]")
            assert [g.get("data-viz-layer-id") for g in groups] == ["curves", "hatch", "border"]
            hatch_paths = groups[1].findall("{http://www.w3.org/2000/svg}path")
            assert hatch_paths and all(p.get("data-viz-feature-role") == "truchet-hatch"
                                       for p in hatch_paths)
            if effect == "circle-rings":
                assert any(p.get("d", "").rstrip().upper().endswith("Z") for p in hatch_paths)
    for relative in ("design.json", "design.svg", "surfaces/panel.svg"):
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


def test_dense_hatching_never_publishes_partial_bundle(tmp_path, capsys):
    job = {"schema_version": 1, "seed": 31,
           "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": "truchet-multiscale",
                       "target_domain_ids": ["panel"],
                       "parameters": {"hatch_layer_id": "hatch", "hatch_spacing": 1e-9},
                       "logical_layers": [{"id": "curves"}, {"id": "hatch"}]}]}
    source, output = tmp_path / "job.json", tmp_path / "bundle"
    source.write_text(json.dumps(job))
    with pytest.raises(SystemExit) as error:
        main([str(source), "--output-dir", str(output)])
    assert error.value.code == 2
    assert "hatch" in capsys.readouterr().err.lower() and not output.exists()


@pytest.mark.parametrize("angle", [0, 45, 135])
def test_compatibility_adapter_matches_shared_geometry(angle):
    from viz_virtualserver.fill_effects import render_fill_effect
    from viz_virtualserver.generators.truchet.hatching import parallel_hatches
    from viz_virtualserver.generators.truchet.models import CurvePath

    holed = Polygon(SQUARE, holes=[((20, 20), (60, 20), (60, 60), (20, 60))])
    for region in (holed, box(0, 0, 10, 10).union(box(20, 0, 30, 10))):
        old = parallel_hatches(region, spacing=3, angle=angle)
        shared = render_fill_effect(region, effect="parallel-hatch",
                                    parameters={"spacing": 3, "angle": angle})
        assert old and all(isinstance(p, CurvePath) for p in old)
        assert [(p.points, p.closed) for p in old] == [(p.points, p.closed) for p in shared]


def test_multiscale_uses_shared_catalogue(monkeypatch):
    from viz_virtualserver.fill_effects import render_fill_effect
    from viz_virtualserver.generators.truchet import multiscale_composition

    calls = []

    def observed(region, *, effect, parameters):
        calls.append((effect, parameters))
        return render_fill_effect(region, effect=effect, parameters=parameters)

    monkeypatch.setattr(multiscale_composition, "render_fill_effect", observed)
    result = generate(parameters={"hatch_layer_id": "hatch", "hatch_spacing": 3,
                                  "hatch_angle": 0}, layers=("curves", "hatch"))
    assert calls == [("parallel-hatch", {"spacing": 3 / 40, "angle": 0})]
    assert any(p.layer_id == "hatch" and len(p.points) == 2 for p in result.paths)


@pytest.mark.parametrize("region", ["painted", "unpainted"])
def test_crosshatch_preserves_curves_layers_and_inset(region):
    parameters = {"hatch_layer_id": "hatch", "hatch_spacing": 3., "hatch_angle": 0.,
                  "hatch_region": region, "artwork_inset": 5., "outline_layer_id": "border"}
    layers = (*CHANNELS, "hatch", "border")
    parallel = generate(parameters=parameters, layers=layers)
    result = generate(parameters={**parameters, "hatch_effect": "crosshatch"}, layers=layers)
    assert tuple(p for p in result.paths if p.layer_id != "hatch") == tuple(
        p for p in parallel.paths if p.layer_id != "hatch")
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert len(hatches) > sum(p.layer_id == "hatch" for p in parallel.paths)
    assert {(p.points[0][0] == p.points[1][0], p.points[0][1] == p.points[1][1])
            for p in hatches} == {(True, False), (False, True)}
    assert all(p.semantic_path.feature_role == "truchet-hatch"
               and p.semantic_path.geometry.points == p.points for p in hatches)
    arrangement = assemble_multiscale((0, 0, 80, 80), parameters=MultiscaleParameters(), seed=31)
    painted = affinity.scale(set_precision(compose_regions(arrangement, curve_tolerance=.02), 0),
                             xfact=40, yfact=40, origin=(0, 0))
    inset = box(5, 5, 75, 75)
    selected = painted.intersection(inset) if region == "painted" else inset.difference(painted)
    grid = [LineString(((0, v), (80, v))) for v in range(0, 81, 3)]
    grid.extend(LineString(((v, 0), (v, 80))) for v in range(0, 81, 3))
    expected = unary_union([line.intersection(selected) for line in grid])
    actual = lines(hatches)
    assert actual.hausdorff_distance(expected) < 1e-7
    assert actual.length == pytest.approx(expected.length, abs=1e-7)
    assert result == generate(
        parameters={**parameters, "hatch_effect": "crosshatch"}, layers=layers)


def test_effect_selector_is_validated_but_disabled_hatches_preserve_output():
    assert generate(parameters={"hatch_effect": "crosshatch"}) == generate()
    with pytest.raises(ValueError):
        generate(parameters={"hatch_effect": "missing"})


@pytest.mark.parametrize("region", ["painted", "unpainted"])
def test_circle_rings_preserve_closed_paths_insets_and_provenance(region):
    parameters = {"hatch_layer_id": "hatch", "hatch_effect": "circle-rings",
                  "hatch_spacing": 8., "hatch_radius": 2., "hatch_curve_tolerance": .02,
                  "hatch_angle": 0., "hatch_region": region,
                  "artwork_inset": 5., "outline_layer_id": "border"}
    layers = (*CHANNELS, "hatch", "border")
    result = generate(parameters=parameters, layers=layers)
    baseline = generate(parameters={"artwork_inset": 5., "outline_layer_id": "border"},
                        layers=(*CHANNELS, "border"))
    assert tuple(p for p in result.paths if p.layer_id != "hatch") == baseline.paths
    hatches = [p for p in result.paths if p.layer_id == "hatch"]
    assert hatches and any(p.closed for p in hatches) and any(not p.closed for p in hatches)
    assert box(5, 5, 75, 75).buffer(1e-8).covers(lines(hatches))
    assert all(p.semantic_path.geometry.closed == p.closed
               and p.semantic_path.geometry.points == p.points
               and p.semantic_path.feature_role == "truchet-hatch" for p in hatches)
    arrangement = assemble_multiscale((0, 0, 80, 80), parameters=MultiscaleParameters(), seed=31)
    painted = affinity.scale(set_precision(compose_regions(arrangement, curve_tolerance=.02), 0),
                             xfact=40, yfact=40, origin=(0, 0))
    selected = painted if region == "painted" else box(0, 0, 80, 80).difference(painted)
    assert selected.buffer(1e-8).covers(lines(hatches))
    assert result == generate(parameters=parameters, layers=layers)


@pytest.mark.parametrize("tile_size", [20., 40.])
def test_ring_radius_and_tolerance_use_design_units(tile_size):
    result = generate(parameters={"hatch_layer_id": "hatch", "hatch_effect": "circle-rings",
                                  "hatch_spacing": 8., "hatch_radius": 2.,
                                  "hatch_curve_tolerance": .01, "base_tile_size": tile_size},
                      layers=("curves", "hatch"))
    rings = [p for p in result.paths if p.layer_id == "hatch" and p.closed]
    assert rings
    for ring in rings:
        centre = ((min(x for x, _ in ring.points) + max(x for x, _ in ring.points)) / 2,
                  (min(y for _, y in ring.points) + max(y for _, y in ring.points)) / 2)
        assert all(math.hypot(x - centre[0], y - centre[1]) == pytest.approx(2., abs=1e-7)
                   for x, y in ring.points)
        for a, b in zip(ring.points, ring.points[1:] + ring.points[:1], strict=True):
            distance = math.hypot((a[0] + b[0]) / 2 - centre[0],
                                  (a[1] + b[1]) / 2 - centre[1])
            assert 2 - distance <= .01 + 1e-7


@pytest.mark.parametrize("parameters", [
    {"hatch_radius": 0}, {"hatch_radius": math.inf},
    {"hatch_curve_tolerance": 0}, {"hatch_curve_tolerance": math.nan},
])
def test_invalid_ring_controls_reject_even_when_disabled(parameters):
    with pytest.raises(ValueError):
        generate(parameters=parameters)


def test_disabled_ring_controls_preserve_output():
    assert generate(parameters={"hatch_effect": "circle-rings", "hatch_radius": 3.,
                                "hatch_curve_tolerance": .01}) == generate()


def test_world_translation_cannot_hide_unrepresentable_ring_tolerance():
    vertices = tuple((x + 1e10, y) for x, y in SQUARE)
    with pytest.raises(ValueError, match="represent"):
        generate(vertices=vertices, layers=("curves", "hatch"), parameters={
            "hatch_layer_id": "hatch", "hatch_effect": "circle-rings",
            "hatch_spacing": 8., "hatch_radius": 2., "hatch_curve_tolerance": 1e-7,
        })


def test_ring_world_conversion_reserves_rounding_budget():
    vertices = tuple((x + 1e13, y) for x, y in SQUARE)
    result = generate(vertices=vertices, layers=("curves", "hatch"), parameters={
        "hatch_layer_id": "hatch", "hatch_effect": "circle-rings", "hatch_angle": 0.,
        "hatch_spacing": 8., "hatch_radius": 1., "hatch_curve_tolerance": .07613,
        "curve_tolerance": .2, "max_depth": 0,
    })
    rings = [p for p in result.paths if p.layer_id == "hatch" and p.closed]
    assert rings
    for ring in rings:
        centre = ((min(x for x, _ in ring.points) + max(x for x, _ in ring.points)) / 2,
                  (min(y for _, y in ring.points) + max(y for _, y in ring.points)) / 2)
        for a, b in zip(ring.points, ring.points[1:] + ring.points[:1], strict=True):
            distance = math.hypot((a[0] + b[0]) / 2 - centre[0],
                                  (a[1] + b[1]) / 2 - centre[1])
            assert 1 - distance <= .07613 + 1e-9


def test_ring_inset_keeps_one_contiguous_arc_across_closure_seam():
    from viz_virtualserver.canvas.design import VectorPath
    from viz_virtualserver.generators.truchet.panels import apply_panel_options

    # A closed diamond's lexicographic seam lies on its left side. A right-side
    # inset cut should leave one three-edge arc, not two paths meeting at the seam.
    domain = PolygonDomain("panel", ((-3, -3), (1.5, -3), (1.5, 3), (-3, 3)))
    source = VectorPath(((-1., 0.), (0., -1.), (1., 0.), (0., 1.)), True, "hatch", "panel")
    result = apply_panel_options(
        (source,), domain, artwork_inset=1., outline_layer_id=None,
        pass_id="rings", merge_ring_layer_id="hatch")
    assert len(result) == 1 and not result[0].closed
    assert result[0].points == ((.5, -.5), (0., -1.), (-1., 0.), (0., 1.), (.5, .5))
    curve = VectorPath(source.points, True, "curves", "panel")
    combined = apply_panel_options(
        (source, curve), domain, artwork_inset=1., outline_layer_id=None,
        pass_id="rings", merge_ring_layer_id="hatch")
    assert sum(p.layer_id == "hatch" for p in combined) == 1
    assert sum(p.layer_id == "curves" for p in combined) == 2
