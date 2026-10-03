"""Canonical and legacy entrypoints resolve to the same installed implementation."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_legacy_modules_alias_canonical_implementations() -> None:
    modules = {
        "viz_canvas.models": "viz_virtualserver.canvas.models",
        "concentric.service": "viz_virtualserver.generators.concentric.service",
        "lsystem.service": "viz_virtualserver.generators.lsystem.service",
        "radial_tiles.service": "viz_virtualserver.generators.radial_tiles.service",
        "voronoi_cells.service": "viz_virtualserver.generators.voronoi_cells.service",
    }
    for legacy, canonical in modules.items():
        assert importlib.import_module(legacy) is importlib.import_module(canonical)


def test_legacy_and_canonical_app_share_routes() -> None:
    legacy_app = importlib.import_module("server").app
    canonical_app = importlib.import_module("viz_virtualserver.server").app
    assert legacy_app is canonical_app
    assert TestClient(canonical_app).get("/").status_code == 200
    client = TestClient(canonical_app)
    for path in ("/ClippedVoronoi", "/LSystem", "/ConcentricPoints"):
        assert client.post(path, json={}).status_code != 404


def test_legacy_cli_shares_canonical_entrypoint() -> None:
    legacy = importlib.import_module("scripts.generate_domain_bundle")
    canonical = importlib.import_module("viz_virtualserver.cli.domain_bundle")
    assert legacy is canonical
    assert "voronoi-cells" in canonical.ALGORITHMS


def test_legacy_and_canonical_cli_publish_identical_bundles(tmp_path: Path) -> None:
    legacy = importlib.import_module("scripts.generate_domain_bundle")
    canonical = importlib.import_module("viz_virtualserver.cli.domain_bundle")
    job = Path(__file__).resolve().parents[1] / "examples/domain-jobs/voronoi-three-polygons.json"
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    assert legacy.main([str(job), "--output-dir", str(old_dir)]) == 0
    assert canonical.main([str(job), "--output-dir", str(new_dir)]) == 0
    for relative in (
        "design.json", "design.svg", "surfaces/square.svg",
        "surfaces/triangle.svg", "surfaces/pentagon.svg",
    ):
        assert (old_dir / relative).read_bytes() == (new_dir / relative).read_bytes()
