"""Compatibility imports for the namespaced package."""

import importlib as _importlib
import sys as _sys

_target = _importlib.import_module("viz_virtualserver.canvas")
for _name in (
    "api",
    "bundle",
    "design",
    "frames",
    "geometry",
    "job_io",
    "jobs",
    "json_values",
    "logical_layers",
    "models",
    "projection",
    "runner",
    "semantics",
    "state_validation",
    "svg",
):
    _module = _importlib.import_module(f"viz_virtualserver.canvas.{_name}")
    _sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
for _name in getattr(_target, "__all__", ()):
    globals()[_name] = getattr(_target, _name)
__all__ = getattr(_target, "__all__", ())
