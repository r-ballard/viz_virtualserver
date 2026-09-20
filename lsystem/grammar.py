from __future__ import annotations

from collections.abc import Iterator
from typing import Literal


class ExpansionLimitError(ValueError):
    """Raised before an L-system rewrite would exceed the configured symbol ceiling."""


def iter_generations(
    axiom: str,
    rules: dict[str, str],
    generations: int,
    max_symbols: int,
) -> Iterator[tuple[int, str]]:
    """Yield generation number and expanded command string without retaining history."""

    if len(axiom) > max_symbols:
        raise ExpansionLimitError(
            f"generation 0 contains {len(axiom)} symbols, exceeding max_symbols={max_symbols}"
        )

    current = axiom
    yield 0, current

    for generation in range(1, generations + 1):
        pieces: list[str] = []
        symbol_count = 0

        for symbol in current:
            replacement = rules.get(symbol, symbol)
            symbol_count += len(replacement)
            if symbol_count > max_symbols:
                raise ExpansionLimitError(
                    f"generation {generation} exceeds max_symbols={max_symbols}"
                )
            pieces.append(replacement)

        current = "".join(pieces)
        yield generation, current


def iter_tagged_generations(
    axiom: str,
    rules: dict[str, str],
    generations: int,
    max_symbols: int,
    *,
    lineage_policy: Literal["inherit_all", "rewrite", "inherit_first"] = "inherit_all",
) -> Iterator[tuple[int, tuple[tuple[str, int], ...]]]:
    """Yield symbols with policy-defined birth tags, independent of turtle geometry.

    Carry-through symbols retain their age. For explicit productions, inherit_all
    preserves age on all same-symbol children; inherit_first preserves only the
    first match; rewrite dates every child to the current step, even for F -> F.
    """

    if lineage_policy not in ("inherit_all", "rewrite", "inherit_first"):
        raise ValueError("lineage_policy must be 'inherit_all', 'rewrite', or 'inherit_first'")

    if len(axiom) > max_symbols:
        raise ExpansionLimitError(
            f"generation 0 contains {len(axiom)} symbols, exceeding max_symbols={max_symbols}"
        )

    current = tuple((symbol, 0) for symbol in axiom)
    yield 0, current

    for generation in range(1, generations + 1):
        expanded: list[tuple[str, int]] = []
        for symbol, birth_generation in current:
            replacement = rules.get(symbol)
            if replacement is None:
                expanded.append((symbol, birth_generation))
                continue

            inherited = False
            for child in replacement:
                if child == symbol and (
                    lineage_policy == "inherit_all"
                    or (lineage_policy == "inherit_first" and not inherited)
                ):
                    expanded.append((child, birth_generation))
                    inherited = True
                else:
                    expanded.append((child, generation))

                if len(expanded) > max_symbols:
                    raise ExpansionLimitError(
                        f"generation {generation} exceeds max_symbols={max_symbols}"
                    )

        current = tuple(expanded)
        yield generation, current
