"""Minimal py5 rendering check intended to run inside the renderer container."""

from pathlib import Path

import py5

OUTPUT = Path("/tmp/py5-smoke.png")


def setup() -> None:
    py5.size(256, 256)
    py5.background(255)
    py5.stroke(0)
    py5.stroke_weight(2)
    py5.line(32, 224, 128, 32)
    py5.line(128, 32, 224, 224)
    py5.save_frame(OUTPUT)
    py5.exit_sketch()


py5.run_sketch(block=True)
print(OUTPUT)
