import hashlib
import struct

import pytest
from shapely import to_wkb
from shapely.geometry import MultiPolygon, Polygon, box

from viz_virtualserver.region_selection import (
    WeightedOption,
    choose_components,
    identify_components,
)


def test_canonical_identity_and_weight_fixture():
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    records = identify_components(polygon)
    canonical = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    expected = hashlib.sha256(to_wkb(canonical, byte_order=0, output_dimension=2)).hexdigest()
    assert records[0].id == expected
    fields = ("viz-component-choice-v1", "31", "0", "0,2", expected)
    encoded = b"".join(struct.pack(">Q", len(v.encode())) + v.encode() for v in fields)
    bucket = int.from_bytes(hashlib.sha256(encoded).digest(), "big") % 5
    options = (WeightedOption("blank", 2), WeightedOption("dots", 3))
    result = choose_components(records, options, domain_seed=31, component_seed=0, bands=(0, 2))
    assert result[0].choice_id == ("blank" if bucket < 2 else "dots")
    assert result == choose_components(
        records, options[::-1], domain_seed=31, component_seed=0, bands=(2, 0)
    )


def test_holes_ring_order_signed_zero_and_unrelated_members():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    holes = [[(2, 2), (3, 2), (3, 3), (2, 3)], [(6, 6), (7, 6), (7, 7), (6, 7)]]
    a = identify_components(Polygon(outer, holes))
    b = identify_components(Polygon(outer[2:] + outer[:2], [h[::-1] for h in holes[::-1]]))
    assert a[0].id == b[0].id
    assert (
        identify_components(Polygon([(-0.0, -0.0), (1, 0), (1, 1), (0, 1)]))[0].id
        == identify_components(box(0, 0, 1, 1))[0].id
    )
    tiny = box(20, 20, 20 + 1e-8, 20 + 1e-8)
    components = identify_components(MultiPolygon([tiny, a[0].geometry]))
    assert len(components) == 2 and a[0].id in [c.id for c in components]
    opts = [WeightedOption("a", 1), WeightedOption("b", 1)]
    old = choose_components(a, opts, domain_seed=3, component_seed=0, bands=(1,))
    new = choose_components(components, opts, domain_seed=3, component_seed=0, bands=(1,))
    assert old[0].choice_id == next(c.choice_id for c in new if c.component.id == a[0].id)
    assert identify_components(Polygon()) == ()
    assert len(identify_components(MultiPolygon([box(0, 0, 1, 1), box(1, 1, 2, 2)]))) == 2


def test_repeated_vertices_full_precision_and_caps(monkeypatch):
    from viz_virtualserver.region_selection import components

    p = [(0, 0), (1, 0), (1, 0), (1, 1), (0, 1)]
    assert (
        identify_components(Polygon(p))[0].id == identify_components(Polygon(p[2:] + p[:2] + [p[2]]))[0].id
    )
    assert (
        identify_components(box(0, 0, 1, 1))[0].id
        != identify_components(box(0, 0, 1.0000000000000002, 1))[0].id
    )
    monkeypatch.setattr(components, "MAX_COMPONENT_COORDINATES", 4)
    with pytest.raises(ValueError, match="coordinate"):
        identify_components(box(0, 0, 1, 1))
    monkeypatch.setattr(components, "MAX_COMPONENT_COORDINATES", 1_000_000)
    monkeypatch.setattr(components, "MAX_COMPONENTS", 1)
    with pytest.raises(ValueError, match="component"):
        identify_components(MultiPolygon([box(0, 0, 1, 1), box(2, 0, 3, 1)]))


def test_invalid_geometry_and_digest_collision(monkeypatch):
    from viz_virtualserver.region_selection import components

    with pytest.raises(ValueError):
        identify_components(Polygon([(0, 0), (1, 1), (0, 1), (1, 0)]))
    monkeypatch.setattr(components, "_digest", lambda value: "collision")
    with pytest.raises(ValueError, match="collision"):
        identify_components(MultiPolygon([box(0, 0, 1, 1), box(2, 0, 3, 1)]))


@pytest.mark.parametrize("weight", [0, -1, True, 1.0, 1_000_001])
def test_invalid_options(weight):
    with pytest.raises(ValueError):
        WeightedOption("x", weight)
