import hashlib
import math
import struct

import pytest
from shapely.geometry import Polygon, box

from viz_virtualserver.fill_effects import (
    estimate_fill_candidates,
    list_fill_effects,
    render_fill_effect,
)
from viz_virtualserver.fill_effects.vector_fields import VectorSample


class Constant:
    def __init__(self, value):
        self.value = value

    def sample(self, x, y):
        return self.value


@pytest.mark.parametrize("effect", ["stroke-dots", "vortex-marks", "field-marks"])
def test_constant_field_agrees_with_static_product_and_descriptor(effect):
    class Vector:
        def sample(self, x, y):
            return VectorSample(1, 0)

    context = {"field": Vector()} if effect == "field-marks" else {}
    region = box(-12, -12, 12, 12)
    sampled = render_fill_effect(
        region,
        effect=effect,
        parameters={"density": 0.5, "spacing": 3},
        density_field=Constant(0.5),
        **context,
    )
    static = render_fill_effect(
        region, effect=effect, parameters={"density": 0.25, "spacing": 3}, **context
    )
    assert sampled == static
    assert next(e for e in list_fill_effects() if e.id == effect).supports_density_field


@pytest.mark.parametrize("value", [True, "0", None, -0.1, 1.1, math.nan, math.inf])
def test_invalid_density_samples(value):
    with pytest.raises(ValueError, match="density"):
        render_fill_effect(box(-1, -1, 1, 1), effect="stroke-dots", density_field=Constant(value))


def test_context_validation_direct_endpoints_and_unsupported():
    from viz_virtualserver.fill_effects.field_marks import render_field_marks
    from viz_virtualserver.fill_effects.stroke_dots import stroke_dots
    from viz_virtualserver.fill_effects.vortex_marks import vortex_marks

    class Vector:
        def sample(self, x, y):
            return VectorSample(1, 0)

    direct = (
        (stroke_dots, {}),
        (render_field_marks, {"field": Vector()}),
        (vortex_marks, {"center_x": 0, "center_y": 0}),
    )
    for renderer, context in direct:
        for region in (Polygon(), box(-1, -1, 1, 1)):
            for d in (0, 1):
                with pytest.raises(ValueError, match="density"):
                    renderer(
                        region,
                        spacing=8,
                        mark_length=0.5,
                        angle=0,
                        density=d,
                        density_field=object(),
                        **context,
                    )
    for effect in ("parallel-hatch", "crosshatch", "circle-rings"):
        with pytest.raises(ValueError):
            render_fill_effect(Polygon(), effect=effect, density_field=Constant(0.5))


def test_callback_order_zero_skips_and_exception_context():
    events = []

    class Density:
        def sample(self, x, y):
            events.append("density")
            return 0

    class Vector:
        def sample(self, x, y):
            pytest.fail("sampled rejected vector")

    assert (
        render_fill_effect(
            box(-1, -1, 1, 1), effect="field-marks", field=Vector(), density_field=Density()
        )
        == ()
    )
    assert events
    events.clear()
    assert (
        render_fill_effect(
            box(-1, -1, 1, 1),
            effect="field-marks",
            field=Vector(),
            density_field=Density(),
            parameters={"density": 0},
        )
        == ()
    )
    assert not events

    class Broken:
        def sample(self, x, y):
            raise RuntimeError("callback failed")

    with pytest.raises(ValueError, match="density") as caught:
        render_fill_effect(box(-1, -1, 1, 1), effect="stroke-dots", density_field=Broken())
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_plane_decisions_nested_and_fragment_ownership():
    class Plane:
        def __init__(self, offset):
            self.offset = offset

        def sample(self, x, y):
            return min(1.0, max(0.0, (x + 6) / 12 + self.offset))

    outputs = [
        render_fill_effect(
            box(-6, -6, 6, 6),
            effect="stroke-dots",
            parameters={"spacing": 3, "mark_length": 1},
            density_field=Plane(offset),
        )
        for offset in (0, 0.25)
    ]
    assert set(outputs[0]) <= set(outputs[1])
    for output, offset in zip(outputs, (0, 0.25), strict=True):
        expected = set()
        for row in range(-2, 3):
            for column in range(-2, 3):
                x, y = column * 3, row * 3
                density = min(1.0, max(0.0, (x + 6) / 12 + offset))
                numerator, denominator = density.as_integer_ratio()
                fields = ("viz-mark-density-v1", "0", str(row), str(column))
                encoded = b"".join(struct.pack(">Q", len(v.encode())) + v.encode() for v in fields)
                h = int.from_bytes(hashlib.sha256(encoded).digest(), "big")
                if h < (numerator << 256) // denominator:
                    expected.add(((max(-6.0, x - 0.5), float(y)), (min(6.0, x + 0.5), float(y))))
        assert {stroke.points for stroke in output} == expected
    region = box(-3, -1, 3, 1).difference(box(-0.5, -0.5, 0.5, 0.5))
    strokes = render_fill_effect(
        region,
        effect="stroke-dots",
        parameters={"spacing": 8, "mark_length": 6},
        density_field=Constant(0.5),
    )
    assert len(strokes) in (0, 2)
    assert estimate_fill_candidates(
        region, effect="stroke-dots", parameters={"density": 0}
    ) == estimate_fill_candidates(region, effect="stroke-dots")
