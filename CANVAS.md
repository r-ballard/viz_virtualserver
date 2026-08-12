# Intrinsic vector canvases

`viz-virtualserver` treats the drawing canvas as part of the generated vector artifact rather than assuming that every algorithm draws into an anonymous rectangle. This is a design-space concern: `plotter-workflow` still owns physical paper placement, imposition, pen assignment, HP-GL conversion, and DPX-3300 transport.

The initial canvas contract supports `rectangle`, `square`, `triangle`, and custom `polygon` domains. It is intentionally independent of any one algorithm or origami layout.

## Geometry model

A resolved canvas contains:

- an SVG design-space `width` and `height`;
- an ordered polygon describing the drawable domain;
- a centroid;
- an `up_anchor` identifying one polygon edge or vertex as the semantic top of the artwork;
- a normalized `up_vector` from the centroid toward that anchor; and
- geometry helpers such as point containment, distance-to-boundary, and random point sampling.

The coordinate system is normal SVG design space: x increases to the right and y increases downward.

`up_anchor` uses one of two forms:

```text
edge:N
vertex:N
```

where `N` is a zero-based index into the ordered canvas polygon.

This makes reading orientation geometric and explicit. For example, a conventional rectangular page is side-up:

```json
{
  "shape": "rectangle",
  "width": 1000,
  "height": 700,
  "up_anchor": "edge:0"
}
```

A square whose corner is the intended top uses:

```json
{
  "shape": "square",
  "width": 1000,
  "height": 1000,
  "up_anchor": "vertex:0"
}
```

The canonical triangle is ordered with vertex 0 at its apex, so triangle canvases default to `vertex:0`:

```text
          vertex 0
             /\
            /  \
           /    \
          /      \
  vertex 2--------vertex 1
```

That gives triangular selector/reveal artwork a native apex-up orientation rather than asking an imposition script to reinterpret a rectangular source later.

## API

Resolve canvas geometry:

```bash
curl -sS http://localhost:5699/Canvas \
  -H 'content-type: application/json' \
  --data @examples/canvases/triangle.json
```

Generate an SVG template carrying the intrinsic canvas contract:

```bash
curl -sS http://localhost:5699/CanvasSvg \
  -H 'content-type: application/json' \
  --data @examples/canvases/triangle.json \
  > triangle.svg
```

For visual inspection, opt into a drawable canvas boundary:

```bash
curl -sS 'http://localhost:5699/CanvasSvg?boundary=true&boundary_stroke_width=2' \
  -H 'content-type: application/json' \
  --data @examples/canvases/triangle.json \
  > triangle-guide.svg
```

The boundary is deliberately opt-in because it is real SVG stroke geometry and therefore could be plotted. The intrinsic clipping path under `<defs>` is non-rendering.

## SVG contract

A triangle template contains root metadata similar to:

```xml
<svg
  viewBox="0 0 1000 1000"
  data-viz-canvas-version="1"
  data-viz-canvas-shape="triangle"
  data-viz-canvas-coordinate-system="svg-y-down"
  data-viz-canvas-up-anchor="vertex:0"
  data-viz-canvas-up-vector="0,-1"
  data-viz-canvas-polygon="500,0 1000,1000 0,1000"
  data-viz-canvas-clip-id="viz-canvas-clip">
  <defs>
    <clipPath id="viz-canvas-clip" clipPathUnits="userSpaceOnUse">
      <path d="M 500 0 L 1000 1000 L 0 1000 Z" />
    </clipPath>
  </defs>
</svg>
```

Future SVG exporters should reuse `viz_canvas.svg.canvas_root_attributes()` and `append_canvas_clip()` rather than reproduce these attributes independently. `append_canvas_clip()` returns `url(#viz-canvas-clip)` so the exporter can apply the clip directly to each drawable group.

For strict multi-pen output, the existing `pen-N` groups must remain **top-level** SVG children. Apply the canvas clip to those groups directly rather than nesting them inside a canvas wrapper:

```xml
<g id="pen-1" data-pen="1" clip-path="url(#viz-canvas-clip)" ...>
  ...
</g>
```

That preserves the current `viz-virtualserver` -> `plotter-workflow` pen-layer contract while still making the logical canvas intrinsic to the SVG.

## Generator-facing behavior

The canvas is not only an export-time crop. Algorithms can consume the geometry while they generate paths:

```python
canvas.contains((x, y))
canvas.random_point(rng)
canvas.distance_to_boundary((x, y))
canvas.centroid
canvas.up_vector
canvas.polygon
```

This is the intended foundation for shape-aware algorithms. For example, a concentric-circle generator can choose centers only inside a triangle and use distance-to-boundary to choose radii or density, instead of drawing into a rectangle and discarding most of the result afterward.

Final clipping remains useful as a defensive SVG boundary even when an algorithm is shape-aware.

## Cootie-catcher use

The intended division of responsibility is:

```text
viz-virtualserver
  selector/reveal source -> native triangle canvas, apex-up
  outer source           -> square canvas, side-up or corner-up as declared

plotter-workflow
  maps source up_vector to the folded panel's intended reading direction
  scales/translates into the physical imposition polygon
  applies final defensive polygon clipping
```

`plotter-workflow` should not need to invent triangle-aware generative behavior. It consumes a vector file whose logical domain and orientation are already explicit.

## Scope of this first slice

This patch establishes the canvas contract and API only. It does **not** yet change L-system output or the py5 renderer. The next integration should exercise this abstraction with one existing algorithm before extracting any shared algorithm package or changing repository boundaries.
