"""Overlapping concentric motifs can share an outline without double-drawn arcs."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from viz_virtualserver.generators.concentric.models import ConcentricPointsRequest
from viz_virtualserver.generators.concentric.service import _payload_vector_paths
from viz_virtualserver.generators.concentric.svg import result_to_svg


def _overlapping_payload(mode: str) -> dict:
    return {
        "seed": 1,
        "settings": {
            "boundary_mode": "clip",
            "ring_spacing": "linear",
            "overlap_mode": "allow",
            "overlap_trim": mode,
            "center_bias": "uniform",
        },
        "points": [
            {"index": 1, "center": [40.0, 50.0], "radii": [2.0, 5.0]},
            {"index": 2, "center": [46.0, 50.0], "radii": [2.0, 5.0]},
        ],
    }


def test_outer_mode_draws_one_shared_border_and_keeps_inner_rings() -> None:
    paths = _payload_vector_paths(_overlapping_payload("outer"), layer_id="artwork")
    assert len(paths) == 3
    assert all(path.closed for path in paths)
    assert min(x for path in paths for x, _ in path.points) == pytest.approx(35.0)
    assert max(x for path in paths for x, _ in path.points) == pytest.approx(51.0)


def test_all_mode_removes_inner_ring_segments_inside_neighbor_outer_disk() -> None:
    paths = _payload_vector_paths(_overlapping_payload("all"), layer_id="artwork")
    assert len(paths) == 3
    assert sum(path.closed for path in paths) == 1
    inner = [path for path in paths if not path.closed]
    assert all(len(path.points) > 2 for path in inner)
    for path in inner:
        other_x = 46.0 if min(x for x, _ in path.points) < 40.0 else 40.0
        assert all((x - other_x) ** 2 + (y - 50.0) ** 2 >= 25.0 - 1e-3 for x, y in path.points)


def test_none_mode_preserves_four_independent_closed_rings() -> None:
    paths = _payload_vector_paths(_overlapping_payload("none"), layer_id="artwork")
    assert len(paths) == 4
    assert all(path.closed for path in paths)


def test_tangent_or_disjoint_outer_rings_remain_independent() -> None:
    payload = _overlapping_payload("all")
    payload["points"][1]["center"] = [50.0, 50.0]
    paths = _payload_vector_paths(payload, layer_id="artwork")
    assert len(paths) == 4
    assert all(path.closed for path in paths)


def test_trim_requires_overlaps_to_be_allowed() -> None:
    with pytest.raises(ValidationError, match="overlap_trim"):
        ConcentricPointsRequest(overlap_mode="avoid", overlap_trim="all")


def test_svg_uses_paths_for_shared_boundary() -> None:
    request = ConcentricPointsRequest(
        canvas={"shape": "square", "width": 100, "height": 100},
        overlap_trim="outer",
    )
    root = ET.fromstring(result_to_svg(_overlapping_payload("outer"), request))
    svg = "{http://www.w3.org/2000/svg}"
    layer = root.find(f"{svg}g")
    assert layer is not None
    assert root.attrib["data-viz-overlap-trim"] == "outer"
    assert len(layer.findall(f"{svg}path")) == 3
    assert not layer.findall(f".//{svg}circle")
