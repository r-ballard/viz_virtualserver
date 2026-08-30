from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from viz_canvas import (
    AffineTransform,
    CompositionTransform,
    DesignPass,
    DomainArtworkJob,
    PolygonDomain,
    PolygonSurface,
    derive_domain_seed,
)


def make_domain(domain_id: str) -> PolygonDomain:
    return PolygonDomain(
        id=domain_id,
        vertices=((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)),
    )


def make_pass(pass_id: str = "design") -> DesignPass:
    return DesignPass(pass_id, "algorithm", ("triangle",))


def test_job_omitted_surfaces_create_one_ordered_surface_per_domain() -> None:
    triangle = make_domain("triangle")
    square = PolygonDomain(
        id="square",
        vertices=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
    )

    job = DomainArtworkJob(
        schema_version=1,
        seed=42,
        domains=(triangle, square),
        surfaces=None,
        groups=(),
        relations=(),
        composition_transforms=(),
        passes=(make_pass(),),
    )

    assert [(item.id, item.domain_id) for item in job.resolved_surfaces] == [
        ("triangle", "triangle"),
        ("square", "square"),
    ]


def test_domain_seed_is_stable_across_unrelated_reordering() -> None:
    before = derive_domain_seed(42, "pass", "algorithm", "stable")
    after = derive_domain_seed(42, "pass", "algorithm", "stable")

    assert before == after
    assert before != derive_domain_seed(42, "pass", "algorithm", "other")


def test_job_rejects_explicitly_empty_surfaces() -> None:
    with pytest.raises(ValueError, match="explicit surfaces collection must not be empty"):
        DomainArtworkJob(
            schema_version=1,
            seed=42,
            domains=(make_domain("triangle"),),
            surfaces=(),
            groups=(),
            relations=(),
            composition_transforms=(),
            passes=(make_pass(),),
        )


def test_job_rejects_duplicate_domain_ids() -> None:
    with pytest.raises(ValueError, match="duplicate domain id: triangle"):
        DomainArtworkJob(
            schema_version=1,
            seed=42,
            domains=(make_domain("triangle"), make_domain("triangle")),
            surfaces=None,
            groups=(),
            relations=(),
            composition_transforms=(),
            passes=(make_pass(),),
        )


def test_job_rejects_surface_for_unknown_domain() -> None:
    with pytest.raises(ValueError, match="unknown domain: missing"):
        DomainArtworkJob(
            schema_version=1,
            seed=42,
            domains=(make_domain("triangle"),),
            surfaces=(PolygonSurface("surface", "missing"),),
            groups=(),
            relations=(),
            composition_transforms=(),
            passes=(make_pass(),),
        )


def test_job_rejects_invalid_pass_graph() -> None:
    with pytest.raises(ValueError, match="unknown dependency: missing"):
        DomainArtworkJob(
            schema_version=1,
            seed=42,
            domains=(make_domain("triangle"),),
            surfaces=None,
            groups=(),
            relations=(),
            composition_transforms=(),
            passes=(
                DesignPass("design", "algorithm", ("triangle",), depends_on=("missing",)),
            ),
        )


def test_job_rejects_transform_for_unknown_domain() -> None:
    with pytest.raises(ValueError, match="unknown domain: missing"):
        DomainArtworkJob(
            schema_version=1,
            seed=42,
            domains=(make_domain("triangle"),),
            surfaces=None,
            groups=(),
            relations=(),
            composition_transforms=(
                CompositionTransform("missing", AffineTransform.identity()),
            ),
            passes=(make_pass(),),
        )


def test_job_defensively_copies_collections_and_is_immutable() -> None:
    domains = [make_domain("triangle")]
    surfaces = [PolygonSurface("surface", "triangle")]
    transforms = [CompositionTransform("triangle", AffineTransform.identity())]
    passes = [make_pass()]

    job = DomainArtworkJob(
        schema_version=1,
        seed=42,
        domains=domains,
        surfaces=surfaces,
        groups=[],
        relations=[],
        composition_transforms=transforms,
        passes=passes,
    )
    domains.clear()
    surfaces.clear()
    transforms.clear()
    passes.clear()

    assert [domain.id for domain in job.domains] == ["triangle"]
    assert [surface.id for surface in job.surfaces or ()] == ["surface"]
    assert [transform.domain_id for transform in job.composition_transforms] == ["triangle"]
    assert [design_pass.id for design_pass in job.passes] == ["design"]
    with pytest.raises(FrozenInstanceError):
        job.seed = 99  # type: ignore[misc]
