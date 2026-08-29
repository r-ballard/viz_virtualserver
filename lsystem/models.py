from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PenLayerSpec(BaseModel):
    """Map a contiguous generation span to one physical plotter pen."""

    pen: int = Field(ge=1, le=8)
    start_generation: int = Field(ge=0)
    end_generation: int = Field(ge=0)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_range(self) -> PenLayerSpec:
        if self.end_generation < self.start_generation:
            raise ValueError("end_generation must be >= start_generation")
        return self


class LSystemRequest(BaseModel):
    """Definition of a deterministic context-free L-system drawing."""

    axiom: str = Field(min_length=1)
    rules: dict[str, str]
    generations: int = Field(default=4, ge=0, le=50)
    angle: float = 90.0
    step: float = Field(default=10.0, gt=0)
    initial_heading: float = 0.0
    draw_symbols: list[str] = Field(default_factory=lambda: ["F"])
    move_symbols: list[str] = Field(default_factory=lambda: ["f"])
    pen_layers: list[PenLayerSpec] | None = None
    growth_mode: Literal["cumulative", "delta"] = "cumulative"
    max_symbols: int = Field(default=1_000_000, ge=1, le=10_000_000)

    @model_validator(mode="after")
    def validate_symbols_and_layers(self) -> LSystemRequest:
        bad_keys = [key for key in self.rules if len(key) != 1]
        if bad_keys:
            raise ValueError(f"rule keys must be single symbols: {bad_keys}")

        for name, symbols in (
            ("draw_symbols", self.draw_symbols),
            ("move_symbols", self.move_symbols),
        ):
            if any(len(symbol) != 1 for symbol in symbols):
                raise ValueError(f"{name} entries must be single symbols")
            if len(set(symbols)) != len(symbols):
                raise ValueError(f"{name} contains duplicate symbols")

        overlap = set(self.draw_symbols) & set(self.move_symbols)
        if overlap:
            raise ValueError(f"symbols cannot both draw and move: {sorted(overlap)}")

        if self.pen_layers is not None:
            self._validate_explicit_layers()

        return self

    def _validate_explicit_layers(self) -> None:
        assert self.pen_layers is not None
        if not self.pen_layers:
            raise ValueError("pen_layers cannot be empty when provided")

        pens = [layer.pen for layer in self.pen_layers]
        if len(set(pens)) != len(pens):
            raise ValueError("each physical pen may appear only once in pen_layers")

        covered: dict[int, int] = {}
        for layer in self.pen_layers:
            if layer.end_generation > self.generations:
                raise ValueError(
                    f"pen {layer.pen} ends at generation {layer.end_generation}, "
                    f"but generations={self.generations}"
                )
            for generation in range(layer.start_generation, layer.end_generation + 1):
                if generation in covered:
                    raise ValueError(
                        f"generation {generation} is assigned to both pen "
                        f"{covered[generation]} and pen {layer.pen}"
                    )
                covered[generation] = layer.pen

        expected = set(range(self.generations + 1))
        missing = sorted(expected - set(covered))
        if missing:
            raise ValueError(f"pen_layers do not cover generations: {missing}")
