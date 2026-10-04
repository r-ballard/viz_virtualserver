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

from .curve_layers import component_layer, curve_layer_ids
from .multiscale_composition import render_multiscale, render_multiscale_components
from .multiscale_models import MultiscaleParameters
from .multiscale_subdivision import assemble_multiscale
from .panels import apply_panel_options

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
        parameters = MultiscaleParameters.model_validate(dict(design_pass.parameters))
        layer_ids = curve_layer_ids(design_pass.logical_layers,
                                    outline_layer_id=parameters.outline_layer_id)
        paths = []
        for domain in domains:
            xs, ys = zip(*domain.vertices, strict=True)
            arrangement = assemble_multiscale(
                (min(xs), min(ys), max(xs), max(ys)),
                parameters=parameters,
                seed=context.domain_seeds[domain.id],
            )
            domain_paths = []
            if len(layer_ids) == 1:
                for path in render_multiscale(arrangement, domain,
                                             curve_tolerance=parameters.curve_tolerance):
                    domain_paths.append(VectorPath(
                        path.points, path.closed, layer_ids[0], domain.id))
            else:
                for component_id, path in render_multiscale_components(
                    arrangement, domain, curve_tolerance=parameters.curve_tolerance
                ):
                    layer_id = component_layer(component_id, seed=context.domain_seeds[domain.id],
                                               layer_ids=layer_ids)
                    domain_paths.append(VectorPath(path.points, path.closed, layer_id, domain.id))
            paths.extend(apply_panel_options(tuple(domain_paths), domain,
                artwork_inset=parameters.artwork_inset,
                outline_layer_id=parameters.outline_layer_id,
                pass_id=design_pass.id))
        return DesignResult(tuple(paths), (), design_pass.id)
