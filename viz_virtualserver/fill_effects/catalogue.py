"""Explicit fill catalogue, parameter validation, and rendering dispatch."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real

from shapely.geometry.base import BaseGeometry

from .models import EffectParameter, FillEffectDescriptor, FillStroke
from .parallel_hatch import parallel_hatches

_PARALLEL_HATCH = FillEffectDescriptor(
    id="parallel-hatch",
    name="Parallel hatch",
    description="Parallel open strokes clipped to composed polygonal regions.",
    parameters=(EffectParameter("spacing", 2.0, "input-units", 0.0),
                EffectParameter("angle", 45.0, "degrees")),
)
_REGISTRY = {"parallel-hatch": (_PARALLEL_HATCH, parallel_hatches)}


def list_fill_effects() -> tuple[FillEffectDescriptor, ...]:
    """Return implemented effects in stable registration order."""
    return tuple(descriptor for descriptor, _ in _REGISTRY.values())


def _validate_region(region: BaseGeometry) -> None:
    if not isinstance(region, BaseGeometry) or not region.is_valid:
        raise ValueError("fill region must be valid polygonal geometry")
    if region.geom_type in ("Polygon", "MultiPolygon"):
        return
    if region.geom_type == "GeometryCollection":
        for part in region.geoms:
            _validate_region(part)
        return
    raise ValueError("fill region must be polygonal geometry")


def render_fill_effect(
    region: BaseGeometry, *, effect: str,
    parameters: Mapping[str, object] | None = None,
) -> tuple[FillStroke, ...]:
    """Render strokes without changing frame, assigning layers, or repairing regions."""
    if not isinstance(effect, str) or effect not in _REGISTRY:
        raise ValueError(f"unknown fill effect: {effect!r}")
    descriptor, renderer = _REGISTRY[effect]
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ValueError("fill parameters must be a mapping")
    supplied = dict(parameters) if parameters is not None else {}
    names = {parameter.name for parameter in descriptor.parameters}
    if any(name not in names for name in supplied):
        raise ValueError("unknown fill parameter")
    controls = {}
    for parameter in descriptor.parameters:
        value = supplied.get(parameter.name, parameter.default)
        try:
            valid = (not isinstance(value, bool) and isinstance(value, Real)
                     and math.isfinite(value))
            number = float(value) if valid else math.nan
        except (OverflowError, TypeError, ValueError):
            valid, number = False, math.nan
        if not valid or (parameter.exclusive_minimum is not None
                         and number <= parameter.exclusive_minimum):
            raise ValueError(f"invalid fill parameter {parameter.name}: {value!r}")
        controls[parameter.name] = number
    _validate_region(region)
    return renderer(region, **controls)
