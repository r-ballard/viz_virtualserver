import math
from dataclasses import FrozenInstanceError

import pytest

from viz_canvas import PathGeometry, SemanticAttributeSchema, SemanticPath


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
