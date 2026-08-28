import json
import xml.etree.ElementTree as ET

from concentric.models import ConcentricPointsRequest
from concentric.service import generate_concentric_points
from concentric.svg import result_to_svg

SVG = "{http://www.w3.org/2000/svg}"


def test_svg_preserves_canvas_metadata_and_top_level_pen_group() -> None:
    request = ConcentricPointsRequest(
        canvas={"shape": "triangle", "width": 100, "height": 80},
        seed=3,
        point_count=2,
        ring_count=4,
        pen=3,
        color="#123456",
    )
    result = generate_concentric_points(request)
    root = ET.fromstring(result_to_svg(result, request, stroke_width=2.0))

    assert root.attrib["width"] == "100"
    assert root.attrib["height"] == "80"
    assert root.attrib["viewBox"] == "0 0 100 80"
    assert root.attrib["data-viz-canvas-shape"] == "triangle"
    assert root.attrib["data-viz-canvas-up-anchor"] == "vertex:0"
    assert root.attrib["data-viz-algorithm"] == "concentric-points"
    assert root.attrib["data-viz-boundary-mode"] == "clip"

    direct_groups = [child for child in root if child.tag == f"{SVG}g"]
    assert len(direct_groups) == 1
    layer = direct_groups[0]
    assert layer.attrib["id"] == "pen-3"
    assert layer.attrib["data-pen"] == "3"
    assert layer.attrib["stroke"] == "#123456"
    assert layer.attrib["stroke-width"] == "2"
    assert layer.attrib["fill"] == "none"
    assert layer.attrib["data-viz-role"] == "algorithm-layer"
    assert layer.attrib["data-viz-algorithm"] == "concentric-points"
    assert layer.attrib["clip-path"] == "url(#viz-canvas-clip)"

    circles = root.findall(f".//{SVG}circle")
    assert len(circles) == request.point_count * request.ring_count

    metadata = root.find(f"{SVG}metadata")
    assert metadata is not None
    assert json.loads(metadata.text or "") == {
        "schema": "viz-domain/v1",
        "domains": [
            {
                "id": "concentric-source",
                "vertices": [[50.0, 0.0], [100.0, 80.0], [0.0, 80.0]],
                "provenance": None,
            }
        ],
    }


def test_svg_has_nonrendering_intrinsic_canvas_clip() -> None:
    request = ConcentricPointsRequest(
        canvas={"shape": "square", "width": 100, "height": 100},
        point_count=1,
        ring_count=1,
    )
    result = generate_concentric_points(request)
    root = ET.fromstring(result_to_svg(result, request))

    clip = root.find(f"{SVG}defs/{SVG}clipPath")
    assert clip is not None
    assert clip.attrib["id"] == "viz-canvas-clip"
    assert clip.find(f"{SVG}path") is not None


def test_svg_records_refinement_modes_on_root() -> None:
    request = ConcentricPointsRequest(
        canvas={"shape": "triangle", "width": 100, "height": 100},
        seed=5,
        point_count=2,
        ring_count=3,
        ring_spacing="progressive",
        overlap_mode="avoid",
        center_bias="vertices",
        center_bias_strength=0.5,
    )
    result = generate_concentric_points(request)
    root = ET.fromstring(result_to_svg(result, request))

    assert root.attrib["data-viz-ring-spacing"] == "progressive"
    assert root.attrib["data-viz-overlap-mode"] == "avoid"
    assert root.attrib["data-viz-center-bias"] == "vertices"
