"""Fixed marks consume field direction, with independent lattice and clipping."""

import math

import pytest
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box


def vortex(region, **parameters):
    from viz_virtualserver.fill_effects import render_fill_effect

    return render_fill_effect(region, effect="vortex-marks", parameters=parameters)


def test_vortex_cardinal_marks_have_literal_tangent_endpoints():
    result = vortex(box(-2.5, -2.5, 2.5, 2.5), spacing=2, mark_length=.5)
    assert len(result) == 8  # The zero vector at the centre contributes no mark.
    assert {((2., -.25), (2., .25)), ((-2., -.25), (-2., .25)),
            ((-.25, 2.), (.25, 2.)), ((-.25, -2.), (.25, -2.))} <= {p.points for p in result}
    for stroke in result:
        a, b = stroke.points
        x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        assert (b[0] - a[0]) * x + (b[1] - a[1]) * y == pytest.approx(0, abs=1e-12)
        assert math.dist(a, b) == pytest.approx(.5, abs=1e-12)
        assert not stroke.closed


def test_vortex_catalogue_defaults_and_lattice_rotation():
    from viz_virtualserver.fill_effects import list_fill_effects

    effect = next(e for e in list_fill_effects() if e.id == "vortex-marks")
    assert [(p.name, p.default, p.unit) for p in effect.parameters] == [
        ("spacing", 8, "input-units"), ("mark_length", .5, "input-units"),
        ("angle", 0, "degrees"), ("center_x", 0, "input-units"),
        ("center_y", 0, "input-units"),
    ]
    region = box(-9, -9, 9, 9)
    assert vortex(region) == vortex(region, spacing=8, mark_length=.5,
                                    angle=0, center_x=0, center_y=0)
    rotated = vortex(region, angle=45)
    assert rotated and rotated != vortex(region)
    assert rotated == vortex(region, angle=225)


def test_field_renderer_ignores_magnitude_for_fixed_mark_length():
    from viz_virtualserver.fill_effects.field_marks import render_field_marks
    from viz_virtualserver.fill_effects.vector_fields import VectorSample

    class VerticalField:
        def __init__(self, magnitude):
            self.magnitude = magnitude

        def sample(self, x, y):
            return VectorSample(0., self.magnitude)

    for magnitude in (7., 700.):
        result = render_field_marks(box(-1, -1, 1, 1), spacing=8,
                                    mark_length=.5, angle=0, field=VerticalField(magnitude))
        assert tuple(p.points for p in result) == (((0., -.25), (0., .25)),)


def test_field_direction_is_independent_of_region_mask():
    region = box(-9, -9, 9, 9)
    original = vortex(region)
    masked = vortex(region.difference(box(-1, -1, 1, 1)))
    assert masked == original  # Removing the zero-vector centre changes no marks.


def test_outside_centres_and_holes_clip_in_any_mark_direction():
    assert tuple(p.points for p in vortex(box(-.2, .2, .2, .8), center_x=1)) == (
        ((0., .2), (0., .25)),
    )
    hole = Polygon(((-1, -1), (1, -1), (1, 1), (-1, 1)),
                   holes=[[(-.1, -.2), (.1, -.2), (.1, .2), (-.1, .2)]])
    separated = MultiPolygon([box(-1, -1, -.1, 1), box(.1, -1, 1, 1)])
    for region in (hole, separated):
        assert tuple(p.points for p in vortex(region, mark_length=1, center_y=1)) == (
            ((-.5, 0.), (-.1, 0.)), ((.1, 0.), (.5, 0.)),
        )
    assert vortex(box(-1, -1, 1, 1)) == ()
    assert vortex(GeometryCollection()) == ()


@pytest.mark.parametrize("parameters", [
    {"mark_length": 0}, {"mark_length": True}, {"spacing": 0}, {"angle": math.inf},
    {"center_x": math.nan}, {"center_y": "40"}, {"center_x": True}, {"unknown": 1},
])
def test_vortex_controls_validate_before_empty_region(parameters):
    with pytest.raises(ValueError, match="parameter"):
        vortex(Polygon(), **parameters)


def test_field_renderer_guards_before_evaluation_and_handles_empty_dimensions(monkeypatch):
    from viz_virtualserver.fill_effects import field_marks

    class ForbiddenField:
        def sample(self, x, y):
            pytest.fail("preflight must happen before field evaluation")

    monkeypatch.setattr(field_marks, "MAX_MARK_CANDIDATES", 8)
    with pytest.raises(ValueError, match="candidate marks"):
        field_marks.render_field_marks(box(-9, -9, 9, 9), spacing=8,
                                        mark_length=.5, angle=0, field=ForbiddenField())
    assert field_marks.render_field_marks(box(3, 0, 4, 1e9), spacing=8,
                                          mark_length=.5, angle=0, field=ForbiddenField()) == ()
    monkeypatch.setattr(field_marks, "MAX_MARK_POINTS", 1)
    with pytest.raises(ValueError, match="points"):
        field_marks.render_field_marks(box(-1, -1, 1, 1), spacing=8,
                                        mark_length=.5, angle=0, field=ForbiddenField())


def test_field_renderer_clipped_point_cap(monkeypatch):
    from viz_virtualserver.fill_effects import field_marks

    monkeypatch.setattr(field_marks, "MAX_MARK_POINTS", 2)
    separated = MultiPolygon([box(-1, -1, -.1, 1), box(.1, -1, 1, 1)])
    with pytest.raises(ValueError, match="points"):
        vortex(separated, mark_length=1, center_y=1)
    monkeypatch.setattr(field_marks, "MAX_MARK_POINTS", 4)
    assert len(vortex(separated, mark_length=1, center_y=1)) == 2


def test_generic_renderer_rejects_invalid_field_output_and_geometry():
    from viz_virtualserver.fill_effects.field_marks import render_field_marks

    class InvalidField:
        def sample(self, x, y):
            return None

    for region in (box(-1, -1, 1, 1), Point(0, 0)):
        with pytest.raises(ValueError):
            render_field_marks(region, spacing=8, mark_length=.5, angle=0, field=InvalidField())


def test_vortex_rejects_unrepresentable_mark_length():
    with pytest.raises(ValueError, match="represent"):
        vortex(box(1e10, 1, 1e10 + 10, 9), mark_length=1e-6)
