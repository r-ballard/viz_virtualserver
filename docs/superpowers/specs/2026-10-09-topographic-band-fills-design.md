# Topographic elevation-band fills

## Status and intent

Concept approved October 9, 2026; written spec approved for planning October 11,
2026. Physical pen-force testing is deferred independently of this software work.
Extend the merged `topographic` algorithm with deterministic elevation-band
regions that can be left empty or filled using the existing vector fill catalogue.
The user approved explicit band selection, per-rule effects and logical channels,
independently available contours, and an alternating stroke-dot example.

Success means intentional filled/unfilled bands, correct islands and holes,
stable band identities, independent polygon artwork, multicolor logical channels,
and ordinary plotter-ready bundles. Preserve current contour-only behavior when
fills are disabled. This is architectural because reusable scalar regions and
topographic fill rules introduce new geometry and configuration boundaries.

## Approach and alternatives

Extract regions from the same normalized sampled field and elevation levels used
for contours, before curve simplification. Reuse the catalogue's polygonal input
contract and render vector strokes clipped to selected regions.

Filling individually closed contour loops cannot distinguish hills, depressions,
nested holes, or areas reaching the polygon boundary. Deriving regions from
simplified output would make band selection depend on a plotting optimization.
Both are unsuitable foundations. A raster mask would be easier but introduces
staircase boundaries and makes precision unnecessarily dependent on pixel shape.
Use interpolated scalar-cell geometry instead.

## Scope

Include reusable indexed region extraction, explicit optional fill rules,
catalogue parameter validation, logical-channel integration, geometry and output
budgets, documentation, analytic tests, and a visually inspected tuning example.

Defer random band selection, parity/range selector syntax, per-component fills,
automatic density-by-altitude rules, raster/solid SVG fills, physical pen-spacing
compensation, new fill effects, terrain-gradient marks, geographic elevation data,
shared terrain across polygons, and exported derived domains. Existing contour
lines remain part of the same algorithm; do not add a second terrain pass whose
derived seed would produce different geography.

## Band identity and scalar geometry

For `contour_count=N`, levels remain `i/(N+1)` for i=1..N. Produce N+1 band
identities, numbered 0..N from lowest to highest. Band 0 extends below the first
level, band N above the last; intermediate band k lies between levels k and k+1.
The outer bands cover all remaining terrain within the target polygon, including
boundary extrema. Empty bands retain their indices; never renumber visible bands.

Use the existing exact-level policy (equal samples classified below) consistently
in extraction. Shared elevation boundaries have no area; they can belong to the
closures of adjacent band polygons. Interiors must be disjoint, and the union of
all band regions must cover the target polygon within a scale-aware floating-point
tolerance. Preserve MultiPolygons, islands, and holes. Omit zero-area contacts
rather than passing points or lines to fill renderers. A rule's disconnected
pieces retain one band identity, not inferred component numbers.

Introduce a focused `scalar_fields/regions.py` interface accepting `SampledField`,
ordered levels, and a target polygon, returning immutable indexed records with
polygonal geometry. It has no SVG, pen, logical-layer, or fill-effect knowledge.
Extraction uses interpolated grid crossings and saddle connectivity consistent
with `scalar_fields/contours.py`. Share the needed cell topology helpers rather
than maintaining incompatible saddle/equality implementations. Keep contour-only
output byte-compatible through that refactor.

Build scalar-cell band regions and compose them before final polygon clipping.
Cell contribution boundaries must reuse shared crossings; handle ambiguous saddle
cells and exact-level plateaus explicitly. Do not triangulate every cell with a
fixed diagonal that changes existing contour connectivity. Validate polygonal
output, partition coverage, and absence of area overlap; invalid topology fails
clearly rather than silently using `buffer(0)`, deleting small components, or
inventing bridges. Detailed cell assembly belongs in the implementation plan,
supported by analytic fixtures before service integration.

Region geometry is the sampled terrain approximation, not exact geography.
`sample_spacing` controls its resolution. `simplify_tolerance` affects plotted
contours only; do not simplify band boundaries separately or move fill strokes
outside the true target. Drawn simplified contours may deviate from unsimplified
fill boundaries by their existing tolerance. A fill example should use zero or
small contour tolerance to make that difference unobtrusive.

The generator's existing constant/negligible-field behavior remains no artwork,
including fills, when normalization returns no usable field. It does not invent
a constant elevation or assign the whole domain to band 0. The reusable extractor
can still partition an already supplied constant sampled field at explicit levels;
that analytic case is distinct from the generator's normalization policy.

## Fill rule contract

Add `band_fills` to `TopographicParameters`, defaulting to an empty immutable
sequence. JSON uses an array. Each entry is a strict object with these fields:

| Field | Requirement |
| --- | --- |
| `bands` | Nonempty array of distinct strict integer indices in 0..contour_count |
| `effect` | Existing catalogue effect ID |
| `parameters` | Optional object; defaults and accepted keys come from that effect |
| `layer_id` | Nonempty declared logical layer ID dedicated to fill strokes |

Supported effects are the five currently implemented catalogue entries:
`parallel-hatch`, `crosshatch`, `circle-rings`, `stroke-dots`, and `vortex-marks`.
Use catalogue validation rather than duplicating effect-specific numeric rules.
Unknown fields/effects/parameters, invalid numbers, boolean/string indices,
duplicate indices, out-of-range indices, and references to undeclared layers
fail before field evaluation or publication. Explicit null values are invalid.

Reject overlap in selected band indices across rules; one band has at most one
rule in this release. Rule order and the order of indices within a rule do not
change geometry. Canonicalize index lists ascending and order rules by their
selected bands for deterministic output. Multiple non-overlapping rules may use
the same fill layer. An unspecified band is unfilled. Empty rules list means no
region extraction and preserves the original fast contour-only path.

Within each domain and rule, union the selected band regions before rendering
that effect. This removes artificial seams between adjacent bands assigned the
same effect and parameters. Do not union across domains or distinct rules.
Catalogue effects use the polygon-bounds local origin for lattice phase and field
centers, including `vortex-marks`. All effect lengths remain intrinsic domain
units. Restore the origin only when constructing final VectorPaths. Group ordering
or imposition placement must not move the fill lattice relative to the artwork.

Example for N=8, selecting alternating bands:

```json
"band_fills": [
  {
    "bands": [0, 2, 4, 6, 8],
    "effect": "stroke-dots",
    "parameters": {"spacing": 3.0, "mark_length": 0.5, "angle": 0.0},
    "layer_id": "terrain-dots"
  }
]
```

The first example declares `topographic-contours`, `topographic-index`, and
`terrain-dots`. A second example uses two non-overlapping rules with different
effects/channels to demonstrate deterministic multicolor assignment.

## Logical layers and bundle integration

Keep the first two declared layers as intermediate and index contours, in the
existing order. With no fill rules, require exactly those two as today. With fill
rules, additional distinct declared layers must be exactly the set of referenced
fill layer IDs. A fill layer cannot equal either contour layer. Retain every
declared channel in the audit catalog even if its bands have no visible area or
the effect emits no strokes; SVG groups continue to contain actual paths only.

Keep contour paths first, then fill paths in canonical rule/stroke order. Return
only domain-frame VectorPaths and no derived domains. Existing producing-pass
provenance applies to both. Identify fill semantic paths as `topographic-fill`
through the existing neutral adapter, without altering the neutral schema or
remapping physical pens. No promise of individual-band provenance is made for
strokes spanning a union of several bands.

Reuse the current topographic neutral projection and opt-in unused-layer
retention. Preserve current contour-only bundle bytes and channel ordering.
There are no job schema changes, new endpoints, dependencies, or plotter-workflow
code changes. Downstream pen/color assignment, imposition, text, and transport
stay in their existing workflow.

## Resource limits and failures

Retain existing sampling, contour workload, segment, and pass-wide plotted-vertex
limits. Count contour and fill vertices together against the 1,000,000 per-pass
limit. Retain all catalogue renderer candidate/output limits.

Add a per-domain region cell-level workload cap of 12,000,000 and an intermediate
polygon-coordinate budget of 1,000,000 during extraction/composition. Check costs
before allocating cell geometry collections; count incremental intermediate
geometry as it is produced, not only after union. Allow at most N+1 non-overlapping
rules by construction. Extremely dense fills, excessive region geometry, invalid
partitions, and numerical precision loss fail with domain/rule context and
suggest increasing sample/fill spacing or reducing contour count.

No silent resolution reduction, clipping outside the region, partial publication,
or dropped islands. Existing atomic bundle publication must preserve any prior
output on failure. Parameter validation happens before generation even when the
selected region would be empty, so invalid empty-band rules are not ignored.

## Validation and acceptance

Analytic fixtures cover a plane, radial hill, depression, two hills with a saddle,
exact-level vertices, flat plateaus, constant field, and levels outside the sample
range. Assert stable identities, valid regions, holes/islands, polygon coverage,
and disjoint interiors. Exercise both saddle decisions and ties consistently
against the contour extractor. Use convex and concave targets, negative origins,
reversed winding, and boundary contacts. Include small islands that must survive.

Rule tests cover strict validation, overlapping/duplicate selection, effect
defaults and parameter rejection, undeclared/conflicting layers, empty bands,
zero rules, canonical rule ordering, and combined output budgets. With a fixed
seed and parameters, repeated generation is identical; translated artwork and
target reordering preserve its relative pattern. Every fill stroke segment is
covered by its selected union, including hole avoidance and concave clipping.
All five effects work through the catalogue; no separate terrain renderer.

Regression fixtures show existing contour-only paths and bundles unchanged.
Compare extracted regions/fills across contour simplification settings and verify
they are identical. Test CLI audit catalogs and empty channels, failure atomicity,
and downstream neutral validation.

Generate and inspect examples showing alternating stroke-dot bands, mixed
effects/channels, nested holes, and a concave target. Inspect both neutral bundle
surfaces and a colored review preview. Run targeted tests, full suite, Ruff,
and one fresh whole-branch review under the user's preserved native execution
method before pushing a PR. Do not merge automatically.

## Roadmap boundaries

Stable band identities are the basis for later selection policies, density by
altitude, and band-aware exports. Scalar regions can serve future raster field
sources without coupling them to the fill catalogue. Terrain gradients can later
drive vector-field marks; this release's vortex marks keep their current evaluator.
