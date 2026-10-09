import pytest
from shapely.geometry import LineString, Polygon

from viz_virtualserver.canvas.design import DesignPass, LogicalLayer
from viz_virtualserver.canvas.geometry import CanvasGeometry
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.canvas.runner import AlgorithmContext
from viz_virtualserver.generators.topographic.service import TopographicDomainAlgorithm


def generate(domains, *, params=None, layers=('contours', 'index'), seed=31, transforms=None):
    p = DesignPass('map', 'topographic', tuple(d.id for d in domains),
                   params or {}, tuple(LogicalLayer(v) for v in layers))
    ctx = AlgorithmContext(1, 2, {d.id: seed for d in domains}, (), (), (), transforms or {})
    return TopographicDomainAlgorithm().generate(
        canvas=CanvasGeometry('square', 20, 20, ((0, 0), (20, 0), (20, 20), (0, 20)), 'edge:0'),
        domains=domains, design_pass=p, context=ctx)


SQUARE = PolygonDomain('a', ((0, 0), (20, 0), (20, 20), (0, 20)))
PARAMS = dict(terrain_scale=8, sample_spacing=1, contour_count=8, terrain_smoothing=.5)


def test_service_reproducible_neutral_and_contained():
    result = generate((SQUARE,), params=PARAMS)
    assert result == generate((SQUARE,), params=PARAMS)
    assert result != generate((SQUARE,), params=PARAMS, seed=32)
    assert result.paths and not result.derived_domains
    assert {p.layer_id for p in result.paths} == {'contours', 'index'}
    for p in result.paths:
        assert p.domain_id == 'a' and p.coordinate_frame == 'domain'
        assert p.producing_pass_id == 'map'
        assert Polygon(SQUARE.vertices).buffer(1e-9).covers(
            LineString(p.points+(p.points[:1] if p.closed else ())))


def test_translation_order_winding_and_independence():
    b = PolygonDomain('b', tuple((x-40, y-30) for x, y in SQUARE.vertices))
    alone = generate((SQUARE,), params=PARAMS)
    together = generate((b, SQUARE), params=PARAMS)
    assert tuple(p for p in together.paths if p.domain_id == 'a') == alone.paths
    shifted = generate((PolygonDomain('a', b.vertices),), params=PARAMS)
    assert len(shifted.paths) == len(alone.paths)
    for a, c in zip(alone.paths, shifted.paths, strict=True):
        assert a.closed == c.closed and a.layer_id == c.layer_id
        for pa, pc in zip(a.points, c.points, strict=True):
            assert pc == pytest.approx((pa[0]-40, pa[1]-30))
    reversed_result = generate((PolygonDomain('a', SQUARE.vertices[::-1]),), params=PARAMS)
    assert reversed_result == alone


def test_concave_polygon_is_contained():
    d = PolygonDomain('c', ((0, 0), (20, 0), (20, 20), (10, 8), (0, 20)))
    for p in generate((d,), params=PARAMS).paths:
        assert Polygon(d.vertices).buffer(1e-9).covers(
            LineString(p.points+(p.points[:1] if p.closed else ())))


@pytest.mark.parametrize('layers', [(), ('a',), ('a', 'a'), ('a', 'b', 'c')])
def test_exactly_two_distinct_layers(layers):
    with pytest.raises(ValueError, match='two.*layer'):
        generate((SQUARE,), params=PARAMS, layers=layers)


def test_index_numbering_and_empty_channels():
    assert {p.layer_id for p in generate((SQUARE,), params={**PARAMS, 'index_every': 1}).paths}
    assert all(p.layer_id == 'index' for p in
               generate((SQUARE,), params={**PARAMS, 'index_every': 1}).paths)
    assert all(p.layer_id == 'contours' for p in
               generate((SQUARE,), params={**PARAMS, 'index_every': 9}).paths)
    with pytest.raises(ValueError, match='composition'):
        generate((SQUARE,), params=PARAMS, transforms={'a': object()})


def test_invalid_parameters_and_pass_wide_budget(monkeypatch):
    from viz_virtualserver.generators.topographic import service
    with pytest.raises(ValueError):
        generate((SQUARE,), params={'sample_spacing': 1e-300})
    count = sum(len(p.points) for p in generate((SQUARE,), params=PARAMS).paths)
    monkeypatch.setattr(service, 'MAX_VERTICES', count)
    assert generate((SQUARE,), params=PARAMS).paths
    with pytest.raises(ValueError, match='b.*vertex'):
        generate((SQUARE, PolygonDomain('b', SQUARE.vertices)), params=PARAMS)
