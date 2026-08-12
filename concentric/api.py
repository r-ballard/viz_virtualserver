from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from viz_canvas.geometry import CanvasError

from .models import ConcentricPointsRequest
from .service import ConcentricError, generate_concentric_points
from .svg import result_to_svg

router = APIRouter(tags=["concentric-points"])


@router.post("/ConcentricPoints")
async def concentric_points(data: ConcentricPointsRequest):
    """Return deterministic centers and concentric radii in an intrinsic canvas."""

    try:
        return generate_concentric_points(data)
    except (CanvasError, ConcentricError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/ConcentricPointsSvg", response_class=Response)
async def concentric_points_svg(
    data: ConcentricPointsRequest,
    stroke_width: float = Query(default=1.0, gt=0.0),
):
    """Return pen-layered SVG rings clipped to the request's intrinsic canvas."""

    try:
        result = generate_concentric_points(data)
        svg = result_to_svg(result, data, stroke_width=stroke_width)
    except (CanvasError, ConcentricError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(content=svg, media_type="image/svg+xml")
