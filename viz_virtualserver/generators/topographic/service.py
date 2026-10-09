from viz_virtualserver.canvas.design import (
    AlgorithmCapabilities,
    DesignResult,
    VectorPath,
)
from viz_virtualserver.scalar_fields.contours import extract_contours
from viz_virtualserver.scalar_fields.models import MAX_SEGMENTS, MAX_VERTICES
from viz_virtualserver.scalar_fields.sampling import plan_grid, sample_field, smooth_normalize
from viz_virtualserver.scalar_fields.terrain import TerrainField

from .geometry import prepare_contours
from .models import TopographicParameters


class TopographicDomainAlgorithm:
    name = 'topographic'
    capabilities = AlgorithmCapabilities()

    def generate(self, *, canvas, domains, design_pass, context):
        del canvas
        if context.composition_transforms:
            raise ValueError('topographic does not support composition-frame terrain')
        p = TopographicParameters.model_validate(dict(design_pass.parameters))
        layers = tuple(layer.id for layer in design_pass.logical_layers)
        if len(layers) != 2 or len(set(layers)) != 2 or any(not v.strip() for v in layers):
            raise ValueError('topographic requires exactly two distinct logical layers')
        paths = []
        vertex_count = 0
        levels = tuple(i/(p.contour_count+1) for i in range(1, p.contour_count+1))
        index_levels = {level for i, level in enumerate(levels, 1) if i % p.index_every == 0}
        for domain in domains:
            try:
                xs, ys = zip(*domain.vertices, strict=True)
                x0, y0 = min(xs), min(ys)
                width, height = max(xs)-x0, max(ys)-y0
                plan = plan_grid((0, 0, width, height), spacing=p.sample_spacing,
                                 smoothing=p.terrain_smoothing, contour_count=p.contour_count)
                terrain = TerrainField(context.domain_seeds[domain.id], scale=p.terrain_scale,
                                       octaves=p.octaves, roughness=p.roughness,
                                       warp_strength=p.warp_strength)
                sampled = smooth_normalize(sample_field(terrain, plan), plan)
                if sampled is None:
                    continue
                contours = extract_contours(sampled, levels, max_segments=MAX_SEGMENTS)
                # Clip in local coordinates too, preserving translation invariance.
                from viz_virtualserver.canvas.models import PolygonDomain
                local = PolygonDomain(domain.id, tuple((x-x0, y-y0) for x, y in domain.vertices))
                contours = prepare_contours(contours, local, tolerance=p.simplify_tolerance)
                for contour in contours:
                    vertex_count += len(contour.points)
                    if vertex_count > MAX_VERTICES:
                        raise ValueError(
                            'vertex cost limit exceeded; increase spacing or reduce levels')
                    points = tuple((x+x0, y+y0) for x, y in contour.points)
                    paths.append(VectorPath(points, contour.closed,
                                            layers[1 if contour.level in index_levels else 0],
                                            domain.id))
            except ValueError as error:
                raise ValueError(f'topographic domain {domain.id}: {error}') from error
        return DesignResult(tuple(paths), (), design_pass.id)
