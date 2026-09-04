from __future__ import annotations

import dataclasses
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import viz_canvas.bundle as bundle_module
from viz_canvas.bundle import write_design_bundle
from viz_canvas.design import DesignPass, DesignResult, DesignState, VectorPath
from viz_canvas.frames import AffineTransform, CompositionTransform
from viz_canvas.jobs import DomainArtworkJob
from viz_canvas.models import PolygonDomain
from viz_canvas.semantics import PolygonSurface
from viz_canvas.svg import SVG_NS

NS = {"svg": SVG_NS}


def _job(
    *,
    surface_ids: tuple[str, ...] = ("First", "Second"),
) -> tuple[DomainArtworkJob, DesignState]:
    first = PolygonDomain("first-domain", ((0, 0), (10, 0), (0, 10)))
    second = PolygonDomain("second-domain", ((20, 0), (30, 0), (20, 10)))
    job = DomainArtworkJob(
        schema_version=1,
        seed=42,
        domains=(first, second),
        surfaces=(
            PolygonSurface(surface_ids[0], first.id),
            PolygonSurface(surface_ids[1], second.id),
        ),
        groups=(),
        relations=(),
        composition_transforms=(
            CompositionTransform(
                first.id,
                AffineTransform(a=2, b=0, c=0, d=2, e=100, f=50),
            ),
        ),
        passes=(DesignPass("draw", "fixture", (first.id, second.id)),),
    )
    state = DesignState(
        source_domains=job.domains,
        results=(
            DesignResult(
                paths=(
                    VectorPath(((1, 2), (3, 4)), False, "ink", first.id),
                    VectorPath(
                        ((102, 52), (104, 54)),
                        False,
                        "ink",
                        first.id,
                        "composition",
                    ),
                    VectorPath(((21, 2), (23, 4)), False, "ink", second.id),
                ),
                derived_domains=(),
                producing_pass_id="draw",
            ),
        ),
    )
    return job, state


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_work_directories(parent: Path) -> list[Path]:
    return sorted(parent.glob(".bundle-*"))


@pytest.mark.parametrize("output", ["", ".", Path(""), Path(".")])
def test_empty_or_dot_destination_is_rejected_before_filesystem_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str | Path
) -> None:
    job, state = _job()
    current = tmp_path / "current"
    current.mkdir()
    sentinel = current / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")
    monkeypatch.chdir(current)

    def reject_staging(*args: object, **kwargs: object) -> Path:
        pytest.fail("unsafe destination reached filesystem staging")

    monkeypatch.setattr(bundle_module, "_make_sibling_directory", reject_staging)

    with pytest.raises(ValueError, match="current directory"):
        write_design_bundle(job, state, output)  # type: ignore[arg-type]

    assert sentinel.read_text(encoding="utf-8") == "original"
    assert tuple(current.iterdir()) == (sentinel,)


def test_absolute_current_directory_destination_is_rejected_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def reject_staging(*args: object, **kwargs: object) -> Path:
        pytest.fail("unsafe destination reached filesystem staging")

    monkeypatch.setattr(bundle_module, "_make_sibling_directory", reject_staging)

    with pytest.raises(ValueError, match="current directory"):
        write_design_bundle(job, state, tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "original"


def test_existing_file_destination_is_rejected_without_modification(tmp_path: Path) -> None:
    job, state = _job()
    destination = tmp_path / "bundle"
    destination.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a directory"):
        write_design_bundle(job, state, destination)

    assert destination.read_text(encoding="utf-8") == "original"
    assert _bundle_work_directories(tmp_path) == []


def test_bundle_writes_ordered_surface_files_and_verified_digests(
    tmp_path: Path,
) -> None:
    job, state = _job()

    bundle = write_design_bundle(job, state, tmp_path / "bundle")

    assert bundle.root == (tmp_path / "bundle").resolve()
    assert [path.name for path in bundle.surface_paths] == ["first.svg", "second.svg"]
    audit = json.loads(bundle.audit_path.read_text(encoding="utf-8"))
    assert [item["surface_id"] for item in audit["surfaces"]] == ["First", "Second"]
    assert [item["path"] for item in audit["surfaces"]] == [
        "surfaces/first.svg",
        "surfaces/second.svg",
    ]
    assert [item["sha256"] for item in audit["surfaces"]] == [
        _sha256(bundle.surface_paths[0]),
        _sha256(bundle.surface_paths[1]),
    ]
    assert audit["design_svg"] == {
        "path": "design.svg",
        "sha256": _sha256(bundle.design_svg_path),
    }
    assert _bundle_work_directories(tmp_path) == []


def test_canonical_svg_applies_domain_transform_once_by_path_frame(
    tmp_path: Path,
) -> None:
    job, state = _job()

    bundle = write_design_bundle(job, state, tmp_path / "bundle")

    root = ET.fromstring(bundle.design_svg_path.read_text(encoding="utf-8"))
    paths = root.findall("svg:g[@id='ink']/svg:path", NS)
    assert [path.attrib["d"] for path in paths] == [
        "M 102 54 L 106 58",
        "M 102 52 L 104 54",
        "M 21 2 L 23 4",
    ]
    assert [path.attrib["data-viz-source-coordinate-frame"] for path in paths] == [
        "domain",
        "composition",
        "domain",
    ]
    assert [path.attrib["data-viz-coordinate-frame"] for path in paths] == [
        "composition",
        "composition",
        "domain",
    ]
    assert [path.attrib["data-viz-serialized-coordinate-frame"] for path in paths] == [
        "composition",
        "composition",
        "domain",
    ]
    metadata = json.loads(root.find("svg:metadata", NS).text)
    assert metadata["domains"][0]["vertices"] == [
        [100.0, 50.0],
        [120.0, 50.0],
        [100.0, 70.0],
    ]


def test_canonical_svg_preserves_interleaved_path_order_and_owner_frame_metadata(
    tmp_path: Path,
) -> None:
    job, state = _job()
    first = job.domains[0]
    ordered_state = dataclasses.replace(
        state,
        results=(
            DesignResult(
                paths=(
                    VectorPath(((1, 1), (2, 2)), False, "ink", first.id),
                    VectorPath(
                        ((102, 52), (104, 54)),
                        False,
                        "accent",
                        first.id,
                        "composition",
                    ),
                    VectorPath(((3, 3), (4, 4)), False, "ink", first.id),
                ),
                derived_domains=(),
                producing_pass_id="draw",
            ),
        ),
    )

    root = ET.fromstring(
        write_design_bundle(job, ordered_state, tmp_path / "bundle")
        .design_svg_path.read_text(encoding="utf-8")
    )
    groups = root.findall("svg:g", NS)

    assert [group.attrib["id"] for group in groups] == [
        "ink",
        "accent",
        "ink--run-2",
    ]
    document_ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
    assert len(set(document_ids)) == len(document_ids)
    assert [group.attrib["data-viz-layer"] for group in groups] == [
        "ink",
        "accent",
        "ink",
    ]
    paths = [group.find("svg:path", NS) for group in groups]
    assert [path.attrib["d"] for path in paths] == [
        "M 102 52 L 104 54",
        "M 102 52 L 104 54",
        "M 106 56 L 108 58",
    ]
    assert [path.attrib["data-viz-domain-id"] for path in paths] == [
        first.id,
        first.id,
        first.id,
    ]
    assert [path.attrib["data-viz-source-coordinate-frame"] for path in paths] == [
        "domain",
        "composition",
        "domain",
    ]


def test_repeated_bundle_generation_is_byte_deterministic(tmp_path: Path) -> None:
    job, state = _job()

    first = write_design_bundle(job, state, tmp_path / "first")
    second = write_design_bundle(job, state, tmp_path / "second")

    assert first.audit_path.read_bytes() == second.audit_path.read_bytes()
    assert first.design_svg_path.read_bytes() == second.design_svg_path.read_bytes()
    assert [path.read_bytes() for path in first.surface_paths] == [
        path.read_bytes() for path in second.surface_paths
    ]


def test_filename_collision_does_not_replace_existing_output(tmp_path: Path) -> None:
    job, state = _job(surface_ids=("Panel A", "panel-a"))
    destination = tmp_path / "bundle"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError, match="filename collision"):
        write_design_bundle(job, state, destination)

    assert sentinel.read_text(encoding="utf-8") == "original"
    assert tuple(destination.iterdir()) == (sentinel,)


@pytest.mark.parametrize("surface_id", ["***", ".", "..", "CON.txt"])
def test_unsafe_sanitized_filename_is_rejected_before_publication(
    tmp_path: Path, surface_id: str
) -> None:
    job, state = _job(surface_ids=(surface_id, "safe"))
    destination = tmp_path / "bundle"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError, match="safe filename"):
        write_design_bundle(job, state, destination)

    assert sentinel.read_text(encoding="utf-8") == "original"


def test_publish_failure_restores_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    destination = (tmp_path / "bundle").resolve()
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")
    original_replace = Path.replace

    def fail_new_bundle_move(source: Path, target: Path) -> Path:
        if source.name.startswith(".bundle-") and Path(target) == destination:
            raise OSError("simulated publication failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_new_bundle_move)

    with pytest.raises(OSError, match="simulated publication failure"):
        write_design_bundle(job, state, destination)

    assert sentinel.read_text(encoding="utf-8") == "original"
    assert tuple(destination.iterdir()) == (sentinel,)
    assert _bundle_work_directories(tmp_path) == []


def test_initial_backup_move_failure_leaves_existing_bundle_and_no_work_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    destination = (tmp_path / "bundle").resolve()
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")
    original_replace = Path.replace

    def fail_backup_move(source: Path, target: Path) -> Path:
        if source == destination:
            raise OSError("simulated backup move failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_backup_move)

    with pytest.raises(OSError, match="simulated backup move failure"):
        write_design_bundle(job, state, destination)

    assert sentinel.read_text(encoding="utf-8") == "original"
    assert _bundle_work_directories(tmp_path) == []


def test_restore_failure_preserves_primary_error_and_recoverable_prior_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    destination = (tmp_path / "bundle").resolve()
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")
    original_replace = Path.replace

    def fail_publish_and_restore(source: Path, target: Path) -> Path:
        target = Path(target)
        if source.name.startswith(".bundle-") and target == destination:
            raise OSError("simulated publish move failure")
        if source.parent.name.startswith(".bundle-backup-") and target == destination:
            raise OSError("simulated restore move failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_publish_and_restore)

    with pytest.raises(OSError, match="simulated publish move failure") as error:
        write_design_bundle(job, state, destination)

    assert isinstance(error.value.__cause__, OSError)
    assert "simulated restore move failure" in str(error.value.__cause__)
    assert not destination.exists()
    work_directories = _bundle_work_directories(tmp_path)
    assert len(work_directories) == 1
    assert work_directories[0].name.startswith(".bundle-backup-")
    recovered = work_directories[0] / "bundle" / "keep.txt"
    assert recovered.read_text(encoding="utf-8") == "original"


def test_replacing_existing_bundle_cleans_backup_wrapper(tmp_path: Path) -> None:
    job, state = _job()
    destination = tmp_path / "bundle"
    destination.mkdir()
    (destination / "keep.txt").write_text("old", encoding="utf-8")

    write_design_bundle(job, state, destination)

    assert not (destination / "keep.txt").exists()
    assert _bundle_work_directories(tmp_path) == []


def test_no_overwrite_policy_preserves_existing_bundle(tmp_path: Path) -> None:
    job, state = _job()
    destination = tmp_path / "bundle"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        write_design_bundle(job, state, destination, overwrite=False)

    assert sentinel.read_text(encoding="utf-8") == "original"
    assert tuple(destination.iterdir()) == (sentinel,)
    assert _bundle_work_directories(tmp_path) == []


def test_no_overwrite_atomically_preserves_destination_created_at_rename_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    destination = tmp_path / "bundle"

    def fallback(source: Path, target: Path) -> Path:
        return source.rename(target)

    no_replace = getattr(bundle_module, "_rename_directory_no_replace", fallback)

    def create_competitor_then_rename(source: Path, target: Path) -> None:
        destination.mkdir()
        no_replace(source, target)

    monkeypatch.setattr(
        bundle_module,
        "_rename_directory_no_replace",
        create_competitor_then_rename,
        raising=False,
    )

    with pytest.raises(FileExistsError, match="already exists"):
        write_design_bundle(job, state, destination, overwrite=False)

    assert destination.is_dir()
    assert tuple(destination.iterdir()) == ()
    assert _bundle_work_directories(tmp_path) == []


def test_no_replace_fails_safely_on_unsupported_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "keep.txt"
    sentinel.write_text("staged", encoding="utf-8")
    destination = tmp_path / "destination"
    monkeypatch.setattr(bundle_module.sys, "platform", "unsupported-os")

    with pytest.raises(RuntimeError, match="atomic no-replace.*unsupported"):
        bundle_module._rename_directory_no_replace(source, destination)

    assert sentinel.read_text(encoding="utf-8") == "staged"
    assert not destination.exists()


def test_bundle_rejects_state_from_another_job_before_publication(tmp_path: Path) -> None:
    job, state = _job()
    other = PolygonDomain("other", ((0, 0), (5, 0), (0, 5)))
    mismatched = DesignState(source_domains=(other,), results=state.results)
    destination = tmp_path / "bundle"

    with pytest.raises(ValueError, match="source domains"):
        write_design_bundle(job, mismatched, destination)

    assert not destination.exists()


def test_bundle_rejects_path_owned_by_unrelated_state_domain(tmp_path: Path) -> None:
    job, state = _job()
    restricted_job = dataclasses.replace(
        job,
        passes=(DesignPass("draw", "fixture", (job.domains[0].id,)),),
    )
    destination = tmp_path / "bundle"

    with pytest.raises(ValueError, match="path owner.*producing pass"):
        write_design_bundle(restricted_job, state, destination)

    assert not destination.exists()


def test_malformed_staged_audit_is_rejected_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, state = _job()
    original_write = bundle_module._write_utf8

    def write_malformed_audit(path: Path, content: str) -> None:
        original_write(path, "{malformed" if path.name == "design.json" else content)

    monkeypatch.setattr(bundle_module, "_write_utf8", write_malformed_audit)

    with pytest.raises(RuntimeError, match="malformed staged design.json"):
        write_design_bundle(job, state, tmp_path / "bundle")

    assert not (tmp_path / "bundle").exists()
    assert _bundle_work_directories(tmp_path) == []


@pytest.mark.parametrize(
    ("corruption", "expected"),
    [
        ("design-path", "design SVG path"),
        ("design-digest", "design SVG digest"),
        ("surface-digest", "surface digest"),
        ("surface-order", "surface entries"),
    ],
)
def test_inconsistent_staged_audit_is_rejected_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
    expected: str,
) -> None:
    job, state = _job()
    original_write = bundle_module._write_utf8

    def write_inconsistent_audit(path: Path, content: str) -> None:
        if path.name == "design.json":
            audit = json.loads(content)
            if corruption == "design-path":
                audit["design_svg"]["path"] = "wrong.svg"
            elif corruption == "design-digest":
                audit["design_svg"]["sha256"] = "0" * 64
            elif corruption == "surface-digest":
                audit["surfaces"][0]["sha256"] = "0" * 64
            else:
                audit["surfaces"].reverse()
            content = json.dumps(audit, separators=(",", ":"))
        original_write(path, content)

    monkeypatch.setattr(bundle_module, "_write_utf8", write_inconsistent_audit)

    with pytest.raises(RuntimeError, match=expected):
        write_design_bundle(job, state, tmp_path / "bundle")

    assert not (tmp_path / "bundle").exists()
    assert _bundle_work_directories(tmp_path) == []
