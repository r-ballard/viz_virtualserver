from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

import concentric.models as orbital_models
import concentric.service as orbital_service
import lsystem.service as lsystem_service
import scripts.generate_domain_bundle as cli_module
import viz_canvas.bundle as bundle_module
from lsystem.models import LSystemRequest
from viz_canvas.job_io import read_domain_artwork_job
from viz_canvas.jobs import DomainArtworkJob
from viz_canvas.models import PolygonDomain

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_domain_bundle.py"
EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "cootie-catcher.json"
RADIAL_TILES_EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "radial-tiles-three-polygons.json"
ORBITAL_EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "orbital-concentric-three-polygons.json"
CIRCULAR_EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "orbital-concentric-circular.json"
ELLIPTICAL_EXAMPLE = REPO_ROOT / "examples" / "domain-jobs" / "orbital-concentric-elliptical.json"
COOTIE_CATCHER_ORBITAL_EXAMPLE = (
    REPO_ROOT / "examples" / "domain-jobs" / "cootie-catcher-orbital.json"
)
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


@pytest.mark.parametrize("mode, births, path_count", [
    ("cumulative", [1, 2, 3, 4], 15),
    ("delta", [4], 1),
])
def test_lsystem_birth_projection_publishes_neutral_surface(
    mode: str, births: list[int], path_count: int, tmp_path: Path,
) -> None:
    request = LSystemRequest(
        axiom="X", rules={"X": "FX", "F": "FF"}, generations=4, step=1,
    )
    domain = PolygonDomain("generation-4", ((0, 0), (16, 0), (16, 1), (0, 1)))
    job = DomainArtworkJob(1, 0, (domain,), None, (), (), (), ())
    design = lsystem_service.generate_lsystem_design(
        request, domain_id=domain.id, growth_mode=mode,
    )
    bundle = bundle_module.write_neutral_bundle(
        job, design, tmp_path / mode, projection=lsystem_service.LSYSTEM_BIRTH_PROJECTION,
    )
    audit = json.loads(bundle.audit_path.read_text(encoding="utf-8"))
    assert audit["projection"]["id"] == "lsystem-birth-generation"
    assert len(audit["logical_layers"]) == len(births)
    root = ET.fromstring(bundle.surface_paths[0].read_text(encoding="utf-8"))
    groups = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id]")
    assert [group.attrib["data-viz-layer-id"] for group in groups] == [
        f"birth-generation-i-{birth}" for birth in births
    ]
    paths = [path for group in groups for path in group.findall("{http://www.w3.org/2000/svg}path")]
    assert len(paths) == path_count
    assert all("data-pen" not in group.attrib for group in groups)


def test_cli_registers_radial_tiles_algorithm() -> None:
    assert "radial-tiles" in cli_module.ALGORITHMS


def test_cli_registers_orbital_concentric_algorithm() -> None:
    assert "orbital-concentric" in cli_module.ALGORITHMS


def test_radial_tiles_example_generates_three_surface_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "radial-tiles"

    result = _run_cli(output_dir, job=RADIAL_TILES_EXAMPLE)

    assert result.returncode == 0, result.stderr
    audit = json.loads((output_dir / "design.json").read_text(encoding="utf-8"))
    assert [surface["surface_id"] for surface in audit["surfaces"]] == [
        "square",
        "triangle",
        "concave",
    ]
    assert {path.name for path in (output_dir / "surfaces").glob("*.svg")} == {
        "square.svg",
        "triangle.svg",
        "concave.svg",
    }


def test_orbital_example_generates_three_layer_surface_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "orbital"

    result = _run_cli(output_dir, job=ORBITAL_EXAMPLE)

    assert result.returncode == 0, result.stderr
    svg = (output_dir / "surfaces" / "triangle.svg").read_text(encoding="utf-8")
    assert svg.index('id="orbits"') < svg.index('id="primary-bodies"')
    assert svg.index('id="primary-bodies"') < svg.index('id="accent-bodies"')


def test_orbital_semantic_presets_support_more_than_eight_owned_layers(tmp_path: Path) -> None:
    job = read_domain_artwork_job(ORBITAL_EXAMPLE)
    job = replace(
        job,
        passes=tuple(
            replace(
                design_pass,
                logical_layers=(),
                parameters={
                    "orbit_count": 4,
                    "bodies_per_orbit_range": [3, 3],
                    "accent_probability": 0.4,
                },
            )
            for design_pass in job.passes
        ),
    )
    default = orbital_service.generate_orbital_design(job)
    per_body = orbital_service.generate_orbital_design(job, projection="orbital-per-body")
    assert [entry.id for entry in default.catalog.entries] == [
        "orbits",
        "primary-bodies",
        "accent-bodies",
    ]
    assert len(per_body.catalog.entries) > 8
    assert per_body == orbital_service.generate_orbital_design(job, projection="orbital-per-body")
    assert {path.semantic_path.path_id: (path.points, path.closed) for path in default.paths} == {
        path.semantic_path.path_id: (path.points, path.closed) for path in per_body.paths
    }
    body_layers = {}
    for path in per_body.paths:
        if path.semantic_path.feature_role != "orbit":
            body_layers.setdefault(path.layer_id, set()).add(path.domain_id)
    assert all(len(owners) == 1 for owners in body_layers.values())
    assert len(body_layers) == 13 * len(job.domains)
    projection = orbital_models.orbital_projection("orbital-per-body")
    bundle = bundle_module.write_neutral_bundle(
        job, per_body, tmp_path / "per-body", projection=projection
    )
    audit = json.loads(bundle.audit_path.read_text(encoding="utf-8"))
    assert len(audit["logical_layers"]) == len(per_body.catalog.entries)
    assert audit["projection"]["id"] == "orbital-per-body"
    for surface in audit["surfaces"]:
        root = ET.fromstring((bundle.root / surface["path"]).read_text(encoding="utf-8"))
        groups = root.findall("{http://www.w3.org/2000/svg}g[@data-viz-layer-id]")
        assert len(groups) > 8


@pytest.mark.parametrize("example", [CIRCULAR_EXAMPLE, ELLIPTICAL_EXAMPLE])
def test_orbital_preset_generates_three_surfaces_and_layers(
    example: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / example.stem

    result = _run_cli(output_dir, job=example)

    assert result.returncode == 0, result.stderr
    assert {path.name for path in (output_dir / "surfaces").glob("*.svg")} == {
        "square.svg",
        "triangle.svg",
        "pentagon.svg",
    }
    svg = (output_dir / "surfaces" / "triangle.svg").read_text(encoding="utf-8")
    assert all(
        f'id="{layer}"' in svg
        for layer in ("orbits", "primary-bodies", "accent-bodies")
    )


@pytest.mark.parametrize(
    ("example", "expected_ellipse_parameters"),
    [
        (
            CIRCULAR_EXAMPLE,
            {
                "orbit_eccentricity": 0.0,
                "orbit_eccentricity_variation": 0.0,
                "orbit_rotation": 0.0,
                "orbit_rotation_variation": 0.0,
            },
        ),
        (
            ELLIPTICAL_EXAMPLE,
            {
                "orbit_eccentricity": 0.18,
                "orbit_eccentricity_variation": 0.06,
                "orbit_rotation": 0.25,
                "orbit_rotation_variation": 0.55,
            },
        ),
    ],
)
def test_orbital_preset_declares_selected_ellipse_parameters(
    example: Path, expected_ellipse_parameters: dict[str, float]
) -> None:
    payload = json.loads(example.read_text(encoding="utf-8"))

    parameters = payload["passes"][0]["parameters"]
    assert {
        "orbit_eccentricity": parameters["orbit_eccentricity"],
        "orbit_eccentricity_variation": parameters["orbit_eccentricity_variation"],
        "orbit_rotation": parameters["orbit_rotation"],
        "orbit_rotation_variation": parameters["orbit_rotation_variation"],
    } == expected_ellipse_parameters


@pytest.mark.parametrize("example", [CIRCULAR_EXAMPLE, ELLIPTICAL_EXAMPLE])
def test_orbital_preset_explicitly_declares_all_algorithm_parameters(
    example: Path,
) -> None:
    payload = json.loads(example.read_text(encoding="utf-8"))

    assert set(payload["passes"][0]["parameters"]) == {
        "system_count",
        "orbit_count",
        "ring_spacing",
        "ring_spacing_power",
        "boundary_mode",
        "radius_scale",
        "center_margin",
        "min_center_spacing",
        "orbit_eccentricity",
        "orbit_eccentricity_variation",
        "orbit_rotation",
        "orbit_rotation_variation",
        "bodies_per_orbit_range",
        "body_radius_range",
        "central_body_radius",
        "accent_probability",
        "minimum_body_separation",
        "orbit_gaps",
        "gap_clearance",
    }


def test_cootie_catcher_orbital_generates_twenty_owned_orbital_surfaces(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "cootie-catcher-orbital"

    result = _run_cli(output_dir, job=COOTIE_CATCHER_ORBITAL_EXAMPLE)

    assert result.returncode == 0, result.stderr
    audit = json.loads((output_dir / "design.json").read_text(encoding="utf-8"))
    assert [surface["surface_id"] for surface in audit["surfaces"]] == SEMANTIC_IDS
    assert {path.name for path in (output_dir / "surfaces").glob("*.svg")} == {
        f"{surface_id}.svg" for surface_id in SEMANTIC_IDS
    }
    for domain_id in SEMANTIC_IDS:
        svg = (output_dir / "surfaces" / f"{domain_id}.svg").read_text(encoding="utf-8")
        root = ET.fromstring(svg)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        layers = {
            layer.attrib["id"]: layer
            for layer in root.findall("svg:g[@data-viz-role='logical-layer']", namespace)
        }
        assert layers["orbits"].findall("svg:path", namespace)
        assert layers["primary-bodies"].findall("svg:path", namespace)
        paths = root.findall(
            "svg:g[@data-viz-role='logical-layer']/svg:path", namespace
        )
        assert paths
        assert all(path.attrib["data-viz-domain-id"] == domain_id for path in paths)


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
        raise RuntimeError("atomic no-replace directory publication is unsupported on test-os")

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

    first_actual_digests = [_sha256(first_root / entry["path"]) for entry in first_surfaces]
    second_actual_digests = [_sha256(second_root / entry["path"]) for entry in second_surfaces]
    assert first_actual_digests == first_audit_digests
    assert second_actual_digests == second_audit_digests
