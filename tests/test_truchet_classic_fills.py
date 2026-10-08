"""Opt-in classic fills preserve the symbolic arrangement and curve artwork."""

import json
import math
import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.cli.domain_bundle import main
from viz_virtualserver.generators.truchet.assembly import assemble_grid
from viz_virtualserver.generators.truchet.models import TruchetParameters
from viz_virtualserver.generators.truchet.service import TruchetDomainAlgorithm

SQUARE = ((0, 0), (40, 0), (40, 40), (0, 40))
CHANNELS = ("blue", "orange", "green")
EFFECTS = ("parallel-hatch", "crosshatch", "circle-rings", "stroke-dots")


def generate(*, parameters=None, layers=CHANNELS, vertices=SQUARE):
    return TruchetDomainAlgorithm().generate(
        canvas=CanvasGeometry("square", 40, 40, SQUARE, "edge:0"),
        domains=(PolygonDomain("panel", vertices),),
        design_pass=DesignPass("tiles", "truchet", ("panel",), parameters or {},
                               tuple(LogicalLayer(layer) for layer in layers)),
        context=AlgorithmContext(1, 2, {"panel": 31}, (), (), (), {}),
    )


def lines(paths):
    return unary_union([LineString(p.points + (p.points[:1] if p.closed else ())) for p in paths])


@pytest.mark.parametrize("effect", EFFECTS)
@pytest.mark.parametrize("field", ["painted", "unpainted"])
def test_classic_fills_preserve_curves_colors_borders_and_insets(effect, field):
    from viz_virtualserver.generators.truchet.classic_regions import compose_regions
    from viz_virtualserver.generators.truchet.geometry import sample_arrangement

    parameters = {"arc_a": -.1, "arc_b": .3, "artwork_inset": 2.,
                  "outline_layer_id": "border", "hatch_layer_id": "fill",
                  "hatch_effect": effect, "hatch_region": field, "hatch_spacing": 3.,
                  "hatch_angle": 0., "hatch_radius": .6, "hatch_mark_length": .5,
                  "hatch_curve_tolerance": .01}
    result = generate(parameters=parameters, layers=(*CHANNELS, "fill", "border"))
    baseline = generate(parameters={"arc_a": -.1, "arc_b": .3, "artwork_inset": 2.,
                                    "outline_layer_id": "border"}, layers=(*CHANNELS, "border"))
    assert tuple(p for p in result.paths if p.layer_id != "fill") == baseline.paths
    fills = [p for p in result.paths if p.layer_id == "fill"]
    assert fills and all(p.domain_id == "panel" for p in fills)
    assert all(p.semantic_path.feature_role == "truchet-hatch"
               and p.semantic_path.geometry.points == p.points
               and p.semantic_path.geometry.closed == p.closed for p in fills)
    arrangement = assemble_grid((0, 0, 40, 40), tile_size=10., seed=31)
    _, painted = compose_regions(arrangement, sample_arrangement(
        arrangement, TruchetParameters(arc_a=-.1, arc_b=.3)))
    target = box(2, 2, 38, 38)
    selected = painted.intersection(target) if field == "painted" else target.difference(painted)
    assert selected.buffer(1e-8).covers(lines(fills))
    assert result == generate(parameters=parameters, layers=(*CHANNELS, "fill", "border"))


def test_disabled_fill_controls_preserve_output_and_skip_region_composition(monkeypatch):
    from viz_virtualserver.generators.truchet import service

    def forbidden(*args, **kwargs):
        pytest.fail("disabled fills must not compose regions")

    monkeypatch.setattr(service, "compose_regions", forbidden)
    assert generate(parameters={"hatch_effect": "stroke-dots", "hatch_region": "unpainted",
                                "hatch_spacing": .1, "hatch_mark_length": .2}) == generate()


@pytest.mark.parametrize("parameters,layers", [
    ({"hatch_layer_id": "fill"}, CHANNELS),
    ({"hatch_layer_id": "fill"}, ("fill",)),
    ({"hatch_layer_id": " "}, (*CHANNELS, "fill")),
    ({"hatch_layer_id": "fill", "outline_layer_id": "fill"}, (*CHANNELS, "fill")),
    ({"hatch_spacing": 0}, CHANNELS), ({"hatch_radius": math.inf}, CHANNELS),
    ({"hatch_mark_length": True}, CHANNELS), ({"hatch_region": "both"}, CHANNELS),
    ({"hatch_effect": "missing"}, CHANNELS),
])
def test_classic_fill_controls_reject_invalid_configuration(parameters, layers):
    with pytest.raises(ValueError):
        generate(parameters=parameters, layers=layers)


@pytest.mark.parametrize("effect", EFFECTS)
def test_classic_fill_neutral_export_is_deterministic(tmp_path, effect):
    job = {"schema_version": 1, "seed": 31, "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": "truchet", "target_domain_ids": ["panel"],
                       "parameters": {"hatch_layer_id": "fill", "hatch_effect": effect,
                                      "hatch_spacing": 3., "artwork_inset": 2.,
                                      "outline_layer_id": "border"},
                       "logical_layers": [{"id": "curves"}, {"id": "fill"}, {"id": "border"}]}]}
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job), encoding="utf-8")
    outputs = (tmp_path / "first", tmp_path / "second")
    for output in outputs:
        assert main([str(source), "--output-dir", str(output)]) == 0
        for relative in ("design.svg", "surfaces/panel.svg"):
            root = ET.parse(output / relative).getroot()
            assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"
            groups = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id]")
            assert [g.get("data-viz-layer-id") for g in groups] == ["curves", "fill", "border"]
            paths = groups[1].findall("{http://www.w3.org/2000/svg}path")
            assert paths and all(p.get("data-viz-feature-role") == "truchet-hatch" for p in paths)
            if effect == "circle-rings":
                assert any(p.get("d", "").rstrip().upper().endswith("Z") for p in paths)
    for relative in ("design.json", "design.svg", "surfaces/panel.svg"):
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


@pytest.mark.parametrize("effect", EFFECTS)
def test_classic_fills_ignore_area_free_corner_contacts(effect):
    result = generate(vertices=((0, 0), (10, 5), (0, 10)), layers=("curves", "fill"),
                      parameters={"arc_a": 0., "arc_b": 0., "hatch_layer_id": "fill",
                                  "hatch_effect": effect, "hatch_spacing": 2.})
    assert any(p.layer_id == "fill" for p in result.paths)


@pytest.mark.parametrize("offset", [0., 1e8])
def test_classic_fills_respect_split_concave_and_translated_insets(offset):
    vertices = tuple((x + offset, y) for x, y in (
        (0, 0), (16, 0), (16, 6), (24, 6), (24, 0), (40, 0),
        (40, 16), (24, 16), (24, 10), (16, 10), (16, 16), (0, 16),
    ))
    target = Polygon(vertices).buffer(-2, join_style="mitre")
    result = generate(vertices=vertices, layers=("curves", "fill"), parameters={
        "hatch_layer_id": "fill", "hatch_effect": "crosshatch", "hatch_region": "unpainted",
        "hatch_spacing": 2., "hatch_angle": 0., "artwork_inset": 2.,
    })
    fills = [p for p in result.paths if p.layer_id == "fill"]
    assert fills and target.buffer(1e-7).covers(lines(fills))
    assert all(p.points[0] != p.points[-1] for p in fills)


def test_classic_fill_rejects_unrepresentable_world_mark_length():
    with pytest.raises(ValueError, match="represent"):
        generate(vertices=tuple((x + 1e10, y) for x, y in SQUARE), layers=("curves", "fill"),
                 parameters={"hatch_layer_id": "fill", "hatch_effect": "stroke-dots",
                             "hatch_mark_length": 1e-6})


def test_dense_classic_fill_never_publishes_bundle(tmp_path, capsys):
    source, output = tmp_path / "job.json", tmp_path / "bundle"
    source.write_text(json.dumps({"schema_version": 1, "seed": 31,
        "domains": [{"id": "panel", "vertices": SQUARE}], "passes": [{
            "id": "tiles", "algorithm": "truchet", "target_domain_ids": ["panel"],
            "parameters": {"hatch_layer_id": "fill", "hatch_spacing": 1e-9},
            "logical_layers": [{"id": "curves"}, {"id": "fill"}],
        }]}), encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main([str(source), "--output-dir", str(output)])
    assert error.value.code == 2
    assert "scan rows" in capsys.readouterr().err and not output.exists()
