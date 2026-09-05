from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from viz_canvas.models import CanvasSpec

BoundaryMode = Literal["inscribed", "clip"]
RingSpacingMode = Literal["linear", "random", "progressive"]
OverlapMode = Literal["allow", "avoid"]
CenterBias = Literal["uniform", "centroid", "boundary", "vertices"]


class ConcentricPointsRequest(BaseModel):
    """Configuration for deterministic concentric-circle vector generation."""

    model_config = ConfigDict(extra="forbid")

    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    seed: int = 0
    point_count: int = Field(default=5, ge=1, le=256)
    point_count_range: tuple[int, int] | None = None
    ring_count: int = Field(default=8, ge=1, le=256)
    ring_spacing: RingSpacingMode = "linear"
    ring_spacing_power: float = Field(default=2.0, gt=0.0)
    boundary_mode: BoundaryMode = "clip"
    radius_scale: float = Field(default=1.0, gt=0.0, le=1.0)
    radius_variation: float = Field(default=0.0, ge=0.0, lt=1.0)
    min_ring_radius: float = Field(default=0.0, ge=0.0)
    max_ring_radius: float | None = Field(default=None, gt=0.0)
    overlap_mode: OverlapMode = "allow"
    center_margin: float = Field(default=0.0, ge=0.0)
    min_center_spacing: float = Field(default=0.0, ge=0.0)
    center_bias: CenterBias = "uniform"
    center_bias_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    max_sampling_attempts: int = Field(default=100_000, ge=1, le=10_000_000)
    pen: int = Field(default=1, ge=1, le=8)
    color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_refinement_contract(self) -> ConcentricPointsRequest:
        if self.point_count_range is not None:
            minimum, maximum = self.point_count_range
            if not 1 <= minimum <= maximum <= 256:
                raise ValueError(
                    "point_count_range must satisfy 1 <= minimum <= maximum <= 256"
                )

        if self.max_ring_radius is not None and self.max_ring_radius <= self.min_ring_radius:
            raise ValueError("max_ring_radius must be greater than min_ring_radius")

        return self
