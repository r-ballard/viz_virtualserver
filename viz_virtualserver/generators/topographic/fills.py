"""Catalogue strokes clipped to explicit unions of elevation bands."""

from shapely.errors import GEOSException
from shapely.ops import unary_union

from viz_virtualserver.fill_effects import FillStroke, estimate_fill_candidates, render_fill_effect
from viz_virtualserver.region_selection import (
    WeightedOption,
    choose_components,
    identify_components,
)
from viz_virtualserver.scalar_fields.contours import canonical_contour
from viz_virtualserver.scalar_fields.gradients import SampledGradient
from viz_virtualserver.scalar_fields.models import MAX_VERTICES, SampledField

from .component_models import ComponentFillRule

MAX_COMPONENT_CANDIDATES = 100_000


def render_band_fills(
    regions,
    rules,
    *,
    domain_seed: int | None = None,
    sampled_field: SampledField | None = None,
    max_vertices: int = MAX_VERTICES,
):
    if type(max_vertices) is not int or max_vertices < 0:
        raise ValueError("fill vertex allowance must be a nonnegative integer")
    indexed = {r.index: r.geometry for r in regions}
    result = []
    gradient = None
    vertices = 0

    def render_one(selected, style):
        nonlocal gradient, vertices
        context = {}
        if style.effect == "field-marks":
            if sampled_field is None:
                raise ValueError("field-marks requires sampled terrain")
            if gradient is None:
                gradient = SampledGradient(sampled_field)
            context["field"] = gradient.vector_field(style.field_direction)
        strokes = render_fill_effect(
            selected, effect=style.effect, parameters=style.parameters, **context
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
        result.extend((style.layer_id, s) for s in canonical)

    for rule in sorted(rules, key=lambda r: r.bands):
        label = ""
        try:
            selected = unary_union([indexed[b] for b in rule.bands])
            if not isinstance(rule, ComponentFillRule):
                label = f"{rule.effect}/{rule.layer_id}"
                render_one(selected, rule)
                continue
            decisions = choose_components(
                identify_components(selected) if not selected.is_empty else (),
                tuple(WeightedOption(c.id, c.weight) for c in rule.component_choices),
                domain_seed=domain_seed,
                component_seed=rule.component_seed,
                bands=rule.bands,
            )
            choices = {c.id: c for c in rule.component_choices}
            candidates = 0
            for decision in decisions:
                choice = choices[decision.choice_id]
                label = f"component {decision.component.id} choice {choice.id}"
                if choice.effect is None:
                    continue
                if vertices >= max_vertices:
                    raise ValueError("component fill vertex allowance exhausted; increase spacing")
                candidates += estimate_fill_candidates(
                    decision.component.geometry, effect=choice.effect, parameters=choice.parameters
                )
                if candidates > MAX_COMPONENT_CANDIDATES:
                    raise ValueError("component fill candidate budget exceeded; increase spacing")
                render_one(decision.component.geometry, choice)
        except (ValueError, GEOSException) as error:
            raise ValueError(f"band fill {rule.bands} {label}: {error}") from error
    return tuple(result)
