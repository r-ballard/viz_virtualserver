import xml.etree.ElementTree as ET

import pytest

import lsystem.service as lsystem_service
import lsystem.svg as lsystem_svg
from lsystem.models import LSystemRequest
from lsystem.service import generate_lsystem
from lsystem.svg import result_to_svg

SVG = "{http://www.w3.org/2000/svg}"


def test_service_groups_precomputed_generations_by_pen():
    request = LSystemRequest(
        axiom="F",
        rules={"F": "FF"},
        generations=2,
        step=1,
        angle=90,
        pen_layers=[
            {"pen": 1, "start_generation": 0, "end_generation": 1, "color": "#000000"},
            {"pen": 2, "start_generation": 2, "end_generation": 2, "color": "#FF0000"},
        ],
    )
    result = generate_lsystem(request)

    assert result["total_segments"] == 7
    assert [item["generation"] for item in result["layers"][0]["generations"]] == [0, 1]
    assert [item["generation"] for item in result["layers"][1]["generations"]] == [2]
    assert result["layers"][1]["generations"][0]["paths"][0][-1] == (4.0, 0.0)


def test_svg_preserves_pen_and_generation_metadata():
    request = LSystemRequest(axiom="F", rules={"F": "F+F"}, generations=1, angle=90, step=1)
    svg = result_to_svg(generate_lsystem(request))

    assert 'id="pen-1"' in svg
    assert 'data-generation="0"' in svg
    assert 'id="pen-2"' in svg
    assert 'data-generation="1"' in svg
    assert '<path d="M ' in svg


def test_generation_page_svgs_share_bounds_and_map_one_generation_to_each_pen():
    request = LSystemRequest(
        axiom="F",
        rules={"F": "F+F"},
        generations=2,
        angle=90,
        step=1,
        pen_layers=[
            {"pen": 1, "start_generation": 0, "end_generation": 1, "color": "#000000"},
            {"pen": 2, "start_generation": 2, "end_generation": 2, "color": "#FF0000"},
        ],
    )

    pages = lsystem_svg.result_to_generation_svgs(
        generate_lsystem(request), generation_numbers=(1, 2)
    )

    assert tuple(pages) == (1, 2)
    roots = [ET.fromstring(pages[generation]) for generation in pages]
    assert roots[0].attrib["viewBox"] == roots[1].attrib["viewBox"]

    for generation, root in zip(pages, roots, strict=True):
        layers = root.findall(SVG + "g")
        assert len(layers) == 1
        assert layers[0].attrib["id"] == f"pen-{generation}"
        assert layers[0].attrib["data-pen"] == str(generation)
        assert layers[0].attrib["data-generations"] == str(generation)
        drawings = layers[0].findall(SVG + "g")
        assert len(drawings) == 1
        assert drawings[0].attrib["data-generation"] == str(generation)


def test_growth_pages_support_cumulative_and_delta_geometry_with_independent_bounds():
    request = LSystemRequest(
        axiom="X",
        rules={"X": "FX", "F": "FF"},
        generations=2,
        angle=90,
        step=1,
        pen_layers=[
            {"pen": 1, "start_generation": 0, "end_generation": 1, "color": "#000000"},
            {"pen": 2, "start_generation": 2, "end_generation": 2, "color": "#FF0000"},
        ],
    )

    cumulative = lsystem_service.generate_lsystem_growth_pages(
        request, generation_numbers=(1, 2), growth_mode="cumulative"
    )
    delta = lsystem_service.generate_lsystem_growth_pages(
        request, generation_numbers=(1, 2), growth_mode="delta"
    )

    assert [layer["pen"] for layer in cumulative[1]["layers"]] == [1]
    assert [layer["pen"] for layer in cumulative[2]["layers"]] == [1, 2]
    assert [
        generation["segment_count"]
        for layer in cumulative[2]["layers"]
        for generation in layer["generations"]
    ] == [1, 2]
    assert cumulative[1]["bounds"]["width"] == pytest.approx(1.0)
    assert cumulative[2]["bounds"]["width"] == pytest.approx(3.0)

    assert [layer["pen"] for layer in delta[2]["layers"]] == [2]
    assert delta[2]["bounds"]["width"] == pytest.approx(2.0)

    delta_request = LSystemRequest.model_validate(
        {**request.model_dump(), "growth_mode": "delta"}
    )
    configured_delta = lsystem_service.generate_lsystem_growth_pages(
        delta_request, generation_numbers=(2,)
    )
    assert [layer["pen"] for layer in configured_delta[2]["layers"]] == [2]

    cumulative_svgs = lsystem_svg.growth_pages_to_svgs(cumulative)
    delta_svgs = lsystem_svg.growth_pages_to_svgs(delta)
    cumulative_roots = {
        generation: ET.fromstring(svg) for generation, svg in cumulative_svgs.items()
    }
    assert cumulative_roots[1].attrib["viewBox"] == "0 0 1 1"
    assert cumulative_roots[1].attrib["viewBox"] != cumulative_roots[2].attrib["viewBox"]
    assert [
        group.attrib["id"] for group in cumulative_roots[2].findall(SVG + "g")
    ] == ["pen-1", "pen-2"]
    assert [
        group.attrib["id"]
        for group in ET.fromstring(delta_svgs[2]).findall(SVG + "g")
    ] == ["pen-2"]


def test_growth_page_combines_multiple_birth_generations_mapped_to_one_pen():
    request = LSystemRequest(
        axiom="X",
        rules={"X": "FX", "F": "FF"},
        generations=2,
        step=1,
        pen_layers=[
            {"pen": 1, "start_generation": 0, "end_generation": 2, "color": "#000000"}
        ],
    )

    page = lsystem_service.generate_lsystem_growth_pages(
        request, generation_numbers=(2,)
    )[2]

    assert len(page["layers"]) == 1
    assert page["layers"][0]["pen"] == 1
    assert [
        generation["generation"] for generation in page["layers"][0]["generations"]
    ] == [1, 2]
    root = ET.fromstring(lsystem_svg.growth_pages_to_svgs({2: page})[2])
    assert len(root.findall(SVG + "g")) == 1
