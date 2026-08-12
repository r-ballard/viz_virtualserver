import pytest
from pydantic import ValidationError

from viz_canvas.models import CanvasSpec


def test_square_requires_equal_dimensions() -> None:
    with pytest.raises(ValidationError, match="width == height"):
        CanvasSpec(shape="square", width=100, height=80)


def test_polygon_requires_points() -> None:
    with pytest.raises(ValidationError, match="at least three points"):
        CanvasSpec(shape="polygon")


def test_polygon_points_must_fit_declared_viewbox() -> None:
    with pytest.raises(ValidationError, match="inside the declared"):
        CanvasSpec(
            shape="polygon",
            width=100,
            height=100,
            points=[(0, 0), (101, 0), (0, 100)],
        )


def test_named_shape_rejects_custom_points() -> None:
    with pytest.raises(ValidationError, match="only be supplied"):
        CanvasSpec(shape="triangle", points=[(0, 0), (1, 0), (0, 1)])
