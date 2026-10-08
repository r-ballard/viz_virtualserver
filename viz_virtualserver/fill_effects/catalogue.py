"""Explicit fill catalogue, parameter validation, and rendering dispatch."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real

from shapely.geometry.base import BaseGeometry

from .circle_rings import circle_rings
from .crosshatch import crosshatches
from .models import EffectParameter, FillEffectDescriptor, FillStroke
from .parallel_hatch import parallel_hatches
from .region_validation import validate_region as _validate_region
from .stroke_dots import stroke_dots
from .vortex_marks import vortex_marks

_PARALLEL_HATCH = FillEffectDescriptor(
    id="parallel-hatch",
    name="Parallel hatch",
    description="Parallel open strokes clipped to composed polygonal regions.",
    parameters=(EffectParameter("spacing", 2.0, "input-units", 0.0),
                EffectParameter("angle", 45.0, "degrees")),
)
_CROSSHATCH = FillEffectDescriptor(
    id="crosshatch",
    name="Crosshatch",
    description="Two perpendicular hatch families clipped to composed polygonal regions.",
    parameters=_PARALLEL_HATCH.parameters,
)
_REGISTRY = {
    "parallel-hatch": (_PARALLEL_HATCH, parallel_hatches),
    "crosshatch": (_CROSSHATCH, crosshatches),
    "circle-rings": (FillEffectDescriptor(
        id="circle-rings", name="Circle rings",
        description="Circle outlines on a rotated square lattice, clipped to polygonal regions.",
        parameters=(EffectParameter("spacing", 8.0, "input-units", 0.0),
                    EffectParameter("radius", 2.0, "input-units", 0.0),
                    EffectParameter("angle", 0.0, "degrees"),
                    EffectParameter("curve_tolerance", .02, "input-units", 0.0)),
    ), circle_rings),
    "stroke-dots": (FillEffectDescriptor(
        id="stroke-dots", name="Stroke dots",
        description="Short open marks on a rotated square lattice, clipped to polygonal regions.",
        parameters=(EffectParameter("spacing", 8.0, "input-units", 0.0),
                    EffectParameter("mark_length", .5, "input-units", 0.0),
                    EffectParameter("angle", 0.0, "degrees")),
    ), stroke_dots),
    "vortex-marks": (FillEffectDescriptor(
        id="vortex-marks", name="Vortex marks",
        description="Fixed-length marks tangent to a vortex field on a rotated square lattice.",
        parameters=(EffectParameter("spacing", 8.0, "input-units", 0.0),
                    EffectParameter("mark_length", .5, "input-units", 0.0),
                    EffectParameter("angle", 0.0, "degrees"),
                    EffectParameter("center_x", 0.0, "input-units"),
                    EffectParameter("center_y", 0.0, "input-units")),
    ), vortex_marks),
}


def list_fill_effects() -> tuple[FillEffectDescriptor, ...]:
    """Return implemented effects in stable registration order."""
    return tuple(descriptor for descriptor, _ in _REGISTRY.values())


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
