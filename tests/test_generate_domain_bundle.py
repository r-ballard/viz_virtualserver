from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_domain_bundle.py"
EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "cootie-catcher.json"
SEMANTIC_IDS = [
    *(f"outer-{index}" for index in range(1, 5)),
    *(f"selector-{index}" for index in range(1, 9)),
    *(f"reveal-{index}" for index in range(1, 9)),
]
PARAMETERS = {
    "point_count": 2,
    "ring_count": 3,
    "ring_spacing": "linear",
    "boundary_mode": "clip",
    "radius_scale": 0.65,
    "overlap_mode": "allow",
    "coordinate_frame": "domain",
}


def _run_cli(
    output_dir: Path, *extra: str, job: Path = EXAMPLE
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(job),
            "--output-dir",
            str(output_dir),
            *extra,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_example_declares_twenty_placement_free_semantic_surfaces() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert [domain["id"] for domain in payload["domains"]] == SEMANTIC_IDS
    assert [surface["id"] for surface in payload["surfaces"]] == SEMANTIC_IDS
    assert [surface["domain_id"] for surface in payload["surfaces"]] == SEMANTIC_IDS
    assert [domain["vertices"] for domain in payload["domains"][:4]] == [
        [[0, 0], [100, 0], [100, 100], [0, 100]]
    ] * 4
    assert [domain["vertices"] for domain in payload["domains"][4:]] == [
        [[0, 0], [100, 0], [0, 100]]
    ] * 16
    assert payload["composition_transforms"] == []

    forbidden_keys = {
        "sheet",
        "sheet_width",
        "sheet_height",
        "placement",
        "placements",
        "slot",
        "slot_polygon",
        "rotation",
        "physical_rotation",
        "pen",
        "hpgl",
        "transport",
        "x",
        "y",
    }

    def all_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                nested_key
                for nested_value in value.values()
                for nested_key in all_keys(nested_value)
            }
        if isinstance(value, list):
            return {nested_key for nested_value in value for nested_key in all_keys(nested_value)}
        return set()

    assert all_keys(payload).isdisjoint(forbidden_keys)


def test_example_declares_explicit_selector_reveal_relations_and_independent_passes() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert payload["relations"] == [
        {
            "id": f"selector-{index}-to-reveal-{index}",
            "relation_type": "corresponds_to",
            "source": {"domain_id": f"selector-{index}"},
            "target": {"domain_id": f"reveal-{index}"},
        }
        for index in range(1, 9)
    ]
    assert len(payload["passes"]) == 20
    for domain_id, design_pass in zip(SEMANTIC_IDS, payload["passes"], strict=True):
        assert design_pass == {
            "id": f"generate-{domain_id}",
            "algorithm": "concentric-points",
            "target_domain_ids": [domain_id],
            "parameters": PARAMETERS,
            "logical_layers": [{"id": "artwork", "label": "Artwork"}],
        }


def test_cli_generates_one_to_many_bundle_and_prints_canonical_locations(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "cootie"

    result = _run_cli(output_dir)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"design.json: {output_dir.resolve() / 'design.json'}",
        f"design.svg: {output_dir.resolve() / 'design.svg'}",
        f"surfaces: {output_dir.resolve() / 'surfaces'}",
    ]
    audit = json.loads((output_dir / "design.json").read_text(encoding="utf-8"))
    assert [entry["surface_id"] for entry in audit["surfaces"]] == SEMANTIC_IDS
    assert {path.name for path in (output_dir / "surfaces").glob("*.svg")} == {
        f"{surface_id}.svg" for surface_id in SEMANTIC_IDS
    }


def test_cli_refuses_existing_destination_without_overwrite(tmp_path: Path) -> None:
    output_dir = tmp_path / "cootie"
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")

    result = _run_cli(output_dir)

    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "original"
    assert tuple(output_dir.iterdir()) == (sentinel,)


def test_cli_overwrite_atomically_replaces_existing_destination(tmp_path: Path) -> None:
    output_dir = tmp_path / "cootie"
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")

    result = _run_cli(output_dir, "--overwrite")

    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    assert {path.name for path in output_dir.iterdir()} == {
        "design.json",
        "design.svg",
        "surfaces",
    }


def test_cli_rejects_an_unregistered_algorithm_without_publishing(tmp_path: Path) -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["passes"][0]["algorithm"] = "not-registered"
    job_path = tmp_path / "unknown-algorithm.json"
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    output_dir = tmp_path / "cootie"

    result = _run_cli(output_dir, job=job_path)

    assert result.returncode != 0
    assert "unknown algorithm: not-registered" in result.stderr
    assert not output_dir.exists()
