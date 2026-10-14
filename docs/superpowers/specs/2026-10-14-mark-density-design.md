# Deterministic mark density

## Intent and scope

Add predictable density control for plotter-ready dots and field marks. The user
approved seeded thinning: retain a stable subset of existing lattice candidates,
with density independent of spacing, mark length, vector direction and component
choice. Increasing density adds marks without moving or replacing retained marks.

This is shared mark selection, first exposed through the fill catalogue and
topographic ordinary/component rules. Support stroke-dots, vortex-marks and
field-marks. Hatch lines and circle rings retain their existing controls. Truchet
density controls, ordered dithering, error diffusion, variable density fields,
raster import and terrain-driven density remain later work. No new dependencies,
neutral schemas or physical pen settings. Physical testing remains deferred.

Seeded thinning is selected because it is independent of traversal and integrates
with the existing vector lattice. Ordered dithering would add regular texture;
error diffusion needs traversal and source-density semantics absent from this step.
This is statistical coverage, not calibrated ink coverage or exact mark counts.

## Public controls

Append numeric `density` to the catalogue parameters for the three supported mark
effects: default1, inclusive range0 through1. Existing numeric controls/defaults
retain their order and values. Reject booleans, strings, nulls, nonfinite numbers
and values outside the interval before geometry evaluation.

Extend EffectParameter with optional inclusive `minimum` and `maximum` bounds,
defaultNone. Preserve exclusive_minimum for existing positive controls. The shared
validator enforces every declared bound; no effect-specific duplicate validator.
Hatch/ring effects reject density as an unknown control, including on empty regions.

Extend `render_fill_effect` with keyword `density_seed: int = 0`. It is a strict
signed64-bit integer, separate from numeric parameters so seeds never become floats.
Reject bool, float, string and out-of-range seeds, even when density is1 or the
region is empty. Non-mark effects reject nonzero density_seed; zero is the harmless
default. Existing field-context requirements remain in force at every density.

Add optional `density_seed` to topographic rendering styles and component choices,
default0, with the same strict signed64-bit range. It may be supplied only for the
three supported mark effects. Other styles and blank choices must omit the field,
including an explicit0. Keep density inside the existing numeric parameters mapping.
Every potential component choice validates these controls before terrain sampling.

Example ordinary rule:

```json
{"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots",
 "parameters": {"spacing": 3, "mark_length": 0.5, "density": 0.4},
 "density_seed": 0, "layer_id": "terrain-dots"}
```

Component-choice entries use the same fields. Blank treatment and density0 both
emit no strokes, but a density0 style still declares its logical layer and validates
its controls. Blank choice syntax continues to forbid rendering fields.

## Candidate selection

Create one reusable pure mark-selection helper taking lattice row/column integers,
density and an integer seed. It has no polygon, terrain, effect, channel or clipping
ownership. Selection uses versioned SHA256, not Python hash or an RNG sequence.

Encode the UTF-8 fields `viz-mark-density-v1`, decimal seed, decimal row and decimal
column, each prefixed with its unsigned8-byte big-endian length. Convert the digest
to an unsigned integer h. Retain the candidate exactly when
`h < floor(density * 2**256)`, computing that threshold using density's exact integer
ratio rather than a rounded float product. Special cases: density0 always rejects;
density1 always retains without hashing.

The same (seed,row,column) threshold is shared across supported mark effects.
Changing vector direction or mark length does not reshuffle selection; rotating
or resizing the lattice moves candidate centres while preserving index decisions.
No physical-coordinate hashes or iteration ordinals. Negative indices are valid.

Selection occurs after candidate planning and finite centre validation, before
field sampling, stroke construction or clipping. For a retained candidate,
existing geometry and clipping proceed unchanged. Every fragment from a clipped
mark shares its one retention decision. Rejected field marks do not sample vectors.
Zero vectors may still suppress a retained field candidate as before.

## Topographic seed and frame

Derive the catalogue seed once for each style/domain from the effective domain
seed and style density_seed. Use a distinct versioned length-prefixed SHA256 tag
`viz-topographic-density-v1` with decimal domain seed and decimal style seed, then
interpret the first8 digest bytes as a signed big-endian integer. This decouples
thinning from terrain sampling, weighted component selection and generator traversal.

Do not include component ID, palette choice ID, band selection, layer ID, effect ID
or controls in that derivation. The same local lattice and style seed therefore
share the same mask across disconnected components and union rendering. Adding an
island or changing which component owns a retained candidate does not reshuffle it.
Density_seed changes the mask without changing terrain or palette assignments.

Topographic rendering passes the derived seed only for supported mark styles.
Standalone catalogue calls use explicit density_seed or default0; they do not infer
a domain seed. Topographic direct rendering helpers require domain seed context
when thinning below1, while density1 ordinary calls preserve their existing API.
Component rules already require the domain seed for weighted selection.

Keep the existing bounds-local frame and lattice origin, with translation and
composition behavior unchanged. Full-precision geometry and clipping may still
have the existing representability limits; density introduces no snapping.

## Defaults, validation and budgets

Omitted density and explicit1 produce exactly the existing stroke geometry,
orientation, sorting and neutral output. Omitted controls continue to leave raw
job audit serialization unchanged; supplied density/seed appear in the audit.
Density0 yields no strokes and retains declared channels, after normal control,
field-context, region and candidate-plan validation. Do not allocate gradients
solely for a topographic field-mark style at density0, but validate its orientation
and field availability according to the existing service contract.

Candidate costs count the full planned lattice, regardless of density. A low
density must not bypass per-call or aggregate candidate limits. The shared estimator
validates density but strips it before invoking unchanged frame/lattice planners.
Existing sample/region/point/pass budgets and atomic publication remain unchanged.
Density0 can skip iteration after successful planning; ordinary effects continue
their existing execution paths and limits.

Changing density must not alter geometry selection, contour simplification,
weighted component assignments, terrain normalization or logical-layer ownership.
An invalid unused choice or empty-region style still fails early. No post-export
random deletion, automatic minimum pen clearance, silent truncation or geometry repair.

## Verification

Pin literal selector digest/threshold fixtures independently of rendering. Test
negative and large indices, exact density endpoints, exact integer-ratio threshold,
strict controls/seeds, deterministic independent calls, different seeds and nested
retained candidate sets for densities0,0.25,0.5,0.75,1. Cover thresholds immediately
around a known candidate cutoff without relying on approximate percentages.

Catalogue tests cover immutable inclusive-bound descriptors, new defaults, invalid
controls even on empty geometry, unsupported effects, missing field context and
strict seed types. All prior mark geometry remains identical at omitted/explicit1.

Renderer tests verify selection before clipping, all fragments retained together,
holes and concave boundaries, unchanged surviving endpoints, independent vector
direction/lattice angle, zero-vector behavior, no field sampling for rejected marks,
and full candidate budgets at sparse/zero densities. Candidate estimator counts
remain unchanged across density settings.

Topographic tests cover ordinary and component styles, independent terrain/palette
seeds, fixed domain-local phase, union/component mask agreement, target/rule/choice
order, translation/winding, simplification invariance, empty channels and gradient
allocation avoided for density0. Verify density_seed changes only thinning.

CLI tests prove repeatable audit/SVG bytes, explicit control retention, unused
channels and failure preserving an existing destination. Save baseline contour,
band-fill, gradient and component-choice bundles, then compare every neutral file.
Add a small tuning job and a controlled same-seed comparison of sparse-to-dense
marks; differently identified CLI panels are independent terrains and must not be
presented as a controlled comparison. Render and inspect composed/neutral previews,
and verify current plotter-workflow contracts read-only.

Run full suite/Ruff/whitespace and one fresh whole-branch read-only review under
native execution, then push/create PR against main without merging. Preserve
prior worktrees and previews. Physical plotting remains deferred.

## Design status

Concept approved. This written spec awaits user review before implementation planning.
No product code has been changed.
