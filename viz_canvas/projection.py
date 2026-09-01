"""Intrinsic per-surface projections of completed polygon artwork jobs."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point

from .design import DesignState, LogicalLayer, VectorPath
from .frames import AffineTransform, resolve_composition_transforms
from .jobs import DomainArtworkJob
from .models import Point as CanvasPoint
from .models import PolygonDomain
from .semantics import PolygonSurface


@dataclass(frozen=True, slots=True)
class SurfaceProjection:
    """One surface's artwork expressed in its rebased intrinsic frame."""

    surface: PolygonSurface
    domain: PolygonDomain
    paths: tuple[VectorPath, ...]
    layers: tuple[LogicalLayer, ...]
    bounds: tuple[float, float, float, float]
    up_anchor: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(self.paths))
        object.__setattr__(self, "layers", tuple(self.layers))
        object.__setattr__(self, "bounds", tuple(float(value) for value in self.bounds))


def project_surfaces(
    job: DomainArtworkJob, state: DesignState
) -> tuple[SurfaceProjection, ...]:
    """Project completed neutral paths into each declared surface's local frame."""

    domains = {domain.id: domain for domain in job.domains}
    transforms = resolve_composition_transforms(
        job.domains, job.composition_transforms
    )
    for result in state.results:
        for path in result.paths:
            if path.coordinate_frame == "composition" and path.domain_id not in transforms:
                raise ValueError(
                    f"composition transform required for domain: {path.domain_id}"
                )
    declared_layers = _declared_layers(job)
    projections: list[SurfaceProjection] = []

    for surface in job.resolved_surfaces:
        domain = domains[surface.domain_id]
        min_x, min_y, max_x, max_y = _bounds(domain.vertices)
        projected_paths: list[VectorPath] = []
        for result in state.results:
            for path in result.paths:
                if path.domain_id != domain.id:
                    continue
                projected_paths.extend(
                    _project_path(
                        path,
                        domain=domain,
                        transform=transforms.get(domain.id),
                        offset=(min_x, min_y),
                    )
                )

        rebased_domain = PolygonDomain(
            id=domain.id,
            vertices=tuple(
                (float(x) - min_x, float(y) - min_y) for x, y in domain.vertices
            ),
            provenance=domain.provenance,
        )
        paths = tuple(projected_paths)
        projections.append(
            SurfaceProjection(
                surface=surface,
                domain=rebased_domain,
                paths=paths,
                layers=_projection_layers(paths, declared_layers),
                bounds=(0.0, 0.0, max_x - min_x, max_y - min_y),
                up_anchor="edge:0",
            )
        )

    return tuple(projections)


def _declared_layers(job: DomainArtworkJob) -> tuple[LogicalLayer, ...]:
    layers: list[LogicalLayer] = []
    seen: set[str] = set()
    for design_pass in job.passes:
        for layer in design_pass.logical_layers:
            if layer.id not in seen:
                seen.add(layer.id)
                layers.append(layer)
    return tuple(layers)


def _projection_layers(
    paths: tuple[VectorPath, ...], declared_layers: tuple[LogicalLayer, ...]
) -> tuple[LogicalLayer, ...]:
    used = {path.layer_id for path in paths}
    layers = [layer for layer in declared_layers if layer.id in used]
    seen = {layer.id for layer in layers}
    for path in paths:
        if path.layer_id not in seen:
            seen.add(path.layer_id)
            layers.append(LogicalLayer(path.layer_id))
    return tuple(layers)


def _project_path(
    path: VectorPath,
    *,
    domain: PolygonDomain,
    transform: AffineTransform | None,
    offset: CanvasPoint,
) -> tuple[VectorPath, ...]:
    if path.coordinate_frame == "composition":
        if transform is None:
            raise ValueError(f"composition transform required for domain: {domain.id}")
        local_points = tuple(transform.inverse().apply(point) for point in path.points)
        components = _clip_line_components(local_points, path.closed, domain)
    else:
        components = ((path.points, path.closed),)

    min_x, min_y = offset
    return tuple(
        VectorPath(
            points=tuple((x - min_x, y - min_y) for x, y in points),
            closed=closed,
            layer_id=path.layer_id,
            domain_id=path.domain_id,
            coordinate_frame="domain",
        )
        for points, closed in components
    )


def _clip_line_components(
    points: tuple[CanvasPoint, ...], closed: bool, domain: PolygonDomain
) -> tuple[tuple[tuple[CanvasPoint, ...], bool], ...]:
    line_points = (*points, points[0]) if closed else points
    source = LineString(line_points)
    intersection = source.intersection(_polygon(domain))
    lines = _line_strings(intersection)
    ordered = sorted(lines, key=lambda line: source.project(Point(line.coords[0])))

    components: list[tuple[tuple[CanvasPoint, ...], bool]] = []
    for line in ordered:
        coordinates = tuple((float(x), float(y)) for x, y in line.coords)
        if source.project(Point(coordinates[0])) > source.project(Point(coordinates[-1])):
            coordinates = tuple(reversed(coordinates))
        component_closed = closed and coordinates[0] == coordinates[-1]
        if component_closed:
            coordinates = coordinates[:-1]
        minimum = 3 if component_closed else 2
        if len(coordinates) >= minimum:
            components.append((coordinates, component_closed))
    return tuple(components)


def _line_strings(geometry) -> tuple[LineString, ...]:
    if isinstance(geometry, LineString):
        return () if geometry.is_empty else (geometry,)
    if isinstance(geometry, (MultiLineString, GeometryCollection)):
        return tuple(
            line
            for component in geometry.geoms
            for line in _line_strings(component)
        )
    return ()


def _polygon(domain: PolygonDomain):
    from shapely.geometry import Polygon

    return Polygon(domain.vertices)


def _bounds(
    vertices: tuple[CanvasPoint, ...],
) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in vertices]
    ys = [float(point[1]) for point in vertices]
    return min(xs), min(ys), max(xs), max(ys)
