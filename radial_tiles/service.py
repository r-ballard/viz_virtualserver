from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from viz_canvas.design import AlgorithmCapabilities, DesignPass, DesignResult, VectorPath
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import Point, PolygonDomain

if TYPE_CHECKING:
    from viz_canvas.runner import AlgorithmContext

_LAYER_IDS = ("structural-rings", "primary-tiles", "accent-tiles")
_RING_SEGMENTS = 72


class RadialTilesParameters(BaseModel):
    """Validated controls for sparse plotter-native radial tile fields."""

    model_config = ConfigDict(extra="forbid", strict=True)

    motif_count: int = Field(default=3, ge=1, le=20)
    ring_count: int = Field(default=4, ge=1, le=20)
    tile_density: int = Field(default=18, ge=3, le=120)
    center_drift: float = Field(default=0.06, ge=0.0, le=0.5)
    angular_jitter: float = Field(default=0.12, ge=0.0, le=0.45)
    radial_jitter: float = Field(default=0.08, ge=0.0, le=0.45)
    omission_rate: float = Field(default=0.12, ge=0.0, le=0.9)
    closed_tiles: bool = True


class RadialTilesDomainAlgorithm:
    """Generate independently seeded radial tile fields for polygon domains."""

    name = "radial-tiles"
    capabilities = AlgorithmCapabilities(
        supports_simple_polygon=True,
        supports_concave_polygon=True,
    )

    def generate(
        self,
        *,
        canvas: CanvasGeometry,
        domains: tuple[PolygonDomain, ...],
        design_pass: DesignPass,
        context: AlgorithmContext,
    ) -> DesignResult:
        del canvas
        layer_ids = tuple(layer.id for layer in design_pass.logical_layers)
        if len(layer_ids) != 3:
            raise ValueError("radial-tiles design pass requires exactly three logical layers")
        if layer_ids != _LAYER_IDS:
            raise ValueError(
                "radial-tiles logical layers must be structural-rings, "
                "primary-tiles, accent-tiles in that order"
            )

        parameters = RadialTilesParameters.model_validate(dict(design_pass.parameters))
        paths_by_layer: dict[str, list[VectorPath]] = {
            layer_id: [] for layer_id in _LAYER_IDS
        }
        for domain in domains:
            domain_paths = _domain_paths(
                domain=domain,
                seed=context.domain_seeds[domain.id],
                parameters=parameters,
            )
            for path in domain_paths:
                paths_by_layer[path.layer_id].append(path)

        paths = tuple(
            path for layer_id in _LAYER_IDS for path in paths_by_layer[layer_id]
        )

        return DesignResult(
            paths=paths,
            derived_domains=(),
            producing_pass_id=design_pass.id,
        )


def _domain_paths(
    *, domain: PolygonDomain, seed: int, parameters: RadialTilesParameters
) -> list[VectorPath]:
    rng = random.Random(seed)
    minimum_x = min(point[0] for point in domain.vertices)
    maximum_x = max(point[0] for point in domain.vertices)
    minimum_y = min(point[1] for point in domain.vertices)
    maximum_y = max(point[1] for point in domain.vertices)
    scale = min(maximum_x - minimum_x, maximum_y - minimum_y)
    center_x, center_y = domain.centroid
    paths: list[VectorPath] = []

    for motif_index in range(parameters.motif_count):
        orbit = scale * rng.uniform(0.0, 0.62)
        orbit_angle = rng.uniform(0.0, math.tau)
        motif_center = (
            center_x + orbit * math.cos(orbit_angle),
            center_y + orbit * math.sin(orbit_angle),
        )
        spacing = scale * rng.uniform(0.055, 0.095)
        hole_radius = scale * rng.uniform(0.05, 0.11)
        drift_center = motif_center

        for ring_index in range(parameters.ring_count):
            drift_angle = rng.uniform(0.0, math.tau)
            drift_distance = spacing * parameters.center_drift * rng.random()
            drift_center = (
                drift_center[0] + drift_distance * math.cos(drift_angle),
                drift_center[1] + drift_distance * math.sin(drift_angle),
            )
            middle_radius = hole_radius + ring_index * spacing
            ring_jitter = 1.0 + rng.uniform(
                -parameters.radial_jitter, parameters.radial_jitter
            )
            middle_radius *= ring_jitter
            paths.append(
                VectorPath(
                    points=_circle_points(drift_center, middle_radius),
                    closed=True,
                    layer_id="structural-rings",
                    domain_id=domain.id,
                )
            )
            paths.extend(
                _tile_paths(
                    domain_id=domain.id,
                    center=drift_center,
                    middle_radius=middle_radius,
                    spacing=spacing,
                    motif_index=motif_index,
                    ring_index=ring_index,
                    rng=rng,
                    parameters=parameters,
                )
            )

    return paths


def _tile_paths(
    *,
    domain_id: str,
    center: Point,
    middle_radius: float,
    spacing: float,
    motif_index: int,
    ring_index: int,
    rng: random.Random,
    parameters: RadialTilesParameters,
) -> list[VectorPath]:
    count = max(3, round(parameters.tile_density * (1.0 + 0.12 * ring_index)))
    step = math.tau / count
    band_width = spacing * rng.uniform(0.45, 0.72)
    paths: list[VectorPath] = []

    for tile_index in range(count):
        if rng.random() < parameters.omission_rate:
            continue
        start_jitter = rng.uniform(-1.0, 1.0) * parameters.angular_jitter * step
        end_jitter = rng.uniform(-1.0, 1.0) * parameters.angular_jitter * step
        gap = step * rng.uniform(0.12, 0.3)
        start = tile_index * step + gap / 2.0 + start_jitter
        end = (tile_index + 1) * step - gap / 2.0 + end_jitter
        if end <= start:
            continue
        radial_variation = band_width * parameters.radial_jitter
        inner_start = max(
            0.001,
            middle_radius
            - band_width / 2.0
            + rng.uniform(-radial_variation, radial_variation),
        )
        inner_end = max(
            0.001,
            middle_radius
            - band_width / 2.0
            + rng.uniform(-radial_variation, radial_variation),
        )
        outer_start = (
            middle_radius
            + band_width / 2.0
            + rng.uniform(-radial_variation, radial_variation)
        )
        outer_end = (
            middle_radius
            + band_width / 2.0
            + rng.uniform(-radial_variation, radial_variation)
        )
        points = (
            _polar(center, inner_start, start),
            _polar(center, outer_start, start),
            _polar(center, outer_end, end),
            _polar(center, inner_end, end),
        )
        accent = (tile_index + ring_index + motif_index) % 5 == 0
        paths.append(
            VectorPath(
                points=points,
                closed=parameters.closed_tiles,
                layer_id="accent-tiles" if accent else "primary-tiles",
                domain_id=domain_id,
            )
        )
    return paths


def _circle_points(center: Point, radius: float) -> tuple[Point, ...]:
    return tuple(
        _polar(center, radius, math.tau * index / _RING_SEGMENTS)
        for index in range(_RING_SEGMENTS)
    )


def _polar(center: Point, radius: float, angle: float) -> Point:
    return (
        center[0] + radius * math.cos(angle),
        center[1] + radius * math.sin(angle),
    )
