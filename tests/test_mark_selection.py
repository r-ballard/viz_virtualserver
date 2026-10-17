import math

import pytest

from viz_virtualserver.fill_effects.mark_selection import (
    MarkSelection,
    derive_density_seed,
    validate_density_seed,
)


def test_literal_digest_and_nested_independent_sets():
    from viz_virtualserver.fill_effects.mark_selection import _candidate_hash

    assert _candidate_hash(-7, -3, 12) == int(
        "e903e3d31dd126fd85ebd501b03950b8e6f143424860945d7cb5930708735f25", 16
    )
    positions = [(r, c) for r in range(-8, 9) for c in range(-8, 9)]
    sets = [
        {p for p in positions if MarkSelection(d, -7).accepts(*p)} for d in (0, 0.25, 0.5, 0.75, 1)
    ]
    assert not sets[0] and len(sets[-1]) == len(positions)
    assert all(a <= b for a, b in zip(sets, sets[1:]))
    assert 0 < len(sets[2]) < len(positions)
    assert {p for p in positions[::-1] if MarkSelection(0.5, -7).accepts(*p)} == sets[2]
    assert {p for p in positions if MarkSelection(0.5, 8).accepts(*p)} != sets[2]
    assert isinstance(MarkSelection(0.5, -(2**63)).accepts(-(2**100), 2**100), bool)


def test_exact_ratio_boundary_and_endpoint_no_hash(monkeypatch):
    from viz_virtualserver.fill_effects import mark_selection as m

    numerator, denominator = (0.1).as_integer_ratio()
    threshold = (numerator << 256) // denominator
    monkeypatch.setattr(m, "_candidate_hash", lambda *args: threshold)
    assert not MarkSelection(0.1, 0).accepts(0, 0)
    monkeypatch.setattr(m, "_candidate_hash", lambda *args: threshold - 1)
    assert MarkSelection(0.1, 0).accepts(0, 0)
    monkeypatch.setattr(m, "_candidate_hash", lambda *args: pytest.fail("hashed endpoint"))
    assert not MarkSelection(0, 0).accepts(0, 0)
    assert MarkSelection(1, 0).accepts(0, 0)


@pytest.mark.parametrize("seed", [True, 1.0, "0", None, -(2**63) - 1, 2**63])
def test_strict_seeds_even_at_endpoints(seed):
    with pytest.raises(ValueError):
        validate_density_seed(seed)
    with pytest.raises(ValueError):
        MarkSelection(0, seed)


@pytest.mark.parametrize("density", [True, "0", None, -0.1, 1.1, math.nan, math.inf])
def test_invalid_density(density):
    with pytest.raises(ValueError):
        MarkSelection(density, 0)


def test_domain_seed_derivation_and_strict_indices():
    assert derive_density_seed(31, 0) == -7421177190933531874
    assert derive_density_seed(31, 0) != derive_density_seed(31, 1)
    assert -(2**63) <= derive_density_seed(2**64 - 1, -(2**63)) < 2**63
    with pytest.raises(ValueError):
        derive_density_seed(True, 0)
    with pytest.raises(ValueError):
        MarkSelection(1, 0).accepts(True, 0)
