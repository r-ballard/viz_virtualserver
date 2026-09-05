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

## Domain artwork job v1

The generic bundle CLI consumes a strict JSON document with `schema_version: 1`.
Unknown fields are rejected. `schema_version`, the job and group seeds, polygon
coordinates, and affine matrix entries must be JSON numbers of the documented
kind; booleans and numeric strings are not coerced. Integer and floating-point
JSON coordinates and matrix entries are both accepted.

This example shows every v1 collection and the two relation-endpoint forms:

```json
{
  "schema_version": 1,
  "seed": 42,
  "domains": [
    {"id": "a", "vertices": [[0, 0], [100, 0], [0, 100]]},
    {"id": "b", "vertices": [[0.0, 0.0], [80.5, 0.0], [0.0, 80.5]]}
  ],
  "surfaces": [
    {
      "id": "front",
      "domain_id": "a",
      "feature_aliases": {
        "base": {"domain_id": "a", "feature_type": "edge", "index": 0}
      }
    },
    {"id": "back", "domain_id": "b"}
  ],
  "groups": [
    {
      "id": "pair",
      "surface_ids": ["back", "front"],
      "seed": 7,
      "metadata": {"purpose": "coordinated artwork"}
    }
  ],
  "relations": [
    {
      "id": "paired-edges",
      "relation_type": "corresponds_to",
      "source": {"domain_id": "a", "feature_type": "edge", "index": 0},
      "target": {"domain_id": "b"},
      "metadata": {"weight": 1.0}
    }
  ],
  "composition_transforms": [
    {"domain_id": "a", "matrix": [1, 0, 0, 1, 0, 0]},
    {"domain_id": "b", "matrix": [1, 0, 0, 1, 120, 0]}
  ],
  "passes": [
    {
      "id": "join",
      "algorithm": "some-registered-algorithm",
      "target_domain_ids": ["a", "b"],
      "parameters": {"coordinate_frame": "composition", "spacing": 4},
      "logical_layers": [{"id": "ink", "label": "Ink"}],
      "group_context_ids": ["pair"],
      "relation_context_ids": ["paired-edges"],
      "depends_on": []
    }
  ]
}
```

`domains` and `passes` are required. `groups`, `relations`, and
`composition_transforms` may be omitted and then mean empty collections.
Omitting `surfaces` creates one surface per source domain in domain order, with
the domain ID reused as the surface ID. An explicitly empty `surfaces` array is
invalid. All IDs and list orders are preserved.

Pass parameters are recursively copied into immutable JSON values. JSON objects
become read-only mappings and JSON arrays become tuples internally; audit and
request serialization converts them back to ordinary JSON objects and arrays.
This prevents a caller or algorithm from changing a validated job through a
nested list or object reference.

### Pass coordinate frames

`parameters.coordinate_frame` is runner-owned and accepts exactly `"domain"`
or `"composition"`; omission means `"domain"`. The runner removes this key
before constructing the algorithm-specific request, so it is not an algorithm
option. Values such as `"physical"`, alternate casing, and misspellings are
errors. Physical placement is never a design-job coordinate frame.

A composition-frame pass requires an explicit, invertible SVG affine matrix
`[a, b, c, d, e, f]` for every target domain. The matrix maps domain-local
coordinates as `(x, y) -> (a*x + c*y + e, b*x + d*y + f)`. No transform is
inferred from polygon position or list order.

Derived domains are intentionally domain-local in v1 and do not inherit or
infer a composition transform from their provenance. They may be targeted by a
later domain-frame pass. A composition-frame pass may not target a derived
domain, and it may not return a composition-frame path owned by a newly derived
domain, because no declared inverse exists for a coherent surface projection.
The runner rejects both cases before bundle publication.

Derived provenance names at least one source among the producing pass's target
domains, repeats that producing pass ID, and includes a nonempty operation.

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

## Bundle audit and filename contract

A published bundle contains only `design.json`, `design.svg`, and the
`surfaces/` directory. `design.json` uses schema `viz-design-bundle/v1` and
records the complete validated job identity:

- source domain IDs, ordered vertices, and provenance;
- whether surfaces were omitted or explicitly declared, including feature aliases;
- ordered group members, seeds, and recursively serialized metadata;
- relation types, typed endpoints, and metadata;
- ordered composition matrices;
- every pass algorithm, target, parameter, logical layer, semantic context, and dependency;
- ordered derived-domain geometry and provenance;
- per-pass result summaries, including each path's owner, logical layer,
  coordinate frame, and `producing_pass_id`; and
- canonical and surface output paths, SHA-256 digests, and the producing pass
  IDs represented in each surface.

`job_sha256` is the SHA-256 digest of the job-identity fields serialized as
UTF-8 JSON with sorted object keys, compact separators, ASCII escaping, and no
non-finite numbers. Array order remains significant. Before publication, the
writer parses the staged audit and compares the entire value with the expected
audit, then independently rehashes `design.svg` and every surface SVG.

Surface filenames derive from surface IDs. The writer lowercases ASCII, keeps
`a-z`, `0-9`, `.`, `_`, and `-`, replaces each other run with `-`, and trims
leading/trailing `-`. It rejects empty, dot-only, trailing-dot, Windows device
names, and collisions after sanitization. For example, `"Panel A"` becomes
`surfaces/panel-a.svg`; declaring both `"Panel A"` and `"panel-a"` is an error.
Filename validation happens before an existing bundle can be replaced.

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
