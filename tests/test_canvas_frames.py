import math

import pytest

from viz_canvas.frames import (
    AffineTransform,
    CompositionTransform,
    resolve_composition_transforms,
)
from viz_canvas.models import PolygonDomain


@pytest.fixture
def triangle() -> PolygonDomain:
    return PolygonDomain(
        id="triangle",
        vertices=((0.0, 0.0), (10.0, 0.0), (5.0, 10.0)),
    )


def test_affine_transform_round_trips_a_point() -> None:
    transform = AffineTransform(a=2, b=0, c=0, d=3, e=10, f=-5)

    point = transform.apply((4, 6))

    assert point == pytest.approx((18, 13))
    assert transform.inverse().apply(point) == pytest.approx((4, 6))


def test_affine_transform_composes_in_application_order() -> None:
    scale = AffineTransform(a=2, b=0, c=0, d=3, e=0, f=0)
    translate = AffineTransform(a=1, b=0, c=0, d=1, e=10, f=-5)

    composed = translate.compose(scale)

    assert composed.apply((4, 6)) == pytest.approx((18, 13))


def test_affine_transform_rejects_non_finite_matrix_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        AffineTransform(a=math.inf, b=0, c=0, d=1, e=0, f=0)


def test_affine_transform_rejects_matrix_with_non_finite_determinant() -> None:
    with pytest.raises(ValueError, match="invertible"):
        AffineTransform(a=1e308, b=0, c=0, d=1e308, e=0, f=0)


def test_affine_transform_rejects_matrix_with_non_finite_inverse_coefficients() -> None:
    with pytest.raises(ValueError, match="invertible"):
        AffineTransform(a=1e308, b=0, c=0, d=1e-308, e=1e308, f=1e308)


def test_affine_transform_rejects_matrix_whose_inverse_is_below_tolerance() -> None:
    with pytest.raises(ValueError, match="invertible"):
        AffineTransform(a=1e308, b=0, c=0, d=1, e=0, f=0)


def test_composition_transform_rejects_singular_matrix() -> None:
    with pytest.raises(ValueError, match="invertible"):
        AffineTransform(a=1, b=2, c=2, d=4, e=0, f=0)


def test_composition_transform_rejects_non_affine_transform() -> None:
    with pytest.raises(ValueError, match="AffineTransform"):
        CompositionTransform("triangle", None)  # type: ignore[arg-type]


def test_composition_transform_rejects_unknown_domain(triangle: PolygonDomain) -> None:
    with pytest.raises(ValueError, match="unknown domain: missing"):
        resolve_composition_transforms(
            domains=(triangle,),
            transforms=(CompositionTransform("missing", AffineTransform.identity()),),
        )


def test_composition_transform_rejects_duplicate_domain_ids(
    triangle: PolygonDomain,
) -> None:
    transform = AffineTransform.identity()

    with pytest.raises(ValueError, match="duplicate transform domain id: triangle"):
        resolve_composition_transforms(
            domains=(triangle,),
            transforms=(
                CompositionTransform("triangle", transform),
                CompositionTransform("triangle", transform),
            ),
        )


def test_resolved_composition_transforms_are_immutable_and_not_implicit(
    triangle: PolygonDomain,
) -> None:
    resolved = resolve_composition_transforms(domains=(triangle,), transforms=())

    assert dict(resolved) == {}
    with pytest.raises(TypeError):
        resolved["triangle"] = AffineTransform.identity()  # type: ignore[index]
