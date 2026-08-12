import pytest
from pydantic import ValidationError

from concentric.models import ConcentricPointsRequest


def test_defaults_use_clip_mode_and_one_pen() -> None:
    request = ConcentricPointsRequest()
    assert request.boundary_mode == "clip"
    assert request.pen == 1
    assert request.canvas.shape == "rectangle"


def test_invalid_pen_and_color_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ConcentricPointsRequest(pen=9)
    with pytest.raises(ValidationError):
        ConcentricPointsRequest(color="black")


def test_invalid_count_range_and_radius_bounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ConcentricPointsRequest(point_count_range=(8, 3))
    with pytest.raises(ValidationError):
        ConcentricPointsRequest(point_count_range=(0, 3))
    with pytest.raises(ValidationError):
        ConcentricPointsRequest(min_ring_radius=20, max_ring_radius=10)
