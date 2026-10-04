"""Use the existing neutral-layer handoff for opted-in Truchet color channels."""

from __future__ import annotations

from viz_virtualserver.canvas.design import DesignState, LogicalLayer
from viz_virtualserver.canvas.jobs import DomainArtworkJob
from viz_virtualserver.canvas.logical_layers import (
    FixedLayerSpec,
    MatchSpec,
    PathGeometry,
    ProjectedDesign,
    ProjectionRule,
    ProjectionSpec,
    SemanticAttributeSchema,
    SemanticPath,
    project_paths,
)

from .curve_layers import curve_layer_ids

_ALGORITHMS = {"truchet", "truchet-multiscale"}
_SCHEMA = SemanticAttributeSchema(("curve_channel",))


def truchet_color_projection(job: DomainArtworkJob) -> ProjectionSpec | None:
    if not any(p.algorithm in _ALGORITHMS and len(p.logical_layers) > 1 for p in job.passes):
        return None
    if any(p.algorithm not in _ALGORITHMS for p in job.passes):
        raise ValueError("multi-channel Truchet export requires a Truchet-only job")
    layers: dict[str, LogicalLayer] = {}
    for design_pass in job.passes:
        curve_layer_ids(design_pass.logical_layers,
                        outline_layer_id=design_pass.parameters.get("outline_layer_id"))
        for layer in design_pass.logical_layers:
            resolved = LogicalLayer(layer.id, layer.label or layer.id)
            previous = layers.setdefault(layer.id, resolved)
            if previous != resolved:
                raise ValueError(f"curve channel {layer.id!r} has conflicting labels across passes")
    return ProjectionSpec("truchet-curve-channels", tuple(
        ProjectionRule(MatchSpec(attributes={"curve_channel": (layer.id,)}),
                       fixed=FixedLayerSpec(layer.id, layer.label))
        for layer in layers.values()
    ))


def project_truchet_color_paths(
    state: DesignState, projection: ProjectionSpec
) -> ProjectedDesign:
    paths = tuple(
        SemanticPath(
            path_id=f"{result.producing_pass_id}:path:{index}",
            domain_id=path.domain_id,
            geometry=PathGeometry(path.points, path.closed, path.coordinate_frame),
            feature_role=(path.semantic_path.feature_role
                          if path.semantic_path else "truchet-curve"),
            attributes={"curve_channel": path.layer_id},
        )
        for result in state.results
        for index, path in enumerate(result.paths)
    )
    return project_paths(paths, _SCHEMA, projection)
