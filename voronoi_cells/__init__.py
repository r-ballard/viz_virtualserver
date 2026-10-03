"""Compatibility imports for the namespaced package."""

import importlib as _importlib
import sys as _sys

_target = _importlib.import_module("viz_virtualserver.generators.voronoi_cells")
for _name in ("service",):
    _module = _importlib.import_module(f"viz_virtualserver.generators.voronoi_cells.{_name}")
    _sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
for _name in getattr(_target, "__all__", ()):
    globals()[_name] = getattr(_target, _name)
__all__ = getattr(_target, "__all__", ())
