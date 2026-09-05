from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.generate_domain_bundle as cli_module
import viz_canvas.bundle as bundle_module

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


def _normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_cli_refuses_destination_created_after_precheck_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "cootie"
    sentinel = output_dir / "keep.txt"
    original_verify = bundle_module._verify_staged_bundle

    def verify_then_create_destination(*args: object, **kwargs: object) -> None:
        original_verify(*args, **kwargs)  # type: ignore[arg-type]
        output_dir.mkdir()
        sentinel.write_text("racing writer", encoding="utf-8")

    monkeypatch.setattr(
        bundle_module,
        "_verify_staged_bundle",
        verify_then_create_destination,
    )

    with pytest.raises(SystemExit) as error:
        cli_module.main([str(EXAMPLE), "--output-dir", str(output_dir)])

    assert error.value.code == 2
    assert "already exists" in capsys.readouterr().err
    assert sentinel.read_text(encoding="utf-8") == "racing writer"
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


def test_cli_formats_unsupported_platform_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "cootie"

    def fail_publication(*args: object, **kwargs: object) -> object:
        raise RuntimeError(
            "atomic no-replace directory publication is unsupported on test-os"
        )

    monkeypatch.setattr(cli_module, "write_design_bundle", fail_publication)

    with pytest.raises(SystemExit) as error:
        cli_module.main([str(EXAMPLE), "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "error: atomic no-replace directory publication is unsupported" in captured.err
    assert "Traceback" not in captured.err


def test_cli_regeneration_is_deterministic_for_all_twenty_surfaces(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_result = _run_cli(first_root)
    second_result = _run_cli(second_root)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert _normalized_text(first_root / "design.json") == _normalized_text(
        second_root / "design.json"
    )
    assert _normalized_text(first_root / "design.svg") == _normalized_text(
        second_root / "design.svg"
    )

    first_audit = json.loads((first_root / "design.json").read_text(encoding="utf-8"))
    second_audit = json.loads((second_root / "design.json").read_text(encoding="utf-8"))
    first_surfaces = first_audit["surfaces"]
    second_surfaces = second_audit["surfaces"]
    assert [entry["surface_id"] for entry in first_surfaces] == SEMANTIC_IDS
    assert [entry["surface_id"] for entry in second_surfaces] == SEMANTIC_IDS

    first_audit_digests = [entry["sha256"] for entry in first_surfaces]
    second_audit_digests = [entry["sha256"] for entry in second_surfaces]
    assert len(first_audit_digests) == 20
    assert first_audit_digests == second_audit_digests

    first_actual_digests = [
        _sha256(first_root / entry["path"]) for entry in first_surfaces
    ]
    second_actual_digests = [
        _sha256(second_root / entry["path"]) for entry in second_surfaces
    ]
    assert first_actual_digests == first_audit_digests
    assert second_actual_digests == second_audit_digests
