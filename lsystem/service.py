from __future__ import annotations

from viz_canvas.logical_layers import (
    DynamicLayerSpec,
    MatchSpec,
    ProjectedDesign,
    ProjectionRule,
    ProjectionSpec,
    SemanticAttributeSchema,
    SemanticPath,
    project_paths,
)

from .geometry import (
    Bounds,
    GenerationGeometry,
    commands_to_geometry,
    tagged_commands_to_geometries,
    tagged_commands_to_semantic_paths,
    union_bounds,
)
from .grammar import iter_generations, iter_tagged_generations
from .layers import layer_for_generation, resolve_pen_layers
from .models import LSystemRequest, PenLayerSpec

LSYSTEM_ATTRIBUTE_SCHEMA = SemanticAttributeSchema(("birth_generation", "visible_generation"))
LSYSTEM_BIRTH_PROJECTION = ProjectionSpec(
    "lsystem-birth-generation",
    (ProjectionRule(
        MatchSpec(feature_role="segment"),
        dynamic=DynamicLayerSpec("birth-generation", "Birth generation", ("birth_generation",)),
    ),),
)


def generate_lsystem_semantics(
    request: LSystemRequest,
    *,
    domain_id: str,
    generation: int | None = None,
    growth_mode: str | None = None,
) -> tuple[SemanticPath, ...]:
    """Return segments visible in one generation, without overlaying earlier snapshots.

    Cumulative growth includes birth generations 1 through the selected generation;
    delta growth includes only that generation's births. Axiom lineage (birth 0)
    is excluded, matching the established growth-page contract. Coordinates retain
    the turtle's intrinsic frame; the caller owns the enclosing domain and surface.
    """

    generation = request.generations if generation is None else generation
    if type(generation) is not int or not 0 <= generation <= request.generations:
        raise ValueError("generation must be an integer from 0 through request.generations")
    growth_mode = request.growth_mode if growth_mode is None else growth_mode
    if growth_mode not in {"cumulative", "delta"}:
        raise ValueError("growth_mode must be 'cumulative' or 'delta'")
    if not isinstance(domain_id, str) or not domain_id.strip():
        raise ValueError("domain_id must be a non-empty string")

    commands = next(
        commands
        for visible_generation, commands in iter_tagged_generations(
            request.axiom, request.rules, generation, request.max_symbols,
        )
        if visible_generation == generation
    )
    paths = tagged_commands_to_semantic_paths(
        commands,
        domain_id=domain_id,
        generation=generation,
        step=request.step,
        angle_degrees=request.angle,
        initial_heading_degrees=request.initial_heading,
        draw_symbols=set(request.draw_symbols),
        move_symbols=set(request.move_symbols),
    )
    return tuple(
        path for path in paths
        if 1 <= path.attributes["birth_generation"] <= generation
        and (growth_mode == "cumulative" or path.attributes["birth_generation"] == generation)
    )


def generate_lsystem_design(
    request: LSystemRequest,
    *,
    domain_id: str,
    generation: int | None = None,
    growth_mode: str | None = None,
    projection: ProjectionSpec = LSYSTEM_BIRTH_PROJECTION,
) -> ProjectedDesign:
    """Project one growth snapshot into neutral logical layers, independent of pens."""

    paths = generate_lsystem_semantics(
        request, domain_id=domain_id, generation=generation, growth_mode=growth_mode,
    )
    return project_paths(paths, LSYSTEM_ATTRIBUTE_SCHEMA, projection)


def generate_lsystem(request: LSystemRequest) -> dict:
    """Expand an L-system and return precomputed polyline geometry grouped by plotter pen."""

    layer_specs = resolve_pen_layers(request.generations, request.pen_layers)
    geometries: list[GenerationGeometry] = []

    for generation, commands in iter_generations(
        request.axiom,
        request.rules,
        request.generations,
        request.max_symbols,
    ):
        geometries.append(
            commands_to_geometry(
                commands,
                generation=generation,
                step=request.step,
                angle_degrees=request.angle,
                initial_heading_degrees=request.initial_heading,
                draw_symbols=set(request.draw_symbols),
                move_symbols=set(request.move_symbols),
            )
        )

    overall_bounds = union_bounds([geometry.bounds for geometry in geometries])
    layer_payloads = [_empty_layer_payload(layer) for layer in layer_specs]
    payload_by_pen = {payload["pen"]: payload for payload in layer_payloads}

    total_segments = 0
    for geometry in geometries:
        layer = layer_for_generation(geometry.generation, layer_specs)
        total_segments += geometry.segment_count
        payload_by_pen[layer.pen]["generations"].append(
            {
                "generation": geometry.generation,
                "symbol_count": geometry.symbol_count,
                "path_count": len(geometry.paths),
                "segment_count": geometry.segment_count,
                "paths": geometry.paths,
            }
        )

    return {
        "axiom": request.axiom,
        "generation_count": request.generations + 1,
        "max_generation": request.generations,
        "step": request.step,
        "angle": request.angle,
        "initial_heading": request.initial_heading,
        "bounds": {
            "min_x": overall_bounds.min_x,
            "min_y": overall_bounds.min_y,
            "max_x": overall_bounds.max_x,
            "max_y": overall_bounds.max_y,
            "width": overall_bounds.width,
            "height": overall_bounds.height,
        },
        "total_segments": total_segments,
        "layers": layer_payloads,
    }


def generate_lsystem_growth_pages(
    request: LSystemRequest,
    *,
    generation_numbers: tuple[int, ...],
    growth_mode: str | None = None,
) -> dict[int, dict]:
    """Build independently bounded generation pages with growth-age layers."""

    growth_mode = growth_mode or request.growth_mode
    if growth_mode not in {"cumulative", "delta"}:
        raise ValueError("growth_mode must be 'cumulative' or 'delta'")

    requested = set(generation_numbers)
    pages: dict[int, dict] = {}
    layer_specs = resolve_pen_layers(request.generations, request.pen_layers)
    for generation, commands in iter_tagged_generations(
        request.axiom,
        request.rules,
        request.generations,
        request.max_symbols,
    ):
        if generation not in requested:
            continue
        geometries = tagged_commands_to_geometries(
            commands,
            generation=generation,
            step=request.step,
            angle_degrees=request.angle,
            initial_heading_degrees=request.initial_heading,
            draw_symbols=set(request.draw_symbols),
            move_symbols=set(request.move_symbols),
        )
        selected_births = [
            birth_generation
            for birth_generation in geometries
            if birth_generation >= 1
            and (growth_mode == "cumulative" or birth_generation == generation)
        ]
        selected_geometries = [geometries[birth] for birth in selected_births]
        bounds = union_bounds([geometry.bounds for geometry in selected_geometries])
        growth_by_pen: dict[int, tuple[PenLayerSpec, list[tuple[int, GenerationGeometry]]]] = {}
        for birth_generation in selected_births:
            layer = layer_for_generation(birth_generation, layer_specs)
            if layer.pen not in growth_by_pen:
                growth_by_pen[layer.pen] = (layer, [])
            growth_by_pen[layer.pen][1].append(
                (birth_generation, geometries[birth_generation])
            )
        pages[generation] = {
            "bounds": _bounds_payload(bounds),
            "layers": [
                _growth_layer_payload(layer, growth)
                for layer, growth in growth_by_pen.values()
            ],
        }

    missing = [generation for generation in generation_numbers if generation not in pages]
    if missing:
        raise ValueError(f"generations are not present in result: {missing}")
    return {generation: pages[generation] for generation in generation_numbers}


def _empty_layer_payload(layer: PenLayerSpec) -> dict:
    return {
        "pen": layer.pen,
        "color": layer.color,
        "start_generation": layer.start_generation,
        "end_generation": layer.end_generation,
        "generations": [],
    }


def _growth_layer_payload(
    layer: PenLayerSpec,
    growth: list[tuple[int, GenerationGeometry]],
) -> dict:
    return {
        "pen": layer.pen,
        "color": layer.color,
        "start_generation": layer.start_generation,
        "end_generation": layer.end_generation,
        "generations": [
            {
                "generation": birth_generation,
                "page_generation": geometry.generation,
                "drawable_symbol_count": geometry.segment_count,
                "path_count": len(geometry.paths),
                "segment_count": geometry.segment_count,
                "paths": geometry.paths,
            }
            for birth_generation, geometry in growth
        ],
    }


def _bounds_payload(bounds: Bounds) -> dict[str, float]:
    return {
        "min_x": bounds.min_x,
        "min_y": bounds.min_y,
        "max_x": bounds.max_x,
        "max_y": bounds.max_y,
        "width": bounds.width,
        "height": bounds.height,
    }
