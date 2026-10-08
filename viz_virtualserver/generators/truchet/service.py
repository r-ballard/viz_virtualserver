from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from shapely.geometry import Polygon

from viz_virtualserver.canvas.design import (
    AlgorithmCapabilities,
    DesignPass,
    DesignResult,
    VectorPath,
)
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.logical_layers import PathGeometry, SemanticPath
from viz_virtualserver.canvas.models import PolygonDomain

from .assembly import assemble_grid
from .classic_fills import render_classic_fill, validate_fill_precision
from .classic_regions import compose_regions
from .curve_layers import component_layer, curve_layer_ids
from .geometry import clip_paths, render_arrangement, sample_arrangement, trace_connections
from .models import TruchetParameters
from .panels import apply_panel_options

if TYPE_CHECKING:
    from viz_virtualserver.canvas.runner import AlgorithmContext


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
        parameters = TruchetParameters.model_validate(dict(design_pass.parameters))
        layer_ids = curve_layer_ids(design_pass.logical_layers,
                                    outline_layer_id=parameters.outline_layer_id,
                                    hatch_layer_id=parameters.hatch_layer_id)
        paths = []
        for domain in domains:
            xs, ys = zip(*domain.vertices, strict=True)
            arrangement = assemble_grid(
                (min(xs), min(ys), max(xs), max(ys)),
                tile_size=parameters.tile_size,
                seed=context.domain_seeds[domain.id],
            )
            fills = ()
            if parameters.hatch_layer_id is not None:
                validate_fill_precision(domain.vertices, parameters)
                sampled = sample_arrangement(arrangement, parameters)
                curves = trace_connections(sampled)
                _, painted = compose_regions(arrangement, sampled)
                ox, oy = arrangement.origin
                target = Polygon(tuple((x - ox, y - oy) for x, y in domain.vertices))
                selected = (target.intersection(painted) if parameters.hatch_region == "painted"
                            else target.difference(painted))
                fills = render_classic_fill(selected, origin=arrangement.origin,
                                            vertices=domain.vertices, parameters=parameters)
            else:
                curves = render_arrangement(arrangement, parameters)
            domain_paths = []
            if len(layer_ids) == 1:
                domain_paths.extend(VectorPath(p.points, p.closed, layer_ids[0], domain.id)
                                    for p in clip_paths(curves, domain))
            else:
                for component_id, curve in enumerate(curves):
                    layer_id = component_layer(component_id, seed=context.domain_seeds[domain.id],
                                               layer_ids=layer_ids)
                    for path in clip_paths((curve,), domain):
                        domain_paths.append(VectorPath(
                            path.points, path.closed, layer_id, domain.id))
                domain_paths.sort(key=lambda p: (p.points, p.closed))
            domain_paths.extend(VectorPath(p.points, p.closed, parameters.hatch_layer_id, domain.id)
                                for p in fills)
            panel_paths = apply_panel_options(tuple(domain_paths), domain,
                artwork_inset=parameters.artwork_inset,
                outline_layer_id=parameters.outline_layer_id,
                pass_id=design_pass.id,
                merge_ring_layer_id=(parameters.hatch_layer_id
                                     if parameters.hatch_effect == "circle-rings" else None))
            for index, path in enumerate(panel_paths):
                if path.layer_id == parameters.hatch_layer_id:
                    path = replace(path, semantic_path=SemanticPath(
                        path_id=f"{design_pass.id}:hatch:{domain.id}:{index}",
                        domain_id=domain.id, geometry=PathGeometry(path.points, path.closed),
                        feature_role="truchet-hatch", attributes={"curve_channel": path.layer_id},
                    ))
                paths.append(path)
        return DesignResult(tuple(paths), (), design_pass.id)
