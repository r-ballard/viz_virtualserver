"""Intrinsic canvas geometry for generative vector artwork."""

from .design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    DesignState,
    DomainAlgorithm,
    LogicalLayer,
    VectorPath,
    execute_design_pass,
    execute_design_passes,
    validate_pass_graph,
)
from .frames import (
    AffineTransform,
    CompositionTransform,
    resolve_composition_transforms,
)
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
from .job_io import load_domain_artwork_job, read_domain_artwork_job
from .jobs import DomainArtworkJob, derive_domain_seed
from .models import CanvasSpec, DomainProvenance, Edge, Point, PolygonDomain
from .projection import SurfaceProjection, project_surfaces
from .runner import AlgorithmContext, run_domain_artwork_job
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
    "AlgorithmContext",
    "AlgorithmCapabilities",
    "AffineTransform",
    "CanvasError",
    "CanvasGeometry",
    "CanvasSpec",
    "CompositionTransform",
    "DesignPass",
    "DesignResult",
    "DesignState",
    "DomainProvenance",
    "DomainRef",
    "DomainRelation",
    "DomainAlgorithm",
    "DomainArtworkJob",
    "Edge",
    "FeatureRef",
    "FeatureType",
    "LogicalLayer",
    "Point",
    "PolygonDomain",
    "PolygonGroup",
    "PolygonSurface",
    "RelationEndpoint",
    "RelationType",
    "SurfaceProjection",
    "VectorPath",
    "build_canvas",
    "execute_design_pass",
    "execute_design_passes",
    "derive_domain_seed",
    "is_convex_polygon",
    "load_domain_artwork_job",
    "polygon_centroid",
    "polygon_edges",
    "polygon_signed_area",
    "polygon_winding",
    "project_surfaces",
    "resolve_composition_transforms",
    "read_domain_artwork_job",
    "run_domain_artwork_job",
    "validate_simple_polygon",
    "validate_semantics",
    "validate_pass_graph",
]
