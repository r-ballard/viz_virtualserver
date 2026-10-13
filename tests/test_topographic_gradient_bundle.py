import json
import xml.etree.ElementTree as ET

import pytest

from viz_virtualserver.cli import domain_bundle as cli

SVG = "{http://www.w3.org/2000/svg}"


def payload():
    return {
        "schema_version": 1,
        "seed": 31,
        "domains": [{"id": "panel", "vertices": [[0, 0], [20, 0], [20, 20], [10, 12], [0, 20]]}],
        "passes": [
            {
                "id": "map",
                "algorithm": "topographic",
                "target_domain_ids": ["panel"],
                "parameters": {
                    "terrain_scale": 8,
                    "sample_spacing": 1,
                    "contour_count": 8,
                    "band_fills": [
                        {
                            "bands": [0, 2, 4, 6, 8],
                            "effect": "field-marks",
                            "field_direction": "contour",
                            "parameters": {"spacing": 3},
                            "layer_id": "marks",
                        },
                        {
                            "bands": [1, 3, 5, 7],
                            "effect": "stroke-dots",
                            "parameters": {"spacing": 3},
                            "layer_id": "dots",
                        },
                    ],
                },
                "logical_layers": [
                    {"id": "contours"},
                    {"id": "index"},
                    {"id": "marks"},
                    {"id": "dots"},
                ],
            }
        ],
    }


def test_gradient_bundle_reproducible_mixed_effects_roles_and_atomic_error(tmp_path):
    job = payload()
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job))
    a, b = tmp_path / "a", tmp_path / "b"
    for dest in (a, b):
        assert cli.main([str(source), "--output-dir", str(dest)]) == 0
    for relative in ("design.json", "design.svg", "surfaces/panel.svg"):
        assert (a / relative).read_bytes() == (b / relative).read_bytes()
    root = ET.parse(a / "surfaces/panel.svg").getroot()
    for layer in ("marks", "dots"):
        paths = root.findall(f"{SVG}g[@data-viz-layer-id='{layer}']/{SVG}path")
        assert paths and all(p.get("data-viz-feature-role") == "topographic-fill" for p in paths)
    manifest = json.loads((a / "design.json").read_text())
    assert [v["id"] for v in manifest["logical_layers"]] == ["contours", "index", "marks", "dots"]
    before = {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    job["passes"][0]["parameters"]["band_fills"][0]["field_direction"] = None
    source.write_text(json.dumps(job))
    with pytest.raises(SystemExit):
        cli.main([str(source), "--output-dir", str(a), "--overwrite"])
    assert before == {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}


def test_flat_gradient_keeps_empty_channel_and_no_partial_budget_output(tmp_path, monkeypatch):
    from viz_virtualserver.fill_effects.vector_fields import VectorSample
    from viz_virtualserver.generators.topographic import service
    from viz_virtualserver.scalar_fields.gradients import GradientField

    source = tmp_path / "job.json"
    source.write_text(json.dumps(payload()))
    with monkeypatch.context() as patch:
        patch.setattr(GradientField, "sample", lambda *args: VectorSample(0, 0))
        dest = tmp_path / "empty-marks"
        assert cli.main([str(source), "--output-dir", str(dest)]) == 0
    root = ET.parse(dest / "surfaces/panel.svg").getroot()
    assert not root.findall(f"{SVG}g[@data-viz-layer-id='marks']")
    manifest = json.loads((dest / "design.json").read_text())
    assert "marks" in [v["id"] for v in manifest["logical_layers"]]
    monkeypatch.setattr(service, "MAX_VERTICES", 1)
    with pytest.raises(SystemExit):
        cli.main([str(source), "--output-dir", str(tmp_path / "failed")])
    assert not (tmp_path / "failed").exists()
