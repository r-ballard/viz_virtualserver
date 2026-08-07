from __future__ import annotations

from collections.abc import Iterator


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
