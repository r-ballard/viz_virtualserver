"""Deterministic, atomic publication of canonical polygon design bundles."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .design import DesignState
from .jobs import DomainArtworkJob
from .projection import SurfaceProjection, project_surfaces
from .svg import canonical_design_to_svg, surface_projection_to_svg

_UNSAFE_FILENAME_RUN = re.compile(r"[^a-z0-9._-]+")
_WINDOWS_DEVICE_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


@dataclass(frozen=True, slots=True)
class DesignBundle:
    """Paths to one fully published canonical design bundle."""

    root: Path
    audit_path: Path
    design_svg_path: Path
    surface_paths: tuple[Path, ...]


def write_design_bundle(
    job: DomainArtworkJob, state: DesignState, output_dir: Path
) -> DesignBundle:
    """Validate, render, and atomically publish a complete design bundle."""

    destination = _absolute_destination(Path(output_dir))
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("bundle destination must not be a link or junction")
    if destination.exists() and not destination.is_dir():
        raise ValueError("bundle destination must be a directory")

    _validate_state(job, state)
    projections = project_surfaces(job, state)
    _validate_projections(job, projections)
    filenames = _surface_filenames(projections)
    design_svg = canonical_design_to_svg(job, state)
    surface_svgs = tuple(surface_projection_to_svg(projection) for projection in projections)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _make_sibling_directory(destination, prefix=f".{destination.name}-")
    backup: Path | None = None
    published = False
    try:
        surfaces_dir = temporary / "surfaces"
        surfaces_dir.mkdir()
        surface_digests: list[str] = []
        for filename, svg in zip(filenames, surface_svgs, strict=True):
            path = surfaces_dir / filename
            _write_utf8(path, svg)
            surface_digests.append(_sha256(path))

        design_svg_path = temporary / "design.svg"
        _write_utf8(design_svg_path, design_svg)
        design_digest = _sha256(design_svg_path)
        audit = _audit_payload(
            job,
            state,
            projections,
            filenames,
            tuple(surface_digests),
            design_digest,
        )
        _write_utf8(
            temporary / "design.json",
            json.dumps(audit, ensure_ascii=True, separators=(",", ":")) + "\n",
        )
        _verify_staged_bundle(
            temporary,
            filenames=filenames,
            surface_digests=tuple(surface_digests),
            design_digest=design_digest,
        )

        if destination.exists():
            backup = _make_sibling_directory(
                destination, prefix=f".{destination.name}-backup-"
            )
            destination.replace(backup / destination.name)
        try:
            temporary.replace(destination)
        except BaseException:
            if backup is not None:
                (backup / destination.name).replace(destination)
            raise
        published = True
    finally:
        if temporary.exists():
            _remove_created_directory(temporary, destination.parent)
        if published and backup is not None and backup.exists():
            try:
                _remove_created_directory(backup, destination.parent)
            except (OSError, RuntimeError):
                # Publication already succeeded. Leaving the exact task-owned backup
                # is safer than reporting a failed write after replacing the bundle.
                pass

    return DesignBundle(
        root=destination,
        audit_path=destination / "design.json",
        design_svg_path=destination / "design.svg",
        surface_paths=tuple(destination / "surfaces" / name for name in filenames),
    )


def _absolute_destination(output_dir: Path) -> Path:
    requested = output_dir if output_dir.is_absolute() else Path.cwd() / output_dir
    parent = requested.parent.resolve(strict=False)
    if requested.name in {"", ".", ".."}:
        raise ValueError("bundle destination must name a directory")
    destination = parent / requested.name
    if not destination.is_absolute() or destination.parent != parent:
        raise ValueError("bundle destination path is unsafe")
    return destination


def _make_sibling_directory(destination: Path, *, prefix: str) -> Path:
    created = Path(tempfile.mkdtemp(prefix=prefix, dir=destination.parent)).resolve(strict=True)
    if (
        not created.is_absolute()
        or created.parent != destination.parent
        or created == destination
        or not created.name.startswith(prefix)
    ):
        raise RuntimeError("created sibling directory path is unsafe")
    return created


def _remove_created_directory(path: Path, parent: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise RuntimeError("refusing to remove linked bundle work directory")
    resolved = path.resolve(strict=True)
    if not resolved.is_absolute() or resolved.parent != parent or resolved == parent:
        raise RuntimeError("refusing to remove unsafe bundle work directory")
    shutil.rmtree(resolved)


def _surface_filenames(projections: tuple[SurfaceProjection, ...]) -> tuple[str, ...]:
    filenames: list[str] = []
    owners: dict[str, str] = {}
    for projection in projections:
        surface_id = projection.surface.id
        stem = _sanitize_filename(surface_id)
        filename = f"{stem}.svg"
        previous = owners.get(filename)
        if previous is not None:
            raise ValueError(
                f"surface filename collision after sanitization: {previous!r} and "
                f"{surface_id!r}"
            )
        owners[filename] = surface_id
        filenames.append(filename)
    return tuple(filenames)


def _sanitize_filename(surface_id: str) -> str:
    stem = _UNSAFE_FILENAME_RUN.sub("-", surface_id.lower()).strip("-")
    device_stem = stem.split(".", 1)[0]
    if (
        not stem
        or stem in {".", ".."}
        or stem.endswith(".")
        or device_stem in _WINDOWS_DEVICE_NAMES
    ):
        raise ValueError(f"surface id does not produce a safe filename: {surface_id!r}")
    return stem


def _validate_state(job: DomainArtworkJob, state: DesignState) -> None:
    if state.source_domains != job.domains:
        raise ValueError("design state source domains do not match the job")
    expected_pass_ids = tuple(design_pass.id for design_pass in job.passes)
    result_pass_ids = tuple(result.producing_pass_id for result in state.results)
    if result_pass_ids != expected_pass_ids:
        raise ValueError("design state results do not match declared pass order")
    result_derived = tuple(
        domain for result in state.results for domain in result.derived_domains
    )
    if state.derived_domains != result_derived:
        raise ValueError("design state derived domains do not match result provenance")
    domain_ids = {domain.id for domain in (*state.source_domains, *state.derived_domains)}
    if len(domain_ids) != len(state.source_domains) + len(state.derived_domains):
        raise ValueError("design state contains duplicate domain ids")
    for result in state.results:
        for path in result.paths:
            if path.domain_id not in domain_ids:
                raise ValueError(f"design path references unknown domain: {path.domain_id}")


def _validate_projections(
    job: DomainArtworkJob, projections: tuple[SurfaceProjection, ...]
) -> None:
    expected = tuple(surface.id for surface in job.resolved_surfaces)
    actual = tuple(projection.surface.id for projection in projections)
    if actual != expected:
        raise ValueError("surface projection ids do not match declared surface order")


def _audit_payload(
    job: DomainArtworkJob,
    state: DesignState,
    projections: tuple[SurfaceProjection, ...],
    filenames: tuple[str, ...],
    surface_digests: tuple[str, ...],
    design_digest: str,
) -> dict[str, object]:
    return {
        "schema": "viz-design-bundle/v1",
        "schema_version": job.schema_version,
        "seed": job.seed,
        "domain_ids": [domain.id for domain in job.domains],
        "group_ids": [group.id for group in job.groups],
        "relation_ids": [relation.id for relation in job.relations],
        "passes": [
            {
                "id": design_pass.id,
                "algorithm": design_pass.algorithm,
                "target_domain_ids": list(design_pass.target_domain_ids),
                "depends_on": list(design_pass.depends_on),
            }
            for design_pass in job.passes
        ],
        "derived_domains": [
            {
                "id": domain.id,
                "provenance": {
                    "source_domain_ids": list(domain.provenance.source_domain_ids),
                    "generating_pass_id": domain.provenance.generating_pass_id,
                    "operation": domain.provenance.operation,
                },
            }
            for domain in state.derived_domains
        ],
        "design_svg": {"path": "design.svg", "sha256": design_digest},
        "surfaces": [
            {
                "surface_id": projection.surface.id,
                "domain_id": projection.surface.domain_id,
                "path": f"surfaces/{filename}",
                "sha256": digest,
            }
            for projection, filename, digest in zip(
                projections, filenames, surface_digests, strict=True
            )
        ],
    }


def _write_utf8(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_staged_bundle(
    root: Path,
    *,
    filenames: tuple[str, ...],
    surface_digests: tuple[str, ...],
    design_digest: str,
) -> None:
    if {path.name for path in root.iterdir()} != {"design.json", "design.svg", "surfaces"}:
        raise RuntimeError("staged bundle has missing or unexpected root entries")
    surfaces = root / "surfaces"
    if tuple(sorted(path.name for path in surfaces.iterdir())) != tuple(sorted(filenames)):
        raise RuntimeError("staged bundle has missing or unexpected surface files")
    if _sha256(root / "design.svg") != design_digest:
        raise RuntimeError("staged design SVG digest mismatch")
    for filename, digest in zip(filenames, surface_digests, strict=True):
        if _sha256(surfaces / filename) != digest:
            raise RuntimeError(f"staged surface SVG digest mismatch: {filename}")
