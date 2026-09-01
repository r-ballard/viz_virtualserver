"""Intrinsic per-surface projections of completed polygon artwork jobs."""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import GeometryCollection, LineString, MultiLineString

from .design import DesignState, LogicalLayer, VectorPath
from .frames import AffineTransform, resolve_composition_transforms
from .geometry import EPSILON
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

    measured_components: list[tuple[float, tuple[CanvasPoint, ...], bool]] = []
    for line in lines:
        coordinates = tuple((float(x), float(y)) for x, y in line.coords)
        forward = _traversal_fit(
            coordinates[0],
            coordinates[-1],
            float(line.length),
            line_points,
            closed=closed,
        )
        reverse = _traversal_fit(
            coordinates[-1],
            coordinates[0],
            float(line.length),
            line_points,
            closed=closed,
        )
        if abs(forward[0] - reverse[0]) <= EPSILON:
            forward_direction = _direction_error(coordinates, line_points)
            reverse_direction = _direction_error(
                tuple(reversed(coordinates)), line_points
            )
            reverse_component = reverse_direction < forward_direction
        else:
            reverse_component = reverse[0] < forward[0]
        if reverse_component:
            coordinates = tuple(reversed(coordinates))
            source_measure = reverse[1]
        else:
            source_measure = forward[1]
        component_closed = closed and coordinates[0] == coordinates[-1]
        if component_closed:
            coordinates = coordinates[:-1]
        minimum = 3 if component_closed else 2
        if len(coordinates) >= minimum:
            measured_components.append(
                (source_measure, coordinates, component_closed)
            )
    measured_components.sort(key=lambda component: component[0])
    return tuple(
        (coordinates, component_closed)
        for _, coordinates, component_closed in measured_components
    )


def _traversal_fit(
    start: CanvasPoint,
    end: CanvasPoint,
    component_length: float,
    source_points: tuple[CanvasPoint, ...],
    *,
    closed: bool,
) -> tuple[float, float]:
    positions, total_length = _source_positions((start, end), source_points)
    candidates: list[tuple[float, float]] = []
    for start_measure in positions[0]:
        for end_measure in positions[1]:
            distance = end_measure - start_measure
            if closed:
                distance %= total_length
                if distance <= EPSILON and component_length > EPSILON:
                    distance = total_length
            candidates.append((abs(distance - component_length), start_measure))
    if not candidates:
        raise ValueError("clipped path component does not follow source path")
    return min(candidates)


def _source_positions(
    points: tuple[CanvasPoint, CanvasPoint],
    source_points: tuple[CanvasPoint, ...],
) -> tuple[tuple[tuple[float, ...], tuple[float, ...]], float]:
    positions: list[list[float]] = [[], []]
    source_measure = 0.0
    for segment_start, segment_end in zip(source_points, source_points[1:]):
        segment_length = math.dist(segment_start, segment_end)
        for index, point in enumerate(points):
            parameter = _segment_parameter(point, segment_start, segment_end)
            if parameter is not None:
                positions[index].append(source_measure + parameter * segment_length)
        source_measure += segment_length
    if not all(positions):
        raise ValueError("clipped path endpoint does not lie on source path")
    return (tuple(positions[0]), tuple(positions[1])), source_measure


def _direction_error(
    coordinates: tuple[CanvasPoint, ...], source_points: tuple[CanvasPoint, ...]
) -> float:
    for start, end in zip(coordinates, coordinates[1:]):
        edge_length = math.dist(start, end)
        if edge_length <= EPSILON:
            continue
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        errors: list[float] = []
        for segment_start, segment_end in zip(source_points, source_points[1:]):
            if _segment_parameter(midpoint, segment_start, segment_end) is None:
                continue
            segment_length = math.dist(segment_start, segment_end)
            dot = (
                (end[0] - start[0]) * (segment_end[0] - segment_start[0])
                + (end[1] - start[1]) * (segment_end[1] - segment_start[1])
            ) / (edge_length * segment_length)
            errors.append(1.0 - dot)
        if errors:
            return min(errors)
    return math.inf


def _segment_parameter(
    point: CanvasPoint, start: CanvasPoint, end: CanvasPoint
) -> float | None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= EPSILON * EPSILON:
        return None
    parameter = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    if not -EPSILON <= parameter <= 1.0 + EPSILON:
        return None
    projected = (start[0] + parameter * dx, start[1] + parameter * dy)
    if math.dist(point, projected) > EPSILON:
        return None
    return min(1.0, max(0.0, parameter))


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
