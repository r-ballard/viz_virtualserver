import pytest
from shapely.geometry import LineString, Polygon

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.generators.truchet.multiscale_service import TruchetMultiscaleDomainAlgorithm


def generate(domains, *, params=None, layers=("truchet-curves",), seeds=None):
    canvas = CanvasGeometry("square", 80, 80, ((0, 0), (80, 0), (80, 80), (0, 80)), "edge:0")
    design_pass = DesignPass("tiles", "truchet-multiscale", tuple(d.id for d in domains) or ("p",),
                             params or {}, tuple(LogicalLayer(i) for i in layers))
    context = AlgorithmContext(1, 2, seeds or {d.id: 31 for d in domains}, (), (), (), {})
    return TruchetMultiscaleDomainAlgorithm().generate(
        canvas=canvas, domains=domains, design_pass=design_pass, context=context)


@pytest.mark.parametrize("vertices", [
    ((0, 0), (80, 0), (80, 80), (0, 80)),
    ((-20, -30), (60, -30), (20, 30)),
    ((0, 0), (80, 0), (80, 80), (40, 25), (0, 80)),
])
def test_service_reproducibility_ownership_and_containment(vertices):
    domain = PolygonDomain("p", vertices)
    result = generate((domain,))
    assert result == generate((domain,))
    assert result.paths and not result.derived_domains
    for p in result.paths:
        assert p.domain_id == "p" and p.layer_id == "truchet-curves"
        assert p.coordinate_frame == "domain" and p.producing_pass_id == "tiles"
        assert Polygon(vertices).buffer(1e-8).covers(LineString(
            p.points + (p.points[:1] if p.closed else ())))


def test_domain_seeds_are_independent_and_owned():
    vertices = ((0, 0), (40, 0), (40, 40), (0, 40))
    a, b = PolygonDomain("a", vertices), PolygonDomain("b", vertices)
    result = generate((a, b), seeds={"a": 31, "b": 71})
    assert tuple(p for p in result.paths if p.domain_id == "a") == generate((a,)).paths
    pa = tuple(p.points for p in result.paths if p.domain_id == "a")
    pb = tuple(p.points for p in result.paths if p.domain_id == "b")
    assert pa != pb


@pytest.mark.parametrize("layers", [(), ("wrong",), ("truchet-curves", "extra")])
def test_invalid_layers_rejected(layers):
    with pytest.raises(ValueError, match="truchet-curves"):
        generate((), layers=layers)


@pytest.mark.parametrize("params", [{"arc_a": 0.2}, {"tile_size": 10}, {"max_depth": "3"}])
def test_invalid_parameters_rejected_before_domains(params):
    with pytest.raises(ValueError):
        generate((), params=params)
