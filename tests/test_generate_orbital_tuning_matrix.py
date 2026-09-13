from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.generate_orbital_tuning_matrix import generate_matrix

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_JOB = REPO_ROOT / "examples" / "domain-jobs" / "orbital-concentric-tuning-base.json"
SCRIPT = REPO_ROOT / "scripts" / "generate_orbital_tuning_matrix.py"


def test_matrix_generates_named_deterministic_variants(tmp_path: Path) -> None:
    outputs = generate_matrix(BASE_JOB, tmp_path / "matrix")

    assert [path.name for path in outputs] == [
        "density-low",
        "density-medium",
        "density-high",
        "eccentricity-circular",
        "eccentricity-subtle",
        "eccentricity-varied",
    ]
    manifest = json.loads((tmp_path / "matrix" / "matrix.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in manifest["variants"]] == [path.name for path in outputs]
    assert [item["parameters"] for item in manifest["variants"]] == [
        {"orbit_count": 5},
        {"orbit_count": 8},
        {"orbit_count": 12},
        {"orbit_eccentricity": 0.0, "orbit_eccentricity_variation": 0.0},
        {"orbit_eccentricity": 0.18, "orbit_eccentricity_variation": 0.06},
        {"orbit_eccentricity": 0.32, "orbit_eccentricity_variation": 0.22},
    ]
    assert [item["seed"] for item in manifest["variants"]] == [20260912] * 6
    assert [item["bundle_path"] for item in manifest["variants"]] == [
        path.name for path in outputs
    ]


def test_matrix_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_outputs = generate_matrix(BASE_JOB, first_root)
    second_outputs = generate_matrix(BASE_JOB, second_root)

    assert [path.name for path in first_outputs] == [path.name for path in second_outputs]
    assert _sha256(first_root / "matrix.json") == _sha256(second_root / "matrix.json")
    for first_output, second_output in zip(first_outputs, second_outputs, strict=True):
        assert _sha256(first_output / "design.svg") == _sha256(second_output / "design.svg")
        for surface_name in ("square.svg", "triangle.svg", "pentagon.svg"):
            assert _sha256(first_output / "surfaces" / surface_name) == _sha256(
                second_output / "surfaces" / surface_name
            )


def test_matrix_refuses_existing_destination_without_overwrite(tmp_path: Path) -> None:
    output_root = tmp_path / "matrix"
    output_root.mkdir()
    sentinel = output_root / "sentinel.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        generate_matrix(BASE_JOB, output_root)

    assert sentinel.read_text(encoding="utf-8") == "preserve me"
    assert tuple(output_root.iterdir()) == (sentinel,)


def test_cli_overwrite_replaces_an_existing_matrix(tmp_path: Path) -> None:
    output_root = tmp_path / "matrix"
    initial = _run_cli(BASE_JOB, output_root)
    assert initial.returncode == 0, initial.stderr
    sentinel = output_root / "sentinel.txt"
    sentinel.write_text("replace me", encoding="utf-8")

    result = _run_cli(BASE_JOB, output_root, "--overwrite")

    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    assert (output_root / "matrix.json").is_file()


def _run_cli(base_job: Path, output_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(base_job),
            "--output-dir",
            str(output_root),
            *extra,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
