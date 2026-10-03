from itertools import product

import pytest

from truchet.assembly import assemble_grid
from truchet.grammar import compatible, compile_states


def test_seeded_grid_is_compatible_reproducible_and_translation_invariant():
    first = assemble_grid((0, 0, 43, 32), tile_size=10, seed=7)
    assert first == assemble_grid((0, 0, 43, 32), tile_size=10, seed=7)
    translated = assemble_grid((-20, -30, 23, 2), tile_size=10, seed=7)
    assert first.tiles == translated.tiles
    assert (first.columns, first.rows) == (5, 4)
    assert len({assemble_grid((0, 0, 43, 32), tile_size=10, seed=s).tiles for s in range(5)}) > 1
    by_position = {(t.column, t.row): t.state for t in first.tiles}
    for t in first.tiles:
        if t.column:
            assert compatible(by_position[t.column - 1, t.row], 1, t.state, 3)
        if t.row:
            assert compatible(by_position[t.column, t.row - 1], 2, t.state, 0)


def test_all_reachable_neighbor_constraints_admit_a_state():
    states = compile_states()
    # Left and below neighbors are linked through the diagonal predecessor.
    for diagonal, left, below in product(states, repeat=3):
        if compatible(diagonal, 2, left, 0) and compatible(diagonal, 1, below, 3):
            assert any(compatible(left, 1, s, 3) and compatible(below, 2, s, 0) for s in states)


def test_grid_limit_checked_before_allocation():
    assert len(assemble_grid((0, 0, 100000, 1), tile_size=1, seed=1).tiles) == 100000
    with pytest.raises(ValueError, match="100,000"):
        assemble_grid((0, 0, 100001, 1), tile_size=1, seed=1)


def test_decimal_tile_boundaries_preserve_arrangement_under_translation():
    original = assemble_grid((0, 0, 0.3, 0.3), tile_size=0.1, seed=7)
    translated = assemble_grid((-1, -1, -0.7, -0.7), tile_size=0.1, seed=7)
    assert (original.columns, original.rows) == (3, 3)
    assert (translated.columns, translated.rows) == (3, 3)
    assert original.tiles == translated.tiles


def test_meaningful_fractional_tile_is_still_covered():
    arrangement = assemble_grid((0, 0, 0.30000001, 0.3), tile_size=0.1, seed=7)
    assert (arrangement.columns, arrangement.rows) == (4, 3)
