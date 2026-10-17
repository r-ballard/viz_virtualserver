import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from viz_virtualserver.cli import domain_bundle as cli


def test_elevation_bundle_reproducible_audit_empty_and_atomic(tmp_path, monkeypatch):
    job = json.loads(Path("examples/domain-jobs/topographic-elevation-density.json").read_text())
    job["domains"] = job["domains"][:1]
    job["passes"] = job["passes"][:1]
    job["composition_transforms"] = job["composition_transforms"][:1]
    job["domains"][0]["vertices"] = [[0, 0], [20, 0], [20, 20], [0, 20]]
    style = job["passes"][0]["parameters"]["band_fills"][0]
    style["bands"] = [0, 2, 4, 6, 8]
    job["passes"][0]["parameters"]["band_fills"].append(
        {
            "bands": [1, 3, 5, 7],
            "component_choices": [
                {
                    "id": "marks",
                    "weight": 1,
                    "effect": "field-marks",
                    "field_direction": "contour",
                    "density_source": {"type": "elevation", "invert": True},
                    "layer_id": "terrain-marks",
                }
            ],
        }
    )
    job["passes"][0]["logical_layers"].append({"id": "terrain-marks"})
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job))
    original = json.dumps(job)
    a, b = tmp_path / "a", tmp_path / "b"
    for dest in (a, b):
        assert cli.main([str(source), "--output-dir", str(dest)]) == 0
    for name in ("design.json", "design.svg", "surfaces/elevation.svg"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    audit = json.loads((a / "design.json").read_text())
    assert '"density_source"' in json.dumps(audit) and '"invert": true' in json.dumps(audit)
    before = {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    style["density_source"] = {"type": "elevation", "maximum": 0}
    job["passes"][0]["parameters"]["band_fills"][1]["component_choices"][0]["density_source"] = {
        "type": "elevation",
        "maximum": 0,
    }
    source.write_text(json.dumps(job))
    empty = tmp_path / "empty"
    assert cli.main([str(source), "--output-dir", str(empty)]) == 0
    assert len(json.loads((empty / "design.json").read_text())["logical_layers"]) == 4
    root = ET.parse(empty / "surfaces/elevation.svg").getroot()
    assert not any(
        g.get("data-viz-layer-id", "").startswith("terrain-")
        for g in root.iter("{http://www.w3.org/2000/svg}g")
    )
    style["density_source"]["invert"] = 1
    source.write_text(json.dumps(job))
    with pytest.raises(SystemExit):
        cli.main([str(source), "--output-dir", str(a), "--overwrite"])
    assert before == {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    source.write_text(original)
    from viz_virtualserver.scalar_fields.densities import SampledElevationDensity

    def broken(*args):
        raise RuntimeError("injected density failure")

    monkeypatch.setattr(SampledElevationDensity, "sample", broken)
    with pytest.raises(SystemExit):
        cli.main([str(source), "--output-dir", str(a), "--overwrite"])
    assert before == {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
