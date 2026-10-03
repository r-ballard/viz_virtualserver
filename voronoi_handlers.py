"""Compatibility import for viz_virtualserver.legacy.voronoi_handlers."""

import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("viz_virtualserver.legacy.voronoi_handlers")
