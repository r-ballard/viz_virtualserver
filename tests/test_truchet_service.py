import pytest
from shapely.geometry import LineString, Polygon

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.generators.truchet.service import TruchetDomainAlgorithm


def generate(domains, *, params=None, layers=("truchet-curves",)):
    canvas = CanvasGeometry("square", 50, 50, ((0, 0), (50, 0), (50, 50), (0, 50)), "edge:0")
    p = DesignPass(
        "tiles",
        "truchet",
        tuple(d.id for d in domains),
        params or {},
        tuple(LogicalLayer(i) for i in layers),
    )
    context = AlgorithmContext(1, 2, {d.id: 7 for d in domains}, (), (), (), {})
    return TruchetDomainAlgorithm().generate(
        canvas=canvas, domains=domains, design_pass=p, context=context
    )


@pytest.mark.parametrize(
    "vertices",
    [
        ((0, 0), (50, 0), (50, 50), (0, 50)),
        ((-20, -30), (30, -30), (5, 15)),
        ((0, 0), (50, 0), (50, 50), (25, 20), (0, 50)),
    ],
)
def test_service_is_reproducible_neutral_and_whole_segments_are_contained(vertices):
    domain = PolygonDomain("panel", vertices)
    result = generate((domain,))
    assert result == generate((domain,))
    assert result.paths and not result.derived_domains
    for p in result.paths:
        assert p.domain_id == "panel" and p.layer_id == "truchet-curves"
        assert p.coordinate_frame == "domain"
        assert p.producing_pass_id == "tiles"
        pts = p.points + (p.points[:1] if p.closed else ())
        assert Polygon(vertices).buffer(1e-9).covers(LineString(pts))


def test_domains_are_independent_and_translation_preserves_relative_geometry():
    a = PolygonDomain("a", ((0, 0), (30, 0), (30, 30), (0, 30)))
    b = PolygonDomain("b", ((-20, -30), (10, -30), (10, 0), (-20, 0)))
    result = generate((a, b))
    assert tuple(p for p in result.paths if p.domain_id == "a") == generate((a,)).paths
    pa = tuple(p for p in result.paths if p.domain_id == "a")
    pb = tuple(p for p in result.paths if p.domain_id == "b")
    assert len(pa) == len(pb)
    for x, y in zip(pa, pb, strict=True):
        assert x.closed == y.closed
        for (ax, ay), (bx, by) in zip(x.points, y.points, strict=True):
            assert (ax - 20, ay - 30) == pytest.approx((bx, by))


@pytest.mark.parametrize("layers", [(), ("wrong",), ("truchet-curves", "extra")])
def test_wrong_layers_rejected(layers):
    d = PolygonDomain("a", ((0, 0), (10, 0), (10, 10), (0, 10)))
    with pytest.raises(ValueError, match="truchet-curves"):
        generate((d,), layers=layers)
