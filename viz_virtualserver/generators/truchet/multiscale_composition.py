from __future__ import annotations

import math
from itertools import groupby

from shapely import affinity, set_precision
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from viz_virtualserver.canvas.models import PolygonDomain

from .geometry import _canonical_path
from .models import CurvePath
from .multiscale_models import MultiscaleArrangement
from .multiscale_motifs import MAX_POINTS, build_motif, estimate_motif_points


def _precision(arrangement: MultiscaleArrangement, tolerance: float) -> tuple[float, float]:
    if not arrangement.leaves:
        raise ValueError("multi-scale arrangement requires leaves")
    smallest = min(v.bounds[2] - v.bounds[0] for v in arrangement.leaves)
    effective = min(tolerance / arrangement.base_tile_size, smallest / 100)
    grid = min(effective / 16, smallest / 1024)
    maximum = max(abs(c) for v in arrangement.leaves for c in v.bounds) + 1
    if (not math.isfinite(effective) or effective <= 0 or grid == 0
            or math.ulp(maximum) > grid / 4):
        raise ValueError("multi-scale requested precision cannot be represented reliably")
    return effective, grid


def compose_regions(
    arrangement: MultiscaleArrangement, *, curve_tolerance: float
) -> BaseGeometry:
    effective, grid = _precision(arrangement, curve_tolerance)
    # Sampling receives 3/4 of the budget. Snapping moves points by <= grid/sqrt(2),
    # well below the remaining quarter; use identical unit motifs at each scale.
    keys = [(leaf.orientation, leaf.bounds[2] - leaf.bounds[0]) for leaf in arrangement.leaves]
    estimates = {key: estimate_motif_points(orientation=key[0], tolerance=effective * .75/key[1])
                 for key in set(keys)}
    if sum(estimates[key] for key in keys) > MAX_POINTS:
        raise ValueError("multi-scale sampling exceeds 2,000,000 points")
    motifs = {key: build_motif(orientation=key[0], tolerance=effective * .75/key[1])
              for key in sorted(estimates)}
    painted = GeometryCollection()
    try:
        ordered = sorted(arrangement.leaves, key=lambda v: (v.depth, v.address))
        for depth, leaves in groupby(ordered, key=lambda v: v.depth):
            footprints, colored = [], []
            for leaf in leaves:
                left, bottom, right, _ = leaf.bounds
                side = right - left
                motif = motifs[leaf.orientation, side]
                regions = tuple(set_precision(affinity.translate(
                    affinity.scale(region, xfact=side, yfact=side, origin=(0, 0)), left, bottom),
                    grid) for region in (motif.region_zero, motif.region_one))
                footprints.extend(regions)
                colored.append(regions[1 - depth % 2])
            # Same-depth wings agree in overlap. Union them once rather than
            # repeatedly recomputing a growing boundary for every leaf.
            painted = painted.difference(unary_union(footprints)).union(unary_union(colored))
        if not painted.is_valid:
            raise ValueError("invalid multi-scale composed region geometry")
    except GEOSException as exc:
        raise ValueError("multi-scale region composition failed") from exc
    return painted


def _line_parts(geometry: BaseGeometry) -> list[BaseGeometry]:
    pending, lines = [geometry], []
    while pending:
        part = pending.pop()
        if part.is_empty:
            continue
        if part.geom_type in ("LineString", "LinearRing"):
            lines.append(part)
        elif hasattr(part, "geoms"):
            pending.extend(part.geoms)
    return lines


def render_multiscale(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float
) -> tuple[CurvePath, ...]:
    effective, _ = _precision(arrangement, curve_tolerance)
    size = arrangement.base_tile_size
    # Round-trip output and subtraction must fit the reserved precision budget.
    budget = effective * size / 4
    if any(math.ulp(c) * 4 > budget for p in domain.vertices for c in p):
        raise ValueError("multi-scale domain coordinates cannot represent requested precision")
    vertices = []
    for point in domain.vertices:
        local = []
        for value, origin in zip(point, arrangement.origin, strict=True):
            coordinate = (value - origin) / size
            nearest = round(coordinate)
            error = 4 * ((math.ulp(value) + math.ulp(origin)) / size + math.ulp(coordinate))
            local.append(nearest if abs(coordinate - nearest) <= error else coordinate)
        vertices.append(tuple(local))
    target = Polygon(vertices)
    painted = compose_regions(arrangement, curve_tolerance=curve_tolerance)
    # Remove the Boolean precision model before clipping: clipping must retain
    # original polygon edges, not snap intersection points outside the target.
    clipped = set_precision(painted.boundary, 0).intersection(target)
    lines = _line_parts(clipped)
    if not lines:
        return ()
    merged = linemerge(unary_union(lines))
    paths = set()
    for line in _line_parts(merged):
        normalized = _canonical_path(tuple(line.coords))
        if normalized is None:
            continue
        points = tuple((arrangement.origin[0] + x * size,
                        arrangement.origin[1] + y * size) for x, y in normalized.points)
        path = _canonical_path(points + (points[:1] if normalized.closed else ()))
        if path is not None:
            paths.add(path)
    return tuple(sorted(paths, key=lambda p: (p.points, p.closed)))
