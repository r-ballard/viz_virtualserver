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


def test_cli_exports_hatches_curves_and_outline_as_neutral_channels(tmp_path):
    job = {"schema_version": 1, "seed": 31,
           "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": "truchet-multiscale",
                       "target_domain_ids": ["panel"],
                       "parameters": {"hatch_layer_id": "hatch", "hatch_spacing": 3.0,
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
