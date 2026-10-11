import numpy as np
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from viz_virtualserver.canvas.models import PolygonDomain
from viz_virtualserver.scalar_fields.models import SampledField
from viz_virtualserver.scalar_fields.regions import extract_band_regions


def field(values):
    return SampledField((0,0),1,1,np.array(values,float))


def target(size=2):
    return PolygonDomain('p',((0,0),(size,0),(size,size),(0,size)))


def assert_partition(regions, domain):
    polygon=Polygon(domain.vertices)
    assert all(r.geometry.is_valid for r in regions)
    assert unary_union([r.geometry for r in regions]).symmetric_difference(polygon).area < 1e-10
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            assert a.geometry.intersection(b.geometry).area < 1e-12


def test_plane_exact_strips_and_stable_empty_indices():
    regions=extract_band_regions(field([[0,1,2]]*3),(-1,.5,1.5,3),target())
    assert [r.index for r in regions]==list(range(5))
    assert [r.geometry.area for r in regions]==pytest.approx([0,1,2,1,0])
    assert regions[0].lower is None and regions[-1].upper is None
    assert_partition(regions,target())


@pytest.mark.parametrize('values,levels',[
    ([[0,0,0],[0,3,0],[0,0,0]],(.5,1.5)),
    ([[3,3,3],[3,0,3],[3,3,3]],(.5,1.5)),
    ([[2,-1],[-1,2]],(-.5,0,.5)),
    ([[1,-2],[-2,1]],(-1,0,.5)),
    ([[1,-1],[-1,1]],(0,)),
    ([[0,0,1],[0,0,1],[1,1,1]],(0,.5)),
    ([[7,7],[7,7]],(0,7,8)),
])
def test_hills_depressions_saddles_plateaus_partition(values,levels):
    d=target(len(values)-1)
    result=extract_band_regions(field(values),levels,d)
    assert_partition(result,d)


def test_peak_bands_have_holes_and_tiny_island_is_not_deleted():
    f=field([[0,0,0],[0,1,0],[0,0,0]])
    regions=extract_band_regions(f,(.5,.9999999),target())
    assert len(regions[0].geometry.interiors)==1
    assert 0 < regions[-1].geometry.area < 1e-10


def test_concave_winding_and_translated_fields():
    f=field([[0,1,2]]*3)
    vertices=((0,0),(2,0),(2,2),(1,.5),(0,2))
    d=PolygonDomain('c',vertices)
    rs=extract_band_regions(f,(.5,1.5),d)
    assert_partition(rs,d)
    reverse=extract_band_regions(f,(.5,1.5),PolygonDomain('c',vertices[::-1]))
    assert all(a.geometry.equals(b.geometry) for a,b in zip(rs,reverse,strict=True))
    moved=SampledField((-4,-5),1,1,f.values)
    translated=PolygonDomain('c',tuple((x-4,y-5) for x,y in vertices))
    assert_partition(extract_band_regions(moved,(.5,1.5),translated),translated)


def test_extent_and_budgets_fail_clearly(monkeypatch):
    from viz_virtualserver.scalar_fields import regions
    with pytest.raises(ValueError,match='sampled'):
        extract_band_regions(field([[0,1],[0,1]]),(.5,),target(2))
    monkeypatch.setattr(regions,'MAX_REGION_WORK',1)
    with pytest.raises(ValueError,match='work'):
        extract_band_regions(field([[0,1,2]]*3),(.5,),target())
    monkeypatch.setattr(regions,'MAX_REGION_WORK',12_000_000)
    monkeypatch.setattr(regions,'MAX_REGION_COORDINATES',1)
    with pytest.raises(ValueError,match='coordinate'):
        extract_band_regions(field([[0,1,2]]*3),(.5,),target())
