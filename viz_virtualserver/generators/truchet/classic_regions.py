"""Reconstruct the classic grammar's two fields from its sampled tile arcs."""

from __future__ import annotations

import math
from itertools import groupby

from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .geometry import SampledConnection
from .models import TileArrangement


def compose_regions(
    arrangement: TileArrangement, sampled: tuple[SampledConnection, ...],
) -> tuple[BaseGeometry, BaseGeometry]:
    """Return region zero and one near the domain origin, with no tile seams."""
    ox, oy = arrangement.origin
    size = arrangement.tile_size

    def local_corner(key: tuple[int, int]) -> tuple[float, float]:
        # Use the same world arithmetic as the curve sampler before translating,
        # including at decimal grids and large domain coordinates.
        return ((ox + key[0] * size / 2) - ox, (oy + key[1] * size / 2) - oy)

    fields: tuple[list[BaseGeometry], list[BaseGeometry]] = ([], [])
    try:
        for tile, connections in groupby(sampled, key=lambda connection: connection.tile):
            connections = tuple(connections)
            if len(connections) != 2 or {c.index for c in connections} != {0, 1}:
                raise ValueError("classic region reconstruction requires two tile arcs")
            caps, labels = [], []
            for connection in connections:
                a, b = tile.state.connections[connection.index]
                if (a - b) % 4 not in (1, 3):
                    raise ValueError("classic region reconstruction requires adjacent corner arcs")
                label = tile.state.edge_regions[a][0 if b == (a - 1) % 4 else 1]
                other = tile.state.edge_regions[b][0 if a == (b - 1) % 4 else 1]
                if label not in (0, 1) or label != other:
                    raise ValueError("inconsistent classic corner region labels")
                labels.append(label)
                corner = (connection.start[0] if connection.start[0] % 2 == 0
                          else connection.end[0],
                          connection.start[1] if connection.start[1] % 2 == 0
                          else connection.end[1])
                cap = Polygon((local_corner(corner),
                               *((x - ox, y - oy) for x, y in connection.points)))
                if not cap.is_valid or not math.isfinite(cap.area) or cap.area <= 0:
                    raise ValueError("invalid classic corner region geometry")
                caps.append(cap)
            if labels[0] != labels[1]:
                raise ValueError("classic region reconstruction requires two complementary fields")
            left, bottom = local_corner((2 * tile.column, 2 * tile.row))
            right, top = local_corner((2 * tile.column + 2, 2 * tile.row + 2))
            footprint = box(left, bottom, right, top)
            if not math.isfinite(footprint.area) or footprint.area <= 0:
                raise ValueError("classic tile area cannot be represented reliably")
            if any(not footprint.covers(cap) for cap in caps) or caps[0].intersection(caps[1]).area:
                raise ValueError("classic corner regions exceed the supported tile geometry")
            corners = unary_union(caps)
            middle = footprint.difference(corners)
            fields[labels[0]].append(corners)
            fields[1 - labels[0]].append(middle)
        result = tuple(unary_union(parts) if parts else GeometryCollection() for parts in fields)
        if any(not region.is_valid for region in result):
            raise ValueError("invalid classic composed region geometry")
    except GEOSException as exc:
        raise ValueError("classic region composition failed") from exc
    return result
