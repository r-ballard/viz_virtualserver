"""Shared marching-square crossings and saddle connectivity."""

import math
from dataclasses import dataclass

from viz_virtualserver.canvas.models import Point

from .models import SampledField


@dataclass(frozen=True, slots=True)
class Crossing:
    key: tuple
    point: Point


def cell_segments(field: SampledField, column: int, row: int, level: float):
    ny, nx = field.values.shape
    if (type(column) is not int or type(row) is not int or not 0 <= column < nx-1
            or not 0 <= row < ny-1 or not math.isfinite(level)):
        raise ValueError('invalid scalar cell or contour level')
    i, j = column, row
    corners = ((i,j),(i+1,j),(i+1,j+1),(i,j+1))
    edges = ((corners[0],corners[1]),(corners[1],corners[2]),
             (corners[3],corners[2]),(corners[0],corners[3]))
    values = field.values
    crossed = [k for k,(a,b) in enumerate(edges)
               if (values[a[1],a[0]] > level) != (values[b[1],b[0]] > level)]
    if not crossed:
        return ()
    if len(crossed) == 4:
        heights = [float(values[y,x]) for x,y in corners]
        scale = max(abs(level), *map(abs,heights), 1)
        a,b,c,d = (v/scale-level/scale for v in heights)
        determinant = a*c-b*d
        pairs = ((0,1),(2,3)) if determinant >= 0 else ((0,3),(1,2))
    else:
        pairs = (tuple(crossed),)

    def crossing(a,b):
        va,vb = float(values[a[1],a[0]]),float(values[b[1],b[0]])
        if va == level:
            key,t = ('v',*a),0.0
        elif vb == level:
            key,t = ('v',*b),1.0
        else:
            key = ('e',*a,*b)
            scale = max(abs(va),abs(vb),abs(level),1)
            t = (level/scale-va/scale)/(vb/scale-va/scale)
        point = (field.origin[0]+(a[0]+t*(b[0]-a[0]))*field.dx,
                 field.origin[1]+(a[1]+t*(b[1]-a[1]))*field.dy)
        if not all(math.isfinite(v) for v in point):
            raise ValueError('scalar crossing coordinates cannot be represented')
        return Crossing(key,point)
    result = []
    for first,second in pairs:
        a,b = crossing(*edges[first]),crossing(*edges[second])
        if a.key != b.key and a.point != b.point:
            result.append((a,b))
    return tuple(result)
