from __future__ import annotations

from typing import TYPE_CHECKING

from viz_virtualserver.canvas.design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    VectorPath,
)
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain

from .multiscale_composition import render_multiscale
from .multiscale_models import MultiscaleParameters
from .multiscale_subdivision import assemble_multiscale

if TYPE_CHECKING:
    from viz_virtualserver.canvas.runner import AlgorithmContext


class TruchetMultiscaleDomainAlgorithm:
    name = "truchet-multiscale"
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
            raise ValueError(
                "truchet-multiscale requires exactly one logical layer: truchet-curves"
            )
        parameters = MultiscaleParameters.model_validate(dict(design_pass.parameters))
        paths = []
        for domain in domains:
            xs, ys = zip(*domain.vertices, strict=True)
            arrangement = assemble_multiscale(
                (min(xs), min(ys), max(xs), max(ys)),
                parameters=parameters,
                seed=context.domain_seeds[domain.id],
            )
            for path in render_multiscale(arrangement, domain,
                                         curve_tolerance=parameters.curve_tolerance):
                paths.append(VectorPath(path.points, path.closed, "truchet-curves", domain.id))
        return DesignResult(tuple(paths), (), design_pass.id)
