from __future__ import annotations

import math
from collections import defaultdict

from shapely.geometry import LineString, Polygon

from viz_canvas.models import Point, PolygonDomain

from .models import CurvePath, TileArrangement, TruchetParameters

_MAX_POINTS = 2_000_000


def _segments(length: float, ratio: float, tolerance: float) -> int:
    sagitta = abs(ratio) * length
    if sagitta <= tolerance:
        return 1
    radius = length * (1 + 4 * ratio * ratio) / (8 * abs(ratio))
    half_angle = 2 * math.atan(2 * abs(ratio))
    fraction = tolerance / (2 * radius)
    if fraction <= 0:
        raise ValueError("Truchet sampling exceeds 2,000,000 points")
    step = 4 * math.asin(math.sqrt(min(1.0, fraction)))
    count = 2 * half_angle / step
    if not math.isfinite(count) or count > _MAX_POINTS:
        raise ValueError("Truchet sampling exceeds 2,000,000 points")
    return max(1, math.ceil(count))


def sample_connection(
    start: Point, end: Point, *, sagitta_ratio: float, tolerance: float
) -> tuple[Point, ...]:
    """Positive sagitta bows to the right of the directed endpoint chord."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    count = _segments(length, sagitta_ratio, tolerance)
    if count == 1:
        return start, end
    ratio = abs(sagitta_ratio)
    radius = length * (1 + 4 * ratio * ratio) / (8 * ratio)
    half_angle = 2 * math.atan(2 * ratio)
    sign = math.copysign(1, sagitta_ratio)
    points = [start]
    for index in range(1, count):
        angle = half_angle * (2 * index / count - 1)
        along = length / 2 + radius * math.sin(angle)
        across = sign * (ratio * length - 2 * radius * math.sin(angle / 2) ** 2)
        points.append(
            (
                start[0] + (dx * along + dy * across) / length,
                start[1] + (dy * along - dx * across) / length,
            )
        )
    points.append(end)
    return tuple(points)


def render_arrangement(
    arrangement: TileArrangement, parameters: TruchetParameters
) -> tuple[CurvePath, ...]:
    length = arrangement.tile_size / math.sqrt(2)
    ratios = (parameters.arc_a, parameters.arc_b)
    counts = tuple(_segments(length, r, parameters.curve_tolerance) + 1 for r in ratios)
    if len(arrangement.tiles) * sum(counts) > _MAX_POINTS:
        raise ValueError("Truchet sampling exceeds 2,000,000 points")
    offsets = ((1, 0), (2, 1), (1, 2), (0, 1))
    curves = []
    adjacency = defaultdict(list)
    for tile in arrangement.tiles:
        keys = tuple((2 * tile.column + x, 2 * tile.row + y) for x, y in offsets)
        for index, (a, b) in enumerate(tile.state.connections):
            start, end = keys[a], keys[b]
            # Orient the chord so its right-hand normal points toward tile center.
            # Opposing corner connections have opposite directed orientations.
            dx, dy = end[0] - start[0], end[1] - start[1]
            cx, cy = 2 * tile.column + 1, 2 * tile.row + 1
            toward_center = dy * (2 * cx - start[0] - end[0]) - dx * (2 * cy - start[1] - end[1])
            if toward_center < 0:
                start, end = end, start

            def position(key):
                return (
                    arrangement.origin[0] + key[0] * arrangement.tile_size / 2,
                    arrangement.origin[1] + key[1] * arrangement.tile_size / 2,
                )

            points = sample_connection(
                position(start),
                position(end),
                sagitta_ratio=ratios[index],
                tolerance=parameters.curve_tolerance,
            )
            curve_id = len(curves)
            curves.append((start, end, points))
            adjacency[start].append(curve_id)
            adjacency[end].append(curve_id)
    unused = set(range(len(curves)))
    paths = []
    starts = sorted(adjacency, key=lambda key: (len(adjacency[key]) != 1, key))
    for start in starts:
        if not any(i in unused for i in adjacency[start]):
            continue
        points = []
        current = start
        while True:
            candidates = [i for i in adjacency[current] if i in unused]
            if not candidates:
                break
            curve_id = candidates[0]
            unused.remove(curve_id)
            a, b, segment = curves[curve_id]
            if current == b:
                segment = segment[::-1]
            current = b if current == a else a
            points.extend(segment if not points else segment[1:])
        closed = current == start
        paths.append(CurvePath(tuple(points[:-1] if closed else points), closed))
    return tuple(paths)


def _canonical_path(points: tuple[Point, ...]) -> CurvePath | None:
    unique = tuple(p for i, p in enumerate(points) if not i or p != points[i - 1])
    if len(unique) < 2:
        return None
    closed = unique[0] == unique[-1]
    if closed:
        unique = unique[:-1]
        if len(unique) < 3:
            return None
        # Start at the lexicographically smallest vertex in either traversal.
        choices = []
        for sequence in (unique, unique[::-1]):
            index = min(range(len(sequence)), key=sequence.__getitem__)
            choices.append(sequence[index:] + sequence[:index])
        unique = min(choices)
    else:
        unique = min(unique, unique[::-1])
    return CurvePath(unique, closed)


def clip_paths(paths: tuple[CurvePath, ...], domain: PolygonDomain) -> tuple[CurvePath, ...]:
    polygon = Polygon(domain.vertices)
    clipped = []
    for path in paths:
        points = path.points + (path.points[:1] if path.closed else ())
        geometry = LineString(points).intersection(polygon)
        pending = [geometry]
        while pending:
            component = pending.pop()
            if component.is_empty:
                continue
            if component.geom_type == "LineString":
                normalized = _canonical_path(tuple(component.coords))
                if normalized is not None:
                    clipped.append(normalized)
            elif hasattr(component, "geoms"):
                pending.extend(component.geoms)
    return tuple(sorted(clipped, key=lambda p: (p.points, p.closed)))
