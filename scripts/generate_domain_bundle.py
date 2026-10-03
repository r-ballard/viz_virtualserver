"""Compatibility CLI path; canonical entrypoint lives in viz_virtualserver.cli."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_impl = importlib.import_module("viz_virtualserver.cli.domain_bundle")
if __name__ == "__main__":
    raise SystemExit(_impl.main())
sys.modules[__name__] = _impl
