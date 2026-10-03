"""Immutable, JSON-compatible values used by validated design jobs."""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

type JsonScalar = None | bool | int | float | str
type FrozenJsonValue = (
    JsonScalar | tuple[FrozenJsonValue, ...] | Mapping[str, FrozenJsonValue]
)
type FrozenJsonObject = Mapping[str, FrozenJsonValue]


def freeze_json_value(value: object, *, context: str = "value") -> FrozenJsonValue:
    """Return an immutable defensive copy of one JSON-compatible value."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{context} JSON number must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJsonValue] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{context} JSON object keys must be strings")
            frozen[key] = freeze_json_value(nested, context=f"{context}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json_value(nested, context=f"{context}[{index}]")
            for index, nested in enumerate(value)
        )
    raise TypeError(f"{context} must contain only JSON-compatible values")


def freeze_json_object(
    value: Mapping[str, object], *, context: str
) -> FrozenJsonObject:
    """Return an immutable defensive copy of a JSON object."""

    frozen = freeze_json_value(value, context=context)
    if not isinstance(frozen, Mapping):  # pragma: no cover - root type is annotated
        raise TypeError(f"{context} must be a JSON object")
    return frozen


def thaw_json_value(value: FrozenJsonValue) -> object:
    """Return ordinary JSON containers suitable for request and audit serialization."""

    if isinstance(value, Mapping):
        return {key: thaw_json_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [thaw_json_value(nested) for nested in value]
    return value
