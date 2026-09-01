from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from viz_canvas.design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    VectorPath,
)
from viz_canvas.geometry import CanvasGeometry, build_canvas
from viz_canvas.models import PolygonDomain

from .models import ConcentricPointsRequest

if TYPE_CHECKING:
    from viz_canvas.runner import AlgorithmContext

Point = tuple[float, float]
_CIRCLE_PATH_SEGMENTS = 64


class ConcentricError(ValueError):
    """Raised when concentric-point generation cannot satisfy its geometry contract."""


def generate_concentric_points(data: ConcentricPointsRequest) -> dict:
    """Generate deterministic circle centers and radii inside an intrinsic canvas."""

    canvas = build_canvas(data.canvas)
    return _generate_concentric_points(data, canvas)


def _generate_concentric_points(
    data: ConcentricPointsRequest,
    canvas: CanvasGeometry,
) -> dict:
    """Run the established generator against supplied canonical domain geometry."""

    rng = random.Random(data.seed)
    point_count = _resolve_point_count(data, rng)
    centers = _sample_centers(canvas, data, rng, point_count)
    point_payloads = []

    for index, center in enumerate(centers, start=1):
        max_radius = _effective_max_radius(canvas, centers, index - 1, data)
        if data.radius_variation > 0.0:
            max_radius *= rng.uniform(1.0 - data.radius_variation, 1.0)

        if max_radius <= data.min_ring_radius + 1e-12:
            raise ConcentricError(
                "generated center has no usable radius above min_ring_radius; "
                "reduce min_ring_radius, center constraints, or overlap restrictions"
            )

        radii = _ring_radii(max_radius, data, rng)
        point_payloads.append(
            {
                "index": index,
                "center": [center[0], center[1]],
                "max_radius": max_radius,
                "radii": radii,
            }
        )

    return {
        "schema_version": 1,
        "algorithm": "concentric-points",
        "seed": data.seed,
        "canvas": canvas.to_payload(),
        "settings": {
            "point_count": point_count,
            "point_count_range": (
                list(data.point_count_range) if data.point_count_range is not None else None
            ),
            "ring_count": data.ring_count,
            "ring_spacing": data.ring_spacing,
            "ring_spacing_power": data.ring_spacing_power,
            "boundary_mode": data.boundary_mode,
            "radius_scale": data.radius_scale,
            "radius_variation": data.radius_variation,
            "min_ring_radius": data.min_ring_radius,
            "max_ring_radius": data.max_ring_radius,
            "overlap_mode": data.overlap_mode,
            "center_margin": data.center_margin,
            "min_center_spacing": data.min_center_spacing,
            "center_bias": data.center_bias,
            "center_bias_strength": data.center_bias_strength,
            "pen": data.pen,
            "color": data.color,
        },
        "points": point_payloads,
    }


class ConcentricDomainAlgorithm:
    """Domain-algorithm adapter for the established concentric generator."""

    name = "concentric"
    capabilities = AlgorithmCapabilities(
        supports_simple_polygon=True,
        supports_concave_polygon=False,
    )

    def generate(
        self,
        *,
        canvas: CanvasGeometry,
        domains: tuple[PolygonDomain, ...],
        design_pass: DesignPass,
        context: AlgorithmContext,
    ) -> DesignResult:
        return generate_concentric_design_result(
            canvas=canvas,
            domains=domains,
            design_pass=design_pass,
            context=context,
        )


def generate_concentric_design_result(
    *,
    canvas: CanvasGeometry,
    domains: tuple[PolygonDomain, ...],
    design_pass: DesignPass,
    context: AlgorithmContext,
) -> DesignResult:
    """Generate neutral closed vector paths for ordered polygon-domain targets."""

    if len(design_pass.logical_layers) != 1:
        raise ValueError("concentric design pass requires exactly one logical layer")

    request_parameters = dict(design_pass.parameters)
    request_parameters.pop("canvas", None)
    request_template = ConcentricPointsRequest(
        canvas={"shape": "rectangle", "width": canvas.width, "height": canvas.height},
        **request_parameters,
    )
    layer_id = design_pass.logical_layers[0].id
    paths: list[VectorPath] = []

    for domain in domains:
        request = request_template.model_copy(
            update={"seed": context.domain_seeds[domain.id]}
        )
        domain_canvas = CanvasGeometry(
            shape="polygon",
            width=canvas.width,
            height=canvas.height,
            polygon=domain.vertices,
            up_anchor="edge:0",
            domains=(domain,),
        )
        payload = _generate_concentric_points(request, domain_canvas)
        paths.extend(
            _payload_vector_paths(
                payload,
                layer_id=layer_id,
                domain_id=domain.id,
            )
        )

    return DesignResult(
        paths=tuple(paths),
        derived_domains=(),
        producing_pass_id=design_pass.id,
    )


def _payload_vector_paths(
    result: dict, *, layer_id: str, domain_id: str = "concentric-source"
) -> list[VectorPath]:
    paths: list[VectorPath] = []
    for point in result["points"]:
        center_x, center_y = point["center"]
        for radius in point["radii"]:
            points = tuple(
                (
                    center_x + radius * math.cos(math.tau * index / _CIRCLE_PATH_SEGMENTS),
                    center_y + radius * math.sin(math.tau * index / _CIRCLE_PATH_SEGMENTS),
                )
                for index in range(_CIRCLE_PATH_SEGMENTS)
            )
            paths.append(
                VectorPath(
                    points=points,
                    closed=True,
                    layer_id=layer_id,
                    domain_id=domain_id,
                )
            )
    return paths


def _resolve_point_count(data: ConcentricPointsRequest, rng: random.Random) -> int:
    if data.point_count_range is None:
        return data.point_count
    minimum, maximum = data.point_count_range
    return rng.randint(minimum, maximum)


def _sample_centers(
    canvas: CanvasGeometry,
    data: ConcentricPointsRequest,
    rng: random.Random,
    point_count: int,
) -> list[Point]:
    centers: list[Point] = []

    for _ in range(data.max_sampling_attempts):
        candidate = _sample_candidate(canvas, data, rng)
        if not canvas.contains(candidate):
            continue
        if canvas.distance_to_boundary(candidate) + 1e-12 < data.center_margin:
            continue
        if any(
            _distance(candidate, center) + 1e-12 < data.min_center_spacing
            for center in centers
        ):
            continue

        centers.append(candidate)
        if len(centers) == point_count:
            return centers

    raise ConcentricError(
        "unable to place requested centers within max_sampling_attempts; "
        "reduce point_count, center_margin, min_center_spacing, or center_bias_strength"
    )


def _sample_candidate(
    canvas: CanvasGeometry,
    data: ConcentricPointsRequest,
    rng: random.Random,
) -> Point:
    point = canvas.random_point(rng)
    if data.center_bias == "uniform" or data.center_bias_strength <= 1e-12:
        return point

    if data.center_bias == "centroid":
        target = canvas.centroid
    elif data.center_bias == "boundary":
        edge_index = rng.randrange(len(canvas.polygon))
        start = canvas.polygon[edge_index]
        end = canvas.polygon[(edge_index + 1) % len(canvas.polygon)]
        edge_fraction = rng.random()
        target = (
            start[0] + (end[0] - start[0]) * edge_fraction,
            start[1] + (end[1] - start[1]) * edge_fraction,
        )
    elif data.center_bias == "vertices":
        target = canvas.polygon[rng.randrange(len(canvas.polygon))]
    else:  # pragma: no cover - Literal/Pydantic validation prevents this
        raise ConcentricError(f"unsupported center_bias: {data.center_bias}")

    blend = data.center_bias_strength * rng.random()
    return (
        point[0] + (target[0] - point[0]) * blend,
        point[1] + (target[1] - point[1]) * blend,
    )


def _effective_max_radius(
    canvas: CanvasGeometry,
    centers: list[Point],
    center_index: int,
    data: ConcentricPointsRequest,
) -> float:
    center = centers[center_index]
    radius = _max_radius(canvas, center, data.boundary_mode) * data.radius_scale

    if data.overlap_mode == "avoid" and len(centers) > 1:
        nearest = min(
            _distance(center, other)
            for index, other in enumerate(centers)
            if index != center_index
        )
        radius = min(radius, nearest / 2.0)

    if data.max_ring_radius is not None:
        radius = min(radius, data.max_ring_radius)

    return radius


def _ring_radii(
    max_radius: float,
    data: ConcentricPointsRequest,
    rng: random.Random,
) -> list[float]:
    if data.ring_count == 1:
        return [max_radius]

    if data.ring_spacing == "linear":
        fractions = [ring / data.ring_count for ring in range(1, data.ring_count + 1)]
    elif data.ring_spacing == "progressive":
        fractions = [
            (ring / data.ring_count) ** data.ring_spacing_power
            for ring in range(1, data.ring_count + 1)
        ]
    elif data.ring_spacing == "random":
        fractions = sorted(rng.random() for _ in range(data.ring_count - 1)) + [1.0]
    else:  # pragma: no cover - Literal/Pydantic validation prevents this
        raise ConcentricError(f"unsupported ring_spacing: {data.ring_spacing}")

    if data.min_ring_radius <= 1e-12:
        return [max_radius * fraction for fraction in fractions]

    first_fraction = fractions[0]
    scale = 1.0 - first_fraction
    if scale <= 1e-12:
        return [max_radius] * data.ring_count

    return [
        data.min_ring_radius
        + (max_radius - data.min_ring_radius) * (fraction - first_fraction) / scale
        for fraction in fractions
    ]


def _max_radius(canvas: CanvasGeometry, center: Point, boundary_mode: str) -> float:
    if boundary_mode == "inscribed":
        return canvas.distance_to_boundary(center)
    if boundary_mode == "clip":
        return max(_distance(center, vertex) for vertex in canvas.polygon)
    raise ConcentricError(f"unsupported boundary_mode: {boundary_mode}")


def _distance(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
