from __future__ import annotations

from .geometry import GenerationGeometry, commands_to_geometry, union_bounds
from .grammar import iter_generations
from .layers import layer_for_generation, resolve_pen_layers
from .models import LSystemRequest, PenLayerSpec


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


def _empty_layer_payload(layer: PenLayerSpec) -> dict:
    return {
        "pen": layer.pen,
        "color": layer.color,
        "start_generation": layer.start_generation,
        "end_generation": layer.end_generation,
        "generations": [],
    }
