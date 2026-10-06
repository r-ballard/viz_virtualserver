"""Optional polygon borders and artwork clearance, independent of tile placement."""

from __future__ import annotations

import math
from dataclasses import replace

from shapely.geometry import Polygon

from viz_virtualserver.canvas.design import VectorPath
from viz_virtualserver.canvas.logical_layers import PathGeometry, SemanticPath
from viz_virtualserver.canvas.models import PolygonDomain

from .geometry import clip_paths_to_geometry
from .models import CurvePath


def apply_panel_options(
    paths: tuple[VectorPath, ...], domain: PolygonDomain, *,
    artwork_inset: float, outline_layer_id: str | None, pass_id: str,
    merge_ring_layer_id: str | None = None,
) -> tuple[VectorPath, ...]:
    if artwork_inset > 0:
        if any(math.ulp(c) * 4 > artwork_inset for p in domain.vertices for c in p):
            raise ValueError(f"domain {domain.id}: artwork inset cannot be represented reliably")
        # Work near zero for buffer/intersection, including translated polygons.
        ox, oy = domain.vertices[0]
        target = Polygon(tuple((x - ox, y - oy) for x, y in domain.vertices)).buffer(
            -artwork_inset, join_style="mitre",
        )
        if target.is_empty:
            raise ValueError(f"domain {domain.id}: artwork inset removes the entire drawing area")
        clipped = []
        for path in paths:
            local = CurvePath(tuple((x - ox, y - oy) for x, y in path.points), path.closed)
            for fragment in clip_paths_to_geometry(
                (local,), target, merge_closed_fragments=path.layer_id == merge_ring_layer_id,
            ):
                clipped.append(replace(path,
                    points=tuple((x + ox, y + oy) for x, y in fragment.points),
                    closed=fragment.closed))
        paths = tuple(sorted(clipped, key=lambda p: (p.points, p.closed, p.layer_id)))
    if outline_layer_id is not None:
        semantic = SemanticPath(
            path_id=f"{pass_id}:outline:{domain.id}", domain_id=domain.id,
            geometry=PathGeometry(domain.vertices, True), feature_role="polygon-outline",
            attributes={"curve_channel": outline_layer_id},
        )
        paths = (*paths, VectorPath(domain.vertices, True, outline_layer_id, domain.id,
                                   semantic_path=semantic))
    return paths
