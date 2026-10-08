"""Both generators consume the same independent field controls and mark units."""

import json
import math
import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.cli.domain_bundle import main
from viz_virtualserver.generators.truchet.multiscale_service import TruchetMultiscaleDomainAlgorithm
from viz_virtualserver.generators.truchet.service import TruchetDomainAlgorithm

SQUARE = ((0, 0), (40, 0), (40, 40), (0, 40))
ALGORITHMS = (TruchetDomainAlgorithm(), TruchetMultiscaleDomainAlgorithm())
CHANNELS = ("blue", "orange", "green")


def generate(algorithm, *, parameters=None, layers=CHANNELS, vertices=SQUARE):
    return algorithm.generate(
        canvas=CanvasGeometry("square", 40, 40, SQUARE, "edge:0"),
        domains=(PolygonDomain("panel", vertices),),
        design_pass=DesignPass("tiles", algorithm.name, ("panel",), parameters or {},
                               tuple(LogicalLayer(layer) for layer in layers)),
        context=AlgorithmContext(1, 2, {"panel": 31}, (), (), (), {}),
    )


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("region", ["painted", "unpainted"])
def test_vortex_preserves_curves_borders_insets_and_semantic_geometry(algorithm, region):
    original = generate(algorithm, parameters={"artwork_inset": 2., "outline_layer_id": "border"},
                        layers=(*CHANNELS, "border"))
    parameters = {"hatch_layer_id": "fill", "hatch_effect": "vortex-marks",
                  "hatch_spacing": 4., "hatch_mark_length": .5, "hatch_angle": 0.,
                  "hatch_field_center_x": 20., "hatch_field_center_y": 20.,
                  "hatch_region": region, "artwork_inset": 2., "outline_layer_id": "border"}
    result = generate(algorithm, parameters=parameters, layers=(*CHANNELS, "fill", "border"))
    assert tuple(p for p in result.paths if p.layer_id != "fill") == original.paths
    marks = [p for p in result.paths if p.layer_id == "fill"]
    assert marks and all(not p.closed and len(p.points) == 2 for p in marks)
    assert all(p.semantic_path.feature_role == "truchet-hatch"
               and p.semantic_path.geometry.points == p.points for p in marks)
    assert box(2, 2, 38, 38).buffer(1e-8).covers(unary_union([LineString(p.points) for p in marks]))
    assert result == generate(
        algorithm, parameters=parameters, layers=(*CHANNELS, "fill", "border"))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("tile_size", [20., 40.])
def test_field_centre_and_mark_length_use_design_units_across_tile_scales(algorithm, tile_size):
    size_control = "tile_size" if algorithm.name == "truchet" else "base_tile_size"
    result = generate(algorithm, layers=("curves", "fill"), parameters={
        size_control: tile_size, "hatch_layer_id": "fill", "hatch_effect": "vortex-marks",
        "hatch_spacing": 4., "hatch_mark_length": .5, "hatch_angle": 0.,
        "hatch_field_center_x": 20., "hatch_field_center_y": 20.,
    })
    marks = [p for p in result.paths if p.layer_id == "fill"]
    assert marks and max(math.dist(*p.points) for p in marks) == pytest.approx(.5, abs=1e-8)
    full_marks = [p for p in marks if math.dist(*p.points) >= .5 - 1e-8]
    assert full_marks
    for p in full_marks:
        a, b = p.points
        x, y = (a[0] + b[0]) / 2 - 20, (a[1] + b[1]) / 2 - 20
        assert (b[0] - a[0]) * x + (b[1] - a[1]) * y == pytest.approx(0, abs=1e-7)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_disabled_vortex_controls_preserve_output_and_validate_centres(algorithm):
    assert generate(algorithm, parameters={"hatch_effect": "vortex-marks",
                                           "hatch_field_center_x": -2.,
                                           "hatch_field_center_y": 30.}) == generate(algorithm)
    for value in (True, "20", math.inf, math.nan):
        with pytest.raises(ValueError):
            generate(algorithm, parameters={"hatch_field_center_x": value})


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_vortex_world_precision_rejects_unrepresentable_marks(algorithm):
    with pytest.raises(ValueError, match="represent"):
        generate(algorithm, vertices=tuple((x + 1e10, y) for x, y in SQUARE),
                 layers=("curves", "fill"), parameters={
                     "hatch_layer_id": "fill", "hatch_effect": "vortex-marks",
                     "hatch_mark_length": 1e-6,
                 })


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_vortex_neutral_bundle_is_deterministic(tmp_path, algorithm):
    source = tmp_path / "job.json"
    source.write_text(json.dumps({"schema_version": 1, "seed": 31,
        "domains": [{"id": "panel", "vertices": SQUARE}], "passes": [{
            "id": "tiles", "algorithm": algorithm.name, "target_domain_ids": ["panel"],
            "parameters": {"hatch_layer_id": "fill", "hatch_effect": "vortex-marks",
                           "hatch_spacing": 4., "hatch_field_center_x": 20.,
                           "hatch_field_center_y": 20.},
            "logical_layers": [{"id": "curves"}, {"id": "fill"}],
        }]}), encoding="utf-8")
    outputs = (tmp_path / "first", tmp_path / "second")
    for output in outputs:
        assert main([str(source), "--output-dir", str(output)]) == 0
        for relative in ("design.svg", "surfaces/panel.svg"):
            root = ET.parse(output / relative).getroot()
            assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"
            paths = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id='fill']/"
                                 "{http://www.w3.org/2000/svg}path")
            assert paths and all(p.get("data-viz-feature-role") == "truchet-hatch" for p in paths)
    for relative in ("design.json", "design.svg", "surfaces/panel.svg"):
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


def test_multiscale_rejects_field_centre_lost_during_normalization():
    with pytest.raises(ValueError, match="represent"):
        generate(TruchetMultiscaleDomainAlgorithm(), layers=("curves", "fill"), parameters={
            "hatch_layer_id": "fill", "hatch_effect": "vortex-marks",
            "hatch_field_center_x": 5e-324,
        })
