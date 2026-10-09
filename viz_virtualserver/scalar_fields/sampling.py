import math

import numpy as np
from scipy.ndimage import gaussian_filter

from . import models
from .models import GridPlan, SampledField, ScalarField


def plan_grid(bounds: tuple[float, float, float, float], *, spacing: float,
              smoothing: float, contour_count: int) -> GridPlan:
    x0, y0, x1, y1 = bounds
    if (not all(math.isfinite(v) for v in (*bounds, spacing, smoothing))
            or spacing <= 0 or smoothing < 0 or x1 <= x0 or y1 <= y0
            or type(contour_count) is not int or contour_count < 1):
        raise ValueError('invalid bounds, spacing, smoothing, or contour count')
    ratios = ((x1-x0)/spacing, (y1-y0)/spacing, 4*smoothing/spacing)
    if any(not math.isfinite(v) or v > models.MAX_SAMPLES for v in ratios):
        raise ValueError('sample cost too high; increase spacing or reduce smoothing')
    ix, iy = max(1, math.ceil(ratios[0])), max(1, math.ceil(ratios[1]))
    dx, dy = (x1-x0)/ix, (y1-y0)/iy
    sigmas = (smoothing/dy, smoothing/dx)
    if any(not math.isfinite(s) or 4*s > models.MAX_SAMPLES for s in sigmas):
        raise ValueError('smoothing sample cost too high; increase spacing')
    hy, hx = (math.ceil(4*s)+1 for s in sigmas)
    nx, ny = ix+1+2*hx, iy+1+2*hy
    count = nx*ny
    if count > models.MAX_SAMPLES or count*contour_count > models.MAX_WORK:
        raise ValueError('sample cost limit exceeded; increase spacing or reduce contour count')
    origin = (x0-hx*dx, y0-hy*dy)
    if not all(math.isfinite(v) for v in origin):
        raise ValueError('sample bounds overflow; reduce coordinate extent')
    return GridPlan(origin, nx, ny, dx, dy, slice(hy, hy+iy+1),
                    slice(hx, hx+ix+1), sigmas)


def sample_field(field: ScalarField, plan: GridPlan) -> SampledField:
    values = np.empty((plan.ny, plan.nx), dtype=np.float64)
    for j in range(plan.ny):
        for i in range(plan.nx):
            values[j, i] = field.sample(plan.origin[0]+i*plan.dx, plan.origin[1]+j*plan.dy)
    return SampledField(plan.origin, plan.dx, plan.dy, values)


def smooth_normalize(field: SampledField, plan: GridPlan) -> SampledField | None:
    values = (gaussian_filter(field.values, plan.sigma_samples, truncate=4, mode='nearest')
              if any(plan.sigma_samples) else field.values)
    if not np.isfinite(values).all():
        raise ValueError('smoothed field must be finite')
    interior = values[plan.interior_rows, plan.interior_columns]
    lo, hi = float(interior.min()), float(interior.max())
    span = hi-lo
    if not math.isfinite(span):
        raise ValueError('field normalization range must be finite')
    if span <= 64*np.finfo(float).eps*max(1, abs(lo), abs(hi)):
        return None
    with np.errstate(over='ignore', invalid='ignore'):
        normalized = (values-lo)/span
    return SampledField(field.origin, field.dx, field.dy, normalized)
