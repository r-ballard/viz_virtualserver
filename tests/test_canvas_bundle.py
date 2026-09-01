from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

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
    metadata = json.loads(root.find("svg:metadata", NS).text)
    assert metadata["domains"][0]["vertices"] == [
        [100.0, 50.0],
        [120.0, 50.0],
        [100.0, 70.0],
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


def test_bundle_rejects_state_from_another_job_before_publication(tmp_path: Path) -> None:
    job, state = _job()
    other = PolygonDomain("other", ((0, 0), (5, 0), (0, 5)))
    mismatched = DesignState(source_domains=(other,), results=state.results)
    destination = tmp_path / "bundle"

    with pytest.raises(ValueError, match="source domains"):
        write_design_bundle(job, mismatched, destination)

    assert not destination.exists()
