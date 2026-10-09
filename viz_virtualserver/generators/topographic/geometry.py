"""Conservative contour simplification and independent polygon clipping."""

import math

from shapely import STRtree
from shapely.geometry import LineString, Polygon

from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.scalar_fields.contours import canonical_contour
from viz_virtualserver.scalar_fields.models import Contour


def _line(c):
    return LineString(c.points+(c.points[:1] if c.closed else ()))


def simplify_contours(contours: tuple[Contour, ...], *, tolerance: float) -> tuple[Contour, ...]:
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('simplification tolerance must be finite and nonnegative')
    if tolerance == 0 or not contours:
        return contours
    originals = [_line(c) for c in contours]
    candidates = list(contours)
    for i, (c, original) in enumerate(zip(contours, originals, strict=True)):
        simplified = original.simplify(tolerance, preserve_topology=True)
        candidate = canonical_contour(c.level, tuple(simplified.coords), c.closed)
        if candidate is None:
            continue
        geometry = _line(candidate)
        if (original.is_simple and not geometry.is_simple
                or geometry.hausdorff_distance(original) > tolerance):
            continue
        candidates[i] = candidate
    # Reversion can expose a new conflict with a neighbor: iterate monotonically.
    while True:
        lines = [_line(c) for c in candidates]
        tree = STRtree(lines)
        revert = set()
        for i, geometry in enumerate(lines):
            for j in tree.query(geometry, predicate='intersects').tolist():
                if j <= i or (candidates[i] == contours[i] and candidates[j] == contours[j]):
                    continue
                overlap = geometry.intersection(lines[j])
                original_overlap = originals[i].intersection(originals[j])
                # Preserve the actual intersection set, rather than just its existence.
                if not original_overlap.covers(overlap):
                    if candidates[i] != contours[i]:
                        revert.add(i)
                    if candidates[j] != contours[j]:
                        revert.add(j)
        if not revert:
            break
        for i in revert:
            candidates[i] = contours[i]
    return tuple(candidates)


def _linear_parts(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == 'LineString':
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for part in geometry.geoms:
            yield from _linear_parts(part)


def clip_contours(contours: tuple[Contour, ...], polygon: PolygonDomain) -> tuple[Contour, ...]:
    boundary = Polygon(polygon.vertices)
    result = []
    for contour in contours:
        line = _line(contour)
        if boundary.covers(line):
            canonical = canonical_contour(contour.level, contour.points, contour.closed)
            if canonical is not None:
                result.append(canonical)
            continue
        for part in _linear_parts(line.intersection(boundary)):
            if part.length == 0:
                continue
            coords = tuple(part.coords)
            canonical = canonical_contour(contour.level, coords, coords[0] == coords[-1])
            if canonical is not None:
                result.append(canonical)
    return tuple(sorted(result, key=lambda c: (c.level, c.points, c.closed)))


def prepare_contours(contours: tuple[Contour, ...], polygon: PolygonDomain, *,
                     tolerance: float) -> tuple[Contour, ...]:
    simplified = simplify_contours(contours, tolerance=tolerance)
    original_clipped = clip_contours(contours, polygon)
    clipped = clip_contours(simplified, polygon)
    # Intersection after clipping must be contained in the original clipped set.
    lines = [_line(c) for c in clipped]
    if not lines:
        return ()
    tree = STRtree(lines)
    from shapely.ops import unary_union
    original_by_level = {}
    for c in original_clipped:
        original_by_level.setdefault(c.level, []).append(_line(c))
    original_by_level = {level: unary_union(parts) for level, parts in original_by_level.items()}
    for i, line in enumerate(lines):
        if line.is_simple is False:
            return original_clipped
        for j in tree.query(line, predicate='intersects').tolist():
            if j <= i:
                continue
            a = original_by_level.get(clipped[i].level)
            b = original_by_level.get(clipped[j].level)
            if a is None or b is None or not a.intersection(b).covers(line.intersection(lines[j])):
                return original_clipped
    return clipped
