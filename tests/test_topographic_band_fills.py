import pytest
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from tests.test_topographic_service import generate, SQUARE, PARAMS
from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.generators.topographic.fills import render_band_fills
from viz_virtualserver.generators.topographic.models import TopographicParameters
from viz_virtualserver.scalar_fields.regions import BandRegion


RULE = {'bands':[0,2,4,6,8],'effect':'stroke-dots',
        'parameters':{'spacing':3,'mark_length':.5},'layer_id':'fill'}


def fill_paths(result):
    return tuple(p for p in result.paths if p.layer_id=='fill')


def test_service_fills_and_simplification_are_independent():
    params={**PARAMS,'band_fills':[RULE]}
    a=generate((SQUARE,),params=params,layers=('contours','index','fill'))
    b=generate((SQUARE,),params={**params,'simplify_tolerance':.5},layers=('contours','index','fill'))
    assert fill_paths(a) and fill_paths(a)==fill_paths(b)
    assert all(p.semantic_path.feature_role=='topographic-fill' for p in fill_paths(a))
    assert all(Polygon(SQUARE.vertices).buffer(1e-9).covers(LineString(p.points)) for p in fill_paths(a))


def test_translation_and_rule_order_preserve_fill_phase():
    params={**PARAMS,'band_fills':[RULE]}
    a=generate((SQUARE,),params=params,layers=('contours','index','fill'))
    d=PolygonDomain('a',tuple((x-30,y-20) for x,y in SQUARE.vertices))
    b=generate((d,),params=params,layers=('contours','index','fill'))
    assert len(fill_paths(a))==len(fill_paths(b))
    for p,q in zip(fill_paths(a),fill_paths(b),strict=True):
        for (x,y),point in zip(p.points,q.points,strict=True):
            assert point==pytest.approx((x-30,y-20))


@pytest.mark.parametrize('effect',['parallel-hatch','crosshatch','circle-rings','stroke-dots','vortex-marks'])
def test_all_catalogue_effects_respect_holes_and_adjacent_band_union(effect):
    left=Polygon(((0,0),(10,0),(10,20),(0,20)))
    right=Polygon(((10,0),(20,0),(20,20),(10,20)),holes=[((12,8),(18,8),(18,14),(12,14))])
    regions=(BandRegion(0,None,.5,left),BandRegion(1,.5,None,right))
    rules=TopographicParameters.model_validate({'band_fills':[{
        'bands':[1,0],'effect':effect,'layer_id':'fill'}]}).band_fills
    strokes=render_band_fills(regions,rules)
    assert strokes
    selected=unary_union([left,right])
    for layer,s in strokes:
        assert layer=='fill'
        assert selected.buffer(1e-9).covers(LineString(s.points+(s.points[:1] if s.closed else ())))


def test_layer_errors_and_invalid_empty_band_rejected_before_sampling(monkeypatch):
    from viz_virtualserver.generators.topographic import service
    monkeypatch.setattr(service,'sample_field',lambda *a,**kw:pytest.fail('sampled'))
    for layers in (('contours','index'),('contours','index','unused'),('fill','index','other')):
        with pytest.raises(ValueError):
            generate((SQUARE,),params={**PARAMS,'band_fills':[RULE]},layers=layers)
    bad={**RULE,'parameters':{'spacing':0}}
    with pytest.raises(ValueError):
        generate((SQUARE,),params={**PARAMS,'band_fills':[bad]},layers=('contours','index','fill'))


def test_zero_rules_skip_region_extraction_and_combined_budget(monkeypatch):
    from viz_virtualserver.generators.topographic import service
    original=service.extract_band_regions
    monkeypatch.setattr(service,'extract_band_regions',lambda *a,**kw:pytest.fail('regions'))
    assert generate((SQUARE,),params=PARAMS).paths
    monkeypatch.setattr(service,'extract_band_regions',original)
    baseline=generate((SQUARE,),params=PARAMS)
    monkeypatch.setattr(service,'MAX_VERTICES',sum(len(p.points) for p in baseline.paths))
    with pytest.raises(ValueError,match='vertex'):
        generate((SQUARE,),params={**PARAMS,'band_fills':[RULE]},layers=('contours','index','fill'))

def test_fill_precision_loss_is_rejected_before_sampling(monkeypatch):
    from viz_virtualserver.generators.topographic import service
    domain=PolygonDomain('large',tuple((x+1e16,y) for x,y in SQUARE.vertices))
    monkeypatch.setattr(service,'sample_field',lambda *a,**kw:pytest.fail('sampled'))
    with pytest.raises(ValueError,match='represent'):
        generate((domain,),params={**PARAMS,'band_fills':[RULE]},layers=('contours','index','fill'))
