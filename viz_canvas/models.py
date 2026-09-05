from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CanvasShape = Literal["rectangle", "square", "triangle", "polygon"]
Point = tuple[float, float]
Edge = tuple[Point, Point]
_UP_ANCHOR_RE = re.compile(r"^(vertex|edge):(\d+)$")


@dataclass(frozen=True, slots=True)
class DomainProvenance:
    source_domain_ids: tuple[str, ...]
    generating_pass_id: str
    operation: str

    def __post_init__(self) -> None:
        source_domain_ids = tuple(self.source_domain_ids)
        if not source_domain_ids:
            raise ValueError("domain provenance requires at least one source domain")
        if (
            any(not isinstance(source_domain_id, str) for source_domain_id in source_domain_ids)
            or not isinstance(self.generating_pass_id, str)
            or not isinstance(self.operation, str)
        ):
            raise ValueError("domain provenance identity parts must be strings")
        if any(not source_domain_id.strip() for source_domain_id in source_domain_ids):
            raise ValueError("domain provenance source domain ids must not be empty")
        if len(source_domain_ids) != len(set(source_domain_ids)):
            raise ValueError("domain provenance contains duplicate source domain ids")
        if not self.generating_pass_id.strip():
            raise ValueError("domain provenance generating pass id must not be empty")
        if not self.operation.strip():
            raise ValueError("domain provenance operation must not be empty")
        object.__setattr__(self, "source_domain_ids", source_domain_ids)


@dataclass(frozen=True, slots=True)
class PolygonDomain:
    id: str
    vertices: tuple[Point, ...]
    provenance: DomainProvenance | None = None

    def __post_init__(self) -> None:
        from .geometry import validate_simple_polygon

        if not self.id:
            raise ValueError("polygon domain id must not be empty")
        vertices = tuple(tuple(vertex) for vertex in self.vertices)
        validate_simple_polygon(vertices)
        object.__setattr__(self, "vertices", vertices)

    def edge(self, index: int) -> Edge:
        if index < 0 or index >= len(self.vertices):
            raise IndexError(f"edge index out of range: {index}")
        return self.vertices[index], self.vertices[(index + 1) % len(self.vertices)]

    @property
    def winding(self) -> str:
        from .geometry import polygon_winding

        return polygon_winding(self.vertices)

    @property
    def centroid(self) -> Point:
        from .geometry import polygon_centroid

        return polygon_centroid(self.vertices)

    @property
    def is_convex(self) -> bool:
        from .geometry import is_convex_polygon

        return is_convex_polygon(self.vertices)


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
