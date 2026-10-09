from pydantic import BaseModel, ConfigDict, Field


class TopographicParameters(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', allow_inf_nan=False)

    terrain_scale: float = Field(default=30.0, gt=0)
    octaves: int = Field(default=5, ge=1, le=8)
    roughness: float = Field(default=.45, ge=0, le=1)
    warp_strength: float = Field(default=.35, ge=0, le=1)
    terrain_smoothing: float = Field(default=1.0, ge=0)
    sample_spacing: float = Field(default=.5, gt=0)
    contour_count: int = Field(default=30, ge=1, le=120)
    index_every: int = Field(default=5, ge=1, le=120)
    simplify_tolerance: float = Field(default=.02, ge=0)
