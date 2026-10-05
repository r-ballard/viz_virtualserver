from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator

from viz_virtualserver.canvas.models import Point

from .panel_models import PanelParameters


class MultiscaleParameters(PanelParameters):
    base_tile_size: float = Field(default=40.0, gt=0)
    max_depth: int = Field(default=3, ge=0, le=6)
    split_probability: float = Field(default=0.45, ge=0, le=1)
    curve_tolerance: float = Field(default=0.02, gt=0)
    hatch_layer_id: str | None = None
    hatch_spacing: float = Field(default=2.0, gt=0)
    hatch_angle: float = 45.0
    hatch_region: Literal["painted", "unpainted"] = "painted"

    @field_validator("hatch_layer_id")
    @classmethod
    def nonblank_hatch(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("hatch_layer_id must be nonblank")
        return value


@dataclass(frozen=True, slots=True, order=True)
class TileAddress:
    root_column: int
    root_row: int
    quadrants: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MultiscaleLeaf:
    address: TileAddress
    parent: TileAddress | None
    bounds: tuple[float, float, float, float]
    depth: int
    orientation: int


@dataclass(frozen=True, slots=True)
class MultiscaleArrangement:
    origin: Point
    base_tile_size: float
    leaves: tuple[MultiscaleLeaf, ...]
