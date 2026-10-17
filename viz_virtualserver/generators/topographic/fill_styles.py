import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from viz_virtualserver.fill_effects import validate_fill_parameters
from viz_virtualserver.fill_effects.mark_selection import MARK_DENSITY_EFFECTS

from .density_models import ElevationDensitySource, reject_null_density_source


class FillStyle(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    effect: str
    parameters: Annotated[Mapping[str, float], PlainSerializer(lambda value: dict(value))] = Field(
        default_factory=dict
    )
    layer_id: str
    field_direction: Literal["slope", "contour"] | None = None
    density_seed: int = Field(default=0, ge=-(2**63), le=2**63 - 1)
    density_source: ElevationDensitySource | None = None
    pen_width: float = Field(default=0, ge=0)
    boundary_margin: float = Field(default=0, ge=0)

    @field_validator("density_source", mode="before")
    @classmethod
    def nonnull_source(cls, value):
        return reject_null_density_source(value)

    @model_validator(mode="after")
    def validated(self):
        if not math.isfinite(self.pen_width / 2 + self.boundary_margin):
            raise ValueError("combined fill clearance must be finite")
        if self.effect not in MARK_DENSITY_EFFECTS and "density_source" in self.model_fields_set:
            raise ValueError("density_source is only supported for dot and field marks")
        if self.effect not in MARK_DENSITY_EFFECTS and "density_seed" in self.model_fields_set:
            raise ValueError("density_seed is only supported for dot and field marks")
        if self.effect == "field-marks":
            if self.field_direction is None:
                raise ValueError(
                    "field-marks requires an explicit slope or contour field_direction"
                )
        elif "field_direction" in self.model_fields_set:
            raise ValueError("field_direction is only supported for field-marks")
        if not self.layer_id.strip():
            raise ValueError("fill layer_id must be nonempty")
        controls = validate_fill_parameters(effect=self.effect, parameters=self.parameters)
        object.__setattr__(self, "parameters", MappingProxyType(controls))
        return self
