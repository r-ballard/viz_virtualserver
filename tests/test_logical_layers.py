import math
from dataclasses import FrozenInstanceError

import pytest

from viz_canvas import PathGeometry, SemanticAttributeSchema, SemanticPath
from viz_canvas.logical_layers import (
    DynamicLayerSpec,
    FixedLayerSpec,
    MatchSpec,
    ProjectionError,
    ProjectionRule,
    ProjectionSpec,
    project_paths,
)

BODY_SCHEMA = SemanticAttributeSchema(("size_class",))
BODY_GROUP_SCHEMA = SemanticAttributeSchema(("size_class", "body_index"))
LSYSTEM_SCHEMA = SemanticAttributeSchema(("generation",))


def body_path(*, size_class: str = "small", path_id: str = "body-1") -> SemanticPath:
    return SemanticPath(
        path_id,
        "domain-1",
        PathGeometry(((0, 0), (1, 1)), False),
        "body",
        {"size_class": size_class},
    )


def generation_paths(*generations: int) -> tuple[SemanticPath, ...]:
    return tuple(
        SemanticPath(
            f"generation-{generation}",
            "domain-1",
            PathGeometry(((0, 0), (1, 1)), False),
            "segment",
            {"generation": generation},
        )
        for generation in generations
    )


def generation_projection() -> ProjectionSpec:
    return ProjectionSpec(
        "lsystem",
        (
            ProjectionRule(
                MatchSpec(feature_role="segment"),
                dynamic=DynamicLayerSpec("generation", "Generation", ("generation",)),
            ),
        ),
    )


def two_domains_same_body() -> tuple[SemanticPath, ...]:
    return tuple(
        SemanticPath(
            f"{domain_id}-body-1",
            domain_id,
            PathGeometry(((0, 0), (1, 1)), False),
            "body",
            {"size_class": "small", "body_index": 1},
        )
        for domain_id in ("domain-a", "domain-b")
    )


def per_body_projection(*, include_domain: bool) -> ProjectionSpec:
    group_by = ("domain_id", "body_index") if include_domain else ("body_index",)
    return ProjectionSpec(
        "orbital",
        (
            ProjectionRule(
                MatchSpec(feature_role="body"),
                dynamic=DynamicLayerSpec("body", "Body", group_by),
            ),
        ),
    )


def test_dynamic_generation_layers_sort_numerically():
    result = project_paths(
        generation_paths(10, 2, 1), LSYSTEM_SCHEMA, generation_projection()
    )

    assert [layer.id for layer in result.layers] == [
        "generation-i-1",
        "generation-i-2",
        "generation-i-10",
    ]


def test_group_by_domain_can_scope_identical_body_indexes():
    result = project_paths(
        two_domains_same_body(), BODY_GROUP_SCHEMA, per_body_projection(include_domain=True)
    )

    assert len(result.layers) == 2


def test_group_by_without_domain_shares_identical_body_indexes():
    result = project_paths(
        two_domains_same_body(), BODY_GROUP_SCHEMA, per_body_projection(include_domain=False)
    )

    assert [path.layer_id for path in result.paths] == ["body-i-1", "body-i-1"]
    assert [layer.id for layer in result.layers] == ["body-i-1"]


def test_dynamic_groups_preserve_scalar_type_identity_and_typed_order():
    paths = tuple(
        SemanticPath(
            f"path-{index}",
            "domain-1",
            PathGeometry(((0, 0), (1, 1)), False),
            "item",
            {"value": value},
        )
        for index, value in enumerate(("1", 1.0, 1, True))
    )
    projection = ProjectionSpec(
        "typed-values",
        (
            ProjectionRule(
                MatchSpec(feature_role="item"),
                dynamic=DynamicLayerSpec("value", "Value", ("value",)),
            ),
        ),
    )

    result = project_paths(paths, SemanticAttributeSchema(("value",)), projection)

    assert [layer.id for layer in result.layers] == [
        "value-b-true",
        "value-i-1",
        "value-n-1.0",
        "value-s-1",
    ]


def test_dynamic_layer_id_collision_with_conflicting_metadata_is_rejected():
    paths = (
        SemanticPath(
            "small-body",
            "domain-1",
            PathGeometry(((0, 0), (1, 1)), False),
            "small-body",
            {"size_class": "small", "body_index": 1},
        ),
        SemanticPath(
            "large-body",
            "domain-1",
            PathGeometry(((0, 0), (1, 1)), False),
            "large-body",
            {"size_class": "large", "body_index": 1},
        ),
    )
    projection = ProjectionSpec(
        "collision",
        (
            ProjectionRule(
                MatchSpec(feature_role="small-body"),
                dynamic=DynamicLayerSpec("body", "Small body", ("body_index",)),
            ),
            ProjectionRule(
                MatchSpec(feature_role="large-body"),
                dynamic=DynamicLayerSpec("body", "Large body", ("body_index",)),
            ),
        ),
    )

    with pytest.raises(ProjectionError, match="body-i-1.*conflicting"):
        project_paths(paths, BODY_GROUP_SCHEMA, projection)


def test_fixed_projection_uses_first_matching_rule_once():
    result = project_paths(
        (body_path(size_class="small"),),
        BODY_SCHEMA,
        ProjectionSpec(
            "orbital",
            (
                ProjectionRule(
                    MatchSpec(feature_role="body", attributes={"size_class": ("small",)}),
                    fixed=FixedLayerSpec("small-bodies", "Small bodies"),
                ),
                ProjectionRule(
                    MatchSpec(feature_role="body"),
                    fixed=FixedLayerSpec("bodies", "Bodies"),
                ),
            ),
        ),
    )
    assert [path.layer_id for path in result.paths] == ["small-bodies"]
    assert [layer.id for layer in result.layers] == ["small-bodies"]


def test_fixed_projection_matches_attribute_membership():
    result = project_paths(
        (body_path(size_class="medium"),),
        BODY_SCHEMA,
        ProjectionSpec(
            "orbital",
            (
                ProjectionRule(
                    MatchSpec(
                        feature_role="body", attributes={"size_class": ("small", "medium")}
                    ),
                    fixed=FixedLayerSpec("small-and-medium", "Small and medium bodies"),
                ),
            ),
        ),
    )

    assert [path.layer_id for path in result.paths] == ["small-and-medium"]
    assert [layer.id for layer in result.layers] == ["small-and-medium"]


def test_fixed_projection_rejects_selector_keys_not_declared_by_schema():
    projection = ProjectionSpec(
        "orbital",
        (
            ProjectionRule(
                MatchSpec(feature_role="body", attributes={"orbit_class": ("inner",)}),
                fixed=FixedLayerSpec("bodies", "Bodies"),
            ),
        ),
    )

    with pytest.raises(ProjectionError, match="orbit_class.*rule 0"):
        project_paths((body_path(),), BODY_SCHEMA, projection)


def test_fixed_projection_reports_unmatched_path_and_projection_context():
    projection = ProjectionSpec(
        "orbital",
        (
            ProjectionRule(
                MatchSpec(feature_role="ring"),
                fixed=FixedLayerSpec("rings", "Rings"),
            ),
        ),
    )

    with pytest.raises(ProjectionError, match="body-unmatched.*projection orbital"):
        project_paths((body_path(path_id="body-unmatched"),), BODY_SCHEMA, projection)


def test_projection_spec_rejects_conflicting_repeated_fixed_layer_ids():
    with pytest.raises(ValueError, match="bodies.*conflicting fixed layer"):
        ProjectionSpec(
            "orbital",
            (
                ProjectionRule(
                    MatchSpec(feature_role="body", attributes={"size_class": ("small",)}),
                    fixed=FixedLayerSpec("bodies", "Small bodies"),
                ),
                ProjectionRule(
                    MatchSpec(feature_role="body"),
                    fixed=FixedLayerSpec("bodies", "All bodies"),
                ),
            ),
        )


def test_projection_spec_allows_repeated_identical_fixed_layer_definitions():
    fixed = FixedLayerSpec("bodies", "Bodies")
    projection = ProjectionSpec(
        "orbital",
        (
            ProjectionRule(
                MatchSpec(feature_role="body", attributes={"size_class": ("small",)}),
                fixed=fixed,
            ),
            ProjectionRule(MatchSpec(feature_role="body"), fixed=fixed),
        ),
    )

    result = project_paths(
        (body_path(size_class="small"), body_path(size_class="large", path_id="body-2")),
        BODY_SCHEMA,
        projection,
    )

    assert [path.layer_id for path in result.paths] == ["bodies", "bodies"]
    assert [(layer.id, layer.label) for layer in result.layers] == [("bodies", "Bodies")]


def test_semantic_path_defensively_freezes_attributes():
    source = {"system_index": 1, "small": True}
    path = SemanticPath("p1", "d1", PathGeometry(((0, 0), (1, 1)), False), "body", source)

    source["system_index"] = 2
    assert dict(path.attributes) == {"system_index": 1, "small": True}
    with pytest.raises(TypeError):
        path.attributes["system_index"] = 3


@pytest.mark.parametrize("value", [None, [], {}, float("nan"), float("inf")])
def test_semantic_path_rejects_non_scalar_attributes(value):
    with pytest.raises(ValueError, match="attribute"):
        SemanticPath(
            "p1", "d1", PathGeometry(((0, 0), (1, 1)), False), "body", {"bad": value}
        )


def test_path_geometry_freezes_points_and_validates_frame():
    points = [[0, 0], [1, 1]]
    geometry = PathGeometry(points, False)

    points[0][0] = 10
    assert geometry.points == ((0, 0), (1, 1))
    assert geometry.coordinate_frame == "domain"

    with pytest.raises(ValueError, match="coordinate frame"):
        PathGeometry(((0, 0), (1, 1)), False, "screen")


def test_path_geometry_reuses_point_validation_contract():
    with pytest.raises(ValueError, match="at least two"):
        PathGeometry(((0, 0),), False)
    with pytest.raises(ValueError, match="at least three"):
        PathGeometry(((0, 0), (1, 1)), True)
    with pytest.raises(ValueError, match="finite"):
        PathGeometry(((0, 0), (math.inf, 1)), False)


def test_semantic_path_requires_non_empty_identity_parts():
    geometry = PathGeometry(((0, 0), (1, 1)), False)
    for args in [("", "d1", "body"), ("p1", "", "body"), ("p1", "d1", "")]:
        with pytest.raises(ValueError):
            SemanticPath(args[0], args[1], geometry, args[2], {})


def test_attribute_schema_freezes_unique_non_empty_keys():
    schema = SemanticAttributeSchema(["system_index", "small"])
    assert schema.keys == ("system_index", "small")
    with pytest.raises(ValueError, match="duplicate"):
        SemanticAttributeSchema(["small", "small"])
    with pytest.raises(ValueError, match="key"):
        SemanticAttributeSchema([""])


@pytest.mark.parametrize(
    ("points", "message"),
    [
        (((0, 0, 0), (1, 1)), "exactly two"),
        (((0, 0), ("1", 1)), "numeric"),
        (((0, 0), (True, 1)), "numeric"),
        (((0, 0), (math.nan, 1)), "finite"),
    ],
)
def test_path_geometry_rejects_invalid_coordinates(points, message):
    with pytest.raises(ValueError, match=message):
        PathGeometry(points, False)


@pytest.mark.parametrize("closed", [1, 0, "closed", "", None])
def test_path_geometry_rejects_non_boolean_closed(closed):
    with pytest.raises(ValueError, match="closed.*bool"):
        PathGeometry(((0, 0), (1, 0), (0, 1)), closed)


def test_semantic_records_are_frozen_and_preserve_scalar_types():
    geometry = PathGeometry(((0, 0), (1, 0), (0, 1)), True, "composition")
    attributes = {"flag": True, "count": 1, "ratio": 1.5, "label": "body"}
    path = SemanticPath("p1", "d1", geometry, "body", attributes)
    keys = list(attributes)
    schema = SemanticAttributeSchema(keys)
    keys.append("extra")

    assert geometry.closed is True
    assert geometry.coordinate_frame == "composition"
    assert dict(path.attributes) == attributes
    assert type(path.attributes["flag"]) is bool
    assert type(path.attributes["count"]) is int
    assert schema.keys == ("flag", "count", "ratio", "label")
    for record, field, replacement in [
        (path, "path_id", "p2"),
        (geometry, "closed", False),
        (schema, "keys", ()),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, replacement)


@pytest.mark.parametrize("field", ["path_id", "domain_id", "feature_role"])
@pytest.mark.parametrize("value", [" \t", True, 1])
def test_semantic_path_rejects_invalid_identity_parts(field, value):
    values = {"path_id": "p1", "domain_id": "d1", "feature_role": "body"}
    values[field] = value
    with pytest.raises(ValueError):
        SemanticPath(
            **values, geometry=PathGeometry(((0, 0), (1, 1)), False), attributes={}
        )


@pytest.mark.parametrize("value", [(1,), {1}, object(), -math.inf])
def test_semantic_path_rejects_other_non_scalar_attributes(value):
    with pytest.raises(ValueError, match="attribute"):
        SemanticPath(
            "p1", "d1", PathGeometry(((0, 0), (1, 1)), False), "body", {"bad": value}
        )
