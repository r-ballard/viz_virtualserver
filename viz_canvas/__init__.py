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
from .semantics import (
    DomainRef,
    DomainRelation,
    FeatureRef,
    FeatureType,
    PolygonGroup,
    PolygonSurface,
    RelationEndpoint,
    RelationType,
    validate_semantics,
)

__all__ = [
    "CanvasError",
    "CanvasGeometry",
    "CanvasSpec",
    "DomainProvenance",
    "DomainRef",
    "DomainRelation",
    "Edge",
    "FeatureRef",
    "FeatureType",
    "Point",
    "PolygonDomain",
    "PolygonGroup",
    "PolygonSurface",
    "RelationEndpoint",
    "RelationType",
    "build_canvas",
    "is_convex_polygon",
    "polygon_centroid",
    "polygon_edges",
    "polygon_signed_area",
    "polygon_winding",
    "validate_simple_polygon",
    "validate_semantics",
]
