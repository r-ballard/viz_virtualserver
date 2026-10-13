import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from viz_virtualserver.cli import domain_bundle as cli


def test_component_bundle_reproducible_atomic_and_potential_empty_channels(tmp_path, monkeypatch):
    job = json.loads(Path("examples/domain-jobs/topographic-component-choices.json").read_text())
    job["domains"] = job["domains"][:1]
    job["domains"][0]["vertices"] = [[0, 0], [20, 0], [20, 20], [0, 20]]
    job["passes"] = job["passes"][:1]
    job["composition_transforms"] = job["composition_transforms"][:1]
    job["passes"][0]["parameters"]["band_fills"].append(
        {"bands": [1, 3, 5, 7], "effect": "parallel-hatch", "layer_id": "terrain-hatch"}
    )
    source = tmp_path / "job.json"
    source.write_text(json.dumps(job))
    a, b = tmp_path / "a", tmp_path / "b"
    for dest in (a, b):
        assert cli.main([str(source), "--output-dir", str(dest)]) == 0
    for relative in ("design.json", "design.svg", "surfaces/square.svg"):
        assert (a / relative).read_bytes() == (b / relative).read_bytes()
    manifest = json.loads((a / "design.json").read_text())
    assert [v["id"] for v in manifest["logical_layers"]] == [
        v["id"] for v in job["passes"][0]["logical_layers"]
    ]
    from viz_virtualserver.generators.topographic import fills
    from viz_virtualserver.region_selection import ComponentDecision

    with monkeypatch.context() as patch:
        patch.setattr(
            fills,
            "choose_components",
            lambda components, *args, **kw: tuple(
                ComponentDecision(c, "blank") for c in components
            ),
        )
        empty = tmp_path / "empty"
        assert cli.main([str(source), "--output-dir", str(empty)]) == 0
    root = ET.parse(empty / "surfaces/square.svg").getroot()
    assert not any(
        g.get("data-viz-layer-id", "") in ("terrain-dots", "terrain-marks")
        for g in root.iter("{http://www.w3.org/2000/svg}g")
    )
    assert len(json.loads((empty / "design.json").read_text())["logical_layers"]) == 5
    before = {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    job["passes"][0]["parameters"]["band_fills"][0]["component_choices"][1]["weight"] = 0
    source.write_text(json.dumps(job))
    with pytest.raises(SystemExit):
        cli.main([str(source), "--output-dir", str(a), "--overwrite"])
    assert before == {p.relative_to(a): p.read_bytes() for p in a.rglob("*") if p.is_file()}
