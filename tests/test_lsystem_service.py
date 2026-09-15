import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import lsystem.service as lsystem_service
import lsystem.svg as lsystem_svg
from lsystem.models import LSystemRequest
from lsystem.service import generate_lsystem
from lsystem.svg import result_to_svg

SVG = "{http://www.w3.org/2000/svg}"


def test_lsystem_projects_birth_generation_without_duplication():
    request = LSystemRequest(
        axiom="X", rules={"X": "FX", "F": "FF"}, generations=4, step=1,
    )
    cumulative = lsystem_service.generate_lsystem_design(request, domain_id="page")
    delta = lsystem_service.generate_lsystem_design(
        request, domain_id="page", growth_mode="delta",
    )

    assert [entry.group_values for entry in cumulative.catalog.entries] == [(1,), (2,), (3,), (4,)]
    assert [entry.group_values for entry in delta.catalog.entries] == [(4,)]
    assert len(cumulative.paths) == 15
    assert len({path.semantic_path.path_id for path in cumulative.paths}) == 15
    assert len(delta.paths) == 1
    assert delta.paths[0] in cumulative.paths
    assert all(
        path.semantic_path.attributes["visible_generation"] == 4 for path in cumulative.paths
    )
    assert cumulative == lsystem_service.generate_lsystem_design(request, domain_id="page")


def test_neutral_birth_layers_are_independent_of_physical_pen_mapping():
    request = LSystemRequest(
        axiom="X", rules={"X": "FX"}, generations=12, step=1,
        pen_layers=[{"pen": 1, "start_generation": 0, "end_generation": 12, "color": "#000000"}],
    )
    design = lsystem_service.generate_lsystem_design(request, domain_id="page")
    assert [entry.group_values for entry in design.catalog.entries] == [
        (generation,) for generation in range(1, 13)
    ]
    assert len(design.paths) == 12


def test_semantic_generation_selection_and_request_growth_mode():
    request = LSystemRequest(
        axiom="X", rules={"X": "FX", "F": "FF"}, generations=4, step=1, growth_mode="delta",
    )
    paths = lsystem_service.generate_lsystem_semantics(request, generation=2, domain_id="page")
    assert len(paths) == 1
    assert dict(paths[0].attributes) == {"birth_generation": 2, "visible_generation": 2}
    assert paths[0].geometry.points == ((2.0, 0.0), (3.0, 0.0))
    assert lsystem_service.generate_lsystem_semantics(request, generation=0, domain_id="page") == ()


@pytest.mark.parametrize("generation", [-1, 5, True, 1.5])
def test_semantic_service_rejects_invalid_generation(generation):
    request = LSystemRequest(axiom="X", rules={"X": "FX"}, generations=4)
    with pytest.raises(ValueError, match="generation"):
        lsystem_service.generate_lsystem_semantics(request, generation=generation, domain_id="page")


def test_semantic_service_rejects_invalid_growth_mode():
    request = LSystemRequest(axiom="X", rules={"X": "FX"})
    with pytest.raises(ValueError, match="growth_mode"):
        lsystem_service.generate_lsystem_semantics(request, domain_id="page", growth_mode="unknown")


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
    ] == [2, 1]
    assert cumulative[1]["bounds"]["width"] == pytest.approx(1.0)
    assert cumulative[2]["bounds"]["width"] == pytest.approx(3.0)

    assert [layer["pen"] for layer in delta[2]["layers"]] == [2]
    assert delta[2]["bounds"]["width"] == pytest.approx(1.0)

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


def test_plant_booklet_example_keeps_generation_eight_plotter_readable():
    config_path = (
        Path(__file__).parents[1] / "examples" / "lsystems" / "plant-booklet.json"
    )
    request = LSystemRequest.model_validate(json.loads(config_path.read_text()))

    page = lsystem_service.generate_lsystem_growth_pages(
        request, generation_numbers=(8,), growth_mode="cumulative"
    )[8]
    segment_counts = [
        generation["segment_count"]
        for layer in page["layers"]
        for generation in layer["generations"]
    ]

    assert [layer["pen"] for layer in page["layers"]] == list(range(1, 9))
    assert 1_000 <= sum(segment_counts) <= 4_000
