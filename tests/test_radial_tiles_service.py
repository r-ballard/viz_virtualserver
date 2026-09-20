from __future__ import annotations

import pytest

from radial_tiles.service import RadialTilesDomainAlgorithm
from viz_canvas.design import DesignPass, LogicalLayer
from viz_canvas.geometry import CanvasGeometry
from viz_canvas.models import PolygonDomain
from viz_canvas.runner import AlgorithmContext

LAYERS = (
    LogicalLayer("structural-rings"),
    LogicalLayer("primary-tiles"),
    LogicalLayer("accent-tiles"),
)


def _domain(domain_id: str, offset: float = 0.0) -> PolygonDomain:
    return PolygonDomain(
        domain_id,
        (
            (offset, 0.0),
            (offset + 80.0, 0.0),
            (offset + 70.0, 50.0),
            (offset + 30.0, 35.0),
            (offset, 50.0),
        ),
    )


def _generate(
    *domains: PolygonDomain,
    seed: int = 17,
    parameters: dict[str, object] | None = None,
    layers: tuple[LogicalLayer, ...] = LAYERS,
):
    design_pass = DesignPass(
        id="radial-pass",
        algorithm="radial-tiles",
        target_domain_ids=tuple(domain.id for domain in domains),
        parameters=parameters or {},
        logical_layers=layers,
    )
    context = AlgorithmContext(
        job_seed=1,
        pass_seed=2,
        domain_seeds={domain.id: seed + index for index, domain in enumerate(domains)},
        surfaces=(),
        groups=(),
        relations=(),
        composition_transforms={},
    )
    canvas = CanvasGeometry(
        shape="polygon",
        width=200.0,
        height=100.0,
        polygon=domains[0].vertices,
        up_anchor="edge:0",
        domains=domains,
    )
    return RadialTilesDomainAlgorithm().generate(
        canvas=canvas,
        domains=domains,
        design_pass=design_pass,
        context=context,
    )


def test_radial_tiles_are_deterministic_neutral_and_layered() -> None:
    domain = _domain("panel")

    first = _generate(domain)
    second = _generate(domain)

    assert first == second
    assert first.producing_pass_id == "radial-pass"
    assert first.paths
    assert {path.layer_id for path in first.paths} == {
        "structural-rings",
        "primary-tiles",
        "accent-tiles",
    }
    assert list(dict.fromkeys(path.layer_id for path in first.paths)) == [
        "structural-rings",
        "primary-tiles",
        "accent-tiles",
    ]
    layer_rank = {layer.id: index for index, layer in enumerate(LAYERS)}
    ranks = [layer_rank[path.layer_id] for path in first.paths]
    assert ranks == sorted(ranks)
    assert {path.domain_id for path in first.paths} == {"panel"}
    assert {path.coordinate_frame for path in first.paths} == {"domain"}


def test_radial_tiles_use_independent_domain_seeds_without_merging() -> None:
    first_domain = _domain("first")
    second_domain = _domain("second", 100.0)

    result = _generate(first_domain, second_domain)

    first_paths = tuple(path for path in result.paths if path.domain_id == "first")
    second_paths = tuple(path for path in result.paths if path.domain_id == "second")
    assert first_paths
    assert second_paths
    assert tuple(path.points for path in first_paths) != tuple(
        path.points for path in second_paths
    )


def test_radial_tiles_require_the_three_named_layers_in_order() -> None:
    with pytest.raises(ValueError, match="three logical layers"):
        _generate(_domain("panel"), layers=LAYERS[:2])

    wrong_order = (LAYERS[1], LAYERS[0], LAYERS[2])
    with pytest.raises(ValueError, match="structural-rings.*primary-tiles.*accent-tiles"):
        _generate(_domain("panel"), layers=wrong_order)


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"motif_count": 0}, "motif_count"),
        ({"ring_count": 0}, "ring_count"),
        ({"tile_density": 2}, "tile_density"),
        ({"omission_rate": 1.5}, "omission_rate"),
        ({"unexpected": 1}, "unexpected"),
        ({"motif_count": "3"}, "motif_count"),
        ({"motif_count": True}, "motif_count"),
        ({"center_drift": "0.2"}, "center_drift"),
        ({"closed_tiles": 1}, "closed_tiles"),
    ],
)
def test_radial_tiles_reject_invalid_parameters(
    parameters: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _generate(_domain("panel"), parameters=parameters)


def test_radial_tiles_parameter_changes_are_deterministic() -> None:
    domain = _domain("panel")
    parameters = {
        "motif_count": 2,
        "ring_count": 3,
        "tile_density": 12,
        "center_drift": 0.08,
        "angular_jitter": 0.12,
        "radial_jitter": 0.08,
        "omission_rate": 0.2,
        "closed_tiles": False,
    }

    configured = _generate(domain, parameters=parameters)

    assert configured == _generate(domain, parameters=parameters)
    assert any(not path.closed for path in configured.paths if path.layer_id != "structural-rings")
