from __future__ import annotations

import math
import random

import pytest

from concentric.service import (
    OrbitalConcentricDomainAlgorithm,
    OrbitalConcentricParameters,
    _body_angles,
    _orbit_paths,
)
from viz_canvas.design import DesignPass, LogicalLayer
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import PolygonDomain
from viz_canvas.runner import AlgorithmContext

LAYERS = tuple(LogicalLayer(layer_id) for layer_id in ("orbits", "primary-bodies", "accent-bodies"))


def _generate(
    parameters: dict[str, object] | None = None,
    layers: tuple[LogicalLayer, ...] = LAYERS,
):
    domain = PolygonDomain("panel", ((0, 0), (120, 0), (120, 80), (0, 80)))
    design_pass = DesignPass(
        id="orbit-pass",
        algorithm="orbital-concentric",
        target_domain_ids=(domain.id,),
        parameters=parameters or {},
        logical_layers=layers,
    )
    context = AlgorithmContext(
        job_seed=1,
        pass_seed=2,
        domain_seeds={domain.id: 37},
        surfaces=(),
        groups=(),
        relations=(),
        composition_transforms={},
    )
    canvas = CanvasGeometry(
        shape="polygon",
        width=120,
        height=80,
        polygon=domain.vertices,
        up_anchor="edge:0",
        domains=(domain,),
    )
    return OrbitalConcentricDomainAlgorithm().generate(
        canvas=canvas,
        domains=(domain,),
        design_pass=design_pass,
        context=context,
    )


def test_orbital_concentric_is_deterministic_and_emits_ordered_layers() -> None:
    parameters = {
        "orbit_count": 5,
        "bodies_per_orbit_range": [1, 3],
        "accent_probability": 0.4,
    }

    first = _generate(parameters)

    assert first == _generate(parameters)
    assert first.paths
    assert list(dict.fromkeys(path.layer_id for path in first.paths)) == [
        "orbits",
        "primary-bodies",
        "accent-bodies",
    ]
    assert {path.domain_id for path in first.paths} == {"panel"}


def test_orbital_concentric_requires_three_named_layers() -> None:
    with pytest.raises(ValueError, match="orbits.*primary-bodies.*accent-bodies"):
        _generate(layers=LAYERS[:2])


@pytest.mark.parametrize(
    "parameters",
    [
        {"unexpected": 1},
        {"orbit_count": "4"},
        {"orbit_gaps": 1},
        {"orbit_eccentricity": 1.0},
        {"bodies_per_orbit_range": [4, 2]},
        {"body_radius_range": [2.0, 1.0]},
        {"minimum_body_separation": math.tau},
    ],
)
def test_orbital_concentric_rejects_invalid_parameters(
    parameters: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _generate(parameters)


def test_zero_ellipse_variation_reuses_shape_and_rotation_for_every_orbit() -> None:
    result = _generate(
        {
            "orbit_count": 4,
            "orbit_eccentricity": 0.5,
            "orbit_eccentricity_variation": 0.0,
            "orbit_rotation": 0.4,
            "orbit_rotation_variation": 0.0,
            "bodies_per_orbit_range": [0, 0],
        }
    )
    orbits = [path for path in result.paths if path.layer_id == "orbits"]

    assert len(orbits) == 4
    assert all(path.closed for path in orbits)
    ratios = []
    angles = []
    for path in orbits:
        xs = [point[0] for point in path.points]
        ys = [point[1] for point in path.points]
        center = (sum(xs) / len(xs), sum(ys) / len(ys))
        farthest = max(path.points, key=lambda point: math.dist(point, center))
        nearest = min(path.points, key=lambda point: math.dist(point, center))
        ratios.append(math.dist(nearest, center) / math.dist(farthest, center))
        angles.append(math.atan2(farthest[1] - center[1], farthest[0] - center[0]))
    assert all(ratio == pytest.approx(math.sqrt(0.75), abs=0.02) for ratio in ratios)
    assert all(abs(angle - angles[0]) < 0.1 for angle in angles)


def test_body_gaps_split_orbits_into_open_segments() -> None:
    parameters = {
        "orbit_count": 2,
        "bodies_per_orbit_range": [2, 2],
        "minimum_body_separation": 0.0,
        "orbit_gaps": True,
    }
    with_gaps = _generate(parameters)
    without_gaps = _generate({**parameters, "orbit_gaps": False})

    gap_orbits = [path for path in with_gaps.paths if path.layer_id == "orbits"]
    complete_orbits = [path for path in without_gaps.paths if path.layer_id == "orbits"]
    assert gap_orbits and all(not path.closed for path in gap_orbits)
    assert len(complete_orbits) == 2
    assert all(path.closed for path in complete_orbits)


def test_impossible_minimum_body_separation_fails_clearly() -> None:
    with pytest.raises(ValueError, match="minimum_body_separation"):
        _generate(
            {
                "orbit_count": 1,
                "bodies_per_orbit_range": [4, 4],
                "minimum_body_separation": 2.0,
            }
        )


def test_small_domain_rejects_body_clearance_that_cannot_fit() -> None:
    domain = PolygonDomain("tiny", ((0, 0), (10, 0), (10, 10), (0, 10)))
    design_pass = DesignPass(
        id="orbit-pass",
        algorithm="orbital-concentric",
        target_domain_ids=(domain.id,),
        logical_layers=LAYERS,
    )
    context = AlgorithmContext(
        job_seed=1,
        pass_seed=2,
        domain_seeds={domain.id: 3},
        surfaces=(),
        groups=(),
        relations=(),
        composition_transforms={},
    )
    canvas = CanvasGeometry(
        shape="polygon",
        width=10,
        height=10,
        polygon=domain.vertices,
        up_anchor="edge:0",
        domains=(domain,),
    )
    with pytest.raises(ValueError, match="usable orbit radius"):
        OrbitalConcentricDomainAlgorithm().generate(
            canvas=canvas, domains=(domain,), design_pass=design_pass, context=context
        )


def test_gap_segmentation_does_not_add_seam_opposite_body() -> None:
    paths = _orbit_paths(
        center=(0, 0),
        major_radius=20,
        minor_radius=20,
        rotation=0,
        bodies=[(math.pi, 1.0, False)],
        parameters=OrbitalConcentricParameters(),
        domain_id="panel",
    )
    assert len(paths) == 1


def test_exact_fit_minimum_separation_is_evenly_distributed() -> None:
    angles = _body_angles(4, math.tau / 4, random.Random(7))
    assert len(angles) == 4
    gaps = [(angles[(index + 1) % 4] - angles[index]) % math.tau for index in range(4)]
    assert gaps == pytest.approx([math.tau / 4] * 4)


def test_body_range_rejects_maximum_count_that_cannot_fit_separation() -> None:
    with pytest.raises(ValueError, match="bodies_per_orbit_range.*minimum_body_separation"):
        OrbitalConcentricParameters(
            bodies_per_orbit_range=(1, 64), minimum_body_separation=0.1
        )
