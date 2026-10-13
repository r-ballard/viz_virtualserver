import math

import numpy as np
import pytest

from viz_virtualserver.scalar_fields.gradients import SampledGradient
from viz_virtualserver.scalar_fields.models import SampledField


def plane(*, dx=2.0, dy=3.0, origin=(-4.0, 7.0), shape=(3, 4), scale=1.0):
    rows, columns = np.indices(shape)
    x = origin[0] + columns * dx
    y = origin[1] + rows * dy
    return SampledField(origin, dx, dy, scale * (2 * x + 3 * y))


@pytest.mark.parametrize("shape", [(2, 2), (3, 4)])
def test_plane_raw_vectors_boundary_and_direction(shape):
    field = plane(shape=shape)
    gradient = SampledGradient(field)
    slope, contour = gradient.vector_field("slope"), gradient.vector_field("contour")
    right = field.origin[0] + (shape[1] - 1) * field.dx
    top = field.origin[1] + (shape[0] - 1) * field.dy
    for x, y in ((-4, 7), (-3, 8), (right, top), (right, 7), (-4, top)):
        a, b = slope.sample(x, y), contour.sample(x, y)
        assert (a.dx, a.dy) == pytest.approx((2, 3))
        assert (b.dx, b.dy) == pytest.approx((-3, 2))
        assert a.direction == pytest.approx((2 / math.sqrt(13), 3 / math.sqrt(13)))


def test_bilinear_raw_components_before_normalization():
    # Node derivatives of x^2+3*y^2: x=(1,2,3), y=(3,6,9).
    field = SampledField((0, 0), 1, 1, np.array([[0, 1, 4], [3, 4, 7], [12, 13, 16]]))
    sample = SampledGradient(field).vector_field("slope").sample(0.25, 0.75)
    assert (sample.dx, sample.dy) == pytest.approx((1.25, 5.25))
    assert sample.direction == pytest.approx(
        (1.25 / math.hypot(1.25, 5.25), 5.25 / math.hypot(1.25, 5.25))
    )


def test_flatness_floor_and_uniform_coordinate_scaling():
    eps = np.finfo(float).eps
    for height_step, zero in ((0, True), (32 * eps, True), (64 * eps, True), (128 * eps, False)):
        field = SampledField((0, 0), 1, 1, np.array([[0, height_step]] * 2))
        gradient = SampledGradient(field)
        sample = gradient.vector_field("slope").sample(0.5, 0.5)
        assert (sample.magnitude == 0) == zero
    field = plane(origin=(0, 0), dx=1, dy=2)
    scaled = SampledField((0, 0), 10, 20, field.values)
    a = SampledGradient(field).vector_field("slope").sample(0.5, 1)
    b = SampledGradient(scaled).vector_field("slope").sample(5, 10)
    assert a.direction == pytest.approx(b.direction)
    assert a.magnitude == pytest.approx(10 * b.magnitude)


@pytest.mark.parametrize("position", [(-4.1, 8), (2.1, 8), (0, 6.9), (0, 13.1), (-5, 14)])
def test_outside_queries_are_zero(position):
    assert SampledGradient(plane()).vector_field("slope").sample(*position).direction == (0, 0)


@pytest.mark.parametrize("value", [math.nan, math.inf, True, "0"])
def test_invalid_queries_rejected(value):
    with pytest.raises(ValueError):
        SampledGradient(plane()).vector_field("slope").sample(value, 8)


def test_arrays_and_adapter_are_immutable_and_views_share_storage():
    gradient = SampledGradient(plane())
    for values in (gradient.dx_values, gradient.dy_values):
        with pytest.raises(ValueError):
            values.setflags(write=True)
    with pytest.raises(AttributeError):
        gradient.dx_values = np.zeros((2, 2))
    assert gradient.vector_field("slope").gradient is gradient
    assert gradient.vector_field("contour").gradient is gradient
    with pytest.raises(ValueError):
        gradient.vector_field("other")


def test_caps_coordinate_precision_and_derivative_overflow(monkeypatch):
    from viz_virtualserver.scalar_fields import gradients

    monkeypatch.setattr(gradients, "MAX_SAMPLES", 3)
    with pytest.raises(ValueError, match="sample"):
        SampledGradient(plane(shape=(2, 2)))
    monkeypatch.setattr(gradients, "MAX_SAMPLES", 250_000)
    with pytest.raises(ValueError, match="represent"):
        SampledGradient(SampledField((1e16, 0), 1, 1, np.ones((2, 2))))
    with pytest.raises(ValueError, match="finite|represent"):
        SampledGradient(SampledField((0, 0), 1e-300, 1, np.array([[-1e300, 1e300]] * 2)))
