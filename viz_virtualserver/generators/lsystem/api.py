from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from .geometry import GeometryError
from .grammar import ExpansionLimitError
from .models import LSystemRequest
from .service import generate_lsystem
from .svg import result_to_svg

router = APIRouter(tags=["l-system"])


@router.post("/LSystem")
async def lsystem(data: LSystemRequest):
    try:
        return generate_lsystem(data)
    except (ExpansionLimitError, GeometryError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/LSystemSvg", response_class=Response)
async def lsystem_svg(
    data: LSystemRequest,
    padding: float = Query(default=10.0, ge=0.0),
    stroke_width: float = Query(default=1.0, gt=0.0),
):
    try:
        result = generate_lsystem(data)
        svg = result_to_svg(result, padding=padding, stroke_width=stroke_width)
    except (ExpansionLimitError, GeometryError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(content=svg, media_type="image/svg+xml")
