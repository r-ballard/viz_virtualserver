from __future__ import annotations

import xml.etree.ElementTree as ET

from viz_canvas.geometry import build_canvas
from viz_canvas.svg import SVG_NS, append_canvas_clip, canvas_root_attributes

from .models import ConcentricPointsRequest

ET.register_namespace("", SVG_NS)


def result_to_svg(
    result: dict,
    data: ConcentricPointsRequest,
    *,
    stroke_width: float = 1.0,
) -> str:
    """Render generated rings as a clipped, pen-layered intrinsic-canvas SVG."""

    if stroke_width <= 0:
        raise ValueError("stroke_width must be positive")

    canvas = build_canvas(data.canvas)
    root_attributes = canvas_root_attributes(canvas)
    root_attributes.update(
        {
            "data-viz-algorithm": "concentric-points",
            "data-viz-seed": str(result["seed"]),
            "data-viz-boundary-mode": str(result["settings"]["boundary_mode"]),
            "data-viz-ring-spacing": str(result["settings"]["ring_spacing"]),
            "data-viz-overlap-mode": str(result["settings"]["overlap_mode"]),
            "data-viz-center-bias": str(result["settings"]["center_bias"]),
        }
    )
    root = ET.Element(_tag("svg"), root_attributes)
    clip_url = append_canvas_clip(root, canvas)

    layer = ET.SubElement(
        root,
        _tag("g"),
        {
            "id": f"pen-{data.pen}",
            "data-pen": str(data.pen),
            "data-viz-role": "algorithm-layer",
            "data-viz-algorithm": "concentric-points",
            "fill": "none",
            "stroke": data.color,
            "stroke-width": _fmt(stroke_width),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
            "clip-path": clip_url,
        },
    )

    for point in result["points"]:
        center_x, center_y = point["center"]
        point_group = ET.SubElement(
            layer,
            _tag("g"),
            {
                "data-viz-point": str(point["index"]),
                "data-viz-center": f"{_fmt(center_x)},{_fmt(center_y)}",
            },
        )
        for ring_index, radius in enumerate(point["radii"], start=1):
            ET.SubElement(
                point_group,
                _tag("circle"),
                {
                    "cx": _fmt(center_x),
                    "cy": _fmt(center_y),
                    "r": _fmt(radius),
                    "data-viz-ring": str(ring_index),
                },
            )

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    )


def _tag(local_name: str) -> str:
    return f"{{{SVG_NS}}}{local_name}"


def _fmt(value: float) -> str:
    text = f"{float(value):.9f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"
