"""Deterministic, atomic publication of canonical polygon design bundles."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .design import DesignState
from .jobs import DomainArtworkJob
from .json_values import thaw_json_value
from .models import PolygonDomain
from .projection import SurfaceProjection, project_surfaces
from .semantics import DomainRef, FeatureRef, PolygonSurface
from .svg import canonical_design_to_svg, surface_projection_to_svg

_UNSAFE_FILENAME_RUN = re.compile(r"[^a-z0-9._-]+")
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
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
    job: DomainArtworkJob,
    state: DesignState,
    output_dir: Path,
    *,
    overwrite: bool = True,
) -> DesignBundle:
    """Validate, render, and atomically publish a complete design bundle.

    Existing callers retain replacement behavior by default. Set ``overwrite=False``
    to enforce no-clobber publication after staging and verification.
    """

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
            expected_audit=audit,
            filenames=filenames,
            surface_digests=tuple(surface_digests),
            design_digest=design_digest,
        )

        if destination.is_symlink() or destination.is_junction():
            raise ValueError("bundle destination must not be a link or junction")
        if destination.exists() and not destination.is_dir():
            raise ValueError("bundle destination must be a directory")
        if destination.exists() and not overwrite:
            raise FileExistsError(f"bundle destination already exists: {destination}")
        if destination.exists():
            backup = _make_sibling_directory(
                destination, prefix=f".{destination.name}-backup-"
            )
            destination.replace(backup / destination.name)
        try:
            if overwrite:
                temporary.replace(destination)
            else:
                _rename_directory_no_replace(temporary, destination)
        except BaseException as publication_error:
            if backup is not None:
                previous_bundle = backup / destination.name
                try:
                    previous_bundle.replace(destination)
                except BaseException as restore_error:
                    publication_error.add_note(
                        "restoring the previous bundle also failed; recover it from "
                        f"{previous_bundle}: {restore_error}"
                    )
                    raise publication_error from restore_error
            raise
        published = True
    finally:
        active_error = sys.exception()
        if temporary.exists():
            try:
                _remove_created_directory(temporary, destination.parent)
            except (OSError, RuntimeError) as cleanup_error:
                if active_error is None:
                    raise
                active_error.add_note(f"temporary bundle cleanup also failed: {cleanup_error}")
        if backup is not None and backup.exists():
            previous_bundle = backup / destination.name
            should_remove_backup = published or not previous_bundle.exists()
            if should_remove_backup:
                try:
                    _remove_created_directory(backup, destination.parent)
                except (OSError, RuntimeError) as cleanup_error:
                    if active_error is None and not published:
                        raise
                    if active_error is not None:
                        active_error.add_note(
                            f"bundle backup cleanup also failed: {cleanup_error}"
                        )

    return DesignBundle(
        root=destination,
        audit_path=destination / "design.json",
        design_svg_path=destination / "design.svg",
        surface_paths=tuple(destination / "surfaces" / name for name in filenames),
    )


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename a directory while refusing an existing destination."""

    if sys.platform == "win32":
        try:
            source.rename(destination)
        except OSError as error:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(
                    f"bundle destination already exists: {destination}"
                ) from error
            raise
        return

    if sys.platform.startswith("linux"):
        _linux_rename_directory_no_replace(source, destination)
        return

    raise RuntimeError(
        f"atomic no-replace directory publication is unsupported on {sys.platform}"
    )


def _linux_rename_directory_no_replace(source: Path, destination: Path) -> None:
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise RuntimeError(
            "atomic no-replace directory publication is unavailable on Linux"
        ) from error

    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        _AT_FDCWD,
        os.fsencode(source),
        _AT_FDCWD,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result == 0:
        return

    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(f"bundle destination already exists: {destination}")
    if error_number in {errno.ENOSYS, errno.EINVAL}:
        raise RuntimeError(
            "atomic no-replace directory publication is unavailable on Linux"
        )
    raise OSError(error_number, os.strerror(error_number), destination)


def _absolute_destination(output_dir: Path) -> Path:
    current_directory = Path.cwd().resolve(strict=True)
    if output_dir == Path("."):
        raise ValueError("bundle destination must not be the current directory")
    requested = output_dir if output_dir.is_absolute() else Path.cwd() / output_dir
    parent = requested.parent.resolve(strict=False)
    if requested.name in {"", ".", ".."}:
        raise ValueError("bundle destination must name a directory")
    destination = parent / requested.name
    if destination == current_directory:
        raise ValueError("bundle destination must not be the current directory")
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
    for design_pass, result in zip(job.passes, state.results, strict=True):
        allowed_owners = {
            *design_pass.target_domain_ids,
            *(domain.id for domain in result.derived_domains),
        }
        for path in result.paths:
            if path.domain_id not in domain_ids:
                raise ValueError(f"design path references unknown domain: {path.domain_id}")
            if path.domain_id not in allowed_owners:
                raise ValueError(
                    f"design path owner {path.domain_id!r} is not a target or derived "
                    f"domain of producing pass {result.producing_pass_id!r}"
                )


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
    job_identity = _job_identity_payload(job)
    return {
        "schema": "viz-design-bundle/v1",
        **job_identity,
        "job_sha256": hashlib.sha256(
            json.dumps(
                job_identity,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "domain_ids": [domain.id for domain in job.domains],
        "group_ids": [group.id for group in job.groups],
        "relation_ids": [relation.id for relation in job.relations],
        "pass_summaries": [
            {
                "producing_pass_id": result.producing_pass_id,
                "path_count": len(result.paths),
                "derived_domain_ids": [domain.id for domain in result.derived_domains],
                "paths": [
                    {
                        "domain_id": path.domain_id,
                        "layer_id": path.layer_id,
                        "coordinate_frame": path.coordinate_frame,
                        "producing_pass_id": path.producing_pass_id,
                    }
                    for path in result.paths
                ],
            }
            for result in state.results
        ],
        "derived_domains": [
            _domain_payload(domain)
            for domain in state.derived_domains
        ],
        "design_svg": {"path": "design.svg", "sha256": design_digest},
        "surfaces": [
            {
                "surface_id": projection.surface.id,
                "domain_id": projection.surface.domain_id,
                "path": f"surfaces/{filename}",
                "sha256": digest,
                "feature_aliases": {
                    alias: _endpoint_payload(reference)
                    for alias, reference in projection.surface.feature_aliases.items()
                },
                "producing_pass_ids": list(
                    dict.fromkeys(
                        path.producing_pass_id
                        for path in projection.paths
                        if path.producing_pass_id is not None
                    )
                ),
            }
            for projection, filename, digest in zip(
                projections, filenames, surface_digests, strict=True
            )
        ],
    }


def _job_identity_payload(job: DomainArtworkJob) -> dict[str, object]:
    return {
        "schema_version": job.schema_version,
        "seed": job.seed,
        "domains": [_domain_payload(domain) for domain in job.domains],
        "declared_surfaces": (
            None
            if job.surfaces is None
            else [_surface_payload(surface) for surface in job.surfaces]
        ),
        "groups": [
            {
                "id": group.id,
                "surface_ids": list(group.surface_ids),
                "seed": group.seed,
                "metadata": thaw_json_value(group.metadata),
            }
            for group in job.groups
        ],
        "relations": [
            {
                "id": relation.id,
                "relation_type": relation.relation_type.value,
                "source": _endpoint_payload(relation.source),
                "target": _endpoint_payload(relation.target),
                "metadata": thaw_json_value(relation.metadata),
            }
            for relation in job.relations
        ],
        "composition_transforms": [
            {
                "domain_id": composition.domain_id,
                "matrix": [
                    composition.transform.a,
                    composition.transform.b,
                    composition.transform.c,
                    composition.transform.d,
                    composition.transform.e,
                    composition.transform.f,
                ],
            }
            for composition in job.composition_transforms
        ],
        "passes": [
            {
                "id": design_pass.id,
                "algorithm": design_pass.algorithm,
                "target_domain_ids": list(design_pass.target_domain_ids),
                "parameters": thaw_json_value(design_pass.parameters),
                "logical_layers": [
                    {"id": layer.id, "label": layer.label}
                    for layer in design_pass.logical_layers
                ],
                "group_context_ids": list(design_pass.group_context_ids),
                "relation_context_ids": list(design_pass.relation_context_ids),
                "depends_on": list(design_pass.depends_on),
            }
            for design_pass in job.passes
        ],
    }


def _domain_payload(domain: PolygonDomain) -> dict[str, object]:
    provenance = domain.provenance
    return {
        "id": domain.id,
        "vertices": [[float(x), float(y)] for x, y in domain.vertices],
        "provenance": (
            None
            if provenance is None
            else {
                "source_domain_ids": list(provenance.source_domain_ids),
                "generating_pass_id": provenance.generating_pass_id,
                "operation": provenance.operation,
            }
        ),
    }


def _surface_payload(surface: PolygonSurface) -> dict[str, object]:
    return {
        "id": surface.id,
        "domain_id": surface.domain_id,
        "feature_aliases": {
            alias: _endpoint_payload(reference)
            for alias, reference in surface.feature_aliases.items()
        },
    }


def _endpoint_payload(endpoint: DomainRef | FeatureRef) -> dict[str, object]:
    payload: dict[str, object] = {"domain_id": endpoint.domain_id}
    if isinstance(endpoint, FeatureRef):
        payload.update(
            {
                "feature_type": endpoint.feature_type.value,
                "index": endpoint.index,
            }
        )
    return payload


def _write_utf8(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_staged_bundle(
    root: Path,
    *,
    expected_audit: dict[str, object],
    filenames: tuple[str, ...],
    surface_digests: tuple[str, ...],
    design_digest: str,
) -> None:
    if {path.name for path in root.iterdir()} != {"design.json", "design.svg", "surfaces"}:
        raise RuntimeError("staged bundle has missing or unexpected root entries")
    surfaces = root / "surfaces"
    if tuple(sorted(path.name for path in surfaces.iterdir())) != tuple(sorted(filenames)):
        raise RuntimeError("staged bundle has missing or unexpected surface files")
    try:
        staged_audit = json.loads((root / "design.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("malformed staged design.json") from exc
    if not isinstance(staged_audit, dict):
        raise RuntimeError("malformed staged design.json")

    expected_design = expected_audit["design_svg"]
    staged_design = staged_audit.get("design_svg")
    if not isinstance(staged_design, dict) or staged_design.get("path") != "design.svg":
        raise RuntimeError("staged audit design SVG path mismatch")
    if staged_design.get("sha256") != expected_design["sha256"]:
        raise RuntimeError("staged audit design SVG digest mismatch")
    if _sha256(root / "design.svg") != design_digest:
        raise RuntimeError("staged design SVG digest mismatch")

    expected_surfaces = expected_audit["surfaces"]
    staged_surfaces = staged_audit.get("surfaces")
    if not isinstance(staged_surfaces, list) or not isinstance(expected_surfaces, list):
        raise RuntimeError("staged audit surface entries mismatch")
    expected_order = [entry["surface_id"] for entry in expected_surfaces]
    staged_order = [
        entry.get("surface_id") if isinstance(entry, dict) else None
        for entry in staged_surfaces
    ]
    if staged_order != expected_order:
        raise RuntimeError("staged audit surface entries are missing or out of order")
    if len(staged_surfaces) != len(filenames):
        raise RuntimeError("staged audit surface entries are missing or out of order")
    for staged, expected, filename, digest in zip(
        staged_surfaces, expected_surfaces, filenames, surface_digests, strict=True
    ):
        if not isinstance(staged, dict) or not isinstance(expected, dict):
            raise RuntimeError("staged audit surface entries mismatch")
        if staged.get("domain_id") != expected["domain_id"]:
            raise RuntimeError("staged audit surface entries mismatch")
        if staged.get("path") != f"surfaces/{filename}":
            raise RuntimeError("staged audit surface path mismatch")
        if staged.get("sha256") != digest:
            raise RuntimeError("staged audit surface digest mismatch")
        if _sha256(surfaces / filename) != digest:
            raise RuntimeError(f"staged surface SVG digest mismatch: {filename}")
    if staged_audit != expected_audit:
        raise RuntimeError("staged audit payload mismatch")
