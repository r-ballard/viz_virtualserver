# Multi-scale Truchet Curves

## Status and intent

Draft for review. The user approved proceeding with seeded random subdivision,
plotter-ready curves, and independent artwork for each polygon. Preserve tile
geometry for future imposition; shared-coordinate generation, separated tile
panels, margins, and borders are future work.

This extension is architectural: midpoint-only tile states cannot describe the
additional connections required between different scales. Preserve the existing
`truchet` algorithm and introduce `truchet-multiscale` alongside it.

Success means visibly mixed scales, reproducible subdivision and motif choices,
connected boundaries through scale transitions, and ordinary design bundles for
convex and concave target polygons.

## Reference and approach

Sources:

- Carlson, *Multi-Scale Truchet Patterns*, Bridges 2018, pp. 39-44:
  https://archive.bridgesmathart.org/2018/bridges2018-39.pdf
- Recipe and reference source:
  https://christophercarlson.com/portfolio/multi-scale-truchet-patterns/

Carlson uses two edge connections at one-third and two-thirds, half-scale tiles,
alternating region identity by depth, and wing geometry extending outside tile
content squares. Small tiles overlay large ones. This produces complete region
boundaries without explicitly pairing loose curve ends. His reference package
constructs colored polygons from alternating internal connections and external
connections around the eight edge points.

Adapt that geometric construction independently in Python, without executing or
bundling the reference package. Internal region composition is topology work,
not plotted fill: final output remains boundary curves only. This replaces the
earlier tentative approach of manually inserting transition connectors. Explicit
connector bookkeeping is harder to verify and is not necessary with winged regions.

## Scope

Include:

- An axis-aligned base grid with recursively subdivided square leaves.
- One diagonal, non-crossing winged motif family in its two distinct orientations.
- Depth-parity region inversion and coarse-to-fine composition.
- Boundary extraction and clipping to each independent target polygon.
- Strict parameters, deterministic output, bounded resource use, tests, examples,
  and a visually inspected SVG tuning sheet.
- Internal immutable leaf records with identity, parent identity, bounds, depth,
  and orientation, sufficient for later tile placement features.

Defer:

- Additional winged motif families, arbitrary curvature, triangle/hexagon tiles.
- Region hatching, stippling, dithering, and user-visible filled output.
- Cross-domain alignment or shared-coordinate arrangements.
- Separate tile-panel output, persisted tile catalogs, outline strokes, margins,
  and physical sheet placement. No plotter-workflow changes in this iteration.
- Spatial subdivision fields and user-authored subdivision trees.

## Parameters and contract

Register `TruchetMultiscaleDomainAlgorithm` as `truchet-multiscale` in
`viz_virtualserver/cli/domain_bundle.py`. Require exactly the logical layer
`truchet-curves`; return domain-local `VectorPath` values and no derived domains.
Support the same simple convex/concave polygon targets as the classic algorithm.
Use existing domain seeds; do not add a new seed parameter or shared job fields.

| Parameter | Default | Validation |
| --- | --- | --- |
| `base_tile_size` | 40.0 | Finite positive side length in domain units |
| `max_depth` | 3 | Strict integer, 0 through 6 |
| `split_probability` | 0.45 | Finite number in [0, 1] |
| `curve_tolerance` | 0.02 | Finite positive geometric error in domain units |

Reject unknown fields, numeric strings, booleans as numbers, and nonfinite values.
The classic algorithm's `arc_a`, `arc_b`, and `tile_size` do not apply to this
motif family. Fixed circular geometry preserves its scale connection properties.

Do not force random subdivision: depth zero or probability zero produces a
uniform winged tiling. Probability one subdivides every base tile to max_depth.
Intermediate probability produces mixed sizes for appropriate seeds; examples
must use verified seeds that actually exhibit multiple depths.

## Arrangement and identity

Anchor the base grid at the domain's minimum x and y. Compute tile counts with
the decimal-boundary normalization already verified for the classic generator.
Add one full base-tile halo on each side before subdivision. Motifs extend at
most one-third of their content side beyond their tile; the halo supplies all
neighbor paint operations that can influence the target polygon.

Retain the complete bounding rectangle plus halo, including cells outside a
concave polygon, until composition finishes. Early target clipping would change
wing interactions. Skip empty targets only according to existing domain validation.

Each root tile has integer grid indices. Each child halves its parent's square;
visit children in low-x/low-y, high-x/low-y, low-x/high-y, high-x/high-y order.
Identify a leaf by root indices and its quadrant-address sequence; record its
parent address, depth, and content bounds. Compare/sort by those symbolic keys,
not floating coordinate equality.

Derive independent subdivision and orientation RNG streams from domain seed,
root indices, and tile address using a stable hash. This prevents rendering
tolerance, traversal implementation, or halo enumeration changes from changing
the artistic arrangement. No dependence on Python's process-randomized hash.

At depth less than max_depth, subdivide with split_probability. At max_depth,
retain the leaf. Choose one of two diagonal orientations independently per leaf.
Region complement is determined by depth parity, not randomized independently.

The arrangement model does not know polygon clipping, physical dimensions in
millimeters, pen assignment, or sheet placement. A later coordinator can supply
another frame without changing subdivision addresses or motif construction.

## Winged motif geometry

Use the unit square [0,1] x [0,1]. Number eight edge points around its boundary:

1. (1/3, 0)
2. (2/3, 0)
3. (1, 1/3)
4. (1, 2/3)
5. (2/3, 1)
6. (1/3, 1)
7. (0, 2/3)
8. (0, 1/3)

The base diagonal motif pairs (1,8), (2,7), (3,6), (4,5). Its second orientation
rotates these pairs by two edge-point positions (one quarter turn). Interior
connections are quarter-circle arcs at opposite corners, with radii 1/3 and 2/3.

Complete region circuits by alternating a bidirectional interior pairing and
the external successor relation 1->2->...->8->1. Alternate inward and outward
endpoint tangent directions on each circuit. Same-edge external links produce
semicircular wings; links around a corner complete the corresponding outer arc.
Assign circuit region identity by the parity of its starting point, independent
of circuit traversal. Deduplicate circuits by their port membership. Require
that every port is accounted for and that the resulting two regions cover the
content square, with disjoint interiors and maximum wing reach 1/3.

Construct arcs analytically and sample adaptively. Avoid radius overflow by
using dimensionless geometry for the unit motif. Use an effective tolerance no
greater than min(requested tolerance, smallest leaf side / 100) to prevent coarse
sampling from collapsing essential transition features. Include exact port
coordinates and shared arc endpoints; no rasterization or image tracing.

## Composition and boundary extraction

Translate and scale work into a domain-relative frame measured in base tile
units. This reduces precision loss on translated domains. Use a documented
precision grid much finer than the effective curve tolerance and smallest leaf
features; account for snapping displacement within the error budget. Reject
requests whose required resolution cannot be represented reliably.

Compose leaves in increasing depth, then stable tile-address order. For each
leaf, let F be the footprint of its two regions, including wings. Let B be its
region-1 geometry after the depth-parity swap. Update the accumulated region:

`painted_region = painted_region.difference(F).union(B)`

Batch nonconflicting same-depth operations where equivalence is demonstrated
by tests. Equal-depth overlapping wings must assign matching identities, so
their order does not introduce visible seams. Never clip a leaf to its content
square or to the target polygon before this operation.

Extract painted_region.boundary before target clipping. Clip the resulting
linework against the original polygon in the same normalized frame; extracting
the boundary after clipping would incorrectly add polygon perimeter strokes.
Normalize component order/direction, remove consecutive duplicate points,
preserve closed loops, discard point-only contacts, and transform to domain
coordinates. Do not join components across exterior gaps or emit tile borders.

Keep this implementation distinct from classic midpoint graph tracing. Reuse
existing path normalization/clipping utilities only where their semantics match.

## Resource limits and failures

Limit the arrangement, including halo, to 10,000 leaves per domain. Count during
subdivision and reject before exceeding the limit; do not silently truncate.
Estimate all motif sampling before constructing polygons, capped at 2,000,000
points per domain. Document why the leaf limit is lower than classic tracing:
this algorithm performs polygon Boolean operations.

Validate parameters and layers before assembly. Invalid region geometry, failed
coverage invariants, unrepresentable precision, or resource-limit failures produce
clear ValueError messages through existing CLI handling. No partial bundle is
published. No silent geometry repair that changes motif topology.

## Module boundaries

Within `viz_virtualserver/generators/truchet/` add focused multi-scale modules:

- Model/parameters: immutable leaves and strict controls.
- Subdivision: deterministic leaf arrangement, identities, and limits.
- Winged motifs: unit-region construction and tolerance-aware sampling.
- Composition: parity painting, precision handling, and boundary extraction.
- Adapter: runner seeds, target ownership, logical layer, and DesignResult.

The existing classic implementation and defaults remain compatible. New tests
should exercise shared helpers if any are extracted; avoid unrelated refactoring.

## Verification and acceptance

- Subdivision leaves partition every root exactly, with no duplicated children,
  overlaps, or gaps; depth/probability endpoint cases are exact.
- Repeated seed gives the same identities, bounds, orientations, and output.
- Translating decimal-coordinate domains preserves relative tile arrangement;
  tolerance changes preserve all leaf and orientation choices.
- Motif ports are exactly at thirds. Both regions cover the unit content square,
  their interiors do not overlap, and wings stay within the stated footprint.
- Test equal-scale and 2:1, 4:1, and 8:1 neighboring scales, both orientations,
  and both depth parities. Extracted curves have no artificial seams or dangling
  interior endpoints in these fixtures.
- Same-depth composition order produces equivalent region geometry.
- Halo composition and a larger reference neighborhood agree inside the target.
- Boundaries contain no accidental content-square edges or target perimeter.
- All emitted segments are within square, triangular, and concave targets,
  including negative coordinates and clockwise vertex input.
- Limits fail before excessive allocation; no partial bundles on rejection.
- CLI publishes deterministic audit JSON, combined SVG, and per-surface SVGs.
- Render and inspect a fixed-seed tuning sheet varying max_depth and probability,
  and examples of polygon clipping. Verify visible scale diversity and smooth
  transition geometry rather than relying on unit tests alone.

## Later imposition

Leaf records preserve identity, parentage, orientation, scale, and content
polygons. Future work can choose a persistent tile catalog or derived-domain
contract and let plotter-workflow arrange separate panels, add spacing and
insets, and draw borders. Winged motif regions are not independently plottable
panels without a design decision about clipping/removing cross-tile wings;
this iteration makes no promise that separating leaves preserves continuity.
