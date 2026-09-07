from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
Path = list[Point]


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True)
class GenerationGeometry:
    generation: int
    symbol_count: int
    paths: list[Path]
    segment_count: int
    bounds: Bounds


class GeometryError(ValueError):
    """Raised when drawing commands contain invalid branch structure."""


def commands_to_geometry(
    commands: str,
    *,
    generation: int,
    step: float,
    angle_degrees: float,
    initial_heading_degrees: float,
    draw_symbols: set[str],
    move_symbols: set[str],
) -> GenerationGeometry:
    """Convert L-system commands directly to numeric polylines.

    No drawing API is invoked. The current position and heading are updated in memory,
    and connected forward moves are accumulated into paths for efficient downstream
    rendering and HPGL conversion.
    """

    x = 0.0
    y = 0.0
    turn_index = 0
    half_turns = 0
    stack: list[tuple[float, float, int, int]] = []
    paths: list[Path] = []
    current_path: Path = [(x, y)]

    angle_radians = math.radians(angle_degrees)
    initial_heading_radians = math.radians(initial_heading_degrees)
    direction_cache: dict[tuple[int, int], tuple[float, float]] = {}

    def direction() -> tuple[float, float]:
        key = (turn_index, half_turns % 2)
        cached = direction_cache.get(key)
        if cached is not None:
            return cached

        heading = initial_heading_radians + turn_index * angle_radians + key[1] * math.pi
        vector = (math.cos(heading), math.sin(heading))
        direction_cache[key] = vector
        return vector

    def flush_path() -> None:
        nonlocal current_path
        if len(current_path) > 1:
            paths.append(current_path)
        current_path = [(x, y)]

    for symbol in commands:
        if symbol in draw_symbols:
            dx, dy = direction()
            x += step * dx
            y += step * dy
            current_path.append((x, y))
        elif symbol in move_symbols:
            flush_path()
            dx, dy = direction()
            x += step * dx
            y += step * dy
            current_path = [(x, y)]
        elif symbol == "+":
            turn_index += 1
        elif symbol == "-":
            turn_index -= 1
        elif symbol == "|":
            half_turns += 1
        elif symbol == "[":
            flush_path()
            stack.append((x, y, turn_index, half_turns))
        elif symbol == "]":
            flush_path()
            if not stack:
                raise GeometryError("encountered ']' without matching '['")
            x, y, turn_index, half_turns = stack.pop()
            current_path = [(x, y)]

    flush_path()

    if stack:
        raise GeometryError(f"{len(stack)} unmatched '[' command(s)")

    bounds = bounds_for_paths(paths)
    segment_count = sum(len(path) - 1 for path in paths)
    return GenerationGeometry(
        generation=generation,
        symbol_count=len(commands),
        paths=paths,
        segment_count=segment_count,
        bounds=bounds,
    )


def tagged_commands_to_geometries(
    commands: tuple[tuple[str, int], ...],
    *,
    generation: int,
    step: float,
    angle_degrees: float,
    initial_heading_degrees: float,
    draw_symbols: set[str],
    move_symbols: set[str],
) -> dict[int, GenerationGeometry]:
    """Render one geometry layer for each drawable symbol birth generation."""

    hidden_draw_symbol = "\0"
    birth_generations = sorted(
        {
            birth_generation
            for symbol, birth_generation in commands
            if symbol in draw_symbols
        }
    )
    geometries: dict[int, GenerationGeometry] = {}
    for birth_generation in birth_generations:
        filtered = "".join(
            (
                hidden_draw_symbol
                if symbol in draw_symbols and symbol_birth != birth_generation
                else symbol
            )
            for symbol, symbol_birth in commands
        )
        geometries[birth_generation] = commands_to_geometry(
            filtered,
            generation=generation,
            step=step,
            angle_degrees=angle_degrees,
            initial_heading_degrees=initial_heading_degrees,
            draw_symbols=draw_symbols,
            move_symbols=move_symbols | {hidden_draw_symbol},
        )
    return geometries


def bounds_for_paths(paths: list[Path]) -> Bounds:
    points = [point for path in paths for point in path]
    if not points:
        return Bounds(0.0, 0.0, 0.0, 0.0)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def union_bounds(bounds: list[Bounds]) -> Bounds:
    if not bounds:
        return Bounds(0.0, 0.0, 0.0, 0.0)
    return Bounds(
        min(item.min_x for item in bounds),
        min(item.min_y for item in bounds),
        max(item.max_x for item in bounds),
        max(item.max_y for item in bounds),
    )
