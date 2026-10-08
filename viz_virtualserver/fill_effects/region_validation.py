"""Polygonal input contract shared by catalogue and direct mark rendering."""

from shapely.geometry.base import BaseGeometry


def validate_region(region: BaseGeometry) -> None:
    if not isinstance(region, BaseGeometry) or not region.is_valid:
        raise ValueError("fill region must be valid polygonal geometry")
    if region.geom_type in ("Polygon", "MultiPolygon"):
        return
    if region.geom_type == "GeometryCollection":
        for part in region.geoms:
            validate_region(part)
        return
    raise ValueError("fill region must be polygonal geometry")
