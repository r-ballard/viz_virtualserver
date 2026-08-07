from __future__ import annotations

from .models import PenLayerSpec

DEFAULT_PEN_COLORS = (
    "#000000",
    "#D62728",
    "#1F77B4",
    "#2CA02C",
    "#9467BD",
    "#17BECF",
    "#FF7F0E",
    "#7F7F7F",
)


def resolve_pen_layers(
    generations: int,
    explicit_layers: list[PenLayerSpec] | None,
) -> list[PenLayerSpec]:
    """Return explicit mappings or evenly partition generations across up to eight pens."""

    if explicit_layers is not None:
        return sorted(explicit_layers, key=lambda layer: layer.start_generation)

    generation_count = generations + 1
    pen_count = min(8, generation_count)
    layers: list[PenLayerSpec] = []

    for index in range(pen_count):
        start = (index * generation_count) // pen_count
        end = ((index + 1) * generation_count) // pen_count - 1
        layers.append(
            PenLayerSpec(
                pen=index + 1,
                start_generation=start,
                end_generation=end,
                color=DEFAULT_PEN_COLORS[index],
            )
        )

    return layers


def layer_for_generation(generation: int, layers: list[PenLayerSpec]) -> PenLayerSpec:
    for layer in layers:
        if layer.start_generation <= generation <= layer.end_generation:
            return layer
    raise ValueError(f"generation {generation} is not assigned to a pen layer")
