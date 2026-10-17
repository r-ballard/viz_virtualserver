"""Strict source configuration separate from numeric catalogue controls."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _MappedDensitySource(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    minimum: float = Field(default=0, ge=0, le=1)
    maximum: float = Field(default=1, ge=0, le=1)
    invert: bool = False

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.minimum > self.maximum:
            raise ValueError("density minimum must not exceed maximum")
        return self


class ElevationDensitySource(_MappedDensitySource):
    type: Literal["elevation"]


class SlopeDensitySource(_MappedDensitySource):
    type: Literal["slope"]
    reference_slope: float = Field(gt=0)


DensitySource = Annotated[ElevationDensitySource | SlopeDensitySource, Field(discriminator="type")]


def reject_null_density_source(value):
    if value is None:
        raise ValueError("density_source must be omitted or an elevation/slope mapping, not null")
    return value
