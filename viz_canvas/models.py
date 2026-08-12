from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CanvasShape = Literal["rectangle", "square", "triangle", "polygon"]
Point = tuple[float, float]
_UP_ANCHOR_RE = re.compile(r"^(vertex|edge):(\d+)$")


class CanvasSpec(BaseModel):
    """Serializable definition of an intrinsic vector drawing canvas.

    Coordinates use SVG design space: x increases rightward and y increases
    downward. ``up_anchor`` defines the semantic reading direction by naming a
    polygon vertex or edge. The actual normalized vector is computed from the
    polygon centroid when geometry is built.
    """

    shape: CanvasShape = "rectangle"
    width: float = Field(default=1000.0, gt=0.0)
    height: float = Field(default=1000.0, gt=0.0)
    points: list[Point] | None = None
    up_anchor: str | None = None

    @model_validator(mode="after")
    def validate_shape_contract(self) -> CanvasSpec:
        if self.shape == "square" and abs(self.width - self.height) > 1e-9:
            raise ValueError("square canvas requires width == height")

        if self.shape == "polygon":
            if self.points is None or len(self.points) < 3:
                raise ValueError("polygon canvas requires at least three points")
            for x, y in self.points:
                if not 0.0 <= float(x) <= self.width or not 0.0 <= float(y) <= self.height:
                    raise ValueError(
                        "polygon points must lie inside the declared width/height viewBox"
                    )
        elif self.points is not None:
            raise ValueError("points may only be supplied for shape='polygon'")

        if self.up_anchor is not None and _UP_ANCHOR_RE.fullmatch(self.up_anchor) is None:
            raise ValueError("up_anchor must have the form 'vertex:N' or 'edge:N'")

        return self
