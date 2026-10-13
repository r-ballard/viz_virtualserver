import math

from viz_virtualserver.canvas.design import (
    AlgorithmCapabilities,
    DesignResult,
    VectorPath,
)
from viz_virtualserver.canvas.json_values import thaw_json_value
from viz_virtualserver.canvas.logical_layers import PathGeometry, SemanticPath
from viz_virtualserver.scalar_fields.contours import extract_contours
from viz_virtualserver.scalar_fields.models import MAX_SEGMENTS, MAX_VERTICES
from viz_virtualserver.scalar_fields.regions import extract_band_regions
from viz_virtualserver.scalar_fields.sampling import plan_grid, sample_field, smooth_normalize
from viz_virtualserver.scalar_fields.terrain import TerrainField

from .component_models import iter_rule_styles
from .fills import render_band_fills
from .geometry import prepare_contours
from .models import TopographicParameters


class TopographicDomainAlgorithm:
    name = "topographic"
    capabilities = AlgorithmCapabilities()

    def generate(self, *, canvas, domains, design_pass, context):
        del canvas
        if context.composition_transforms:
            raise ValueError("topographic does not support composition-frame terrain")
        p = TopographicParameters.model_validate(thaw_json_value(design_pass.parameters))
        layers = tuple(layer.id for layer in design_pass.logical_layers)
        fill_ids = {style.layer_id for r in p.band_fills for style in iter_rule_styles(r)}
        if (
            len(layers) < 2
            or len(set(layers)) != len(layers)
            or any(not v.strip() for v in layers)
            or fill_ids.intersection(layers[:2])
            or set(layers[2:]) != fill_ids
        ):
            raise ValueError(
                "topographic requires two contour layers and exactly referenced fill layers"
            )
        paths = []
        vertex_count = 0
        levels = tuple(i / (p.contour_count + 1) for i in range(1, p.contour_count + 1))
        index_levels = {level for i, level in enumerate(levels, 1) if i % p.index_every == 0}
        for domain in domains:
            try:
                if p.band_fills:
                    resolution = 8 * max(math.ulp(c) for point in domain.vertices for c in point)
                    controls = [p.sample_spacing]
                    for rule in (s for r in p.band_fills for s in iter_rule_styles(r)):
                        controls.append(rule.parameters["spacing"])
                        for key in ("mark_length", "radius", "curve_tolerance"):
                            if key in rule.parameters:
                                controls.append(rule.parameters[key])
                    if resolution > min(controls):
                        raise ValueError(
                            "fill spacing or marks cannot be represented at domain coordinates"
                        )
                xs, ys = zip(*domain.vertices, strict=True)
                x0, y0 = min(xs), min(ys)
                width, height = max(xs) - x0, max(ys) - y0
                plan = plan_grid(
                    (0, 0, width, height),
                    spacing=p.sample_spacing,
                    smoothing=p.terrain_smoothing,
                    contour_count=p.contour_count,
                )
                terrain = TerrainField(
                    context.domain_seeds[domain.id],
                    scale=p.terrain_scale,
                    octaves=p.octaves,
                    roughness=p.roughness,
                    warp_strength=p.warp_strength,
                )
                sampled = smooth_normalize(sample_field(terrain, plan), plan)
                if sampled is None:
                    continue
                contours = extract_contours(sampled, levels, max_segments=MAX_SEGMENTS)
                # Clip in local coordinates too, preserving translation invariance.
                from viz_virtualserver.canvas.models import PolygonDomain

                local = PolygonDomain(
                    domain.id, tuple((x - x0, y - y0) for x, y in domain.vertices)
                )
                regions = ()
                if p.band_fills:
                    regions = extract_band_regions(sampled, levels, local)
                contours = prepare_contours(contours, local, tolerance=p.simplify_tolerance)
                contour_vertices = sum(len(c.points) for c in contours)
                if vertex_count + contour_vertices > MAX_VERTICES:
                    raise ValueError(
                        "vertex cost limit exceeded; increase spacing or reduce levels"
                    )
                fills = ()
                if p.band_fills:
                    fills = render_band_fills(
                        regions,
                        p.band_fills,
                        sampled_field=sampled,
                        max_vertices=MAX_VERTICES - vertex_count - contour_vertices,
                    )
                for contour in contours:
                    vertex_count += len(contour.points)
                    if vertex_count > MAX_VERTICES:
                        raise ValueError(
                            "vertex cost limit exceeded; increase spacing or reduce levels"
                        )
                    points = tuple((x + x0, y + y0) for x, y in contour.points)
                    paths.append(
                        VectorPath(
                            points,
                            contour.closed,
                            layers[1 if contour.level in index_levels else 0],
                            domain.id,
                        )
                    )
                for index, (layer_id, stroke) in enumerate(fills):
                    vertex_count += len(stroke.points)
                    if vertex_count > MAX_VERTICES:
                        raise ValueError(
                            "vertex cost limit exceeded; increase fill spacing or reduce levels"
                        )
                    points = tuple((x + x0, y + y0) for x, y in stroke.points)
                    if len(set(points)) < (3 if stroke.closed else 2):
                        raise ValueError("fill stroke cannot be represented at domain coordinates")
                    semantic = SemanticPath(
                        f"{design_pass.id}:{domain.id}:fill:{index}",
                        domain.id,
                        PathGeometry(points, stroke.closed),
                        "topographic-fill",
                        {},
                    )
                    paths.append(
                        VectorPath(
                            points, stroke.closed, layer_id, domain.id, semantic_path=semantic
                        )
                    )
            except ValueError as error:
                raise ValueError(f"topographic domain {domain.id}: {error}") from error
        return DesignResult(tuple(paths), (), design_pass.id)
