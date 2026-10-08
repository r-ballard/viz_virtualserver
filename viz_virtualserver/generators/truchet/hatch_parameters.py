"""Shared opt-in fill controls for classic and multiscale Truchet."""

from typing import Literal

from pydantic import Field, field_validator

from .panel_models import PanelParameters


class HatchParameters(PanelParameters):
    hatch_layer_id: str | None = None
    hatch_spacing: float = Field(default=2.0, gt=0)
    hatch_angle: float = 45.0
    hatch_effect: Literal[
        "parallel-hatch", "crosshatch", "circle-rings", "stroke-dots"
    ] = "parallel-hatch"
    hatch_radius: float = Field(default=0.5, gt=0)
    hatch_curve_tolerance: float = Field(default=0.02, gt=0)
    hatch_mark_length: float = Field(default=0.5, gt=0)
    hatch_region: Literal["painted", "unpainted"] = "painted"

    @field_validator("hatch_layer_id")
    @classmethod
    def nonblank_hatch(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("hatch_layer_id must be nonblank")
        return value
