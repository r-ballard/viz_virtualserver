from __future__ import annotations

import hashlib

from viz_virtualserver.canvas.design import LogicalLayer


def curve_layer_ids(
    layers: tuple[LogicalLayer, ...], *, outline_layer_id: str | None = None,
) -> tuple[str, ...]:
    ids = tuple(layer.id for layer in layers)
    if (not ids or any(not isinstance(value, str) or not value.strip() for value in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("Truchet requires one or more unique, nonblank curve layer IDs")
    if outline_layer_id is not None:
        if not isinstance(outline_layer_id, str) or not outline_layer_id.strip():
            raise ValueError("outline_layer_id must be a nonblank string")
        if outline_layer_id not in ids:
            raise ValueError("outline_layer_id must name a declared logical layer")
        ids = tuple(value for value in ids if value != outline_layer_id)
        if not ids:
            raise ValueError("Truchet requires at least one curve layer besides the outline")
    return ids


def component_layer(component_id: int, *, seed: int, layer_ids: tuple[str, ...]) -> str:
    if len(layer_ids) == 1:
        return layer_ids[0]
    # Independent of geometry RNG and channel names; channel order is intentional.
    payload = f"truchet-color-v1:{seed}:{component_id}".encode("ascii")
    index = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % len(layer_ids)
    return layer_ids[index]
