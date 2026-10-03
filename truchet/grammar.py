"""Square states: edges 0..3 run bottom, right, top, left around the boundary."""

from .models import TileState


def compile_states() -> tuple[TileState, ...]:
    base = ((1, 0), (0, 1), (1, 0), (0, 1))
    states = []
    for turn in range(4):
        regions = tuple(base[(edge - turn) % 4] for edge in range(4))
        connections = tuple(((a + turn) % 4, (b + turn) % 4) for a, b in ((0, 3), (1, 2)))
        for complement in (False, True):
            fields = tuple(tuple(1 - r for r in edge) for edge in regions) if complement else regions
            states.append(TileState(turn, complement, connections, fields))
    return tuple(states)


def compatible(a: TileState, a_edge: int, b: TileState, b_edge: int) -> bool:
    return a.edge_regions[a_edge] == b.edge_regions[b_edge][::-1]
