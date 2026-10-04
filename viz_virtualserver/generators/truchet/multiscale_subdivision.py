from __future__ import annotations

import hashlib
import math

from .assembly import _tile_count
from .multiscale_models import (
    MultiscaleArrangement,
    MultiscaleLeaf,
    MultiscaleParameters,
    TileAddress,
)

MAX_LEAVES = 10_000


def _choice(seed: int, address: TileAddress, stream: str) -> float:
    # ASCII decimal fields separated by ':'; quadrant digits have no ambiguity.
    payload = (
        f"{seed}:{address.root_column}:{address.root_row}:"
        f"{''.join(map(str, address.quadrants))}:{stream}"
    ).encode("ascii")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return (value >> 11) / (1 << 53)


def assemble_multiscale(
    bounds: tuple[float, float, float, float], *, parameters: MultiscaleParameters, seed: int
) -> MultiscaleArrangement:
    x0, y0, x1, y1 = bounds
    size = parameters.base_tile_size
    if not all(math.isfinite(v) for v in bounds):
        raise ValueError("multi-scale grid bounds must be finite")
    try:
        columns, rows = _tile_count(x0, x1, size), _tile_count(y0, y1, size)
    except ValueError as exc:
        raise ValueError("multi-scale grid bounds invalid or exceed 10,000 leaves") from exc
    count = (columns + 2) * (rows + 2)
    if count > MAX_LEAVES:
        raise ValueError("multi-scale arrangement exceeds 10,000 leaves including halo")
    leaves = []

    def visit(address: TileAddress, box: tuple[float, float, float, float]) -> None:
        nonlocal count
        depth = len(address.quadrants)
        if depth < parameters.max_depth and _choice(seed, address, "split") < (
            parameters.split_probability
        ):
            count += 3
            if count > MAX_LEAVES:
                raise ValueError("multi-scale arrangement exceeds 10,000 leaves including halo")
            left, bottom, right, top = box
            mx, my = (left + right) / 2, (bottom + top) / 2
            children = (
                (left, bottom, mx, my), (mx, bottom, right, my),
                (left, my, mx, top), (mx, my, right, top),
            )
            for q, child in enumerate(children):
                visit(TileAddress(address.root_column, address.root_row,
                                  address.quadrants + (q,)), child)
        else:
            parent = (TileAddress(address.root_column, address.root_row, address.quadrants[:-1])
                      if depth else None)
            leaves.append(MultiscaleLeaf(address, parent, box, depth,
                                        int(_choice(seed, address, "orientation") >= 0.5)))

    for column in range(-1, columns + 1):
        for row in range(-1, rows + 1):
            visit(TileAddress(column, row), (column, row, column + 1, row + 1))
    return MultiscaleArrangement((x0, y0), size, tuple(leaves))
