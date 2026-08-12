import xml.etree.ElementTree as ET

import pytest

from viz_canvas.geometry import build_canvas
from viz_canvas.models import CanvasSpec
from viz_canvas.svg import CLIP_ID, SVG_NS, canvas_to_svg

NS = {"svg": SVG_NS}


def test_triangle_svg_carries_intrinsic_canvas_contract() -> None:
    canvas = build_canvas(CanvasSpec(shape="triangle", width=100, height=80))
    root = ET.fromstring(canvas_to_svg(canvas))

    assert root.attrib["viewBox"] == "0 0 100 80"
    assert root.attrib["data-viz-canvas-version"] == "1"
    assert root.attrib["data-viz-canvas-shape"] == "triangle"
    assert root.attrib["data-viz-canvas-up-anchor"] == "vertex:0"
    assert root.attrib["data-viz-canvas-up-vector"] == "0,-1"
    assert root.attrib["data-viz-canvas-polygon"] == "50,0 100,80 0,80"

    clip = root.find(f"svg:defs/svg:clipPath[@id='{CLIP_ID}']", NS)
    assert clip is not None
    clip_path = clip.find("svg:path", NS)
    assert clip_path is not None
    assert clip_path.attrib["d"] == "M 50 0 L 100 80 L 0 80 Z"

    # The template intentionally does not add a top-level artwork wrapper.
    # Future strict pen-N exporters must keep pen groups at the SVG top level.
    assert root.find("svg:g[@id='canvas-artwork']", NS) is None


def test_boundary_is_opt_in_drawable_guide() -> None:
    canvas = build_canvas(CanvasSpec(shape="triangle"))
    without_guide = ET.fromstring(canvas_to_svg(canvas))
    assert without_guide.find("svg:g[@id='canvas-guide']", NS) is None

    with_guide = ET.fromstring(canvas_to_svg(canvas, include_boundary=True))
    guide = with_guide.find("svg:g[@id='canvas-guide']", NS)
    assert guide is not None
    assert guide.attrib["data-viz-role"] == "canvas-guide"


def test_boundary_stroke_width_must_be_positive() -> None:
    canvas = build_canvas(CanvasSpec(shape="triangle"))
    with pytest.raises(ValueError, match="positive"):
        canvas_to_svg(canvas, boundary_stroke_width=0)
