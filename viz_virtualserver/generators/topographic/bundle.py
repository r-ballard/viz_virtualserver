"""Project declared channels through the existing neutral bundle contract."""

from viz_virtualserver.canvas.design import LogicalLayer
from viz_virtualserver.canvas.logical_layers import (
    FixedLayerSpec,
    LogicalLayerCatalog,
    LogicalLayerCatalogEntry,
    MatchSpec,
    PathGeometry,
    ProjectedDesign,
    ProjectionRule,
    ProjectionSpec,
    SemanticAttributeSchema,
    SemanticPath,
    project_paths,
)


def topographic_projection(job):
    if not any(p.algorithm == 'topographic' for p in job.passes):
        return None
    layers = {}
    for design_pass in job.passes:
        for layer in design_pass.logical_layers:
            resolved = LogicalLayer(layer.id, layer.label or layer.id)
            if layers.setdefault(layer.id, resolved) != resolved:
                raise ValueError(f'logical channel {layer.id!r} has conflicting labels')
    return ProjectionSpec('topographic-channels', tuple(
        ProjectionRule(MatchSpec(attributes={'channel': (layer.id,)}),
                       fixed=FixedLayerSpec(layer.id, layer.label)) for layer in layers.values()))


def project_topographic_paths(state, projection):
    semantic = tuple(
        SemanticPath(f'{result.producing_pass_id}:path:{i}', path.domain_id,
                     PathGeometry(path.points, path.closed, path.coordinate_frame),
                     path.semantic_path.feature_role if path.semantic_path else 'artwork-curve',
                     {'channel': path.layer_id})
        for result in state.results for i, path in enumerate(result.paths))
    projected = project_paths(semantic, SemanticAttributeSchema(('channel',)), projection)
    layers = tuple(LogicalLayer(rule.fixed.id, rule.fixed.label) for rule in projection.rules)
    catalog = LogicalLayerCatalog(tuple(
        LogicalLayerCatalogEntry(layer.id, i+1, layer.label, projection_rule_index=i)
        for i, layer in enumerate(layers)))
    return ProjectedDesign(projected.paths, layers, catalog)
