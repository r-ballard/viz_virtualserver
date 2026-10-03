from __future__ import annotations

import math
import random

from .grammar import compatible, compile_states
from .models import TileArrangement, TilePlacement


def assemble_grid(
    bounds: tuple[float, float, float, float], *, tile_size: float, seed: int
) -> TileArrangement:
    x0, y0, x1, y1 = bounds
    if not all(math.isfinite(v) for v in (*bounds, tile_size)) or tile_size <= 0:
        raise ValueError("grid bounds and tile size must be finite; size must be positive")
    width, height = (x1 - x0) / tile_size, (y1 - y0) / tile_size
    if width <= 0 or height <= 0:
        raise ValueError("grid bounds must have positive dimensions")
    if not math.isfinite(width + height) or width > 100000 or height > 100000:
        raise ValueError("Truchet grid exceeds 100,000 tiles")
    columns, rows = math.ceil(width), math.ceil(height)
    if columns * rows > 100000:
        raise ValueError("Truchet grid exceeds 100,000 tiles")
    rng = random.Random(seed)
    states = compile_states()
    tiles: list[TilePlacement] = []
    for row in range(rows):
        for column in range(columns):
            candidates = tuple(
                state for state in states
                if (not column or compatible(tiles[-1].state, 1, state, 3))
                and (not row or compatible(tiles[(row - 1) * columns + column].state, 2, state, 0))
            )
            if not candidates:
                raise ValueError("compiled Truchet grammar has no compatible tile state")
            tiles.append(TilePlacement(column, row, rng.choice(candidates)))
    return TileArrangement((x0, y0), tile_size, columns, rows, tuple(tiles))
