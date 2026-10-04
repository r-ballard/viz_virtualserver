from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

MAX_POINTS = 2_000_000
_PORTS = ((1, 0), (2, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 2), (0, 1))
_TANGENTS = ((0, 1), (0, 1), (-1, 0), (-1, 0), (0, -1), (0, -1), (1, 0), (1, 0))


@dataclass(frozen=True, slots=True)
class MotifRegions:
    region_zero: BaseGeometry
    region_one: BaseGeometry
    sampled_points: int


@dataclass(frozen=True, slots=True)
class _Arc:
    start: tuple[float, float]
    end: tuple[float, float]
    center: tuple[float, float]
    radius: float
    angle: float
    sweep: float


def _circuits(orientation: int) -> tuple[tuple[int, ...], ...]:
    if orientation not in (0, 1):
        raise ValueError("multi-scale motif orientation must be 0 or 1")
    pairs = ((0, 7), (1, 6), (2, 5), (3, 4))
    partner = {}
    for a, b in pairs:
        a, b = (a + 2 * orientation) % 8, (b + 2 * orientation) % 8
        partner[a], partner[b] = b, a
    result, seen = [], set()
    for start in range(8):
        circuit = [start]
        internal = True
        while True:
            following = partner[circuit[-1]] if internal else (circuit[-1] + 1) % 8
            if following == start:
                break
            circuit.append(following)
            internal = not internal
            if len(circuit) > 16:
                raise ValueError("invalid multi-scale motif circuit")
        key = tuple(sorted(circuit))
        if key not in seen:
            result.append(tuple(circuit))
            seen.add(key)
    if set().union(*(set(c) for c in result)) != set(range(8)):
        raise ValueError("multi-scale motif circuits omit ports")
    return tuple(result)


def _arc(a: int, b: int, tangent_a: tuple[int, int], tangent_b: tuple[int, int]) -> _Arc:
    # Solve normals in integer-thirds coordinates, avoiding translated subtraction.
    start, end = _PORTS[a], _PORTS[b]
    if tangent_a[0] == -tangent_b[0] and tangent_a[1] == -tangent_b[1]:
        center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    else:
        center = ((end[0], start[1]) if tangent_a[0] == 0 else (start[0], end[1]))
    rx, ry = start[0] - center[0], start[1] - center[1]
    sign = 1 if rx * tangent_a[1] - ry * tangent_a[0] > 0 else -1
    angle = math.atan2(ry, rx)
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    sweep = sign * ((sign * (end_angle - angle)) % math.tau)
    return _Arc(tuple(v / 3 for v in start), tuple(v / 3 for v in end),
                tuple(v / 3 for v in center), math.hypot(rx, ry) / 3, angle, sweep)


def _segments(arc: _Arc, tolerance: float) -> int:
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("multi-scale motif tolerance must be finite and positive")
    fraction = tolerance / (2 * arc.radius)
    step = 4 * math.asin(math.sqrt(min(1.0, fraction)))
    if step == 0:
        raise ValueError("multi-scale sampling exceeds 2,000,000 points")
    count = abs(arc.sweep) / step
    if not math.isfinite(count) or count > MAX_POINTS:
        raise ValueError("multi-scale sampling exceeds 2,000,000 points")
    return max(2, math.ceil(count))


def _circuit_arcs(circuit: tuple[int, ...]):
    for i, a in enumerate(circuit):
        b = circuit[(i + 1) % len(circuit)]
        ta = tuple(v * (1 if i % 2 == 0 else -1) for v in _TANGENTS[a])
        tb = tuple(v * (-1 if i % 2 == 0 else 1) for v in _TANGENTS[b])
        # Shared curves use the very same sampled points, reversed when necessary.
        reverse = a > b
        if reverse:
            a, b, ta, tb = b, a, tuple(-v for v in tb), tuple(-v for v in ta)
        yield (a, b, ta, tb), _arc(a, b, ta, tb), reverse


def estimate_motif_points(*, orientation: int, tolerance: float) -> int:
    count = sum(_segments(arc, tolerance) + 1
                for c in _circuits(orientation) for _, arc, _ in _circuit_arcs(c))
    if count > MAX_POINTS:
        raise ValueError("multi-scale sampling exceeds 2,000,000 points")
    return count


def build_motif(*, orientation: int, tolerance: float) -> MotifRegions:
    count = estimate_motif_points(orientation=orientation, tolerance=tolerance)
    sampled, regions = {}, [[], []]
    for circuit in _circuits(orientation):
        points = []
        for key, arc, reverse in _circuit_arcs(circuit):
            if key not in sampled:
                n = _segments(arc, tolerance)
                middle = tuple((
                    arc.center[0] + arc.radius * math.cos(arc.angle + arc.sweep * i / n),
                    arc.center[1] + arc.radius * math.sin(arc.angle + arc.sweep * i / n),
                ) for i in range(1, n))
                sampled[key] = (arc.start, *middle, arc.end)
            segment = sampled[key][::-1] if reverse else sampled[key]
            points.extend(segment[:-1])
        polygon = Polygon(points)
        if not polygon.is_valid or polygon.is_empty:
            raise ValueError("invalid multi-scale motif region geometry")
        regions[circuit[0] % 2].append(polygon)
    zero, one = (unary_union(parts) for parts in regions)
    footprint = zero.union(one)
    if (not zero.is_valid or not one.is_valid or zero.intersection(one).area > 1e-12
            or box(0, 0, 1, 1).difference(footprint).area > 1e-12
            or not box(-1/3 - 1e-12, -1/3 - 1e-12, 4/3 + 1e-12, 4/3 + 1e-12).covers(
                footprint)):
        raise ValueError("multi-scale motif fails region coverage or wing invariants")
    return MotifRegions(zero, one, count)
