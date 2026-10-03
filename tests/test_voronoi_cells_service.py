from __future__ import annotations

import random

import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from viz_canvas.design import DesignPass, DesignState, LogicalLayer, execute_design_pass
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import PolygonDomain
from viz_canvas.runner import AlgorithmContext
from voronoi_cells.service import (
    VoronoiCellsDomainAlgorithm,
    VoronoiCellsParameters,
    inset,
    signed_area,
    subdivide,
)


def _run(*domains: PolygonDomain, seed: int = 17, parameters: dict | None = None):
    design_pass = DesignPass(
        id="cells", algorithm="voronoi-cells",
        target_domain_ids=tuple(domain.id for domain in domains),
        parameters=parameters or {},
        logical_layers=(LogicalLayer("cell-contours"),),
    )
    context = AlgorithmContext(
        job_seed=seed, pass_seed=seed,
        domain_seeds={domain.id: seed for domain in domains},
        surfaces=(), groups=(), relations=(), composition_transforms={},
    )
    canvas = CanvasGeometry(
        shape="polygon", width=100, height=100,
        polygon=domains[0].vertices, up_anchor="edge:0", domains=domains,
    )
    return VoronoiCellsDomainAlgorithm().generate(
        canvas=canvas, domains=domains, design_pass=design_pass, context=context,
    )


def test_subdivision_covers_root_and_inset_creates_gaps() -> None:
    root = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    leaves = subdivide(root, random.Random(17), VoronoiCellsParameters(depth=4))
    assert len(leaves) == 81
    assert sum(signed_area(cell) for cell in leaves) == pytest.approx(10000, abs=1e-6)
    contours = [inset(cell, 0.35) for cell in leaves]
    assert sum(signed_area(cell) for cell in contours if len(cell) >= 3) < 10000


def test_paths_are_deterministic_rounded_and_inside_domains() -> None:
    square = PolygonDomain("square", ((0, 0), (100, 0), (100, 100), (0, 100)))
    triangle = PolygonDomain("triangle", ((50, 0), (100, 100), (0, 100)))
    result = _run(square, triangle)
    assert result == _run(square, triangle)
    assert result != _run(square, triangle, seed=18)
    assert result.paths
    for domain in (square, triangle):
        boundary = ShapelyPolygon(domain.vertices).buffer(1e-7)
        paths = [path for path in result.paths if path.domain_id == domain.id]
        assert paths
        for path in paths:
            assert path.closed and path.coordinate_frame == "domain"
            assert path.layer_id == "cell-contours"
            assert len(path.points) > 3
            assert boundary.covers(ShapelyPolygon(path.points))


def test_clockwise_domain_and_resource_limits() -> None:
    clockwise = PolygonDomain("clockwise", ((0, 0), (0, 100), (100, 100), (100, 0)))
    assert _run(clockwise).paths
    with pytest.raises(ValueError, match="max_cells"):
        _run(clockwise, parameters={"branch": 5, "depth": 5})
    with pytest.raises(ValueError, match="max_path_length_ratio"):
        _run(clockwise, parameters={"max_path_length_ratio": 0.01})


def test_invalid_parameters_and_concave_domain_rejected() -> None:
    square = PolygonDomain("square", ((0, 0), (100, 0), (100, 100), (0, 100)))
    with pytest.raises(ValueError, match="inset_ratio"):
        _run(square, parameters={"inset_ratio": -1.0})
    with pytest.raises(ValueError, match="branch"):
        _run(square, parameters={"branch": "3"})
    concave = PolygonDomain("concave", ((0, 0), (100, 0), (50, 30), (100, 100), (0, 100)))
    design_pass = DesignPass(
        id="cells", algorithm="voronoi-cells", target_domain_ids=("concave",),
        logical_layers=(LogicalLayer("cell-contours"),),
    )
    canvas = CanvasGeometry(
        shape="polygon", width=100, height=100,
        polygon=concave.vertices, up_anchor="edge:0", domains=(concave,),
    )
    with pytest.raises(ValueError, match="concave"):
        execute_design_pass(
            canvas=canvas, state=DesignState(source_domains=(concave,)),
            design_pass=design_pass,
            algorithms={"voronoi-cells": VoronoiCellsDomainAlgorithm()},
        )
