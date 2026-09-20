from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from concentric.models import ORBITAL_ATTRIBUTE_SCHEMA, orbital_projection  # noqa: E402
from concentric.service import (  # noqa: E402
    ConcentricDomainAlgorithm,
    OrbitalConcentricDomainAlgorithm,
    generate_orbital_design,
)
from radial_tiles.service import RadialTilesDomainAlgorithm  # noqa: E402
from viz_canvas.bundle import write_design_bundle, write_neutral_bundle  # noqa: E402
from viz_canvas.job_io import load_domain_artwork_job  # noqa: E402
from viz_canvas.logical_layers import (  # noqa: E402
    DynamicLayerSpec,
    FixedLayerSpec,
    MatchSpec,
    ProjectionRule,
    ProjectionSpec,
)
from viz_canvas.runner import run_domain_artwork_job  # noqa: E402

ALGORITHMS = {
    "concentric-points": ConcentricDomainAlgorithm(),
    "orbital-concentric": OrbitalConcentricDomainAlgorithm(),
    "radial-tiles": RadialTilesDomainAlgorithm(),
}
_MISSING = object()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an atomic bundle from a versioned polygon-domain job."
    )
    parser.add_argument("job", type=Path, help="versioned domain artwork job JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing destination atomically",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    if (output_dir.exists() or output_dir.is_symlink()) and not args.overwrite:
        parser.error(f"output destination already exists: {output_dir}")

    try:
        job, projection = _read_cli_job(args.job)
        if projection is None:
            state = run_domain_artwork_job(job, ALGORITHMS)
            bundle = write_design_bundle(job, state, output_dir, overwrite=args.overwrite)
        else:
            design = generate_orbital_design(job, projection=projection)
            bundle = write_neutral_bundle(
                job,
                design,
                output_dir,
                projection=projection,
                overwrite=args.overwrite,
            )
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))

    print(f"design.json: {bundle.audit_path}")
    print(f"design.svg: {bundle.design_svg_path}")
    print(f"surfaces: {bundle.root / 'surfaces'}")
    return 0


def _read_cli_job(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("domain artwork job must be a JSON object")
    job_payload = dict(payload)
    projection_payload = job_payload.pop("projection", _MISSING)
    job = load_domain_artwork_job(job_payload)
    if projection_payload is _MISSING:
        return job, None
    if any(design_pass.algorithm != "orbital-concentric" for design_pass in job.passes):
        raise ValueError("projection requires an orbital-concentric-only job")
    return job, _parse_projection(projection_payload)


def _parse_projection(payload: object) -> ProjectionSpec:
    if isinstance(payload, str):
        return orbital_projection(payload)
    projection = _object(payload, context="projection")
    _require_fields(projection, {"id", "rules"}, context="projection")
    projection_id = projection["id"]
    rules = projection["rules"]
    if not isinstance(projection_id, str):
        raise ValueError("projection id must be a string")
    if not isinstance(rules, list) or not rules:
        raise ValueError("projection rules must be a non-empty array")
    return ProjectionSpec(
        projection_id,
        tuple(_parse_projection_rule(rule, index) for index, rule in enumerate(rules)),
    )


def _parse_projection_rule(payload: object, index: int) -> ProjectionRule:
    context = f"projection rule {index}"
    rule = _object(payload, context=context)
    _require_fields(
        rule,
        {"match"},
        optional={"layer", "group", "description"},
        context=context,
    )
    if ("layer" in rule) == ("group" in rule):
        raise ValueError(f"{context} requires exactly one of layer or group")
    if "description" in rule and not isinstance(rule["description"], str):
        raise ValueError(f"{context} description must be a string")
    match = _parse_match(rule["match"], context=f"{context} match")
    if "layer" in rule:
        layer = _object(rule["layer"], context=f"{context} layer")
        _require_fields(layer, {"id", "label"}, context=f"{context} layer")
        return ProjectionRule(
            match,
            fixed=FixedLayerSpec(
                _string(layer["id"], "layer id"),
                _string(layer["label"], "layer label"),
            ),
        )
    group = _object(rule["group"], context=f"{context} group")
    _require_fields(
        group,
        {"id_prefix", "label_prefix", "group_by"},
        context=f"{context} group",
    )
    group_by = group["group_by"]
    if not isinstance(group_by, list):
        raise ValueError(f"{context} group_by must be an array")
    keys = tuple(_string(key, "projection group key") for key in group_by)
    _validate_projection_keys(keys)
    return ProjectionRule(
        match,
        dynamic=DynamicLayerSpec(
            _string(group["id_prefix"], "group id_prefix"),
            _string(group["label_prefix"], "group label_prefix"),
            keys,
        ),
    )


def _parse_match(payload: object, *, context: str) -> MatchSpec:
    match = _object(payload, context=context)
    feature_role = None
    if "feature_role" in match:
        feature_role = match["feature_role"]
        if not isinstance(feature_role, str):
            raise ValueError(f"{context} feature_role must be a string")
    domain_id = None
    if "domain_id" in match:
        domain_id = match["domain_id"]
        if not isinstance(domain_id, str):
            raise ValueError(f"{context} domain_id must be a string")
    attributes: dict[str, tuple[object, ...]] = {}
    for key, value in match.items():
        if key in {"feature_role", "domain_id"}:
            continue
        _validate_projection_keys((key,))
        values = value if isinstance(value, list) else [value]
        if not values:
            raise ValueError(f"projection match key {key!r} requires at least one value")
        attributes[key] = tuple(values)
    return MatchSpec(
        feature_role=feature_role,
        attributes=attributes,
        domain_id=domain_id,
    )


def _validate_projection_keys(keys: tuple[str, ...]) -> None:
    declared = {"domain_id", *ORBITAL_ATTRIBUTE_SCHEMA.keys}
    for key in keys:
        if key not in declared:
            raise ValueError(f"undeclared projection key: {key}")


def _object(payload: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be an object")
    if any(not isinstance(key, str) for key in payload):
        raise ValueError(f"{context} keys must be strings")
    return payload


def _require_fields(
    payload: Mapping[str, object],
    required: set[str],
    *,
    optional: set[str] | None = None,
    context: str,
) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - payload.keys())
    unknown = sorted(payload.keys() - allowed)
    if missing:
        raise ValueError(f"{context} missing field: {missing[0]}")
    if unknown:
        raise ValueError(f"{context} has unknown field: {unknown[0]}")


def _string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
