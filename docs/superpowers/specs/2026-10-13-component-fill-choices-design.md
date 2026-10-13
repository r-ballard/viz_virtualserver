# Seeded component fill choices

## Intent

Let disconnected topographic regions independently remain unfilled or use different
catalogue effects. The user approved seeded weighted choices, starting with
topographic band regions while keeping geometry identification and selection reusable.
Keep existing whole-union fill rules as the default, independent polygon artwork,
domain-local phase, plotter-ready strokes and neutral logical pen channels.

This release adds weighted choices only. Manual component overrides, area-based
policies, automatic density, Truchet integration, shared-coordinate artwork, new
fill effects and physical testing are outside scope. The user has deferred plotting
and pen-force testing. Native implementation and one fresh final review remain selected.

## Region semantics

For each rule, union its selected bands first, exactly as current rendering does.
Then take the polygon members of that union as components. A Polygon is one
component; each member of a MultiPolygon is one. Holes stay attached to their
surrounding polygon, never becoming separate candidates. Point-touching polygons
that remain distinct MultiPolygon members are separate components; do not join
them with buffers or invent strokes between them.

Retain every positive-area component, including tiny islands. An empty union has
no components. No ranking, area threshold, geometry repair or simplification is
applied. Unselected bands remain empty independently of component choices.

## Rule syntax

Retain the existing whole-union rule (`bands`, `effect`, `parameters`, `layer_id`,
and optional field_direction). Add a mutually exclusive component-choice rule:

```json
{
  "bands": [0, 2, 4, 6, 8],
  "component_seed": 0,
  "component_choices": [
    {"id": "blank", "weight": 2, "effect": null},
    {"id": "dots", "weight": 3, "effect": "stroke-dots",
     "parameters": {"spacing": 3, "mark_length": 0.5}, "layer_id": "terrain-dots"},
    {"id": "contour", "weight": 1, "effect": "field-marks",
     "field_direction": "contour",
     "parameters": {"spacing": 3, "mark_length": 1.5}, "layer_id": "terrain-marks"}
  ]
}
```

The list must contain 1 through 32 choices with unique, nonblank string IDs and
strict integer weights from 1 through 1,000,000. Each choice requires `id`, `weight`
and `effect`. `effect: null` explicitly means unfilled; it must omit parameters,
layer_id and field_direction. A rendered choice requires a nonblank layer_id and
the existing catalogue controls; field-marks requires explicit slope/contour
field_direction, while other effects must omit it. Parameters may be omitted to
use catalogue defaults, but explicit null is rejected.

component_seed is an optional strict integer, default 0, independent of the terrain
seed; changing it changes assignments without regenerating terrain. Old rules
must omit component_seed and component_choices. Choice rules must omit top-level
effect, parameters, layer_id and field_direction. Reject ambiguous combinations,
unknown keys, null choices, invalid IDs/weights and invalid effects/controls before
sampling. Validate every choice even when its eventual component set is empty.

The existing band range and disjoint selections apply across both rule forms.
Rules and their band lists retain canonical sorting. Store choices in ID order;
input list order does not affect assignments. IDs are case-sensitive; preserve
their exact strings and do not silently trim them. Multiple choices/rules may
share a logical layer. All-blank palettes are allowed and require no extra layer.

## Deterministic identity and weighted selection

Put component extraction/identity and weighted selection in a focused reusable
region-selection module. It knows polygon geometry and seed data, not terrain,
catalogue effects, pen channels, or physical settings. Topographic models and
rendering remain responsible for effect controls and field context.

Identify each component by SHA256 of canonical two-dimensional polygon bytes in
the caller's domain-local frame. Canonicalization fixes exterior/interior winding,
ring starting vertices and hole order, normalizes signed zero, preserves full
coordinate precision and all vertices, and uses explicitly fixed WKB byte order.
Reject nonfinite or invalid polygonal inputs instead of repairing them. Do not use
Python hash, GEOS member order, component ordinal, centroid or rounded area as an ID.
Sort records by digest with canonical bytes as a tie-break; detect a digest collision
between unequal canonical bytes and fail clearly rather than sharing an identity.

For each component, hash a versioned, unambiguous length-prefixed encoding of the
effective domain seed, component_seed, sorted selected band indices and component
ID. Map the unsigned digest integer modulo the sum of weights, then select its
interval from choices sorted by ID. This fixes the algorithm across processes and
uses no mutable RNG stream. It is a deterministic weighted assignment, not a
promise of exact proportions in a small drawing.

Adding or removing another disconnected component, reordering rules/choices,
reversing polygon winding or reordering holes must not change an unchanged
component's choice. Rendering parameter changes preserve assignments for the same
IDs/weights; changing palette IDs/weights deliberately can change assignments.
Changing terrain, selected-band unions or component shape can change identity.

Translation invariance follows the existing bounds-local frame: exactly equivalent
local geometry yields identical identities. Do not quantize or snap geometry to
hide floating-point changes. Translations that lose local coordinate precision
are not promised to retain IDs; document that limit and retain existing precision
guards. Composition placement alone does not change local geometry or assignments.

## Rendering and channels

Existing rules keep the original single-union renderer path and stroke order, so
ordinary contour/fill/gradient-mark bundles remain byte-identical. For choice
rules, identify components, select once per component, then process records in
canonical component order. Blank choices skip rendering.

Render each nonblank component with its selected effect and controls through the
catalogue. Keep the existing domain-local lattice origin; never rebase the lattice
to a component's bounds. Holes and independent fragments remain clipped. Reuse
one sampled gradient adapter per domain across all field-mark choices and ordinary
field-mark rules; allocate only if a field effect actually needs rendering.

First two channels remain intermediate/index contours. The exact additional
channel set is the union of all rendered-choice layer IDs and ordinary-rule fill
IDs, including choices that happen not to be selected. None may alias either
contour layer. Empty channels remain in the audit catalog and omit SVG groups.
An all-blank job with contours declares only the first two channels.

Continue existing topographic-fill provenance and stable pass/domain stroke IDs.
No neutral schema or pen-plan change is needed. Job audit records supplied rules,
weights, IDs and component_seed; no new per-component exported decision manifest
is introduced. The reusable selector returns identity/choice records for tests and
future inspection; manual overrides are not part of this release.

## Limits and failures

Preserve all sample, scalar-region, catalogue and combined 1,000,000-vertex pass
limits. Limit component selection to100,000 components and 1,000,000 input polygon
coordinates per union. Precheck coordinate count before canonicalization and cap
component accumulation before allocating all identity records. Do not silently
drop components on excess.

Per-component rendering can repeat lattice work. Enforce a cumulative rule limit
of 100,000 candidate positions for lattice-based effects, not just a fresh catalogue
limit for each island. Reuse or factor the existing effect candidate-cost calculations
so estimates match actual spacing/angle/radius/mark padding; do not duplicate a
diverging approximation. For crosshatch, count both families. No execution beyond
the limit, silent coarsening, or partial publication. Ordinary union rules retain
their existing effect-specific limits and output.

Combined contour/fill vertices still use the remaining pass allowance, checked
while consuming component results and before rendering subsequent components.
All invalid rules/channels fail before terrain evaluation. Geometry, canonicalization,
selection and rendering errors identify the domain, selected bands and, where
available, component/choice ID. No unbounded allocations or external dependencies.

## Verification

Analytic component tests cover one polygon, disconnected islands, attached holes,
point-touching members, empty geometry, tiny islands, winding/ring/hole/member
order, signed zero, distinct full-precision shapes, invalid/nonfinite input,
canonical WKB fixtures, simulated digest collisions, coordinate/component caps.
Known digest/weight fixtures pin versioned selection independently of the renderer.
Verify unchanged components survive unrelated additions and choices reorder safely.

Model tests cover both rule forms, immutable canonical choices, every catalogue
effect, explicit blank choice syntax, invalid unused choices, nulls/types/extra keys,
strict weights, duplicate IDs, choice-count caps, mixed-rule band overlaps,
all-blank palettes and exact channel sets. Sampling spies prove early validation.

Service tests cover per-component effects/blanks, holes/concave clipping, lattice
phase, shared gradients, zero allocation when blank, stable order, translation of
exactly equivalent local geometry, simplification invariance, changing only
component_seed, seed independence, aggregate candidate limits and remaining pass
vertices. Check containment against each selected component, not just the union.

CLI tests prove reproducible audit/surfaces, empty channels, mixed ordinary/choice
rules and atomic failure preserving an existing destination. Save and compare
baseline contour, band-fill and gradient bundles. Add a small reviewed example with
blank/dots/hatch/terrain-mark choices and a concave target; render neutral and colored
previews, inspect retained islands/holes, and validate downstream contracts.

Run full suite and Ruff, one fresh whole-branch read-only review, then push/create
PR against main without merging. Preserve worktrees and previews. Physical
plotter testing remains deferred.

## Design status

Concept, written spec and implementation plan approved in conversation. Native
execution selected; physical testing remains deferred.
