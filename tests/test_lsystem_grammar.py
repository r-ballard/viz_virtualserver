import pytest

import lsystem.grammar as grammar
from lsystem.grammar import ExpansionLimitError, iter_generations


def test_iter_generations_rewrites_without_retaining_semantics():
    generated = list(iter_generations("F", {"F": "F+F"}, generations=2, max_symbols=100))
    assert generated == [(0, "F"), (1, "F+F"), (2, "F+F+F+F")]


def test_expansion_limit_is_enforced_before_large_generation_is_returned():
    with pytest.raises(ExpansionLimitError, match="generation 4"):
        list(iter_generations("F", {"F": "FF"}, generations=4, max_symbols=15))


def test_tagged_expansion_inherits_first_matching_child_and_marks_new_growth():
    generated = list(
        grammar.iter_tagged_generations(
            "F", {"F": "FF"}, generations=2, max_symbols=100
        )
    )

    assert generated == [
        (0, (("F", 0),)),
        (1, (("F", 0), ("F", 1))),
        (2, (("F", 0), ("F", 2), ("F", 1), ("F", 2))),
    ]
