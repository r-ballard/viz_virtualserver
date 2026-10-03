# Compiled Truchet Grammar

## Status and intent

Draft for user review following approval of the architectural approach.

Create reproducible, plotter-ready Truchet curves in the existing polygon-domain
bundle workflow. The user selected a compiled grammar, uniform-size square tiles,
parameterized corner arcs, complementary region identities, compatible pattern
assembly, and square-grid coverage clipped to arbitrary supported polygons.
Mixed tile sizes and filled-area processing are explicitly deferred.

The source is Walter, Ligler, and Gürsoy's *The Truchet Tile Grammar: A Generative
System for Versatile Tile and Pattern Design* (2024), DOI
10.1007/s00004-024-00779-8, especially Figures 6, 9, 13, 14, and 17.
This release implements its non-overlapping square-tile subset, rather than a
general interpreter or every numbered rule. Overlapping motifs and R7's third
region field are deferred.

## Scope

- Construct square motifs with connections between adjacent edge midpoints at
  two opposing corners, corresponding to R1-R3.
- Retain complementary region variants corresponding to R6. Construction labels
  are internal rather than rendered, consistent with R4-R5.
- Compile rotations and complementary variants into tile states, with edge
  signatures that constrain placement as in R8-R39.
- Assemble a seeded arrangement separately from motif substitution (R40).
- Produce only motif curves, without tile borders or polygon perimeter strokes.
- Support simple convex and concave polygon targets, independent per domain.
- Reuse existing JSON jobs, logical layers, bundle export, and domain seeds.

Extrusions, new HTTP endpoints, composition-wide tilings, user-defined grammar
languages, physical pen assignment, and transport are outside this release.

## Components and integration

Use a new `truchet/` package with focused modules for validated parameters,
compiled tile states, assembly, geometry, and the domain algorithm adapter.
Register `TruchetDomainAlgorithm` under `truchet` in
`scripts/generate_domain_bundle.py`. Its `generate` method follows the existing
`DomainAlgorithm` contract and returns `DesignResult` with no derived domains.
All paths use domain coordinates and the single logical layer `truchet-curves`.
Require exactly that layer to avoid ambiguous output assignments.

Add an algorithm guide, README registration, and example jobs demonstrating a
classic square pattern, an asymmetric motif, and triangle/concave target clipping.
Do not change the shared job or bundle schema.

## Tile representation

A tile state contains quarter-turn orientation, complement flag, midpoint
connection pairs, and ordered region identities along each edge. Use two stable
region identities, not display colors or physical pen numbers.

Represent each edge in a documented traversal direction. Compatibility compares
the complete region sequence after reversing the neighboring edge's traversal;
matching midpoint positions alone is insufficient. Rotations permute edges and
connections; complementation swaps region identities without moving curves.

Keep symbolic states distinct when their geometry can differ under independent
corner parameters. Do not collapse states merely because the classic symmetric
motif would look identical. Record orientation and complement independently of
arc sampling so the same arrangement can be rendered with different curvature.

The internal model retains tile identity, state, and local closed-region
construction information. Future fills can reconstruct regions from this model.
No new persistent region representation is added to `design.json` in this release.

## Parameters and motif geometry

Expose strict parameters:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `tile_size` | 10.0 | Square side length in domain coordinate units; finite and positive |
| `arc_a` | sqrt(2) / 2 - 0.5 | Signed sagitta divided by chord length for the first corner |
| `arc_b` | sqrt(2) / 2 - 0.5 | Same control for the opposite corner |
| `curve_tolerance` | 0.02 | Maximum chord approximation error in domain units; finite and positive |

For both arc controls, allow values in [-0.45, 0.45]. Positive sagitta bows the
connection toward the square center; negative sagitta bows it toward its corner.
Zero produces the straight connection in R2. Equal classic defaults reproduce
Smith's quarter-circle motif. Independent values permit asymmetric motifs and
four distinct orientations. This range keeps the selected opposing regions
non-overlapping and curves inside the square.

Construct circular arcs from endpoints and sagitta. Sample with an error bound,
including exact midpoint endpoints. Avoid division by zero at the straight case.
Reject nonfinite values, unknown parameters, numeric strings, and boolean numbers.

Endpoint continuity is guaranteed across compatible tiles. Tangent continuity is
not promised for arbitrary arc settings: asymmetric curvature may introduce kinks.
The default classic motif should be tangent-continuous at ordinary tile joins.

## Seeded pattern assembly

Anchor the axis-aligned grid at the target domain's minimum x and y coordinates.
Cover its complete bounding rectangle with whole squares; do not shrink edge
tiles. Assemble the rectangle before polygon clipping. Every domain has its own
grid and the runner-provided `context.domain_seeds[domain.id]`.

Use stable row-major traversal and stable candidate ordering. At each position,
filter the compiled states against all previously assigned neighbors and choose
uniformly from the compatible states using the domain RNG. For this complete
square state family, verify that every reachable combination of prior neighbor
constraints has a candidate. Treat an empty candidate set as a grammar invariant
failure with a clear exception, rather than silently accepting a mismatch.

Assembly randomness must not depend on arc sampling or tolerance. Changing
curvature preserves the arrangement; changing seed can change it. Domains do
not merge or influence one another, even when their polygons overlap.

## Path construction and clipping

Render each state's two connections, then trace paths through a graph keyed by
integer grid-edge midpoint identities. This avoids using floating-point proximity
to decide whether connections join. Interior midpoint vertices have degree two;
rectangle-boundary vertices have degree one. Trace all open chains and closed
loops once, reversing component curves as needed and removing duplicated join
points. Use stable start selection and output ordering for reproducibility.

Clip the sampled chains against the authoritative target polygon using Shapely.
Extract all line components from clipping results, discard point-only contacts,
and preserve truly closed surviving loops. Partial loops become open paths.
Remove consecutive duplicate points and omit degenerate paths. Canonicalize
component ordering and direction so incidental geometry-library ordering does
not dictate SVG output. Do not stitch separate components across an exterior gap.

Intrinsic polygon clipping occurs here; downstream physical placement and
defensive clipping remain owned by the plotter workflow.

## Limits and errors

Before assembly, reject bounding grids exceeding 100,000 tiles. Before allocating
sampled geometry, reject estimated sampling exceeding 2,000,000 points per domain.
These are documented implementation limits, not configurable artistic controls.
Validate parameters and layer declarations before generation. Report failures
through the existing ValueError/CLI handling. No partial output bundle is produced.

## Verification and acceptance

- Compiled rotations and complements have correct reversed-edge compatibility.
- Every reachable row-major neighbor constraint admits a state.
- Classic geometry has the expected quarter-circle endpoints and radius;
  straight and asymmetric cases obey sagitta and sampling tolerance.
- Repeated identical jobs produce identical ordered geometry; curvature and
  tolerance changes preserve symbolic arrangement.
- Independent domains retain independent seeds and domain ownership.
- Interior joins produce connected paths without duplicated curve segments;
  open chains and closed loops are both exercised.
- All emitted line segments are covered by square, triangular, and concave
  target polygons, within a documented numerical tolerance.
- Invalid parameters and excessive resource requests fail clearly.
- CLI generation produces valid audit JSON, combined SVG, and surface SVGs.
- Visually inspect classic and asymmetric previews, including polygon clipping,
  to confirm useful plotter artwork and absence of tile-border artifacts.

## Backlog

1. Mixed tile sizes: Carlson-style edge connections, transition handling, and
   assembly rules; not merely random subdivision of this midpoint grammar.
2. Filled regions: reconstruct and union compatible regions before generating
   hatching, crosshatching, stippling, or dithering. Avoid visible tile seams and
   consider pen-lift cost. Python generation is the preferred reproducible path;
   investigate an Inkscape extension or scripted finishing workflow as an option.
3. Overlapping motifs and R7's third region identity, with compatibility tests.
4. Triangle and hexagon tile grammars, distinct from polygon target shapes.
5. Additional arrangement policies and optional derivation inspection.
