"""Canonical full-precision polygon identities without generator ownership."""

import hashlib
import math
from dataclasses import dataclass

from shapely import get_num_coordinates, to_wkb
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

MAX_COMPONENTS = 100_000
MAX_COMPONENT_COORDINATES = 1_000_000


@dataclass(frozen=True, slots=True)
class RegionComponent:
    id: str
    geometry: Polygon


def _rotation(points):
    # Booth's minimum rotation; repeated coordinates remain in the sequence.
    n = len(points)
    doubled = points + points
    i, j, k = 0, 1, 0
    while i < n and j < n and k < n:
        a, b = doubled[i + k], doubled[j + k]
        if a == b:
            k += 1
            continue
        if a > b:
            i += k + 1
            if i == j:
                i += 1
        else:
            j += k + 1
            if i == j:
                j += 1
        k = 0
    at = min(i, j)
    return points[at:] + points[:at]


def _ring(ring):
    points = tuple(tuple(0.0 if v == 0 else float(v) for v in p[:2]) for p in ring.coords)[:-1]
    if any(not math.isfinite(v) for p in points for v in p):
        raise ValueError("component coordinates must be finite")
    result = min(_rotation(points), _rotation(points[::-1]))
    return result + result[:1]


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def identify_components(region: BaseGeometry) -> tuple[RegionComponent, ...]:
    if not isinstance(region, BaseGeometry) or region.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("components require polygonal geometry")
    if get_num_coordinates(region) > MAX_COMPONENT_COORDINATES:
        raise ValueError("component coordinate budget exceeded")
    if not region.is_valid or region.has_z or getattr(region, "has_m", False):
        raise ValueError("components require valid two-dimensional geometry")
    if region.is_empty:
        return ()
    polygons = (region,) if region.geom_type == "Polygon" else region.geoms
    if len(polygons) > MAX_COMPONENTS:
        raise ValueError("component count budget exceeded")
    seen, records = {}, []
    for polygon in polygons:
        if polygon.area <= 0:
            continue
        canonical = Polygon(_ring(polygon.exterior), sorted(_ring(r) for r in polygon.interiors))
        value = to_wkb(canonical, byte_order=0, output_dimension=2, include_srid=False)
        identity = _digest(value)
        if identity in seen and seen[identity] != value:
            raise ValueError("component digest collision")
        seen[identity] = value
        records.append((identity, value, RegionComponent(identity, canonical)))
    return tuple(record for _, _, record in sorted(records, key=lambda v: v[:2]))
