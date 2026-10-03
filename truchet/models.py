from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from viz_canvas.models import Point


class TruchetParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    tile_size: float = Field(default=10.0, gt=0)
    arc_a: float = Field(default=math.sqrt(2) / 2 - 0.5, ge=0.5-math.sqrt(2)/2, le=0.45)
    arc_b: float = Field(default=math.sqrt(2) / 2 - 0.5, ge=0.5-math.sqrt(2)/2, le=0.45)
    curve_tolerance: float = Field(default=0.02, gt=0)


@dataclass(frozen=True, slots=True)
class TileState:
    quarter_turn: int
    complement: bool
    connections: tuple[tuple[int, int], ...]
    edge_regions: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class TilePlacement:
    column: int
    row: int
    state: TileState


@dataclass(frozen=True, slots=True)
class TileArrangement:
    origin: Point
    tile_size: float
    columns: int
    rows: int
    tiles: tuple[TilePlacement, ...]


@dataclass(frozen=True, slots=True)
class CurvePath:
    points: tuple[Point, ...]
    closed: bool
