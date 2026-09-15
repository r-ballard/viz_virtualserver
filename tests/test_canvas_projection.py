from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from viz_canvas import projection as surface_projection
from viz_canvas.design import DesignPass, DesignResult, DesignState, LogicalLayer, VectorPath
from viz_canvas.frames import AffineTransform, CompositionTransform
from viz_canvas.jobs import DomainArtworkJob
from viz_canvas.logical_layers import (
    DynamicLayerSpec,
    LogicalLayerCatalog,
    MatchSpec,
    PathGeometry,
    ProjectionRule,
    ProjectionSpec,
    SemanticAttributeSchema,
    SemanticPath,
    project_paths,
)
from viz_canvas.models import PolygonDomain
from viz_canvas.projection import project_surfaces
from viz_canvas.semantics import PolygonSurface


def _job(
    *,
    domains: tuple[PolygonDomain, ...],
    surfaces: tuple[PolygonSurface, ...] | None = None,
    transforms: tuple[CompositionTransform, ...] = (),
    passes: tuple[DesignPass, ...] = (),
) -> DomainArtworkJob:
    return DomainArtworkJob(
        schema_version=1,
        seed=7,
        domains=domains,
        surfaces=surfaces,
        groups=(),
        relations=(),
        composition_transforms=transforms,
        passes=passes,
    )


def test_projection_rebases_paths_and_preserves_surface_order() -> None:
    first = PolygonDomain("first-domain", ((10, 20), (20, 20), (10, 30)))
    second = PolygonDomain("second-domain", ((100, 200), (120, 200), (100, 220)))
    job = _job(
        domains=(first, second),
        surfaces=(
            PolygonSurface("first", first.id),
            PolygonSurface("second", second.id),
        ),
    )
    state = DesignState(
        source_domains=(first, second),
        results=(
            DesignResult(
                paths=(
                    VectorPath(((10, 20), (15, 25)), False, "ink", first.id),
                    VectorPath(((100, 200), (110, 210)), False, "ink", second.id),
                ),
                derived_domains=(),
                producing_pass_id="draw",
            ),
        ),
    )

    projections = project_surfaces(job, state)

    assert [item.surface.id for item in projections] == ["first", "second"]
    assert projections[0].domain.vertices[0] == pytest.approx((0, 0))
    assert projections[0].paths[0].points[0] == pytest.approx((0, 0))
    assert projections[0].paths[0].producing_pass_id == "draw"
    assert projections[0].bounds == pytest.approx((0, 0, 10, 10))
    assert projections[1].domain.vertices[0] == pytest.approx((0, 0))
    assert projections[1].paths[0].points[0] == pytest.approx((0, 0))


def test_catalog_is_union_while_surfaces_keep_subsets() -> None:
    domains = tuple(
        PolygonDomain(name, ((10, 20), (20, 20), (10, 30)))
        for name in ("a", "b", "empty")
    )
    projected = project_paths(
        tuple(
            SemanticPath(
                f"{domain_id}-{generation}",
                domain_id,
                PathGeometry(((10, 20), (12, 22)), False),
                "segment",
                {"generation": generation},
            )
            for domain_id, generation in (("b", 2), ("a", 1), ("b", 1))
        ),
        SemanticAttributeSchema(("generation",)),
        ProjectionSpec("generations", (
            ProjectionRule(
                MatchSpec(feature_role="segment"),
                dynamic=DynamicLayerSpec("generation", "Generation", ("generation",)),
            ),
        )),
    )
    assert callable(getattr(surface_projection, "project_surface_bundle", None))

    bundle = surface_projection.project_surface_bundle(_job(domains=domains), projected)

    assert [entry.id for entry in bundle.catalog.entries] == [
        "generation-i-1", "generation-i-2",
    ]
    assert [entry.ordinal for entry in bundle.catalog.entries] == [1, 2]
    assert [entry.label for entry in bundle.catalog.entries] == [
        "Generation 1", "Generation 2",
    ]
    assert [entry.projection_rule_index for entry in bundle.catalog.entries] == [0, 0]
    assert [entry.group_values for entry in bundle.catalog.entries] == [(1,), (2,)]
    assert [entry.preview_style for entry in bundle.catalog.entries] == [{}, {}]
    assert [surface.layer_ids for surface in bundle.surfaces] == [
        ("generation-i-1",), ("generation-i-1", "generation-i-2"), (),
    ]
    assert [path.layer_id for path in bundle.surfaces[1].paths] == [
        "generation-i-2", "generation-i-1",
    ]
    assert bundle.surfaces[0].paths[0].points == ((0.0, 0.0), (2.0, 2.0))
    assert project_surfaces(_job(domains=domains), projected) == bundle.surfaces


def test_bundle_filters_after_clipping_and_surface_selection_then_reassigns_ordinals():
    domains = tuple(
        PolygonDomain(name, ((10, 20), (20, 20), (10, 30)))
        for name in ("a", "b", "omitted")
    )
    projected = project_paths(
        tuple(
            SemanticPath(
                f"generation-{generation}",
                domain_id,
                PathGeometry(points, False, "composition"),
                "segment",
                {"generation": generation},
            )
            for generation, domain_id, points in (
                (1, "a", ((40, 40), (41, 41))),
                (2, "b", ((10, 20), (12, 22))),
                (3, "omitted", ((10, 20), (12, 22))),
                (4, "a", ((10, 20), (12, 22))),
            )
        ),
        SemanticAttributeSchema(("generation",)),
        ProjectionSpec("generations", (
            ProjectionRule(
                MatchSpec(),
                dynamic=DynamicLayerSpec("generation", "Generation", ("generation",)),
            ),
        )),
    )
    projected = replace(projected, catalog=LogicalLayerCatalog(tuple(
        replace(entry, preview_style={"stroke": "red"})
        for entry in projected.catalog.entries
    )))
    job = _job(
        domains=domains,
        surfaces=(PolygonSurface("front", "a"), PolygonSurface("back", "b")),
        transforms=tuple(
            CompositionTransform(domain.id, AffineTransform.identity()) for domain in domains
        ),
    )

    bundle = surface_projection.project_surface_bundle(job, projected)

    assert [(entry.id, entry.ordinal, entry.group_values) for entry in bundle.catalog.entries] == [
        ("generation-i-2", 1, (2,)), ("generation-i-4", 2, (4,)),
    ]
    assert [entry.preview_style for entry in bundle.catalog.entries] == [
        {"stroke": "red"}, {"stroke": "red"},
    ]
    assert [surface.layer_ids for surface in bundle.surfaces] == [
        ("generation-i-4",), ("generation-i-2",),
    ]
    assert [entry.ordinal for entry in projected.catalog.entries] == [1, 2, 3, 4]
    assert bundle.surfaces[1].paths[0].points == ((0.0, 0.0), (2.0, 2.0))
    with pytest.raises(FrozenInstanceError):
        bundle.surfaces = ()


def test_bundle_retains_legacy_declared_metadata_and_infers_undeclared_layers():
    domain = PolygonDomain("panel", ((0, 0), (10, 0), (0, 10)))
    job = _job(domains=(domain,), passes=(DesignPass(
        "draw", "algorithm", (domain.id,),
        logical_layers=(LogicalLayer("unused", "Unused"), LogicalLayer("ink", "Ink")),
    ),))
    state = DesignState(source_domains=(domain,), results=(DesignResult(
        paths=tuple(
            VectorPath(((0, 0), (1, 1)), False, layer_id, domain.id)
            for layer_id in ("extra", "ink")
        ),
        derived_domains=(), producing_pass_id="draw",
    ),))

    bundle = surface_projection.project_surface_bundle(job, state)

    assert [(entry.id, entry.ordinal, entry.label) for entry in bundle.catalog.entries] == [
        ("ink", 1, "Ink"), ("extra", 2, None),
    ]
    assert [entry.projection_rule_index for entry in bundle.catalog.entries] == [None, None]
    assert bundle.surfaces[0].layer_ids == ("ink", "extra")
    assert isinstance(project_surfaces(job, state), tuple)
    assert project_surfaces(job, state) == bundle.surfaces


def test_bundle_can_have_no_used_layers():
    domain = PolygonDomain("empty", ((0, 0), (10, 0), (0, 10)))
    bundle = surface_projection.project_surface_bundle(
        _job(domains=(domain,)), DesignState(source_domains=(domain,))
    )

    assert bundle.catalog.entries == ()
    assert bundle.surfaces[0].layer_ids == ()
    assert bundle.surfaces[0].paths == ()


def test_projection_partitions_overlapping_geometry_by_explicit_domain_id() -> None:
    first = PolygonDomain("a", ((0, 0), (10, 0), (0, 10)))
    second = PolygonDomain("b", ((0, 0), (10, 0), (0, 10)))
    state = DesignState(
        source_domains=(first, second),
        results=(
            DesignResult(
                paths=(VectorPath(((1, 1), (2, 2)), False, "ink", second.id),),
                derived_domains=(),
                producing_pass_id="draw",
            ),
        ),
    )

    first_projection, second_projection = project_surfaces(
        _job(domains=(first, second)), state
    )

    assert first_projection.paths == ()
    assert [path.domain_id for path in second_projection.paths] == ["b"]


def test_projection_inverse_maps_composition_paths_before_rebasing() -> None:
    domain = PolygonDomain("panel", ((10, 20), (20, 20), (10, 30)))
    transform = AffineTransform(a=2, b=0, c=0, d=2, e=100, f=200)
    state = DesignState(
        source_domains=(domain,),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((120, 240), (130, 250)),
                        False,
                        "ink",
                        domain.id,
                        "composition",
                    ),
                ),
                derived_domains=(),
                producing_pass_id="coordinated",
            ),
        ),
    )

    (projection,) = project_surfaces(
        _job(
            domains=(domain,),
            transforms=(CompositionTransform(domain.id, transform),),
        ),
        state,
    )

    assert projection.paths[0].coordinate_frame == "domain"
    assert projection.paths[0].points[0] == pytest.approx((0, 0))
    assert projection.paths[0].points[1] == pytest.approx((5, 5))
    assert projection.paths[0].producing_pass_id == "coordinated"


def test_projection_rejects_composition_path_without_owning_transform() -> None:
    domain = PolygonDomain("panel", ((0, 0), (10, 0), (0, 10)))
    state = DesignState(
        source_domains=(domain,),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((0, 0), (5, 5)),
                        False,
                        "ink",
                        domain.id,
                        "composition",
                    ),
                ),
                derived_domains=(),
                producing_pass_id="coordinated",
            ),
        ),
    )

    with pytest.raises(ValueError, match="composition transform required for domain: panel"):
        project_surfaces(_job(domains=(domain,)), state)


def test_projection_rejects_missing_transform_before_surface_partitioning() -> None:
    visible = PolygonDomain("visible", ((0, 0), (10, 0), (0, 10)))
    omitted = PolygonDomain("omitted", ((20, 0), (30, 0), (20, 10)))
    state = DesignState(
        source_domains=(visible, omitted),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((20, 0), (25, 5)),
                        False,
                        "ink",
                        omitted.id,
                        "composition",
                    ),
                ),
                derived_domains=(),
                producing_pass_id="coordinated",
            ),
        ),
    )
    job = _job(
        domains=(visible, omitted),
        surfaces=(PolygonSurface("front", visible.id),),
    )

    with pytest.raises(ValueError, match="composition transform required for domain: omitted"):
        project_surfaces(job, state)


def test_projection_clips_crossing_path_into_concave_components_in_source_order() -> None:
    domain = PolygonDomain(
        "concave",
        ((10, 10), (16, 10), (16, 16), (14, 16), (14, 12), (12, 12), (12, 16), (10, 16)),
    )
    state = DesignState(
        source_domains=(domain,),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((9, 15), (17, 15)),
                        False,
                        "ink",
                        domain.id,
                        "composition",
                    ),
                ),
                derived_domains=(),
                producing_pass_id="coordinated",
            ),
        ),
    )

    (projection,) = project_surfaces(
        _job(
            domains=(domain,),
            transforms=(CompositionTransform(domain.id, AffineTransform.identity()),),
        ),
        state,
    )

    assert [path.points for path in projection.paths] == [
        ((0.0, 5.0), (2.0, 5.0)),
        ((4.0, 5.0), (6.0, 5.0)),
    ]


def test_projection_preserves_closed_path_direction_across_the_closing_seam() -> None:
    domain = PolygonDomain("panel", ((0, 0), (10, 0), (10, 10), (0, 10)))
    state = DesignState(
        source_domains=(domain,),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((5, 5), (15, 5), (15, 15), (5, 15)),
                        True,
                        "ink",
                        domain.id,
                        "composition",
                    ),
                ),
                derived_domains=(),
                producing_pass_id="coordinated",
            ),
        ),
    )

    (projection,) = project_surfaces(
        _job(
            domains=(domain,),
            transforms=(CompositionTransform(domain.id, AffineTransform.identity()),),
        ),
        state,
    )

    assert [path.points for path in projection.paths] == [
        ((5.0, 5.0), (10.0, 5.0)),
        ((5.0, 10.0), (5.0, 5.0)),
    ]


def test_projection_preserves_declared_layer_then_source_and_component_order() -> None:
    domain = PolygonDomain(
        "concave",
        ((0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)),
    )
    passes = (
        DesignPass(
            "draw",
            "algorithm",
            (domain.id,),
            logical_layers=(LogicalLayer("underlay"), LogicalLayer("ink")),
        ),
    )
    state = DesignState(
        source_domains=(domain,),
        results=(
            DesignResult(
                paths=(
                    VectorPath(
                        ((-1, 5), (7, 5)),
                        False,
                        "ink",
                        domain.id,
                        "composition",
                    ),
                    VectorPath(((0, 1), (1, 1)), False, "underlay", domain.id),
                    VectorPath(((0, 3), (1, 3)), False, "ink", domain.id),
                ),
                derived_domains=(),
                producing_pass_id="draw",
            ),
        ),
    )

    (projection,) = project_surfaces(
        _job(
            domains=(domain,),
            transforms=(CompositionTransform(domain.id, AffineTransform.identity()),),
            passes=passes,
        ),
        state,
    )

    assert [layer.id for layer in projection.layers] == ["underlay", "ink"]
    assert [path.layer_id for path in projection.paths] == [
        "ink",
        "ink",
        "underlay",
        "ink",
    ]
    assert [path.points for path in projection.paths[:2]] == [
        ((0.0, 5.0), (2.0, 5.0)),
        ((4.0, 5.0), (6.0, 5.0)),
    ]
