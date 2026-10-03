from __future__ import annotations

import math
import random

from .grammar import compatible, compile_states
from .models import TileArrangement, TilePlacement


def _tile_count(minimum: float, maximum: float, tile_size: float) -> int:
    quotient = (maximum - minimum) / tile_size
    if quotient <= 0:
        raise ValueError("grid bounds must have positive dimensions")
    if not math.isfinite(quotient) or quotient > 100001:
        raise ValueError("Truchet grid exceeds 100,000 tiles")
    # Subtraction at translated decimal bounds can put an exact tile boundary
    # a few representable floats above an integer. Snap only within an error
    # budget derived from the coordinates, preserving meaningful partial tiles.
    nearest = round(quotient)
    error = 4 * ((math.ulp(minimum) + math.ulp(maximum)) / tile_size + math.ulp(quotient))
    if nearest >= 1 and abs(quotient - nearest) <= error:
        return nearest
    return math.ceil(quotient)


def assemble_grid(
    bounds: tuple[float, float, float, float], *, tile_size: float, seed: int
) -> TileArrangement:
    x0, y0, x1, y1 = bounds
    if not all(math.isfinite(v) for v in (*bounds, tile_size)) or tile_size <= 0:
        raise ValueError("grid bounds and tile size must be finite; size must be positive")
    columns, rows = _tile_count(x0, x1, tile_size), _tile_count(y0, y1, tile_size)
    if columns * rows > 100000:
        raise ValueError("Truchet grid exceeds 100,000 tiles")
    rng = random.Random(seed)
    states = compile_states()
    tiles: list[TilePlacement] = []
    for row in range(rows):
        for column in range(columns):
            candidates = tuple(
                state
                for state in states
                if (not column or compatible(tiles[-1].state, 1, state, 3))
                and (not row or compatible(tiles[(row - 1) * columns + column].state, 2, state, 0))
            )
            if not candidates:
                raise ValueError("compiled Truchet grammar has no compatible tile state")
            tiles.append(TilePlacement(column, row, rng.choice(candidates)))
    return TileArrangement((x0, y0), tile_size, columns, rows, tuple(tiles))
