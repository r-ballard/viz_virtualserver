from dataclasses import dataclass
from typing import Protocol

import numpy as np

from viz_virtualserver.canvas.models import Point

MAX_SAMPLES = 250_000
MAX_WORK = 12_000_000
MAX_SEGMENTS = 1_000_000
MAX_VERTICES = 1_000_000


class ScalarField(Protocol):
    def sample(self, x: float, y: float) -> float: ...


@dataclass(frozen=True, slots=True)
class GridPlan:
    origin: Point
    nx: int
    ny: int
    dx: float
    dy: float
    interior_rows: slice
    interior_columns: slice
    sigma_samples: tuple[float, float]


@dataclass(frozen=True, slots=True, eq=False)
class SampledField:
    origin: Point
    dx: float
    dy: float
    values: np.ndarray

    def __post_init__(self):
        import math

        if (not all(math.isfinite(v) for v in (*self.origin, self.dx, self.dy))
                or self.dx <= 0 or self.dy <= 0):
            raise ValueError('field coordinates and steps must be finite and positive')
        values = np.asarray(self.values, dtype=np.float64)
        if values.ndim != 2 or min(values.shape) < 2 or not np.isfinite(values).all():
            raise ValueError('field requires a finite two-dimensional grid of at least 2x2')
        # Back with immutable bytes: callers cannot re-enable writes on an owning array.
        immutable = np.frombuffer(values.tobytes(), dtype=np.float64).reshape(values.shape)
        object.__setattr__(self, 'values', immutable)


@dataclass(frozen=True, slots=True)
class Contour:
    level: float
    points: tuple[Point, ...]
    closed: bool
