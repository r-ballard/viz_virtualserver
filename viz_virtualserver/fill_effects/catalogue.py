"""Explicit fill catalogue, parameter validation, and rendering dispatch."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real

from shapely.geometry.base import BaseGeometry

from .circle_rings import circle_rings
from .crosshatch import crosshatches
from .density_fields import DensityField, validate_density_field
from .field_marks import render_field_marks
from .mark_selection import MARK_DENSITY_EFFECTS, validate_density_seed
from .models import EffectParameter, FillEffectDescriptor, FillStroke
from .parallel_hatch import parallel_hatches
from .region_validation import validate_region as _validate_region
from .stroke_dots import stroke_dots
from .vector_fields import VectorField
from .vortex_marks import vortex_marks

_PARALLEL_HATCH = FillEffectDescriptor(
    id="parallel-hatch",
    name="Parallel hatch",
    description="Parallel open strokes clipped to composed polygonal regions.",
    parameters=(
        EffectParameter("spacing", 2.0, "input-units", 0.0),
        EffectParameter("angle", 45.0, "degrees"),
    ),
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
    "circle-rings": (
        FillEffectDescriptor(
            id="circle-rings",
            name="Circle rings",
            description=(
                "Circle outlines on a rotated square lattice, clipped to polygonal regions."
            ),
            parameters=(
                EffectParameter("spacing", 8.0, "input-units", 0.0),
                EffectParameter("radius", 2.0, "input-units", 0.0),
                EffectParameter("angle", 0.0, "degrees"),
                EffectParameter("curve_tolerance", 0.02, "input-units", 0.0),
            ),
        ),
        circle_rings,
    ),
    "stroke-dots": (
        FillEffectDescriptor(
            id="stroke-dots",
            name="Stroke dots",
            description=(
                "Short open marks on a rotated square lattice, clipped to polygonal regions."
            ),
            parameters=(
                EffectParameter("spacing", 8.0, "input-units", 0.0),
                EffectParameter("mark_length", 0.5, "input-units", 0.0),
                EffectParameter("angle", 0.0, "degrees"),
                EffectParameter("density", 1.0, "fraction", minimum=0.0, maximum=1.0),
            ),
            supports_density_field=True,
        ),
        stroke_dots,
    ),
    "vortex-marks": (
        FillEffectDescriptor(
            id="vortex-marks",
            name="Vortex marks",
            description="Fixed-length marks tangent to a vortex field on a rotated square lattice.",
            parameters=(
                EffectParameter("spacing", 8.0, "input-units", 0.0),
                EffectParameter("mark_length", 0.5, "input-units", 0.0),
                EffectParameter("angle", 0.0, "degrees"),
                EffectParameter("center_x", 0.0, "input-units"),
                EffectParameter("center_y", 0.0, "input-units"),
                EffectParameter("density", 1.0, "fraction", minimum=0.0, maximum=1.0),
            ),
            supports_density_field=True,
        ),
        vortex_marks,
    ),
    "field-marks": (
        FillEffectDescriptor(
            id="field-marks",
            name="Field marks",
            description="Fixed-length marks oriented by a caller-supplied vector field.",
            parameters=(
                EffectParameter("spacing", 8.0, "input-units", 0.0),
                EffectParameter("mark_length", 0.5, "input-units", 0.0),
                EffectParameter("angle", 0.0, "degrees"),
                EffectParameter("density", 1.0, "fraction", minimum=0.0, maximum=1.0),
            ),
            requires_field=True,
            supports_density_field=True,
        ),
        render_field_marks,
    ),
}


def list_fill_effects() -> tuple[FillEffectDescriptor, ...]:
    """Return implemented effects in stable registration order."""
    return tuple(descriptor for descriptor, _ in _REGISTRY.values())


def validate_fill_parameters(
    *,
    effect: str,
    parameters: Mapping[str, object] | None = None,
) -> dict[str, float]:
    """Validate effect controls without generating or requiring geometry."""
    if not isinstance(effect, str) or effect not in _REGISTRY:
        raise ValueError(f"unknown fill effect: {effect!r}")
    descriptor, _ = _REGISTRY[effect]
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
            valid = not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(value)
            number = float(value) if valid else math.nan
        except (OverflowError, TypeError, ValueError):
            valid, number = False, math.nan
        if (
            not valid
            or (parameter.exclusive_minimum is not None and number <= parameter.exclusive_minimum)
            or (parameter.minimum is not None and number < parameter.minimum)
            or (parameter.maximum is not None and number > parameter.maximum)
        ):
            raise ValueError(f"invalid fill parameter {parameter.name}: {value!r}")
        controls[parameter.name] = number
    return controls


def render_fill_effect(
    region: BaseGeometry,
    *,
    effect: str,
    parameters: Mapping[str, object] | None = None,
    field: VectorField | None = None,
    density_seed: int = 0,
    density_field: DensityField | None = None,
) -> tuple[FillStroke, ...]:
    """Render strokes without changing frame, assigning layers, or repairing regions."""
    controls = validate_fill_parameters(effect=effect, parameters=parameters)
    validate_density_seed(density_seed)
    if effect not in MARK_DENSITY_EFFECTS and density_seed != 0:
        raise ValueError("fill effect does not accept a density seed")
    descriptor, renderer = _REGISTRY[effect]
    validate_density_field(density_field)
    if density_field is not None and not descriptor.supports_density_field:
        raise ValueError("fill effect does not accept a density field")
    if descriptor.requires_field:
        if not callable(getattr(field, "sample", None)):
            raise ValueError("fill effect requires a vector field implementing sample(x, y)")
    elif field is not None:
        raise ValueError("fill effect does not accept a vector field")
    _validate_region(region)
    if effect in MARK_DENSITY_EFFECTS:
        controls["density_seed"] = density_seed
        if density_field is not None:
            controls["density_field"] = density_field
    if descriptor.requires_field:
        return renderer(region, **controls, field=field)
    return renderer(region, **controls)


def estimate_fill_candidates(
    region: BaseGeometry, *, effect: str, parameters: Mapping[str, object] | None = None
) -> int:
    """Count actual scan/lattice candidates using the renderer's own plan."""
    controls = validate_fill_parameters(effect=effect, parameters=parameters)
    _validate_region(region)
    controls.pop("density", None)
    if region.is_empty:
        return 0
    if effect in ("parallel-hatch", "crosshatch"):
        from .parallel_hatch import _scan_frame

        angle = controls["angle"] % 180
        angles = (angle,) if effect == "parallel-hatch" else (angle, (angle + 90) % 180)
        frames = [_scan_frame(region, spacing=controls["spacing"], angle=a) for a in angles]
        count = sum(max(0, f.last - f.first + 1) for f in frames)
        from .parallel_hatch import MAX_HATCH_ROWS

        if count > MAX_HATCH_ROWS:
            raise ValueError("hatching exceeds 100,000 scan rows")
        return count
    if effect == "stroke-dots":
        from .stroke_dots import _candidate_plan
    elif effect == "circle-rings":
        from .circle_rings import _candidate_plan
    else:
        from .field_marks import _candidate_plan

        controls = {k: v for k, v in controls.items() if k in ("spacing", "mark_length", "angle")}
    plan = _candidate_plan(region, **controls)
    return plan[-1] if plan is not None else 0
