from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from viz_virtualserver.fill_effects import validate_fill_parameters


class BandFillRule(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    bands: tuple[int, ...]
    effect: str
    parameters: Annotated[Mapping[str, float], PlainSerializer(lambda value: dict(value))] = Field(
        default_factory=dict
    )
    layer_id: str
    field_direction: Literal["slope", "contour"] | None = None

    @field_validator("bands", mode="before")
    @classmethod
    def band_array(cls, value):
        if not isinstance(value, (list, tuple)):
            raise ValueError("bands must be an array")
        return tuple(value)

    @model_validator(mode="after")
    def validated(self):
        if self.effect == "field-marks":
            if self.field_direction is None:
                raise ValueError("field-marks requires an explicit slope or contour field_direction")
        elif "field_direction" in self.model_fields_set:
            raise ValueError("field_direction is only supported for field-marks")
        if not self.bands or len(set(self.bands)) != len(self.bands):
            raise ValueError("bands must be nonempty and distinct")
        if not self.layer_id.strip():
            raise ValueError("fill layer_id must be nonempty")
        controls = validate_fill_parameters(effect=self.effect, parameters=self.parameters)
        object.__setattr__(self, "bands", tuple(sorted(self.bands)))
        object.__setattr__(self, "parameters", MappingProxyType(controls))
        return self


class TopographicParameters(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)

    terrain_scale: float = Field(default=30.0, gt=0)
    octaves: int = Field(default=5, ge=1, le=8)
    roughness: float = Field(default=0.45, ge=0, le=1)
    warp_strength: float = Field(default=0.35, ge=0, le=1)
    terrain_smoothing: float = Field(default=1.0, ge=0)
    sample_spacing: float = Field(default=0.5, gt=0)
    contour_count: int = Field(default=30, ge=1, le=120)
    index_every: int = Field(default=5, ge=1, le=120)
    simplify_tolerance: float = Field(default=0.02, ge=0)

    band_fills: tuple[BandFillRule, ...] = ()

    @field_validator("band_fills", mode="before")
    @classmethod
    def fill_array(cls, value):
        if not isinstance(value, (list, tuple)):
            raise ValueError("band_fills must be an array")
        return tuple(value)

    @model_validator(mode="after")
    def validated_bands(self):
        used = set()
        for rule in self.band_fills:
            if any(b < 0 or b > self.contour_count for b in rule.bands):
                raise ValueError("band index outside contour_count range")
            if used.intersection(rule.bands):
                raise ValueError("band fill rules overlap")
            used.update(rule.bands)
        object.__setattr__(
            self, "band_fills", tuple(sorted(self.band_fills, key=lambda r: r.bands))
        )
        return self
