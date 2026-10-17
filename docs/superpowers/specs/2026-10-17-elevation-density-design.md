# Elevation-driven mark density

## Intent and scope

Vary mark coverage across topographic regions using elevation, building on PR25's
deterministic thinning. The user approved minimum/maximum density and inversion,
with the same plotter-ready vectors, independent component choices and terrain.
Existing fixed-density output remains the default and must stay byte-identical.

This is architectural work because reusable mark renderers gain optional sampled
density context. Start with elevation only. Slope density, nonlinear response curves,
raster import, Truchet controls, ordered dithering, error diffusion and physical
testing remain outside scope. Native implementation and one fresh final review
remain selected. No new dependencies, neutral schemas or physical pen settings.

## Selected approach

Supply an optional scalar density evaluator to the existing mark renderers. A
topographic adapter samples the exact smoothed, normalized terrain already used
for contours and regions. The existing seeded row/column threshold then accepts
or rejects each candidate at its local density. No new random stream or placement
algorithm is needed.

Assigning one density to each elevation band would be simpler but introduce visible
steps; post-export removal would lose candidate ownership and fragment consistency.
Sampling continuous elevation at candidate centres preserves the useful abstraction.

## Topographic style syntax

Add optional density_source to ordinary fill styles and nonblank component choices:

```json
{"bands": [0, 2, 4, 6, 8], "effect": "stroke-dots",
 "parameters": {"spacing": 3, "mark_length": 0.7, "density": 1},
 "density_seed": 7,
 "density_source": {
   "type": "elevation", "minimum": 0.1, "maximum": 0.8, "invert": false
 },
 "layer_id": "terrain-dots"}
```

The source is a frozen strict model with type required and exactly "elevation";
minimum defaults to0, maximum to1, invert tofalse. Bounds must be finite real
numbers in inclusive0 through1, with minimum <= maximum. Reject booleans as
numbers, numeric strings, nonfinite values, unknown source types/keys and explicit
null. Invert is a strict boolean. Equal bounds are valid constant mappings.

Only stroke-dots, vortex-marks and field-marks accept this source. Other effects
and blank choices must omit it, including explicit null. The source belongs on a
style, not in its numeric parameters or at the top of a component-choice rule.
Every potential choice validates before terrain sampling, even if unused or its
band is empty. Share validation between ordinary and component styles.

Existing numeric density is a global multiplier, still default1. The mapping
produces a local value q; final density is `density * q`. This permits global
thinning without changing the elevation response. The density seed and its domain
derivation remain unchanged; the source configuration must not reseed candidates.

## Sampling and mapping

Create a reusable immutable sampled-elevation density adapter consuming SampledField
and the validated mapping. Reuse its immutable values; do not build derivative
arrays or resample terrain. Validate context type, grid bounds, representability
and existing sample cap before use. Do not normalize again over a component, band
or selected union.

For a centre inside the full sampled rectangle, bilinearly interpolate normalized
height h from adjacent nodes. Use the last cell on exact upper boundaries, support
2-by-2 and unequal-spacing grids, and reject nonfinite queries/results explicitly.
Clamp the interpolated height to[0,1], since the sampled smoothing halo can lie
outside the interior normalization range. Then set t=h, or t=1-h when inverted,
and return `minimum + (maximum - minimum) * t`. Keep finite arithmetic bounded and
the result within the declared interval; rounding correction may clamp to those
validated bounds, never hide invalid input or overflow.

Finite centres outside the full sampled rectangle return density0 with no
extrapolation. Even a nonzero minimum applies only inside that rectangle. This
matches the existing gradient source's outside policy; long marks whose centres
lie beyond the halo may be omitted although fragments could reach the polygon.
Document this limit rather than silently changing halo size. Constant mappings
are constant inside the sampled rectangle, not an outside extension.

Smoothing and normalization returning None retain the existing no-artwork behavior.
Changing contour simplification does not change source samples or density.

## Reusable renderer boundary

Introduce a DensityField protocol implementing `sample(x, y) -> float`. It owns
neither geometry nor seed state. Extend render_fill_effect and the three supported
direct renderers with optional density_field context. Vortex forwards it to the
common field-mark renderer. Descriptors expose supports_density_field, defaultfalse,
true only for the three supported mark effects.

Missing density_field means existing fixed-density behavior. Supplied context must
provide a callable sample method, including at density0 and on empty regions.
Unsupported effects reject supplied context. Each evaluated sample must be a
finite real in[0,1], rejecting bool/string/null/out-of-range; do not clamp generic
invalid field outputs. Topographic adapter height clamping is its explicit mapping
policy, not a generic renderer repair.

For each finite candidate centre: sample density (when needed), multiply by the
validated global density, then apply the existing exact seeded threshold with that
local value. Preserve version tags, row/column identity and exact integer-ratio
threshold arithmetic. No per-candidate mutable RNG or float-rounded integer cutoff.
Support variable local thresholds without rebuilding hash inputs unnecessarily.

Only retained candidates evaluate vector direction and construct/clip geometry.
All fragments share the candidate decision. Density-field sampling may be skipped
when the global multiplier is0, after normal context/region/plan validation. As
with existing vector fields, invalid unexecuted sample return values cannot be
validated without calling the evaluator; structural context validation is still
mandatory. A generic callback exception must not publish partial output; preserve
clear rendering/domain context in errors.

## Integration, invariants and limits

Topographic rendering supplies the same SampledField to the density adapter and
gradient views. Validate terrain type immediately even if density is0 or selected
geometry is empty; do not hide invalid context behind lazy sampling. No adapter
allocation when the source is omitted, and no gradient allocation for density-only
dots or rejected/zero-density field marks. All styles may reference the same raw
immutable field with different mappings.

Source bounds, inversion and global density change retention only. They do not
change terrain, component identities/choices, candidate positions, directions,
clipping, channels or stroke endpoints. At the same seed, pointwise-increased
density produces a superset of retained candidates. Inversion generally changes
which areas are dense and carries no global subset promise.

Use the same source/seed/frame across components and union rendering; never
include component, choice, band, layer or effect IDs in density selection. Existing
translation, composition, target/rule ordering and winding behavior remains. The
full-precision local-coordinate limitations still apply.

Candidate estimators remain independent of sampled density and count the full
planned lattice. Preserve per-call and per-rule aggregate caps, remaining combined
pass vertices, scalar budgets and atomic publication. No silent coarsening,
truncation, geometry repair or new minimum pen clearance.

Generalize the exhausted component vertex-allowance preflight to recognize a
topographic source with maximum0 as a known zero-output style, like static density0.
Still validate controls/context and reserve its full candidate work. Other variable
sources cannot promise zero output in advance and retain the conservative guard.
An exhausted allowance must never start a potentially nonempty subsequent renderer.

Declared layers include source-driven styles even when no marks survive. Audit
retains the supplied source configuration and seeds without serializing field
arrays. Feature roles and neutral pen handoff remain unchanged.

## Verification

Analytic source tests: x/y/diagonal planes, 2-by-2 and unequal grids, nonzero origins,
independently calculated bilinear values, exact boundaries, outside centres,
normalized halo excursions, inverted and constant mappings, malformed grids,
nonfinite queries/results, immutability and caps. Pin formula endpoints/midpoints.

Model/catalogue tests: strict source controls and placement on both style forms,
unsupported/blank sources and explicit nulls, every invalid unused choice before
sampling, descriptor capabilities, malformed density context even on empty/zero
calls, and invalid sampled values. Exercise direct entrypoints, not only dispatch.

Renderer tests: constant evaluator agrees with equivalent static density; variable
planes match independently computed candidate decisions; same seeded lattice at
pointwise-increased density yields nested sets; source sampled before vector field;
rejected candidates avoid vector samples; fragment/hole/concave clipping remains
correct; callback failures are contextual and atomic. Counts/budgets stay full.

Service tests: same terrain sampled once, no resampling or derivatives for dots,
ordinary/component source parity, no reshuffling of component choices, fixed frame,
translation/winding/order/simplification invariance, seed changes only retention,
empty channels, known-zero exhausted allowance, invalid unused source, and caps.

Save baseline contour, fill, gradient, component and static-density bundle digests;
all omitted-source outputs must stay byte-identical. CLI tests prove deterministic
audit/SVG bytes, source retention, empty channels and overwrite failure preserving
an existing destination. Add a small example and controlled same-effective-seed
normal/inverted comparison; independent CLI panels must not be described as the
same terrain. Render/inspect composed and neutral previews, validate current
plotter-workflow contracts read-only, and document approximate coverage/boundaries.

Run full suite, Ruff/whitespace and one fresh independent whole-branch review,
resolve substantive findings with regressions, then push/create PR against main
without merging. Preserve worktrees and previews. Physical testing stays deferred.

## Design status

Concept approved by proceeding with the recommended elevation/minimum/maximum/
inversion scope. Written spec awaits review before implementation planning.
No product code has been changed.
