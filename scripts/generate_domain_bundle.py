from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from concentric.service import ConcentricDomainAlgorithm  # noqa: E402
from viz_canvas.bundle import write_design_bundle  # noqa: E402
from viz_canvas.job_io import read_domain_artwork_job  # noqa: E402
from viz_canvas.runner import run_domain_artwork_job  # noqa: E402

ALGORITHMS = {"concentric-points": ConcentricDomainAlgorithm()}


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
        job = read_domain_artwork_job(args.job)
        state = run_domain_artwork_job(job, ALGORITHMS)
        bundle = write_design_bundle(job, state, output_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"design.json: {bundle.audit_path}")
    print(f"design.svg: {bundle.design_svg_path}")
    print(f"surfaces: {bundle.root / 'surfaces'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
