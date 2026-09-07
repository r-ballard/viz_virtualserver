from __future__ import annotations

from html import escape


def result_to_svg(result: dict, *, padding: float = 10.0, stroke_width: float = 1.0) -> str:
    """Render precomputed L-system polylines as stroke-only, pen-colored SVG."""

    bounds = result["bounds"]
    width = max(float(bounds["width"]), 1.0) + 2 * padding
    height = max(float(bounds["height"]), 1.0) + 2 * padding
    min_x = float(bounds["min_x"])
    max_y = float(bounds["max_y"])

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(width)} {_fmt(height)}" '
            f'width="{_fmt(width)}" height="{_fmt(height)}">'
        ),
    ]

    for layer in result["layers"]:
        generation_ids = ",".join(str(item["generation"]) for item in layer["generations"])
        lines.append(
            f'  <g id="pen-{layer["pen"]}" data-pen="{layer["pen"]}" '
            f'data-generations="{escape(generation_ids)}" fill="none" '
            f'stroke="{escape(layer["color"])}" stroke-width="{_fmt(stroke_width)}" '
            'stroke-linecap="round" stroke-linejoin="round">'
        )

        for generation in layer["generations"]:
            lines.append(f'    <g data-generation="{generation["generation"]}">')
            for path in generation["paths"]:
                if len(path) < 2:
                    continue
                path_data = _path_data(path, min_x=min_x, max_y=max_y, padding=padding)
                lines.append(f'      <path d="{path_data}" />')
            lines.append("    </g>")

        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines)


def result_to_generation_svgs(
    result: dict,
    *,
    generation_numbers: tuple[int, ...],
    padding: float = 10.0,
    stroke_width: float = 1.0,
) -> dict[int, str]:
    """Render selected generations as separate pages with shared result bounds."""

    generations = {
        generation["generation"]: (layer, generation)
        for layer in result["layers"]
        for generation in layer["generations"]
    }
    pages: dict[int, str] = {}
    for generation_number in generation_numbers:
        if generation_number not in generations:
            raise ValueError(f"generation {generation_number} is not present in result")
        layer, generation = generations[generation_number]
        page_result = {
            "bounds": result["bounds"],
            "layers": [{**layer, "generations": [generation]}],
        }
        pages[generation_number] = result_to_svg(
            page_result, padding=padding, stroke_width=stroke_width
        )
    return pages


def growth_pages_to_svgs(
    pages: dict[int, dict],
    *,
    padding: float = 0.0,
    stroke_width: float = 1.0,
) -> dict[int, str]:
    """Render independently bounded cumulative or delta growth pages."""

    return {
        generation: result_to_svg(
            page, padding=padding, stroke_width=stroke_width
        )
        for generation, page in pages.items()
    }


def _path_data(path: list, *, min_x: float, max_y: float, padding: float) -> str:
    transformed = [
        (float(x) - min_x + padding, max_y - float(y) + padding)
        for x, y in path
    ]
    first_x, first_y = transformed[0]
    commands = [f"M {_fmt(first_x)} {_fmt(first_y)}"]
    commands.extend(f"L {_fmt(x)} {_fmt(y)}" for x, y in transformed[1:])
    return " ".join(commands)


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"
