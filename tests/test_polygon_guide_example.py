from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "three-polygons.json"
SCRIPT = REPO_ROOT / "scripts" / "generate_domain_bundle.py"
SURFACE_IDS = ["square", "triangle", "pentagon"]


def test_three_polygon_guide_example_generates_documented_bundle(tmp_path: Path) -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert [domain["id"] for domain in payload["domains"]] == SURFACE_IDS
    assert [surface["id"] for surface in payload["surfaces"]] == SURFACE_IDS
    assert [design_pass["target_domain_ids"] for design_pass in payload["passes"]] == [
        [surface_id] for surface_id in SURFACE_IDS
    ]

    output_dir = tmp_path / "three-polygons"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(EXAMPLE),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output_dir.iterdir()} == {
        "design.json",
        "design.svg",
        "surfaces",
    }
    assert {path.name for path in (output_dir / "surfaces").iterdir()} == {
        "square.svg",
        "triangle.svg",
        "pentagon.svg",
    }
