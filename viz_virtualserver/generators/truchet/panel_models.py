from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PanelParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    artwork_inset: float = Field(default=0.0, ge=0)
    outline_layer_id: str | None = None

    @field_validator("outline_layer_id")
    @classmethod
    def nonblank_outline(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("outline_layer_id must be nonblank")
        return value
