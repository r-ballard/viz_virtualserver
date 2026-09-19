import pytest

import lsystem.grammar as grammar
from lsystem.grammar import ExpansionLimitError, iter_generations


def test_iter_generations_rewrites_without_retaining_semantics():
    generated = list(iter_generations("F", {"F": "F+F"}, generations=2, max_symbols=100))
    assert generated == [(0, "F"), (1, "F+F"), (2, "F+F+F+F")]


def test_expansion_limit_is_enforced_before_large_generation_is_returned():
    with pytest.raises(ExpansionLimitError, match="generation 4"):
        list(iter_generations("F", {"F": "FF"}, generations=4, max_symbols=15))


def test_tagged_expansion_inherits_all_matching_children_and_marks_new_growth():
    generated = list(
        grammar.iter_tagged_generations(
            "XF", {"X": "F", "F": "FF"}, generations=2, max_symbols=100
        )
    )

    assert generated == [
        (0, (("X", 0), ("F", 0))),
        (1, (("F", 1), ("F", 0), ("F", 0))),
        (2, (("F", 1), ("F", 1), ("F", 0), ("F", 0), ("F", 0), ("F", 0))),
    ]


@pytest.mark.parametrize("policy, first_births, second_births", [
    ("inherit_all", (0, 0), (0, 0, 0, 0)),
    ("rewrite", (1, 1), (2, 2, 2, 2)),
    ("inherit_first", (0, 1), (0, 2, 1, 2)),
])
def test_lineage_policy_dates_repeated_symbols(policy, first_births, second_births):
    generated = list(grammar.iter_tagged_generations(
        "F", {"F": "FF"}, generations=2, max_symbols=10, lineage_policy=policy,
    ))

    assert generated[0] == (0, (("F", 0),))
    assert generated[1] == (1, tuple(("F", birth) for birth in first_births))
    assert generated[2] == (2, tuple(("F", birth) for birth in second_births))


@pytest.mark.parametrize("policy, first_birth, second_birth", [
    ("inherit_all", 0, 0), ("rewrite", 1, 1), ("inherit_first", 0, 1),
])
def test_lineage_policy_handles_branches_different_symbols_and_carry_through(
    policy, first_birth, second_birth,
):
    generated = list(grammar.iter_tagged_generations(
        "fF", {"F": "G[+F]F"}, generations=1, max_symbols=20, lineage_policy=policy,
    ))

    assert generated[1] == (1, (
        ("f", 0), ("G", 1), ("[", 1), ("+", 1),
        ("F", first_birth), ("]", 1), ("F", second_birth),
    ))


@pytest.mark.parametrize("policy, birth", [
    ("inherit_all", 0), ("rewrite", 1), ("inherit_first", 0),
])
def test_lineage_policy_distinguishes_explicit_identity_rule_from_carry_through(policy, birth):
    generated = list(grammar.iter_tagged_generations(
        "FG", {"F": "F"}, generations=1, max_symbols=10, lineage_policy=policy,
    ))
    assert generated[1] == (1, (("F", birth), ("G", 0)))


@pytest.mark.parametrize("policy", ["unknown", None])
def test_tagged_iterator_rejects_invalid_lineage_policy_even_at_generation_zero(policy):
    with pytest.raises(ValueError, match="lineage_policy"):
        list(grammar.iter_tagged_generations("F", {}, 0, 10, lineage_policy=policy))
