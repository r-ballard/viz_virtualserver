# Terrain-gradient marks

## Intent and scope

Add plotter-ready short strokes whose orientation follows synthetic terrain. The
user approved fixed-length marks as the next roadmap priority after elevation-band
fills. Reuse the field-mark renderer and explicit band selections. Keep independent
polygon artwork, domain-local phase, deterministic generation, and neutral exports.
Physical plotting and pen-force testing remain deferred.

Two orientations are supported: `slope` follows the terrain gradient and `contour`
rotates it by 90 degrees. These strokes are undirected; slope marks indicate the
slope axis, not an arrow showing uphill. Flat areas omit marks. Spacing and mark
length remain explicit, with no automatic density or length modulation.

Excluded: streamlines, collision avoidance, slope-dependent density, blended vector
fields, shared-coordinate terrain, real elevation rasters, and new physical pen
settings. Existing contours and all five current fill effects retain their output.

## Selected approach

Reuse `render_field_marks` with a sampled-gradient evaluator. This extends the
existing raw-vector interface without creating a second lattice or clipping system.
Curved streamlines would require integration, stopping rules, and collision policy;
density modulation would alter placement rather than supply the needed direction
abstraction. Both remain later work.

The reusable catalogue gains `field-marks`, a context-dependent effect. Its numeric
controls are `spacing` (default 8, positive input units), `mark_length` (default 0.5,
positive input units), and `angle` (default 0, finite degrees). `angle` rotates the
lattice, not the sampled vector. The caller supplies a `VectorField` separately from
serializable effect parameters.

## Catalogue boundary

Extend `FillEffectDescriptor` with `requires_field: bool = False`. Only `field-marks`
sets it true. `list_fill_effects` remains ordered and immutable, with the new effect
appended. Parameter validation continues to work without geometry or a field.

Extend `render_fill_effect` with optional keyword `field: VectorField | None = None`.
`field-marks` requires a callable `sample(x, y)` evaluator even for empty regions;
other effects reject a supplied field. Rendering delegates to `render_field_marks`
and retains its `VectorSample` validation, normalization, candidate budgets,
endpoint precision checks, deterministic ordering, and polygon clipping.

This makes the catalogue useful for later callers with other field sources. A
caller that cannot provide field context must reject this effect before expensive
geometry generation. Audit all existing generator catalogue consumers, particularly
Truchet, so adding the descriptor does not imply unsupported field synthesis there.
Their existing effect defaults and numeric controls remain unchanged.

## Sampled gradient evaluator

Add a scalar-field adapter implementing the existing `VectorField` protocol. It
consumes the exact immutable `SampledField` returned by topographic smoothing and
normalization, including its halo. It never resamples seeded terrain.

Compute raw x/y derivatives once per domain using central differences at interior
nodes and first-order one-sided differences at the outer grid edge. Account for
`dx` and `dy` independently; 2-by-2 grids are valid. Bilinearly interpolate the raw
derivative components at each queried mark centre, then return `VectorSample`.
Contour orientation returns `(-gradient_y, gradient_x)` in SVG coordinates.
Normalize direction only in the existing mark renderer, after interpolation.

This is a smooth approximation to sampled terrain directions, not an exact tangent
to marching-square segments. Do not derive direction from simplified contours.

Flatness uses a numerical noise floor: gradient magnitude at or below
`64 * float_epsilon * max(1, max(abs(field.values))) / min(dx, dy)` returns zero.
The threshold is measured in height per input unit and is invariant under uniform
coordinate scaling. It suppresses numerically unstable directions without imposing
an artistic flatness control. Reject nonfinite derivative arrays, thresholds, or
interpolation results explicitly; do not replace invalid values with zero.

Nonfinite query coordinates are errors. Finite queries outside the full sampled
rectangle return zero, with no extrapolation or clamping; exact outer boundary
queries use the adjacent last cell. The halo normally covers padded mark candidates.
If a mark centre lies beyond it, that mark is omitted even when its theoretical
stroke could reach the target. Document this boundary policy. Check grid bounds
and representability before constructing derivative arrays.

Store gradient arrays immutably, following `SampledField`'s byte-backed policy.
Construct them only when at least one field-mark rule exists; share the raw arrays
between slope and contour evaluators for that domain.

## Topographic rule integration

Add optional `field_direction: Literal["slope", "contour"] | None = None` to
`BandFillRule`. It is required explicitly for `effect: "field-marks"`, and must be
omitted for other effects. Reject explicit null when supplied, unknown values,
wrong types, and extraneous fields before sampling. No implicit terrain source is
inferred for arbitrary catalogue effects.

Example pass parameter:

```json
"band_fills": [
  {"bands": [0, 2, 4, 6, 8], "effect": "field-marks",
   "field_direction": "contour",
   "parameters": {"spacing": 3, "mark_length": 1.5, "angle": 0},
   "layer_id": "terrain-marks"}
]
```

All existing band range, disjoint selection, per-rule union, fill-channel and early
control validation rules apply. Rules may share a layer when their selected bands
are disjoint. Unselected bands stay empty. Flat terrain normalization returning
None still produces no contours or fills.

The service supplies the same local normalized field to band-fill rendering.
Non-field effects keep their existing call path. Fill extraction remains before
contour simplification; slope/contour orientation changes only vector sampling.
Attach the existing `topographic-fill` role, stable IDs and channels. The audit
records the user's rule, including orientation, without serializing gradient arrays.
No neutral schema, pen-plan schema or downstream validator change is needed.

## Limits and errors

Preserve all sample, scalar-region, catalogue and pass vertex limits. Derivative
storage is bounded by the existing 250,000-sample field cap and allocated once per
domain. Check that bound for direct adapter callers too. Field-mark candidate and
clipped-point limits remain enforced by the common renderer.

Improve band-fill accumulation to enforce the remaining combined pass vertex
budget while consuming rule outputs, rather than collecting every rule first.
Keep catalogue per-call caps; do not silently truncate output. Count contours and
fills together and fail atomically with domain/rule context. Contour-only bundle
bytes and ordinary fill-rule ordering must remain unchanged.

Any inadequate coordinate precision, invalid field context, numeric overflow, or
budget excess produces a clear ValueError before publishing. Never repair regions,
delete tiny islands, silently coarsen sampling, or bridge clipped fragments.

## Verification and examples

Analytic evaluator tests cover constant fields, x/y and diagonal planes, unequal
grid spacing, nonzero origins, 2-by-2 grids, bilinear interpolation, contour rotation,
flat thresholds, exact/outside boundaries, invalid inputs, immutability, and caps.
Check raw-vector interpolation before normalization with independently calculated
expected components. Test scale behavior and finite arithmetic failures.

Catalogue tests cover immutable descriptors, controls, missing/wrong/unexpected
field context, empty regions, and unchanged outputs for existing effects. Verify
non-field generators reject unsupported context-dependent effects early.

Service tests cover same-field reuse, zero allocation for old effects, direction
selection, holes/islands/concave clipping, unfilled bands, empty channels, translation,
reversed winding, domain/rule order, simplification invariance, shared budgets, and
normalization returning None. Compare ordinary contour and fill bundle bytes before
and after the change, and retain early validation/overwrite atomicity regressions.

Generate a small tuning job showing slope marks, contour marks, and selected bands
on a concave domain. CLI pass/domain seed derivation means distinct panel identities
produce distinct terrain; do not imply these are a controlled direction comparison.
For visual direction comparison, use the Python service with the same effective
seed/domain/terrain and change only orientation. Inspect neutral surfaces and a
colored composed preview. Check the current plotter-workflow neutral validator.

Run full tests and Ruff, then one fresh independent read-only review under the
preserved native execution preference. Push and create a PR against main after
verification; do not merge automatically. Preserve prior worktrees and previews.

## Design status

Concept approved in conversation. Written spec awaits user review before the
implementation plan is prepared. No product code has been changed.
