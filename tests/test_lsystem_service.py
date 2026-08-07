from lsystem.models import LSystemRequest
from lsystem.service import generate_lsystem
from lsystem.svg import result_to_svg


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
