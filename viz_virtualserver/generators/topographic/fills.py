"""Catalogue strokes clipped to explicit unions of elevation bands."""

from shapely.errors import GEOSException
from shapely.ops import unary_union

from viz_virtualserver.fill_effects import FillStroke, render_fill_effect
from viz_virtualserver.scalar_fields.contours import canonical_contour


def render_band_fills(regions, rules):
    indexed = {r.index:r.geometry for r in regions}
    result = []
    for rule in sorted(rules,key=lambda r:r.bands):
        try:
            selected = unary_union([indexed[b] for b in rule.bands])
            strokes = render_fill_effect(selected,effect=rule.effect,parameters=rule.parameters)
            canonical = []
            for stroke in strokes:
                path = canonical_contour(0,stroke.points,stroke.closed)
                if path is not None:
                    canonical.append(FillStroke(path.points,path.closed))
            canonical.sort(key=lambda s:(s.points,s.closed))
            result.extend((rule.layer_id,s) for s in canonical)
        except (ValueError,GEOSException) as error:
            raise ValueError(f'band fill {rule.bands} {rule.effect}/{rule.layer_id}: {error}') from error
    return tuple(result)
