from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from viz_virtualserver.canvas.models import Point

from .hatch_parameters import HatchParameters


class MultiscaleParameters(HatchParameters):
    base_tile_size: float = Field(default=40.0, gt=0)
    max_depth: int = Field(default=3, ge=0, le=6)
    split_probability: float = Field(default=0.45, ge=0, le=1)
    curve_tolerance: float = Field(default=0.02, gt=0)


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
