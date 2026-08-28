import json
import xml.etree.ElementTree as ET

import pytest

from viz_canvas.design import DesignResult, VectorPath
from viz_canvas.geometry import CanvasGeometry, build_canvas
from viz_canvas.models import CanvasSpec, DomainProvenance, PolygonDomain
from viz_canvas.svg import (
    CLIP_ID,
    SVG_NS,
    build_domain_metadata_payload,
    canvas_to_svg,
    serialize_design_result_svg,
)

NS = {"svg": SVG_NS}


def make_canvas(*domains: PolygonDomain) -> CanvasGeometry:
    return CanvasGeometry(
        shape="triangle",
        width=100.0,
        height=80.0,
        polygon=((50.0, 0.0), (100.0, 80.0), (0.0, 80.0)),
        up_anchor="vertex:0",
        domains=domains,
    )


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


def test_design_serializer_preserves_exact_legacy_canvas_metadata_and_clip() -> None:
    canvas = make_canvas(
        PolygonDomain("unrelated", ((10.0, 10.0), (20.0, 10.0), (10.0, 20.0)))
    )

    root = ET.fromstring(serialize_design_result_svg(canvas=canvas, results=()))

    assert root.attrib == {
        "viewBox": "0 0 100 80",
        "width": "100",
        "height": "80",
        "data-viz-canvas-version": "1",
        "data-viz-canvas-shape": "triangle",
        "data-viz-canvas-coordinate-system": "svg-y-down",
        "data-viz-canvas-up-anchor": "vertex:0",
        "data-viz-canvas-up-vector": "0,-1",
        "data-viz-canvas-polygon": "50,0 100,80 0,80",
        "data-viz-canvas-clip-id": "viz-canvas-clip",
    }
    clip = root.find("svg:defs/svg:clipPath", NS)
    assert clip is not None
    assert clip.attrib == {
        "id": "viz-canvas-clip",
        "clipPathUnits": "userSpaceOnUse",
    }
    assert clip.find("svg:path", NS).attrib == {
        "d": "M 50 0 L 100 80 L 0 80 Z"
    }


def test_domain_metadata_payload_preserves_domain_vertex_order_and_provenance() -> None:
    canvas = make_canvas(
        PolygonDomain("a", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))),
        PolygonDomain(
            "b",
            ((2.0, 2.0), (8.0, 2.0), (2.0, 8.0)),
            DomainProvenance(("source",), "pass-a", "offset"),
        ),
    )

    assert build_domain_metadata_payload(canvas) == {
        "schema": "viz-domain/v1",
        "domains": [
            {
                "id": "a",
                "vertices": [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]],
                "provenance": None,
            },
            {
                "id": "b",
                "vertices": [[2.0, 2.0], [8.0, 2.0], [2.0, 8.0]],
                "provenance": {
                    "source_domain_ids": ["source"],
                    "generating_pass_id": "pass-a",
                    "operation": "offset",
                },
            },
        ],
    }


def test_design_serializer_emits_one_deterministic_compact_metadata_node() -> None:
    canvas = make_canvas(
        PolygonDomain("a", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)))
    )

    root = ET.fromstring(serialize_design_result_svg(canvas=canvas, results=()))
    metadata = root.findall("svg:metadata", NS)

    assert len(metadata) == 1
    assert metadata[0].attrib == {"id": "viz-domain-metadata"}
    assert metadata[0].text == (
        '{"schema":"viz-domain/v1","domains":[{"id":"a","vertices":'
        '[[0.0,0.0],[10.0,0.0],[0.0,10.0]],"provenance":null}]}'
    )
    assert json.loads(metadata[0].text) == build_domain_metadata_payload(canvas)


def test_design_paths_compose_repeated_layers_in_first_seen_order() -> None:
    results = (
        DesignResult(
            (
                VectorPath(((0.0, 0.0), (10.0, 10.0)), False, "a"),
                VectorPath(((10.0, 0.0), (0.0, 10.0), (5.0, 5.0)), True, "b"),
            ),
            (),
            "first",
        ),
        DesignResult(
            (VectorPath(((2.0, 3.0), (4.0, 5.0)), False, "a"),),
            (),
            "second",
        ),
    )

    root = ET.fromstring(serialize_design_result_svg(canvas=make_canvas(), results=results))
    layers = root.findall("svg:g", NS)

    assert [layer.attrib for layer in layers] == [
        {
            "id": "a",
            "data-viz-role": "logical-layer",
            "data-viz-layer": "a",
            "clip-path": "url(#viz-canvas-clip)",
            "fill": "none",
            "stroke": "#000000",
            "stroke-width": "1",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        },
        {
            "id": "b",
            "data-viz-role": "logical-layer",
            "data-viz-layer": "b",
            "clip-path": "url(#viz-canvas-clip)",
            "fill": "none",
            "stroke": "#000000",
            "stroke-width": "1",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        },
    ]
    assert [path.attrib for path in layers[0].findall("svg:path", NS)] == [
        {"d": "M 0 0 L 10 10"},
        {"d": "M 2 3 L 4 5"},
    ]
    assert [path.attrib for path in layers[1].findall("svg:path", NS)] == [
        {"d": "M 10 0 L 0 10 L 5 5 Z"}
    ]


def test_design_serializer_draws_no_structural_domain_outlines() -> None:
    root = ET.fromstring(
        serialize_design_result_svg(
            canvas=make_canvas(
                PolygonDomain("a", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)))
            ),
            results=(),
        )
    )

    assert root.findall("svg:g", NS) == []
    assert root.findall("svg:path", NS) == []


def test_design_serializer_supports_empty_domains_and_results() -> None:
    root = ET.fromstring(serialize_design_result_svg(canvas=make_canvas(), results=()))
    metadata = root.find("svg:metadata[@id='viz-domain-metadata']", NS)

    assert metadata is not None
    assert metadata.text == '{"schema":"viz-domain/v1","domains":[]}'
    assert root.findall("svg:g", NS) == []
