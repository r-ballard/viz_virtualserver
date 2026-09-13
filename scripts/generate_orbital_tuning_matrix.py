"""Generate deterministic orbital-concentric comparison bundles."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_domain_bundle import ALGORITHMS  # noqa: E402
from viz_canvas import bundle as bundle_module  # noqa: E402
from viz_canvas.job_io import read_domain_artwork_job  # noqa: E402
from viz_canvas.runner import run_domain_artwork_job  # noqa: E402

VARIANTS: dict[str, dict[str, int | float]] = {
    "density-low": {"orbit_count": 5},
    "density-medium": {"orbit_count": 8},
    "density-high": {"orbit_count": 12},
    "eccentricity-circular": {
        "orbit_eccentricity": 0.0,
        "orbit_eccentricity_variation": 0.0,
    },
    "eccentricity-subtle": {
        "orbit_eccentricity": 0.18,
        "orbit_eccentricity_variation": 0.06,
    },
    "eccentricity-varied": {
        "orbit_eccentricity": 0.32,
        "orbit_eccentricity_variation": 0.22,
    },
}


def generate_matrix(
    base_job: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    """Publish ordinary design bundles for every deterministic tuning variant."""

    destination = _absolute_destination(Path(output_root))
    _refuse_existing_destination(destination, overwrite=overwrite)
    base_payload = _read_json_object(Path(base_job))
    read_domain_artwork_job(Path(base_job))
    _orbital_parameters(base_payload)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = bundle_module._make_sibling_directory(
        destination,
        prefix=f".{destination.name}-",
    )
    try:
        entries: list[dict[str, object]] = []
        for name, parameter_delta in VARIANTS.items():
            derived_payload = copy.deepcopy(base_payload)
            derived_parameters = _orbital_parameters(derived_payload)
            derived_parameters.update(parameter_delta)
            job = _read_derived_job(temporary, name, derived_payload)
            state = run_domain_artwork_job(job, ALGORITHMS)
            bundle = bundle_module.write_design_bundle(
                job,
                state,
                temporary / name,
                overwrite=False,
            )
            entries.append(
                {
                    "name": name,
                    "seed": job.seed,
                    "parameters": parameter_delta,
                    "bundle_path": bundle.root.relative_to(temporary).as_posix(),
                }
            )

        _write_json(
            temporary / "matrix.json",
            {
                "schema": "viz-orbital-tuning-matrix/v1",
                "variants": entries,
            },
        )
        _verify_staged_matrix(temporary)
        _publish_matrix(
            temporary,
            destination,
            overwrite=overwrite,
        )
    finally:
        if temporary.exists():
            _remove_matrix_work_directory(temporary, destination.parent)

    return tuple(destination / name for name in VARIANTS)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic orbital-concentric tuning matrix."
    )
    parser.add_argument("base_job", type=Path, help="versioned orbital-concentric job JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing matrix atomically",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        outputs = generate_matrix(args.base_job, args.output_dir, overwrite=args.overwrite)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))

    print(f"matrix.json: {args.output_dir.resolve() / 'matrix.json'}")
    for output in outputs:
        print(f"bundle: {output}")
    return 0


def _absolute_destination(output_root: Path) -> Path:
    current_directory = Path.cwd().resolve(strict=True)
    if output_root == Path("."):
        raise ValueError("matrix destination must not be the current directory")
    requested = output_root if output_root.is_absolute() else Path.cwd() / output_root
    parent = requested.parent.resolve(strict=False)
    if requested.name in {"", ".", ".."}:
        raise ValueError("matrix destination must name a directory")
    destination = parent / requested.name
    if destination == current_directory:
        raise ValueError("matrix destination must not be the current directory")
    if not destination.is_absolute() or destination.parent != parent:
        raise ValueError("matrix destination path is unsafe")
    return destination


def _refuse_existing_destination(destination: Path, *, overwrite: bool) -> None:
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("matrix destination must not be a link or junction")
    if destination.exists() and not destination.is_dir():
        raise ValueError("matrix destination must be a directory")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"matrix destination already exists: {destination}")


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("base job must be a JSON object")
    return payload


def _orbital_parameters(payload: dict[str, object]) -> dict[str, object]:
    passes = payload.get("passes")
    if not isinstance(passes, list):
        raise ValueError("base job must declare an orbital-concentric pass")
    orbital_passes = [
        design_pass
        for design_pass in passes
        if isinstance(design_pass, dict) and design_pass.get("algorithm") == "orbital-concentric"
    ]
    if len(orbital_passes) != 1:
        raise ValueError("base job must declare exactly one orbital-concentric pass")
    parameters = orbital_passes[0].get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("orbital-concentric pass must declare parameters")
    return parameters


def _read_derived_job(
    matrix_root: Path,
    name: str,
    payload: dict[str, object],
):
    job_path = matrix_root / f".{name}.json"
    _write_json(job_path, payload)
    try:
        return read_domain_artwork_job(job_path)
    finally:
        job_path.unlink(missing_ok=True)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _verify_staged_matrix(root: Path) -> None:
    expected = {"matrix.json", *VARIANTS}
    if {path.name for path in root.iterdir()} != expected:
        raise RuntimeError("staged matrix has missing or unexpected root entries")
    manifest = _read_json_object(root / "matrix.json")
    variants = manifest.get("variants")
    if not isinstance(variants, list):
        raise RuntimeError("staged matrix manifest has invalid variants")
    if [item.get("name") for item in variants if isinstance(item, dict)] != list(VARIANTS):
        raise RuntimeError("staged matrix manifest variant order is invalid")
    for name in VARIANTS:
        if not (root / name / "design.json").is_file():
            raise RuntimeError(f"staged matrix bundle is incomplete: {name}")


def _publish_matrix(temporary: Path, destination: Path, *, overwrite: bool) -> None:
    _refuse_existing_destination(destination, overwrite=overwrite)
    backup: Path | None = None
    try:
        if destination.exists():
            backup = bundle_module._make_sibling_directory(
                destination,
                prefix=f".{destination.name}-backup-",
            )
            destination.replace(backup / destination.name)
        try:
            if overwrite:
                temporary.replace(destination)
            else:
                bundle_module._rename_directory_no_replace(temporary, destination)
        except BaseException as publication_error:
            if backup is not None:
                previous_matrix = backup / destination.name
                try:
                    previous_matrix.replace(destination)
                except BaseException as restore_error:
                    publication_error.add_note(
                        "restoring the previous matrix also failed; recover it from "
                        f"{previous_matrix}: {restore_error}"
                    )
                    raise publication_error from restore_error
            raise
    finally:
        if backup is not None and backup.exists():
            _remove_matrix_work_directory(backup, destination.parent)


def _remove_matrix_work_directory(path: Path, parent: Path) -> None:
    bundle_module._remove_created_directory(path, parent)


if __name__ == "__main__":
    raise SystemExit(main())
