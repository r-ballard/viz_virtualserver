"""Validated optional scalar context for reusable mark renderers."""

from typing import Protocol

from .vector_fields import _finite_number


class DensityField(Protocol):
    def sample(self, x: float, y: float) -> float: ...


def validate_density_field(field):
    if field is not None and not callable(getattr(field, "sample", None)):
        raise ValueError("density field must implement sample(x, y)")


def sample_density(field, x, y):
    validate_density_field(field)
    if field is None:
        raise ValueError("density field is required for sampling")
    try:
        value = _finite_number(field.sample(x, y), "density field sample")
        if not 0 <= value <= 1:
            raise ValueError("density field sample must lie between 0 and 1")
        return value
    except Exception as error:
        raise ValueError(f"density field evaluation failed: {error}") from error


def effective_density(global_density, density_field, x, y):
    value = _finite_number(global_density, "global density")
    if not 0 <= value <= 1:
        raise ValueError("global density must lie between 0 and 1")
    validate_density_field(density_field)
    if value == 0 or density_field is None:
        return value
    return value * sample_density(density_field, x, y)
