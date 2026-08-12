"""Intrinsic canvas geometry for generative vector artwork."""

from .geometry import CanvasError, CanvasGeometry, build_canvas
from .models import CanvasSpec

__all__ = ["CanvasError", "CanvasGeometry", "CanvasSpec", "build_canvas"]
