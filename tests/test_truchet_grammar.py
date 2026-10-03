import math

import pytest

from viz_virtualserver.generators.truchet.grammar import compatible, compile_states
from viz_virtualserver.generators.truchet.models import TruchetParameters


def test_rotations_and_complements_preserve_connections_and_swap_regions():
    states = compile_states()
    assert len(states) == 8
    assert states[0].connections == ((0, 3), (1, 2))
    assert states[2].connections == ((1, 0), (2, 3))
    for normal, inverse in zip(states[::2], states[1::2], strict=True):
        assert normal.connections == inverse.connections
        assert inverse.edge_regions == tuple(
            tuple(1 - r for r in edge) for edge in normal.edge_regions
        )
    assert states[0].edge_regions == ((1, 0), (0, 1), (1, 0), (0, 1))


def test_compatibility_reverses_neighbor_edge():
    a = compile_states()[0]
    assert compatible(a, 1, a, 3) is False
    assert compatible(a, 1, compile_states()[1], 3) is True


def test_default_arc_is_quarter_circle_sagitta():
    p = TruchetParameters()
    assert p.arc_a == pytest.approx(math.sqrt(2) / 2 - 0.5)
    assert p.arc_a == p.arc_b
    assert p.tile_size == 10


@pytest.mark.parametrize(
    "values",
    [
        {"tile_size": 0},
        {"tile_size": True},
        {"tile_size": "10"},
        {"arc_a": float("nan")},
        {"arc_b": 0.46},
        {"arc_a": -0.45},
        {"curve_tolerance": float("inf")},
        {"curve_tolerance": 0},
        {"other": 2},
    ],
)
def test_invalid_controls_rejected(values):
    with pytest.raises(ValueError):
        TruchetParameters.model_validate(values)
