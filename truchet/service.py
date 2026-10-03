from __future__ import annotations

from typing import TYPE_CHECKING

from viz_canvas.design import AlgorithmCapabilities, DesignPass, DesignResult, VectorPath
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import PolygonDomain

from .assembly import assemble_grid
from .geometry import clip_paths, render_arrangement
from .models import TruchetParameters

if TYPE_CHECKING:
    from viz_canvas.runner import AlgorithmContext


class TruchetDomainAlgorithm:
    name = "truchet"
    capabilities = AlgorithmCapabilities(
        supports_simple_polygon=True, supports_concave_polygon=True
    )

    def generate(
        self,
        *,
        canvas: CanvasGeometry,
        domains: tuple[PolygonDomain, ...],
        design_pass: DesignPass,
        context: AlgorithmContext,
    ) -> DesignResult:
        del canvas
        if tuple(layer.id for layer in design_pass.logical_layers) != ("truchet-curves",):
            raise ValueError("truchet requires exactly one logical layer: truchet-curves")
        parameters = TruchetParameters.model_validate(dict(design_pass.parameters))
        paths = []
        for domain in domains:
            xs, ys = zip(*domain.vertices, strict=True)
            arrangement = assemble_grid(
                (min(xs), min(ys), max(xs), max(ys)),
                tile_size=parameters.tile_size,
                seed=context.domain_seeds[domain.id],
            )
            for path in clip_paths(render_arrangement(arrangement, parameters), domain):
                paths.append(VectorPath(path.points, path.closed, "truchet-curves", domain.id))
        return DesignResult(tuple(paths), (), design_pass.id)
