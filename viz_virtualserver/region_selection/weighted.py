"""Versioned independent weighted selection without a mutable random stream."""

import hashlib
import struct
from dataclasses import dataclass

from .components import RegionComponent


@dataclass(frozen=True, slots=True)
class WeightedOption:
    id: str
    weight: int

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("choice ID must be nonblank")
        if type(self.weight) is not int or not 1 <= self.weight <= 1_000_000:
            raise ValueError("choice weight must be an integer from 1 to 1,000,000")


@dataclass(frozen=True, slots=True)
class ComponentDecision:
    component: RegionComponent
    choice_id: str


def choose_components(
    components, options, *, domain_seed: int, component_seed: int, bands: tuple[int, ...]
) -> tuple[ComponentDecision, ...]:
    try:
        validated_options = []
        for option in options:
            if not isinstance(option, WeightedOption) or len(validated_options) >= 32:
                raise ValueError("choices require 1 through 32 weighted options")
            validated_options.append(option)
        options = tuple(sorted(validated_options, key=lambda v: v.id))
        bands = tuple(bands)
    except TypeError as error:
        raise ValueError("options and bands must be iterable") from error
    if (
        not 1 <= len(options) <= 32
        or any(not isinstance(v, WeightedOption) for v in options)
        or len({v.id for v in options}) != len(options)
    ):
        raise ValueError("choices require 1 through 32 unique weighted options")
    if type(domain_seed) is not int or type(component_seed) is not int:
        raise ValueError("component seeds must be integers")
    if (
        not bands
        or any(type(b) is not int or b < 0 for b in bands)
        or len(set(bands)) != len(bands)
    ):
        raise ValueError("bands must be distinct nonnegative integers")
    bands = tuple(sorted(bands))
    total = sum(v.weight for v in options)
    decisions = []
    for component in sorted(components, key=lambda v: v.id):
        fields = (
            "viz-component-choice-v1",
            str(domain_seed),
            str(component_seed),
            ",".join(map(str, bands)),
            component.id,
        )
        encoded = b"".join(
            struct.pack(">Q", len(v.encode("utf-8"))) + v.encode("utf-8") for v in fields
        )
        bucket = int.from_bytes(hashlib.sha256(encoded).digest(), "big") % total
        for option in options:
            if bucket < option.weight:
                decisions.append(ComponentDecision(component, option.id))
                break
            bucket -= option.weight
    return tuple(decisions)
