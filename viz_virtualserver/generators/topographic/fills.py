"""Catalogue strokes clipped to explicit unions of elevation bands."""

from shapely.errors import GEOSException
from shapely.ops import unary_union

from viz_virtualserver.fill_effects import FillStroke, render_fill_effect
from viz_virtualserver.scalar_fields.contours import canonical_contour
from viz_virtualserver.scalar_fields.gradients import SampledGradient
from viz_virtualserver.scalar_fields.models import MAX_VERTICES, SampledField


def render_band_fills(
    regions, rules, *, sampled_field: SampledField | None = None, max_vertices: int = MAX_VERTICES
):
    if type(max_vertices) is not int or max_vertices < 0:
        raise ValueError("fill vertex allowance must be a nonnegative integer")
    indexed = {r.index: r.geometry for r in regions}
    result = []
    gradient = None
    vertices = 0
    for rule in sorted(rules, key=lambda r: r.bands):
        try:
            selected = unary_union([indexed[b] for b in rule.bands])
            context = {}
            if rule.effect == "field-marks":
                if sampled_field is None:
                    raise ValueError("field-marks requires sampled terrain")
                if gradient is None:
                    gradient = SampledGradient(sampled_field)
                context["field"] = gradient.vector_field(rule.field_direction)
            strokes = render_fill_effect(
                selected, effect=rule.effect, parameters=rule.parameters, **context
            )
            canonical = []
            for stroke in strokes:
                path = canonical_contour(0, stroke.points, stroke.closed)
                if path is not None:
                    vertices += len(path.points)
                    if vertices > max_vertices:
                        raise ValueError(
                            "fill vertex cost limit exceeded; increase spacing or reduce levels"
                        )
                    canonical.append(FillStroke(path.points, path.closed))
            canonical.sort(key=lambda s: (s.points, s.closed))
            result.extend((rule.layer_id, s) for s in canonical)
        except (ValueError, GEOSException) as error:
            raise ValueError(
                f"band fill {rule.bands} {rule.effect}/{rule.layer_id}: {error}"
            ) from error
    return tuple(result)
