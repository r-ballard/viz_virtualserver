import math
from copy import deepcopy
from dataclasses import fields

import pytest

from concentric.models import ConcentricPointsRequest
from concentric.service import (
    ConcentricDomainAlgorithm,
    ConcentricError,
    generate_concentric_points,
)
from viz_canvas.design import DesignPass, DesignResult, LogicalLayer
from viz_canvas.geometry import CanvasGeometry, build_canvas
from viz_canvas.models import PolygonDomain


def _triangle_request(**overrides) -> ConcentricPointsRequest:
    payload = {
        "canvas": {"shape": "triangle", "width": 120.0, "height": 100.0},
        "seed": 42,
        "point_count": 4,
        "ring_count": 5,
        "center_margin": 2.0,
        "min_center_spacing": 5.0,
    }
    payload.update(overrides)
    return ConcentricPointsRequest(**payload)


def test_generation_is_deterministic_and_centers_are_inside_triangle() -> None:
    request = _triangle_request()
    first = generate_concentric_points(request)
    second = generate_concentric_points(request)
    assert first == second

    canvas = build_canvas(request.canvas)
    assert len(first["points"]) == request.point_count
    for point in first["points"]:
        assert canvas.contains(tuple(point["center"]))
        assert canvas.distance_to_boundary(tuple(point["center"])) >= request.center_margin
        assert len(point["radii"]) == request.ring_count
        assert point["radii"] == sorted(point["radii"])


def test_representative_request_preserves_point_and_ring_counts() -> None:
    request = _triangle_request()

    result = generate_concentric_points(request)

    assert len(result["points"]) == 4
    assert [len(point["radii"]) for point in result["points"]] == [5, 5, 5, 5]


def test_representative_legacy_request_matches_exact_golden_payload() -> None:
    request = ConcentricPointsRequest(
        canvas={"shape": "triangle", "width": 120.0, "height": 100.0},
        seed=42,
        point_count=2,
        ring_count=3,
        center_margin=2.0,
        min_center_spacing=5.0,
        boundary_mode="inscribed",
        radius_scale=0.75,
    )

    assert generate_concentric_points(request) == {
        "schema_version": 1,
        "algorithm": "concentric-points",
        "seed": 42,
        "canvas": {
            "schema_version": 1,
            "shape": "triangle",
            "width": 120.0,
            "height": 100.0,
            "polygon": [[60.0, 0.0], [120.0, 100.0], [0.0, 100.0]],
            "centroid": [60.0, 66.66666666666667],
            "up_anchor": "vertex:0",
            "up_vector": [0.0, -1.0],
            "bounds": {
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 120.0,
                "max_y": 100.0,
                "width": 120.0,
                "height": 100.0,
            },
        },
        "settings": {
            "point_count": 2,
            "point_count_range": None,
            "ring_count": 3,
            "ring_spacing": "linear",
            "ring_spacing_power": 2.0,
            "boundary_mode": "inscribed",
            "radius_scale": 0.75,
            "radius_variation": 0.0,
            "min_ring_radius": 0.0,
            "max_ring_radius": None,
            "overlap_mode": "allow",
            "center_margin": 2.0,
            "min_center_spacing": 5.0,
            "center_bias": "uniform",
            "center_bias_strength": 0.0,
            "pen": 1,
            "color": "#000000",
        },
        "points": [
            {
                "index": 1,
                "center": [88.37654569968149, 67.66994874229113],
                "max_radius": 7.862410653203609,
                "radii": [
                    2.6208035510678696,
                    5.241607102135739,
                    7.862410653203609,
                ],
            },
            {
                "index": 2,
                "center": [77.98613253354279, 54.49414806032167],
                "max_radius": 9.460519848175124,
                "radii": [
                    3.1535066160583747,
                    6.307013232116749,
                    9.460519848175124,
                ],
            },
        ],
    }


def _design_parameters(**overrides: object) -> dict[str, object]:
    parameters = ConcentricPointsRequest().model_dump(exclude={"canvas", "pen", "color"})
    parameters.update(overrides)
    return parameters


def _domain_canvas(domain: PolygonDomain) -> CanvasGeometry:
    return CanvasGeometry(
        shape="polygon",
        width=300.0,
        height=400.0,
        polygon=domain.vertices,
        up_anchor="edge:0",
        domains=(domain,),
    )


def test_concentric_domain_algorithm_returns_design_result() -> None:
    domain = PolygonDomain(
        id="target",
        vertices=((0.0, 0.0), (100.0, 0.0), (50.0, 80.0)),
    )
    canvas = _domain_canvas(domain)
    design_pass = DesignPass(
        id="concentric",
        algorithm="concentric",
        target_domain_ids=("target",),
        parameters=_design_parameters(point_count=2, ring_count=3),
        logical_layers=(LogicalLayer(id="concentric"),),
    )

    result = ConcentricDomainAlgorithm().generate(
        canvas=canvas,
        domains=(domain,),
        design_pass=design_pass,
    )

    assert isinstance(result, DesignResult)
    assert result.producing_pass_id == "concentric"
    assert len(result.paths) == 6
    assert {path.layer_id for path in result.paths} == {"concentric"}
    assert all(path.closed for path in result.paths)


def test_concentric_result_is_returned_in_canvas_coordinates() -> None:
    domain = PolygonDomain(
        id="translated",
        vertices=((100.0, 200.0), (200.0, 200.0), (150.0, 280.0)),
    )
    canvas = _domain_canvas(domain)
    design_pass = DesignPass(
        id="concentric",
        algorithm="concentric",
        target_domain_ids=("translated",),
        parameters=_design_parameters(
            seed=11,
            point_count=2,
            ring_count=2,
            boundary_mode="inscribed",
        ),
        logical_layers=(LogicalLayer(id="artwork"),),
    )

    result = ConcentricDomainAlgorithm().generate(
        canvas=canvas,
        domains=(domain,),
        design_pass=design_pass,
    )

    assert result.paths
    assert all(
        canvas.contains(point)
        for path in result.paths
        for point in path.points
    )
    assert min(point[0] for path in result.paths for point in path.points) >= 100.0
    assert min(point[1] for path in result.paths for point in path.points) >= 200.0


def test_concentric_adapter_requires_one_logical_layer() -> None:
    domain = PolygonDomain(
        id="target",
        vertices=((0.0, 0.0), (100.0, 0.0), (50.0, 80.0)),
    )
    canvas = _domain_canvas(domain)
    design_pass = DesignPass(
        id="concentric",
        algorithm="concentric",
        target_domain_ids=("target",),
        parameters=_design_parameters(point_count=1, ring_count=1),
    )

    with pytest.raises(ValueError, match="exactly one logical layer"):
        ConcentricDomainAlgorithm().generate(
            canvas=canvas,
            domains=(domain,),
            design_pass=design_pass,
        )


def test_concentric_adapter_accepts_full_request_parameters_in_domain_order() -> None:
    first = PolygonDomain(
        id="first",
        vertices=((10.0, 20.0), (90.0, 20.0), (50.0, 80.0)),
    )
    second = PolygonDomain(
        id="second",
        vertices=((160.0, 220.0), (240.0, 220.0), (200.0, 280.0)),
    )
    canvas = CanvasGeometry(
        shape="rectangle",
        width=300.0,
        height=400.0,
        polygon=((0.0, 0.0), (300.0, 0.0), (300.0, 400.0), (0.0, 400.0)),
        up_anchor="edge:0",
        domains=(first, second),
    )
    parameters = ConcentricPointsRequest(
        seed=17,
        point_count=1,
        ring_count=1,
        boundary_mode="inscribed",
        pen=7,
        color="#abcdef",
    ).model_dump()
    design_pass = DesignPass(
        id="ordered",
        algorithm="concentric",
        target_domain_ids=("first", "second"),
        parameters=parameters,
        logical_layers=(LogicalLayer(id="artwork"),),
    )

    result = ConcentricDomainAlgorithm().generate(
        canvas=canvas,
        domains=(first, second),
        design_pass=design_pass,
    )

    assert len(result.paths) == 2
    path_centers = [
        (
            sum(point[0] for point in path.points) / len(path.points),
            sum(point[1] for point in path.points) / len(path.points),
        )
        for path in result.paths
    ]
    assert first.vertices[0][0] <= path_centers[0][0] <= first.vertices[1][0]
    assert second.vertices[0][0] <= path_centers[1][0] <= second.vertices[1][0]
    assert {path.layer_id for path in result.paths} == {"artwork"}


def test_concentric_adapter_is_deterministic_neutral_and_does_not_mutate_parameters() -> None:
    first = PolygonDomain(
        id="first",
        vertices=((10.0, 20.0), (90.0, 20.0), (50.0, 80.0)),
    )
    second = PolygonDomain(
        id="second",
        vertices=((160.0, 220.0), (240.0, 220.0), (200.0, 280.0)),
    )
    canvas = CanvasGeometry(
        shape="rectangle",
        width=300.0,
        height=400.0,
        polygon=((0.0, 0.0), (300.0, 0.0), (300.0, 400.0), (0.0, 400.0)),
        up_anchor="edge:0",
        domains=(first, second),
    )
    parameters = ConcentricPointsRequest(
        canvas={"shape": "square", "width": 50.0, "height": 50.0},
        seed=23,
        point_count=2,
        ring_count=3,
        boundary_mode="inscribed",
        radius_scale=0.5,
        min_ring_radius=1.0,
        pen=8,
        color="#fedcba",
    ).model_dump()
    parameters_before = deepcopy(parameters)
    design_pass = DesignPass(
        id="deterministic",
        algorithm="concentric",
        target_domain_ids=("first", "second"),
        parameters=parameters,
        logical_layers=(LogicalLayer(id="artwork"),),
    )
    algorithm = ConcentricDomainAlgorithm()

    first_result = algorithm.generate(
        canvas=canvas,
        domains=(first, second),
        design_pass=design_pass,
    )
    second_result = algorithm.generate(
        canvas=canvas,
        domains=(first, second),
        design_pass=design_pass,
    )

    assert first_result == second_result
    assert parameters == parameters_before
    assert len(first_result.paths) == 2 * 2 * 3
    assert {field.name for field in fields(first_result)} == {
        "paths",
        "derived_domains",
        "producing_pass_id",
    }
    assert {field.name for field in fields(first_result.paths[0])} == {
        "points",
        "closed",
        "layer_id",
    }
    assert {path.layer_id for path in first_result.paths} == {"artwork"}
    assert all(path.closed and len(path.points) == 64 for path in first_result.paths)

    first_circle = first_result.paths[0]
    center = (
        sum(point[0] for point in first_circle.points) / 64,
        sum(point[1] for point in first_circle.points) / 64,
    )
    radius = math.dist(center, first_circle.points[0])
    assert first_circle.points[0][0] == pytest.approx(center[0] + radius)
    assert first_circle.points[0][1] == pytest.approx(center[1])
    for index, point in enumerate(first_circle.points):
        angle = math.tau * index / 64
        assert point == pytest.approx(
            (
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle),
            )
        )
    assert radius == pytest.approx(1.0)
    outer_circle = first_result.paths[2]
    outer_radius = math.dist(center, outer_circle.points[0])
    assert outer_radius == pytest.approx(
        _domain_canvas(first).distance_to_boundary(center) * 0.5
    )

    for path in first_result.paths[:6]:
        path_center = (
            sum(point[0] for point in path.points) / 64,
            sum(point[1] for point in path.points) / 64,
        )
        assert _domain_canvas(first).contains(path_center)
    for path in first_result.paths[6:]:
        path_center = (
            sum(point[0] for point in path.points) / 64,
            sum(point[1] for point in path.points) / 64,
        )
        assert _domain_canvas(second).contains(path_center)


def test_concentric_adapter_does_not_merge_or_dedupe_overlapping_domain_batches() -> None:
    first = PolygonDomain(
        "first", ((0.0, 0.0), (60.0, 0.0), (60.0, 60.0), (0.0, 60.0))
    )
    second = PolygonDomain(
        "second", ((40.0, 20.0), (100.0, 20.0), (100.0, 80.0), (40.0, 80.0))
    )
    canvas = CanvasGeometry(
        shape="rectangle",
        width=100.0,
        height=80.0,
        polygon=((0.0, 0.0), (100.0, 0.0), (100.0, 80.0), (0.0, 80.0)),
        up_anchor="edge:0",
        domains=(first, second),
    )
    before = (first.vertices, second.vertices)
    design_pass = DesignPass(
        id="overlap",
        algorithm="concentric",
        target_domain_ids=("first", "second"),
        parameters=_design_parameters(
            seed=7,
            point_count=1,
            ring_count=2,
            boundary_mode="inscribed",
            min_ring_radius=1.0,
        ),
        logical_layers=(LogicalLayer("artwork"),),
    )
    algorithm = ConcentricDomainAlgorithm()

    combined = algorithm.generate(
        canvas=canvas, domains=(first, second), design_pass=design_pass
    )
    assert len(combined.paths) == 4
    path_centers = [
        (
            sum(point[0] for point in path.points) / len(path.points),
            sum(point[1] for point in path.points) / len(path.points),
        )
        for path in combined.paths
    ]
    assert path_centers[0] == pytest.approx(path_centers[1])
    assert path_centers[2] == pytest.approx(path_centers[3])
    assert all(_domain_canvas(first).contains(center) for center in path_centers[:2])
    assert all(_domain_canvas(second).contains(center) for center in path_centers[2:])
    assert (first.vertices, second.vertices) == before


def test_min_center_spacing_is_enforced() -> None:
    request = _triangle_request(point_count=5, min_center_spacing=15.0)
    result = generate_concentric_points(request)
    centers = [tuple(point["center"]) for point in result["points"]]

    for index, first in enumerate(centers):
        for second in centers[index + 1 :]:
            assert math.dist(first, second) >= request.min_center_spacing


def test_inscribed_radius_is_limited_by_boundary_distance() -> None:
    request = _triangle_request(boundary_mode="inscribed", radius_scale=0.75)
    result = generate_concentric_points(request)
    canvas = build_canvas(request.canvas)

    for point in result["points"]:
        center = tuple(point["center"])
        expected = canvas.distance_to_boundary(center) * request.radius_scale
        assert point["max_radius"] == pytest.approx(expected)
        assert point["radii"][-1] == pytest.approx(expected)


def test_clip_radius_reaches_farthest_canvas_vertex() -> None:
    request = _triangle_request(boundary_mode="clip", radius_scale=1.0)
    result = generate_concentric_points(request)
    canvas = build_canvas(request.canvas)

    for point in result["points"]:
        center = tuple(point["center"])
        expected = max(math.dist(center, vertex) for vertex in canvas.polygon)
        assert point["max_radius"] == pytest.approx(expected)


def test_impossible_center_constraints_fail_explicitly() -> None:
    request = _triangle_request(
        point_count=2,
        center_margin=1_000.0,
        max_sampling_attempts=50,
    )
    with pytest.raises(ConcentricError, match="unable to place requested centers"):
        generate_concentric_points(request)


def test_point_count_range_is_seeded_and_reported() -> None:
    request = _triangle_request(point_count_range=(3, 7))
    first = generate_concentric_points(request)
    second = generate_concentric_points(request)

    assert first == second
    assert 3 <= len(first["points"]) <= 7
    assert first["settings"]["point_count"] == len(first["points"])
    assert first["settings"]["point_count_range"] == [3, 7]


def test_progressive_ring_spacing_expands_outward() -> None:
    request = _triangle_request(
        point_count=1,
        ring_count=5,
        ring_spacing="progressive",
        ring_spacing_power=2.0,
    )
    result = generate_concentric_points(request)
    radii = result["points"][0]["radii"]
    gaps = [right - left for left, right in zip([0.0, *radii[:-1]], radii, strict=True)]

    assert gaps == sorted(gaps)
    assert radii[-1] == pytest.approx(result["points"][0]["max_radius"])


def test_random_ring_spacing_is_deterministic_and_sorted() -> None:
    request = _triangle_request(point_count=1, ring_count=8, ring_spacing="random")
    first = generate_concentric_points(request)
    second = generate_concentric_points(request)
    radii = first["points"][0]["radii"]

    assert first == second
    assert radii == sorted(radii)
    assert radii[-1] == pytest.approx(first["points"][0]["max_radius"])


def test_min_and_max_ring_radius_bound_the_generated_rings() -> None:
    request = _triangle_request(
        point_count=1,
        ring_count=5,
        min_ring_radius=10.0,
        max_ring_radius=30.0,
    )
    result = generate_concentric_points(request)
    radii = result["points"][0]["radii"]

    assert radii[0] == pytest.approx(10.0)
    assert radii[-1] == pytest.approx(30.0)


def test_radius_variation_is_deterministic_and_only_reduces_radius() -> None:
    base_request = _triangle_request(point_count=4, radius_variation=0.0)
    varied_request = _triangle_request(point_count=4, radius_variation=0.4)
    base = generate_concentric_points(base_request)
    first = generate_concentric_points(varied_request)
    second = generate_concentric_points(varied_request)

    assert first == second
    for base_point, varied_point in zip(base["points"], first["points"], strict=True):
        assert varied_point["max_radius"] <= base_point["max_radius"]
        assert varied_point["max_radius"] + 1e-9 >= base_point["max_radius"] * 0.6


def test_avoid_overlap_caps_neighboring_outer_rings() -> None:
    request = _triangle_request(
        point_count=5,
        overlap_mode="avoid",
        min_center_spacing=10.0,
    )
    result = generate_concentric_points(request)

    for index, first in enumerate(result["points"]):
        for second in result["points"][index + 1 :]:
            center_distance = math.dist(tuple(first["center"]), tuple(second["center"]))
            assert first["max_radius"] + second["max_radius"] <= center_distance + 1e-9


def test_centroid_bias_moves_centers_toward_canvas_centroid() -> None:
    uniform_request = _triangle_request(
        point_count=50,
        center_margin=0,
        min_center_spacing=0,
        center_bias="uniform",
    )
    biased_request = _triangle_request(
        point_count=50,
        center_margin=0,
        min_center_spacing=0,
        center_bias="centroid",
        center_bias_strength=0.9,
    )
    canvas = build_canvas(uniform_request.canvas)
    uniform = generate_concentric_points(uniform_request)
    biased = generate_concentric_points(biased_request)

    uniform_mean = sum(
        math.dist(tuple(point["center"]), canvas.centroid) for point in uniform["points"]
    ) / len(uniform["points"])
    biased_mean = sum(
        math.dist(tuple(point["center"]), canvas.centroid) for point in biased["points"]
    ) / len(biased["points"])

    assert biased_mean < uniform_mean


def test_vertex_bias_keeps_centers_inside_canvas() -> None:
    request = _triangle_request(
        point_count=20,
        center_margin=0,
        min_center_spacing=0,
        center_bias="vertices",
        center_bias_strength=0.9,
    )
    result = generate_concentric_points(request)
    canvas = build_canvas(request.canvas)

    assert all(canvas.contains(tuple(point["center"])) for point in result["points"])
