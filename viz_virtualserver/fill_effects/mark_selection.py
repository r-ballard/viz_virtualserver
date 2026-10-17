"""Versioned, traversal-independent selection of lattice mark candidates."""

import hashlib
import struct
from dataclasses import dataclass, field

from .vector_fields import _finite_number

MARK_DENSITY_EFFECTS = frozenset(("stroke-dots", "vortex-marks", "field-marks"))


def validate_density_seed(seed: object) -> int:
    if type(seed) is not int or not -(2**63) <= seed < 2**63:
        raise ValueError("density seed must be a signed 64-bit integer")
    return seed


def _encode(*fields):
    return b"".join(struct.pack(">Q", len(v.encode("utf-8"))) + v.encode("utf-8") for v in fields)


def _candidate_hash(seed, row, column):
    value = _encode("viz-mark-density-v1", str(seed), str(row), str(column))
    return int.from_bytes(hashlib.sha256(value).digest(), "big")


def derive_density_seed(domain_seed: int, style_seed: int) -> int:
    if type(domain_seed) is not int:
        raise ValueError("domain seed must be an integer")
    validate_density_seed(style_seed)
    value = _encode("viz-topographic-density-v1", str(domain_seed), str(style_seed))
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big", signed=True)


@dataclass(frozen=True, slots=True)
class MarkSelection:
    density: float = 1.0
    seed: int = 0
    _threshold: int = field(init=False, repr=False)

    def __post_init__(self):
        density = _finite_number(self.density, "mark density")
        if not 0 <= density <= 1:
            raise ValueError("mark density must lie between 0 and 1")
        validate_density_seed(self.seed)
        numerator, denominator = density.as_integer_ratio()
        object.__setattr__(self, "density", density)
        object.__setattr__(self, "_threshold", (numerator << 256) // denominator)

    def accepts(self, row: int, column: int) -> bool:
        if type(row) is not int or type(column) is not int:
            raise ValueError("mark lattice indices must be integers")
        if self.density == 0:
            return False
        if self.density == 1:
            return True
        return _candidate_hash(self.seed, row, column) < self._threshold
