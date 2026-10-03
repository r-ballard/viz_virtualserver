"""The canonical package provides the service and bundle CLI."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from viz_virtualserver.cli.domain_bundle import ALGORITHMS, main
from viz_virtualserver.server import app


def test_canonical_app_routes() -> None:
    client = TestClient(app)
    assert client.get("/").status_code == 200
    for path in ("/ClippedVoronoi", "/LSystem", "/ConcentricPoints"):
        assert client.post(path, json={}).status_code != 404


def test_canonical_cli_publishes_bundle(tmp_path: Path) -> None:
    assert "voronoi-cells" in ALGORITHMS
    job = Path(__file__).resolve().parents[1] / "examples/domain-jobs/voronoi-three-polygons.json"
    assert main([str(job), "--output-dir", str(tmp_path / "bundle")]) == 0
    assert (tmp_path / "bundle/design.svg").is_file()
