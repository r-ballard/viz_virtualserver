"""Strict component palettes reuse the same fill-style controls as union rules."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from .density_models import DensitySource, reject_null_density_source
from .fill_styles import FillStyle


class ComponentFillChoice(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    id: str
    weight: int = Field(ge=1, le=1_000_000)
    effect: str | None
    parameters: Annotated[Mapping[str, float], PlainSerializer(lambda value: dict(value))] = Field(
        default_factory=dict
    )
    layer_id: str | None = None
    field_direction: Literal["slope", "contour"] | None = None
    density_seed: int = Field(default=0, ge=-(2**63), le=2**63 - 1)
    density_source: DensitySource | None = None
    pen_width: float = Field(default=0, ge=0)
    boundary_margin: float = Field(default=0, ge=0)

    @field_validator("density_source", mode="before")
    @classmethod
    def nonnull_source(cls, value):
        return reject_null_density_source(value)

    @model_validator(mode="after")
    def validated(self):
        if not self.id.strip():
            raise ValueError("choice ID must be nonblank")
        if self.effect is None:
            if self.model_fields_set.intersection(
                {
                    "parameters",
                    "layer_id",
                    "field_direction",
                    "density_seed",
                    "density_source",
                    "pen_width",
                    "boundary_margin",
                }
            ):
                raise ValueError("blank choice must omit rendering controls")
            object.__setattr__(self, "parameters", MappingProxyType({}))
        else:
            payload = {
                "effect": self.effect,
                "parameters": self.parameters,
                "layer_id": self.layer_id,
                "pen_width": self.pen_width,
                "boundary_margin": self.boundary_margin,
            }
            if "field_direction" in self.model_fields_set:
                payload["field_direction"] = self.field_direction
            if "density_seed" in self.model_fields_set:
                payload["density_seed"] = self.density_seed
            if "density_source" in self.model_fields_set:
                payload["density_source"] = self.density_source
            style = FillStyle.model_validate(payload)
            object.__setattr__(self, "parameters", style.parameters)
        return self


class ComponentFillRule(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)
    bands: tuple[int, ...]
    component_seed: int = 0
    component_choices: tuple[ComponentFillChoice, ...] = Field(min_length=1, max_length=32)

    @field_validator("bands", "component_choices", mode="before")
    @classmethod
    def array(cls, value):
        if not isinstance(value, (list, tuple)):
            raise ValueError("component selections must be arrays")
        return tuple(value)

    @model_validator(mode="after")
    def validated(self):
        if not self.bands or len(set(self.bands)) != len(self.bands):
            raise ValueError("bands must be nonempty and distinct")
        if len({v.id for v in self.component_choices}) != len(self.component_choices):
            raise ValueError("component choice IDs must be unique")
        object.__setattr__(self, "bands", tuple(sorted(self.bands)))
        object.__setattr__(
            self, "component_choices", tuple(sorted(self.component_choices, key=lambda v: v.id))
        )
        return self


def iter_rule_styles(rule):
    if isinstance(rule, ComponentFillRule):
        yield from (choice for choice in rule.component_choices if choice.effect is not None)
    else:
        yield rule
