# Polygon-domain canvases

`viz-virtualserver` treats the drawing canvas as part of the generated vector artifact rather than assuming that every algorithm draws into an anonymous rectangle. This is a design-space concern: `plotter-workflow` still owns physical paper placement, imposition, pen assignment, HP-GL conversion, and DPX-3300 transport.

The canvas contract supports `rectangle`, `square`, `triangle`, and custom `polygon` domains. It is intentionally independent of any one algorithm or physical layout. `CanvasGeometry` is this repository's API-neutral implementation of the architecture's intrinsic-canvas concept; `CanvasSpec` remains the Pydantic request model used by the HTTP API.

## Canonical domain grammar

```text
IntrinsicCanvas
    -> zero or more PolygonDomains

PolygonDomain
    -> immutable simple ordered polygon
    -> canonical canvas coordinates
    -> overlap with other domains is legal

PolygonSurface
    -> optional semantic reference to exactly one domain

PolygonGroup
    -> ordered semantic surface collection only

DomainRelation
    -> optional typed semantic relationship

DesignPass
    -> targets one or more domains

DesignResult
    -> neutral vector paths + logical layers + optional derived domains
```

The ordered vertices of a `PolygonDomain` define stable features: `edge:i = vertex:i -> vertex:(i+1 mod n)`. Clockwise and counterclockwise input are both accepted, and vertex order is never silently normalized. All domain vertices and generated vector paths use canonical canvas coordinates.

Domains are independent. They may overlap, and overlap does not imply a merge. A `PolygonSurface`, when declared, references exactly one domain. `PolygonGroup` membership preserves the declared surface order but does not imply adjacency, union, or any other geometric relationship. Typed `DomainRelation` values are optional and must be declared explicitly when semantics such as adjacency, correspondence, alignment, containment, or overlap matter.

A `DesignPass` reads one or more target domains and returns neutral `VectorPath` values assigned to logical layers. Logical layers express design intent; they are not physical plotter or pen slots. Operations that change geometry create new derived domains with provenance rather than mutating their source domains.

A conceptual domain collection can contain independent geometry such as:

```json
{
  "domains": [
    {"id": "domain-a", "vertices": [[0, 0], [80, 0], [80, 60], [0, 60]]},
    {"id": "domain-b", "vertices": [[50, 20], [110, 20], [80, 80]]}
  ]
}
```

The overlap between these domains is legal and has no additional meaning unless an explicit semantic relation declares one.

This fragment illustrates the domain collection, not an HTTP request body. The current `CanvasSpec` request model still resolves one legacy canvas polygon; generic multi-domain canvases are assembled through the internal `CanvasGeometry` and design-pass interfaces.

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

Multi-domain design SVGs contain one compact JSON metadata node with schema `viz-domain/v1`:

```xml
<metadata id="viz-domain-metadata">{"schema":"viz-domain/v1","domains":[{"id":"domain-a","vertices":[[0.0,0.0],[80.0,0.0],[80.0,60.0],[0.0,60.0]],"provenance":null},{"id":"domain-b","vertices":[[50.0,20.0],[110.0,20.0],[80.0,80.0]],"provenance":{"source_domain_ids":["domain-a"],"generating_pass_id":"pass-1","operation":"example-operation"}}]}</metadata>
```

The payload shape is exactly:

```json
{
  "schema": "viz-domain/v1",
  "domains": [
    {
      "id": "domain-a",
      "vertices": [[0.0, 0.0], [80.0, 0.0], [80.0, 60.0], [0.0, 60.0]],
      "provenance": null
    },
    {
      "id": "domain-b",
      "vertices": [[50.0, 20.0], [110.0, 20.0], [80.0, 80.0]],
      "provenance": {
        "source_domain_ids": ["domain-a"],
        "generating_pass_id": "pass-1",
        "operation": "example-operation"
      }
    }
  ]
}
```

This metadata is the structural representation of domain geometry. A visible border or outline path is optional artwork and is not required to recover the domain structure. Domain and vertex order are preserved in the payload.

The existing singular `data-viz-canvas-*` root attributes and `viz-canvas-clip` remain part of the compatibility contract for single-domain consumers. They are additive to the versioned multi-domain metadata, not replacements for it.

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

For legacy strict multi-pen output, the existing `pen-N` groups must remain **top-level** SVG children. Apply the canvas clip to those groups directly rather than nesting them inside a canvas wrapper:

```xml
<g id="pen-1" data-pen="1" clip-path="url(#viz-canvas-clip)" ...>
  ...
</g>
```

That preserves the current `viz-virtualserver` -> `plotter-workflow` pen-layer contract while still making the logical canvas intrinsic to the SVG. The neutral design serializer instead emits top-level groups with `data-viz-role="logical-layer"`. The concentric compatibility wrapper separately rebuilds its established physical `pen-N` group from the legacy request; the generic domain model does not assign physical plotter slots.

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

### Generate the placement-free twenty-surface bundle

From the `viz_virtualserver` repository root in Git Bash, generate the example bundle with:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/cootie-catcher.json \
  --output-dir output/cootie-design-bundle
```

The command refuses to replace an existing destination. Regenerate it intentionally with:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/cootie-catcher.json \
  --output-dir output/cootie-design-bundle \
  --overwrite
```

The command prints the canonical `design.json`, `design.svg`, and `surfaces/` locations. The
example declares, in order, `outer-1..4`, `selector-1..8`, and `reveal-1..8`. Every surface is
generated independently in its own local square or triangle coordinates. The job contains no
sheet dimensions, slot polygons, physical rotations, pen assignments, HP-GL, or transport data.

The resulting surface SVGs are inputs to—not replacements for—the existing cootie-catcher
imposition. In `plotter-workflow`, author a separate `cootie.json` placement manifest using that
workflow's existing schema and map each semantic slot to the matching generated projection, for
example:

```json
{"slot": "selector-1", "source": "../viz_virtualserver/output/cootie-design-bundle/surfaces/selector-1.svg"}
```

Repeat that mapping for all twenty semantic slots. Then run the existing `cootie_impose.py`
workflow against `cootie.json`; it remains responsible for the physical sheet, slot geometry,
fit, rotation, clipping, and pen planning. Do not copy those placement fields into
`examples/domain-jobs/cootie-catcher.json`.

## Repository boundaries

`viz_canvas` owns the generic immutable polygon, semantic-reference, pass-execution, and neutral SVG contracts. Algorithms consume those contracts through adapters and declare their geometry capabilities. HTTP request models and legacy endpoint wrappers remain outside that generic core so existing clients can retain their established API and SVG behavior.
