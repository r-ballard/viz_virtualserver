"""Intrinsic canvas geometry for generative vector artwork."""

from .geometry import (
    CanvasError,
    CanvasGeometry,
    build_canvas,
    is_convex_polygon,
    polygon_centroid,
    polygon_edges,
    polygon_signed_area,
    polygon_winding,
    validate_simple_polygon,
)
from .models import CanvasSpec, DomainProvenance, Edge, Point, PolygonDomain

__all__ = [
    "CanvasError",
    "CanvasGeometry",
    "CanvasSpec",
    "DomainProvenance",
    "Edge",
    "Point",
    "PolygonDomain",
    "build_canvas",
    "is_convex_polygon",
    "polygon_centroid",
    "polygon_edges",
    "polygon_signed_area",
    "polygon_winding",
    "validate_simple_polygon",
]
