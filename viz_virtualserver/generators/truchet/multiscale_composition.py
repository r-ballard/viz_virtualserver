from __future__ import annotations

import math
from itertools import groupby

from shapely import affinity, set_precision
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.fill_effects import render_fill_effect

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


def _regions_and_target(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float
) -> tuple[BaseGeometry, Polygon]:
    effective, _ = _precision(arrangement, curve_tolerance)
    size = arrangement.base_tile_size
    # Round-trip output and subtraction must fit the reserved precision budget.
    budget = effective * size / 4
    if any(math.ulp(c) * 4 > budget for p in domain.vertices for c in p):
        raise ValueError("multi-scale domain coordinates cannot represent requested precision")
    # Grid counts may normalize near-integer extents, but the clipping polygon
    # must retain all representable input detail, including very thin domains.
    vertices = tuple(tuple((value - origin) / size
                           for value, origin in zip(point, arrangement.origin, strict=True))
                     for point in domain.vertices)
    target = Polygon(vertices)
    painted = compose_regions(arrangement, curve_tolerance=curve_tolerance)
    # Remove the Boolean precision model before clipping: clipping must retain
    # original polygon edges, not snap intersection points outside the target.
    return set_precision(painted, 0), target


def _boundary_and_target(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float,
) -> tuple[BaseGeometry, Polygon]:
    painted, target = _regions_and_target(arrangement, domain, curve_tolerance=curve_tolerance)
    return painted.boundary, target


def _clipped_paths(
    clipped: BaseGeometry, arrangement: MultiscaleArrangement
) -> tuple[CurvePath, ...]:
    size = arrangement.base_tile_size
    lines = _line_parts(clipped)
    if not lines:
        return ()
    joined = unary_union(lines)
    merged = joined if joined.geom_type == "LineString" else linemerge(joined)
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


def render_multiscale(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float
) -> tuple[CurvePath, ...]:
    boundary, target = _boundary_and_target(arrangement, domain, curve_tolerance=curve_tolerance)
    return _clipped_paths(boundary.intersection(target), arrangement)


def render_multiscale_components(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float
) -> tuple[tuple[int, CurvePath], ...]:
    """Assign identities before clipping so separated fragments share a channel."""
    boundary, target = _boundary_and_target(arrangement, domain, curve_tolerance=curve_tolerance)
    return _component_paths(boundary, target, arrangement)


def _component_paths(
    boundary: BaseGeometry, target: Polygon, arrangement: MultiscaleArrangement,
) -> tuple[tuple[int, CurvePath], ...]:
    lines = _line_parts(boundary)
    if not lines:
        return ()
    sources = set()
    joined = unary_union(lines)
    merged = joined if joined.geom_type == "LineString" else linemerge(joined)
    for line in _line_parts(merged):
        curve = _canonical_path(tuple(line.coords))
        if curve is not None:
            sources.add(curve)
    result = []
    for component_id, source in enumerate(sorted(sources, key=lambda p: (p.points, p.closed))):
        points = source.points + (source.points[:1] if source.closed else ())
        for path in _clipped_paths(LineString(points).intersection(target), arrangement):
            result.append((component_id, path))
    return tuple(sorted(result, key=lambda item: (item[1].points, item[1].closed, item[0])))


def render_multiscale_hatched(
    arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float,
    multicolor: bool, hatch_spacing: float, hatch_angle: float, hatch_region: str,
) -> tuple[tuple[tuple[int, CurvePath], ...], tuple[CurvePath, ...]]:
    """Compose once for boundaries and hatches in the same normalized frame."""
    if any(math.ulp(c) * 4 > hatch_spacing for point in domain.vertices for c in point):
        raise ValueError("hatch spacing cannot be represented reliably at domain coordinates")
    painted, target = _regions_and_target(arrangement, domain, curve_tolerance=curve_tolerance)
    if multicolor:
        curves = _component_paths(painted.boundary, target, arrangement)
    else:
        curves = tuple((0, p) for p in _clipped_paths(
            painted.boundary.intersection(target), arrangement))
    selected = (target.intersection(painted) if hatch_region == "painted"
                else target.difference(painted))
    sampled = render_fill_effect(
        selected, effect="parallel-hatch",
        parameters={"spacing": hatch_spacing / arrangement.base_tile_size, "angle": hatch_angle},
    )
    ox, oy = arrangement.origin
    size = arrangement.base_tile_size
    hatches = []
    for stroke in sampled:
        # Short fragments can collapse after translating to large coordinates.
        path = _canonical_path(tuple((ox + x * size, oy + y * size) for x, y in stroke.points))
        if path is not None:
            hatches.append(path)
    return curves, tuple(hatches)
