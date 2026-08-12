from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from .geometry import CanvasError, build_canvas
from .models import CanvasSpec
from .svg import canvas_to_svg

router = APIRouter(tags=["canvas"])


@router.post("/Canvas")
async def canvas_geometry(data: CanvasSpec):
    """Resolve an intrinsic canvas into polygon, centroid, and orientation metadata."""

    try:
        return build_canvas(data).to_payload()
    except (CanvasError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/CanvasSvg", response_class=Response)
async def canvas_svg(
    data: CanvasSpec,
    boundary: bool = Query(default=False),
    boundary_stroke_width: float = Query(default=1.0, gt=0.0),
):
    """Return an SVG whose logical polygon, up direction, and clip are intrinsic metadata."""

    try:
        canvas = build_canvas(data)
        svg = canvas_to_svg(
            canvas,
            include_boundary=boundary,
            boundary_stroke_width=boundary_stroke_width,
        )
    except (CanvasError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(content=svg, media_type="image/svg+xml")
