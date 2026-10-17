"""Catalogue strokes clipped to explicit unions of elevation bands."""

import math

from shapely.errors import GEOSException
from shapely.ops import unary_union

from viz_virtualserver.fill_effects import FillStroke, estimate_fill_candidates, render_fill_effect
from viz_virtualserver.fill_effects.mark_selection import MARK_DENSITY_EFFECTS, derive_density_seed
from viz_virtualserver.region_selection import (
    WeightedOption,
    choose_components,
    identify_components,
)
from viz_virtualserver.scalar_fields.contours import canonical_contour
from viz_virtualserver.scalar_fields.densities import SampledElevationDensity
from viz_virtualserver.scalar_fields.gradients import SampledGradient
from viz_virtualserver.scalar_fields.models import MAX_VERTICES, SampledField

from .component_models import ComponentFillRule, iter_rule_styles

MAX_COMPONENT_CANDIDATES = 100_000


def is_known_zero_style(style):
    return style.parameters.get("density", 1) == 0 or (
        style.density_source is not None and style.density_source.maximum == 0
    )


class _DeferredField:
    def __init__(self, get_view, direction):
        self._get_view = get_view
        self._direction = direction

    def sample(self, x, y):
        return self._get_view(self._direction).sample(x, y)


def render_band_fills(
    regions,
    rules,
    *,
    domain_seed: int | None = None,
    sampled_field: SampledField | None = None,
    max_vertices: int = MAX_VERTICES,
    coordinate_guard: float = 0,
):
    if type(max_vertices) is not int or max_vertices < 0:
        raise ValueError("fill vertex allowance must be a nonnegative integer")
    if (
        isinstance(coordinate_guard, bool)
        or not isinstance(coordinate_guard, (int, float))
        or not math.isfinite(coordinate_guard)
        or coordinate_guard < 0
    ):
        raise ValueError("fill coordinate guard must be finite and nonnegative")
    if any(style.density_source is not None for rule in rules for style in iter_rule_styles(rule)):
        if not isinstance(sampled_field, SampledField):
            raise ValueError("elevation density requires sampled terrain as a SampledField")
    indexed = {r.index: r.geometry for r in regions}
    result = []
    gradient = None
    vertices = 0
    views = {}
    density_sources = {}

    def get_view(direction):
        nonlocal gradient
        if direction not in views:
            if gradient is None:
                gradient = SampledGradient(sampled_field)
            views[direction] = gradient.vector_field(direction)
        return views[direction]

    def render_one(selected, style):
        nonlocal vertices
        context = {}
        source = style.density_source
        if source is not None:
            if domain_seed is None:
                raise ValueError("sampled density requires domain seed context")
            key = (source.minimum, source.maximum, source.invert)
            if key not in density_sources:
                density_sources[key] = SampledElevationDensity(
                    sampled_field,
                    minimum=source.minimum,
                    maximum=source.maximum,
                    invert=source.invert,
                )
            context["density_field"] = density_sources[key]
        if style.effect in MARK_DENSITY_EFFECTS:
            if style.parameters["density"] < 1 and domain_seed is None:
                raise ValueError("mark thinning requires domain seed context")
            context["density_seed"] = (
                derive_density_seed(domain_seed, style.density_seed)
                if domain_seed is not None
                else style.density_seed
            )
        if style.effect == "field-marks":
            if not isinstance(sampled_field, SampledField):
                raise ValueError("field-marks requires sampled terrain as a SampledField")
            context["field"] = _DeferredField(get_view, style.field_direction)
        clearance = style.pen_width / 2 + style.boundary_margin
        if clearance:
            # GEOS approximates round offsets with inscribed chords. Inflate the
            # radius so even those chords clear concave corners and hole corners.
            # The guard also covers the SVG exporter's nine-decimal rounding.
            guard = (
                max(1e-8, coordinate_guard, 32 * math.ulp(max(abs(v) for v in selected.bounds)))
                if not selected.is_empty
                else 1e-8
            )
            offset = clearance / math.cos(math.pi / 64) + guard
            if not math.isfinite(offset):
                raise ValueError("fill clearance is too large")
            selected = selected.buffer(-offset, quad_segs=16)
            if selected.is_empty:
                return
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
                if vertices >= max_vertices and not is_known_zero_style(choice):
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
