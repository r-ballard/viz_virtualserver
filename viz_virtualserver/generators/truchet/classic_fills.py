"""Shared effects applied to classic composed fields in a near-origin frame."""

from __future__ import annotations

import math

from shapely.geometry import GeometryCollection
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from viz_virtualserver.canvas.models import Point
from viz_virtualserver.fill_effects import render_fill_effect

from .geometry import _canonical_path
from .models import CurvePath, TruchetParameters


def validate_fill_precision(vertices: tuple[Point, ...], parameters: TruchetParameters) -> None:
    resolution = 8 * max(math.ulp(c) for point in vertices for c in point)
    if resolution > min(parameters.tile_size, parameters.curve_tolerance,
                        parameters.hatch_spacing):
        raise ValueError("classic fill geometry or spacing cannot be represented reliably")
    if parameters.hatch_effect == "circle-rings" and resolution >= min(
        parameters.hatch_radius, parameters.hatch_curve_tolerance,
    ):
        raise ValueError(
            "ring radius or tolerance cannot be represented reliably at domain coordinates")
    if parameters.hatch_effect == "stroke-dots" and resolution > parameters.hatch_mark_length:
        raise ValueError("dot mark length cannot be represented reliably at domain coordinates")


def render_classic_fill(
    region: BaseGeometry, *, origin: Point, vertices: tuple[Point, ...],
    parameters: TruchetParameters,
) -> tuple[CurvePath, ...]:
    # Region intersection may also return points/lines from remote corner
    # tangencies. Fill only its area-bearing polygons, not zero-area contacts.
    pending, polygons = [region], []
    while pending:
        part = pending.pop()
        if part.is_empty:
            continue
        if part.geom_type == "Polygon":
            polygons.append(part)
        elif hasattr(part, "geoms"):
            pending.extend(part.geoms)
    selected = unary_union(polygons) if polygons else GeometryCollection()
    controls = {"spacing": parameters.hatch_spacing, "angle": parameters.hatch_angle}
    if parameters.hatch_effect == "circle-rings":
        rounding = 8 * max(math.ulp(c) for point in vertices for c in point)
        tolerance = parameters.hatch_curve_tolerance - rounding
        if tolerance <= 0:
            raise ValueError("ring tolerance cannot be represented reliably at domain coordinates")
        controls.update(radius=parameters.hatch_radius, curve_tolerance=tolerance)
    elif parameters.hatch_effect == "stroke-dots":
        controls["mark_length"] = parameters.hatch_mark_length
    strokes = render_fill_effect(selected, effect=parameters.hatch_effect, parameters=controls)
    ox, oy = origin
    result = []
    for stroke in strokes:
        points = stroke.points + (stroke.points[:1] if stroke.closed else ())
        path = _canonical_path(tuple((x + ox, y + oy) for x, y in points))
        if path is not None:
            result.append(path)
    return tuple(result)
