"""Marching squares with shared crossings and deterministic saddle decisions."""

import math

import numpy as np

from .models import MAX_SEGMENTS, Contour, SampledField


def canonical_contour(level, points, closed):
    points = tuple(p for i, p in enumerate(points) if i == 0 or p != points[i-1])
    if closed and len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(set(points)) < (3 if closed else 2):
        return None
    if closed:
        # Minimum coordinate determines rotation; compare both orientations.
        i = min(range(len(points)), key=points.__getitem__)
        forward = points[i:]+points[:i]
        reverse = (forward[0],)+tuple(reversed(forward[1:]))
        points = min(forward, reverse)
    else:
        points = min(points, tuple(reversed(points)))
    return Contour(level, points, closed)


def extract_contours(field: SampledField, levels: tuple[float, ...], *,
                     max_segments: int = MAX_SEGMENTS) -> tuple[Contour, ...]:
    if (any(not math.isfinite(v) for v in levels)
            or any(a >= b for a, b in zip(levels, levels[1:]))
            or type(max_segments) is not int or max_segments < 1):
        raise ValueError('contour levels must increase and segment budget must be positive')
    values = field.values
    ny, nx = values.shape
    result = []
    segment_count = 0
    for level in levels:
        above = values > level  # Equality is always classified below.
        codes = (above[:-1, :-1]*8 + above[:-1, 1:]*4
                 + above[1:, 1:]*2 + above[1:, :-1])
        rows, cols = np.nonzero((codes != 0) & (codes != 15))
        points, links, edges = {}, {}, set()

        def crossing(a, b):
            # Vertex identities unify crossings exactly at a level vertex.
            va, vb = float(values[a[1], a[0]]), float(values[b[1], b[0]])
            if va == level:
                key, t = ('v', *a), 0.0
            elif vb == level:
                key, t = ('v', *b), 1.0
            else:
                key = ('e', *a, *b)
                # Rescaling avoids overflow of vb-va for finite extreme heights.
                scale = max(abs(va), abs(vb), abs(level), 1)
                t = (level/scale-va/scale)/(vb/scale-va/scale)
            if key not in points:
                points[key] = (field.origin[0]+(a[0]+t*(b[0]-a[0]))*field.dx,
                               field.origin[1]+(a[1]+t*(b[1]-a[1]))*field.dy)
            return key

        for j, i in zip(rows.tolist(), cols.tolist(), strict=True):
            corners = ((i, j), (i+1, j), (i+1, j+1), (i, j+1))
            edge_corners = ((corners[0], corners[1]), (corners[1], corners[2]),
                            (corners[3], corners[2]), (corners[0], corners[3]))
            crossed = [k for k, (a, b) in enumerate(edge_corners)
                       if above[a[1], a[0]] != above[b[1], b[0]]]
            if len(crossed) == 4:
                shifted = [float(values[y, x])-level for x, y in corners]
                scale = max(map(abs, shifted))
                a, b, c, d = (v/scale for v in shifted)
                determinant = a*c-b*d
                # At determinant zero, choose top-right / bottom-left consistently.
                pairs = ((0, 1), (2, 3)) if determinant >= 0 else ((0, 3), (1, 2))
            else:
                pairs = (tuple(crossed),)
            for first, second in pairs:
                a = crossing(*edge_corners[first])
                b = crossing(*edge_corners[second])
                if a == b or points[a] == points[b]:
                    continue
                edge = tuple(sorted((a, b)))
                if edge in edges:
                    continue
                segment_count += 1
                if segment_count > max_segments:
                    raise ValueError('contour segment cost limit exceeded; increase spacing')
                edges.add(edge)
                links.setdefault(a, set()).add(b)
                links.setdefault(b, set()).add(a)

        # Track edges rather than nodes: an exact-level saddle may have degree four.
        unused = set(edges)

        def walk(start, neighbor):
            chain = [start]
            current, nxt = start, neighbor
            while True:
                unused.remove(tuple(sorted((current, nxt))))
                chain.append(nxt)
                current = nxt
                if current == start or len(links[current]) != 2:
                    break
                options = [n for n in links[current] if tuple(sorted((current, n))) in unused]
                if not options:
                    break
                nxt = min(options)
            contour = canonical_contour(level, tuple(points[k] for k in chain),
                                        chain[-1] == start)
            if contour is not None:
                result.append(contour)

        for start in sorted(k for k in links if len(links[k]) != 2):
            for neighbor in sorted(links[start]):
                if tuple(sorted((start, neighbor))) in unused:
                    walk(start, neighbor)
        while unused:
            start, neighbor = min(unused)
            walk(start, neighbor)
    return tuple(sorted(result, key=lambda c: (c.level, c.points, c.closed)))
