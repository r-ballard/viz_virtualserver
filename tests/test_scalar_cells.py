import numpy as np
import pytest

from viz_virtualserver.scalar_fields.cells import cell_segments
from viz_virtualserver.scalar_fields.contours import extract_contours
from viz_virtualserver.scalar_fields.models import SampledField


@pytest.mark.parametrize('values,level', [([[0,1],[0,1]],.5), ([[2,-1],[-1,2]],0),
    ([[1,-2],[-2,1]],0), ([[1,-1],[-1,1]],0), ([[0,0],[0,1]],0),
    ([[1,1],[1,1]],1), ([[1.7e308,-1.7e308],[-1.7e308,1.7e308]],-1e308)])
def test_shared_cell_segments_equal_contour_geometry(values,level):
    field=SampledField((0,0),1,1,np.array(values,float))
    cuts=cell_segments(field,0,0,level)
    expected={tuple(sorted((a.point,b.point))) for a,b in cuts}
    actual=set()
    for c in extract_contours(field,(level,)):
        points=c.points+(c.points[:1] if c.closed else ())
        actual.update(tuple(sorted((a,b))) for a,b in zip(points,points[1:]))
    assert actual==expected


def test_adjacent_cells_share_edge_identity_and_coordinates():
    field=SampledField((-2,3),.7,.8,np.array([[0,0,0],[1,1,1]],float))
    left=cell_segments(field,0,0,.5)
    right=cell_segments(field,1,0,.5)
    common={a.key:a.point for pair in left for a in pair}
    matches=[a for pair in right for a in pair if a.key in common]
    assert len(matches)==1 and matches[0].point==common[matches[0].key]
