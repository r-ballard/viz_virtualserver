from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from viz_canvas import (
    DomainRef,
    DomainRelation,
    FeatureRef,
    FeatureType,
    PolygonDomain,
    PolygonGroup,
    PolygonSurface,
    RelationType,
    validate_semantics,
)


def make_square_domain(domain_id: str) -> PolygonDomain:
    return PolygonDomain(
        id=domain_id,
        vertices=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
    )


def test_feature_ref_preserves_numeric_topology():
    ref = FeatureRef(
        domain_id="domain-a",
        feature_type=FeatureType.EDGE,
        index=2,
    )

    assert ref.domain_id == "domain-a"
    assert ref.feature_type is FeatureType.EDGE
    assert ref.index == 2


def test_surface_references_exactly_one_domain():
    surface = PolygonSurface(id="surface-a", domain_id="domain-a")

    assert surface.domain_id == "domain-a"


def test_two_surfaces_may_reference_same_domain():
    domain = make_square_domain("domain-a")
    surfaces = (
        PolygonSurface(id="surface-1", domain_id=domain.id),
        PolygonSurface(id="surface-2", domain_id=domain.id),
    )

    validate_semantics(domains=(domain,), surfaces=surfaces, groups=(), relations=())


def test_polygon_group_preserves_member_order_without_geometry_semantics():
    domains = (make_square_domain("a"), make_square_domain("b"))
    surfaces = (
        PolygonSurface(id="surface-a", domain_id="a"),
        PolygonSurface(id="surface-b", domain_id="b"),
    )
    group = PolygonGroup(id="group", surface_ids=("surface-b", "surface-a"))

    validate_semantics(domains=domains, surfaces=surfaces, groups=(group,), relations=())

    assert group.surface_ids == ("surface-b", "surface-a")


def test_domain_relations_are_optional():
    validate_semantics(
        domains=(make_square_domain("a"), make_square_domain("b")),
        surfaces=(),
        groups=(),
        relations=(),
    )


@pytest.mark.parametrize("feature_type", [FeatureType.VERTEX, FeatureType.EDGE])
def test_feature_relation_rejects_index_equal_to_vertex_count(feature_type):
    domain = make_square_domain("a")
    relation = DomainRelation(
        id="relation",
        relation_type=RelationType.CORRESPONDS_TO,
        source=FeatureRef("a", feature_type, len(domain.vertices)),
        target=DomainRef("a"),
    )

    with pytest.raises(ValueError, match=rf"{feature_type.value} index"):
        validate_semantics(
            domains=(domain,), surfaces=(), groups=(), relations=(relation,)
        )


def test_feature_relation_rejects_negative_index():
    domain = make_square_domain("a")
    relation = DomainRelation(
        id="relation",
        relation_type=RelationType.ADJACENT,
        source=FeatureRef("a", FeatureType.EDGE, -1),
        target=DomainRef("a"),
    )

    with pytest.raises(ValueError, match="edge index"):
        validate_semantics(
            domains=(domain,), surfaces=(), groups=(), relations=(relation,)
        )


def test_surface_rejects_unknown_domain():
    with pytest.raises(ValueError, match="unknown domain: missing"):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(PolygonSurface(id="surface", domain_id="missing"),),
            groups=(),
            relations=(),
        )


def test_surface_feature_alias_rejects_another_domain():
    surface = PolygonSurface(
        id="surface",
        domain_id="a",
        feature_aliases={"top": FeatureRef("b", FeatureType.EDGE, 0)},
    )

    with pytest.raises(ValueError, match="references another domain"):
        validate_semantics(
            domains=(make_square_domain("a"), make_square_domain("b")),
            surfaces=(surface,),
            groups=(),
            relations=(),
        )


def test_group_rejects_unknown_surface():
    with pytest.raises(
        ValueError, match="group group references unknown surface: missing"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(),
            groups=(PolygonGroup(id="group", surface_ids=("missing",)),),
            relations=(),
        )


def test_relation_rejects_unknown_endpoint_domain():
    relation = DomainRelation(
        id="relation",
        relation_type=RelationType.OVERLAPS,
        source=DomainRef("a"),
        target=DomainRef("missing"),
    )

    with pytest.raises(
        ValueError, match="relation relation references unknown domain: missing"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(),
            groups=(),
            relations=(relation,),
        )


@pytest.mark.parametrize(
    ("kind", "items"),
    [
        ("domain", (make_square_domain("a"), make_square_domain("a"))),
        (
            "surface",
            (PolygonSurface("same", "a"), PolygonSurface("same", "a")),
        ),
        ("group", (PolygonGroup("same", ()), PolygonGroup("same", ()))),
        (
            "relation",
            (
                DomainRelation("same", RelationType.CONTAINS, DomainRef("a"), DomainRef("a")),
                DomainRelation("same", RelationType.MIRRORS, DomainRef("a"), DomainRef("a")),
            ),
        ),
    ],
)
def test_ids_must_be_unique_within_each_type(kind, items):
    kwargs = {
        "domains": (make_square_domain("a"),),
        "surfaces": (),
        "groups": (),
        "relations": (),
    }
    kwargs[f"{kind}s"] = items

    with pytest.raises(ValueError, match=rf"duplicate {kind} id"):
        validate_semantics(**kwargs)


@pytest.mark.parametrize(
    ("kind", "item"),
    [
        ("surface", PolygonSurface("", "a")),
        ("group", PolygonGroup("", ())),
        ("relation", DomainRelation("", RelationType.ALIGNED_WITH, DomainRef("a"), DomainRef("a"))),
    ],
)
def test_semantic_ids_must_be_non_empty(kind, item):
    kwargs = {
        "domains": (make_square_domain("a"),),
        "surfaces": (),
        "groups": (),
        "relations": (),
    }
    kwargs[f"{kind}s"] = (item,)

    with pytest.raises(ValueError, match=rf"{kind} id must not be empty"):
        validate_semantics(**kwargs)


def test_mapping_inputs_are_defensively_copied_and_read_only():
    aliases = {"corner": FeatureRef("a", FeatureType.VERTEX, 0)}
    group_metadata = {"label": "original"}
    relation_metadata = {"weight": 1}
    surface = PolygonSurface("surface", "a", aliases)
    group = PolygonGroup("group", ("surface",), metadata=group_metadata)
    relation = DomainRelation(
        "relation",
        RelationType.CONTINUES_TO,
        DomainRef("a"),
        DomainRef("a"),
        relation_metadata,
    )

    aliases["other"] = FeatureRef("a", FeatureType.VERTEX, 1)
    group_metadata["label"] = "changed"
    relation_metadata["weight"] = 2

    assert tuple(surface.feature_aliases) == ("corner",)
    assert group.metadata["label"] == "original"
    assert relation.metadata["weight"] == 1
    with pytest.raises(TypeError):
        surface.feature_aliases["new"] = FeatureRef("a", FeatureType.VERTEX, 2)
    with pytest.raises(TypeError):
        group.metadata["new"] = True
    with pytest.raises(TypeError):
        relation.metadata["new"] = True
    with pytest.raises(FrozenInstanceError):
        group.id = "changed"


def test_feature_ref_rejects_unknown_feature_type_during_validation():
    relation = DomainRelation(
        "relation",
        RelationType.ADJACENT,
        FeatureRef("a", "face", 0),  # type: ignore[arg-type]
        DomainRef("a"),
    )

    with pytest.raises(
        ValueError, match="relation relation has invalid feature type: 'face'"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(),
            groups=(),
            relations=(relation,),
        )


def test_relation_rejects_unknown_relation_type_during_validation():
    relation = DomainRelation(
        "relation",
        "custom",  # type: ignore[arg-type]
        DomainRef("a"),
        DomainRef("a"),
    )

    with pytest.raises(
        ValueError, match="relation relation has invalid relation type: 'custom'"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(),
            groups=(),
            relations=(relation,),
        )


def test_relation_rejects_endpoint_outside_typed_vocabulary():
    relation = DomainRelation(
        "relation",
        RelationType.CONTAINS,
        object(),  # type: ignore[arg-type]
        DomainRef("a"),
    )

    with pytest.raises(
        ValueError, match="relation relation has invalid source endpoint"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(),
            groups=(),
            relations=(relation,),
        )


def test_surface_rejects_alias_value_outside_typed_vocabulary():
    surface = PolygonSurface(
        "surface",
        "a",
        {"corner": DomainRef("a")},  # type: ignore[dict-item]
    )

    with pytest.raises(
        ValueError, match="surface surface alias 'corner' is not a FeatureRef"
    ):
        validate_semantics(
            domains=(make_square_domain("a"),),
            surfaces=(surface,),
            groups=(),
            relations=(),
        )
