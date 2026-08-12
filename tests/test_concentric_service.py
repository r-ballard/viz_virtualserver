import math

import pytest

from concentric.models import ConcentricPointsRequest
from concentric.service import ConcentricError, generate_concentric_points
from viz_canvas.geometry import build_canvas


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
