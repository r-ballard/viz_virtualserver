import json
import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.cli.domain_bundle import main
from viz_virtualserver.generators.truchet.multiscale_service import TruchetMultiscaleDomainAlgorithm
from viz_virtualserver.generators.truchet.service import TruchetDomainAlgorithm

ALGORITHMS = (TruchetDomainAlgorithm(), TruchetMultiscaleDomainAlgorithm())
SQUARE = ((0, 0), (80, 0), (80, 80), (0, 80))
CHANNELS = ("blue", "orange", "green")
DUMBBELL = ((0, 0), (30, 0), (30, 14), (50, 14), (50, 0), (80, 0),
            (80, 30), (50, 30), (50, 16), (30, 16), (30, 30), (0, 30))


def generate(algorithm, *, vertices=SQUARE, channels=CHANNELS, parameters=None):
    domain = PolygonDomain("panel", vertices)
    design_pass = DesignPass("tiles", algorithm.name, ("panel",), parameters or {},
                             tuple(LogicalLayer(channel) for channel in channels))
    return algorithm.generate(
        canvas=CanvasGeometry("square", 80, 80, SQUARE, "edge:0"),
        domains=(domain,), design_pass=design_pass,
        context=AlgorithmContext(1, 2, {"panel": 31}, (), (), (), {}),
    )


def line(path):
    return LineString(path.points + (path.points[:1] if path.closed else ()))


def by_channel(paths):
    return {channel: unary_union([line(p) for p in paths if p.layer_id == channel])
            for channel in CHANNELS}


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("channels", [("blue",), CHANNELS])
def test_outline_is_original_polygon_and_does_not_recolor_artwork(algorithm, channels):
    original = generate(algorithm, channels=channels)
    bordered = generate(algorithm, channels=("border", *channels),
                        parameters={"outline_layer_id": "border"})
    assert tuple(p for p in bordered.paths if p.layer_id != "border") == original.paths
    outlines = [p for p in bordered.paths if p.layer_id == "border"]
    assert len(outlines) == 1
    assert outlines[0].closed and outlines[0].points == SQUARE
    assert outlines[0].domain_id == "panel" and outlines[0].producing_pass_id == "tiles"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_inset_clips_seeded_artwork_without_changing_channels(algorithm):
    original = generate(algorithm)
    inset = generate(algorithm, channels=(*CHANNELS, "border"),
                     parameters={"artwork_inset": 5.0, "outline_layer_id": "border"})
    target = box(5, 5, 75, 75)
    artwork = [p for p in inset.paths if p.layer_id != "border"]
    assert artwork and len(inset.paths) == len(artwork) + 1
    actual, before = by_channel(artwork), by_channel(original.paths)
    for channel in CHANNELS:
        expected = before[channel].intersection(target)
        assert actual[channel].symmetric_difference(expected).length < 1e-8
    assert all(target.buffer(1e-9).covers(line(p)) for p in artwork)
    assert all(line(p).distance(Polygon(SQUARE).boundary) >= 5 - 1e-9 for p in artwork)
    assert inset == generate(algorithm, channels=(*CHANNELS, "border"),
                            parameters={"artwork_inset": 5.0, "outline_layer_id": "border"})


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_concave_inset_can_split_into_two_artwork_regions(algorithm):
    original = generate(algorithm, vertices=DUMBBELL)
    result = generate(algorithm, vertices=DUMBBELL, channels=(*CHANNELS, "border"),
                      parameters={"artwork_inset": 3.0, "outline_layer_id": "border"})
    target = unary_union((box(3, 3, 27, 27), box(53, 3, 77, 27)))
    artwork = [p for p in result.paths if p.layer_id != "border"]
    actual, before = by_channel(artwork), by_channel(original.paths)
    for channel in CHANNELS:
        expected = before[channel].intersection(target)
        assert actual[channel].symmetric_difference(expected).length < 1e-8
    assert any(line(p).bounds[2] <= 27 for p in artwork)
    assert any(line(p).bounds[0] >= 53 for p in artwork)
    assert all(target.buffer(1e-9).covers(line(p)) for p in artwork)
    assert [p.points for p in result.paths if p.layer_id == "border"] == [DUMBBELL]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_inset_works_for_translated_polygon(algorithm):
    vertices = tuple((x + 1e8, y - 1e8) for x, y in SQUARE)
    result = generate(algorithm, vertices=vertices, parameters={"artwork_inset": 5.0})
    assert result.paths
    target = box(1e8 + 5, -1e8 + 5, 1e8 + 75, -1e8 + 75)
    assert all(target.buffer(1e-7).covers(line(p)) for p in result.paths)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("parameters,channels", [
    ({"artwork_inset": -1.0}, CHANNELS),
    ({"artwork_inset": float("inf")}, CHANNELS),
    ({"artwork_inset": float("nan")}, CHANNELS),
    ({"artwork_inset": 40.0}, CHANNELS),
    ({"outline_layer_id": " "}, CHANNELS),
    ({"outline_layer_id": "missing"}, CHANNELS),
    ({"outline_layer_id": "border"}, ("border",)),
])
def test_invalid_panel_options_reject(algorithm, parameters, channels):
    with pytest.raises(ValueError):
        generate(algorithm, parameters=parameters, channels=channels)


@pytest.mark.parametrize("algorithm", ["truchet", "truchet-multiscale"])
def test_cli_exports_border_as_separate_neutral_channel(tmp_path, algorithm):
    job = {"schema_version": 1, "seed": 31,
           "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": algorithm,
                       "target_domain_ids": ["panel"],
                       "parameters": {"artwork_inset": 5.0, "outline_layer_id": "border"},
                       "logical_layers": [{"id": "curves"}, {"id": "border"}]}]}
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job), encoding="utf-8")
    outputs = (tmp_path / "first", tmp_path / "second")
    for output in outputs:
        assert main([str(source), "--output-dir", str(output)]) == 0
        for relative in ("design.svg", "surfaces/panel.svg"):
            root = ET.fromstring((output / relative).read_text())
            assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"
            groups = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id]")
            assert [g.get("data-viz-layer-id") for g in groups] == ["curves", "border"]
            borders = groups[1].findall("{http://www.w3.org/2000/svg}path")
            assert len(borders) == 1 and borders[0].get("d").strip().endswith("Z")
            assert borders[0].get("data-viz-feature-role") == "polygon-outline"
    for relative in ("design.json", "design.svg", "surfaces/panel.svg"):
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


def test_collapsed_inset_never_publishes_partial_bundle(tmp_path, capsys):
    job = {"schema_version": 1, "seed": 31,
           "domains": [{"id": "panel", "vertices": SQUARE}],
           "passes": [{"id": "tiles", "algorithm": "truchet",
                       "target_domain_ids": ["panel"],
                       "parameters": {"artwork_inset": 40.0},
                       "logical_layers": [{"id": "curves"}]}]}
    source, output = tmp_path / "job.json", tmp_path / "bundle"
    source.write_text(json.dumps(job))
    with pytest.raises(SystemExit) as error:
        main([str(source), "--output-dir", str(output)])
    assert error.value.code == 2
    assert "inset" in capsys.readouterr().err.lower()
    assert not output.exists()
