# Elevation-Driven Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Native execution remains selected. Track steps with checkboxes.

**Goal:** Map sampled elevation to deterministic local mark coverage with minimum/maximum density and inversion.

**Architecture:** An immutable adapter samples the existing normalized height field. Optional density-field context feeds the shared row/column selector before vector evaluation and clipping; topographic styles supply the adapter without changing terrain, component choices or seeds.

**Tech Stack:** Existing Python, NumPy, Pydantic, Shapely, hashlib, pytest and Ruff. No new dependencies.

**Spec:** [Approved elevation-density design](../specs/2026-10-17-elevation-density-design.md).

## Global constraints

- Worktree `.worktrees/elevation-density`, branch `feat/elevation-density`, based on merged PR25 (`c82ee5e`). Preserve root checkout and previous worktrees/previews.
- Elevation source only; stroke-dots/vortex-marks/field-marks only. Missing source preserves existing fixed-density bytes.
- Source type required and exactly elevation; minimum/maximum default0/1, finite strict real bounds0–1 with minimum <= maximum; invert strict boolean defaultfalse. Explicit null/unknown keys rejected.
- Bilinear sampling uses the same smoothed normalized SampledField and halo, no renormalization/resampling/derivatives. Outside full rectangle returns0; inside height clamped to[0,1] before mapping/inversion.
- Final coverage = global density times mapped coverage. Preserve exact integer-ratio thresholds, hash versions, domain/style seed derivation, candidate positions and fragment ownership.
- Full candidate costs at all densities. Preserve all scalar, per-effect, aggregate and combined vertex limits; no repair, truncation, coarsening or partial publication.
- No new neutral/physical pen schema, Truchet controls, rasters or slope-density sources. Physical testing deferred.
- Native implementation, one fresh final independent review, push/create PR against main; do not merge automatically.

## Review focus

1. Halo values may exceed normalized interior bounds; clamp height only in the terrain adapter, never generic invalid callback output (Task1).
2. Exact last rows/columns, anisotropic2-by-2 grids and long-mark centres outside the halo need explicit boundary behavior (Task1).
3. Direct renderer zero/empty shortcuts must still validate region and structural field context (Task2).
4. Invalid unused component sources must fail before terrain sampling, while no-source calls allocate no adapter (Tasks3–4).
5. A source with maximum0 may render under an exhausted vertex allowance but still consumes full candidate work (Task4).

## Verification conventions

Fetch/check latest main and run baseline before code. Save SHA256 digests of every neutral file for topographic-tuning, topographic-band-fills, topographic-gradient-marks, topographic-component-choices and topographic-mark-density. Use new output directories; use unique suffixes if Windows atomic rename is transiently denied.

Use `../../.venv/Scripts/python.exe` from the worktree, unique system-temp test directories, and elevate if Windows ACLs require it:

```powershell
$elevationTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-elevation-density-' + [guid]::NewGuid().ToString('N'))
& '../../.venv/Scripts/python.exe' -m pytest tests/test_elevation_density.py -q -p no:cacheprovider --basetemp $elevationTemp --tb=short
```

Observe meaningful red before implementation; verify each task green, Ruff/whitespace and commit named files as `r-ballard <russellcballard@gmail.com>`. Track evidence/rulings in `.superpowers/sdd/2026-10-17-elevation-density/progress.md`. Use preserved native PowerShell bookkeeping.

### Task1: Immutable sampled-elevation density adapter

**Files:** Create `scalar_fields/densities.py`, `tests/test_elevation_density.py`.

**Interface:** Frozen `SampledElevationDensity(field: SampledField, *, minimum: float = 0, maximum: float = 1, invert: bool = False)` implementing `sample(x: float, y: float) -> float`. Reuse immutable field values; no derivative/copy allocation.

- [ ] Write independent plane fixtures: normalized x/y/diagonal terrain, exact corner/midpoint expectations, unequal spacing and nonzero origin,2-by-2 grids, bilinear values in a nonplanar cell, last-row/column endpoints and outside edges/corners.
- [ ] Test halo heights below0/above1, inversion, constant mappings, minimum/maximum endpoints, finite result bounds and outside0 even with nonzero minimum. Invalid types, wrong terrain, nonfinite queries, degenerate/unrepresentable bounds and sample-cap excess fail. Verify immutable adapter and shared field storage.
- [ ] Run to red. Implement validated grid extent/precision preflight using existing conventions; interpolate raw height with stable bounded weights, reject nonfinite results, clamp height, map/invert, and clamp only rounding excursions to validated mapping bounds. Do not extrapolate or renormalize.
- [ ] Run new and existing scalar sampling/gradient tests green; commit `feat: sample elevation as an immutable density field`.

### Task2: Generic local-density context and mark selection

**Files:** Create `fill_effects/density_fields.py`, `tests/test_density_field_rendering.py`; modify `mark_selection.py`, `models.py`, `catalogue.py`, `stroke_dots.py`, `field_marks.py`, `vortex_marks.py`, public exports as needed.

**Interfaces:** `DensityField` protocol `sample(x,y)->float`; `validate_density_field(field)` structural check and `sample_density(field,x,y)` strict finite0–1 return validation. Add `density_field: DensityField | None = None` keyword to catalogue and supported direct renderers. Descriptor `supports_density_field: bool = False`, true only for the three mark effects.

- [ ] Write descriptor/context tests including invalid/noncallable objects at empty/zero calls, unsupported effects, direct invalid regions, and callback returns bool/string/null/nonfinite/out-of-range. Constant callbacks must match static equivalent coverage exactly for representable products.
- [ ] Add independently calculated plane-callback decisions, pointwise-increased nested sets, direction-independent masks, callback-before-vector ordering and vector sampling avoided for rejected candidates. Hole-split fragments stay together; concave clipping and surviving endpoints unchanged.
- [ ] Test zero global multiplier skips callback evaluation after structural/region/plan checks, callback exceptions retain contextual ValueError with original cause, and full candidate counts/caps unchanged.
- [ ] Run to red. Extend selector with `accepts_at(row, column, density)` reusing the same seed/hash and exact ratio threshold logic; leave `accepts` fixed-density fast path unchanged. Validate local density before endpoint shortcuts.
- [ ] Add `effective_density(global_density, density_field, x, y)` shared validation/product helper. Validate supplied context before empty shortcuts; evaluate only after finite candidate centres, select before vectors/geometry/clipping. Vortex forwards context. Do not modify candidate planners or numeric parameter maps for callbacks.
- [ ] Catch ordinary callback Exceptions at the sampling boundary and raise contextual ValueError from the cause; do not catch process-control exceptions. Preserve existing no-source path geometry and hashing behavior.
- [ ] Run all fill/selector tests green and compare all five baseline jobs; commit `feat: support sampled local density in mark renderers`.

### Task3: Strict topographic source models

**Files:** Create `generators/topographic/density_models.py`, `tests/test_topographic_density_source_parameters.py`; modify `fill_styles.py`, `component_models.py`.

**Interface:** Frozen strict `ElevationDensitySource(type: Literal['elevation'], minimum: float = 0, maximum: float = 1, invert: bool = False)`. Optional `density_source` on ordinary styles/nonblank choices, defaultNone but explicit null rejected. Reuse source/style validation.

- [ ] Test valid mappings/immutability, all supported effects, inverted/equal endpoints, missing type/unknown type, bool/numeric-string bounds, minimum>maximum, nonfinite/out-of-range values, nonbool inversion and extra keys.
- [ ] Test unsupported/blank source including explicit null, wrong placement inside numeric parameters or component-rule root, invalid unused choices and empty selected bands. Sampling spies prove validation occurs before terrain evaluation.
- [ ] Run to red. Implement source typing and model_fields_set checks distinguishing omission/null, share ordinary/component rules and preserve canonical choices/immutable control maps. Keep no-source audits raw and existing defaults unchanged.
- [ ] Run parameter/service-preflight suites green; commit `feat: validate elevation density sources on topographic styles`.

### Task4: Same-field service integration and zero-source budgets

**Files:** Modify `generators/topographic/fills.py` and service only if needed; create `tests/test_topographic_elevation_density.py`.

**Interfaces:** Existing sampled_field/domain_seed helper context unchanged. Build `SampledElevationDensity` only for styles declaring density_source; pass as density_field. Use a focused helper `is_known_zero_style(style)` for static density0 or elevation-source maximum0.

- [ ] Test exact normalized field reuse and one terrain sampling call per domain; no adapter with source omitted; no gradients for source-only dots or density-rejected field marks. Wrong terrain type must fail immediately, including zero/empty cases.
- [ ] Test ordinary/component parity, source/global multiplier product, unchanged weighted choice IDs and contours when mappings/seed change, fixed-frame translation/winding/order/composition, simplify invariance, and pointwise-increased retained sets.
- [ ] Test maximum0 under exhausted allowance, full candidate reservations despite zero output, malformed source before sampling, empty channels, and potential nonzero sources prevented from starting a subsequent renderer after exhaustion.
- [ ] Run to red. Construct source from the existing SampledField without resampling/derivatives, preserve lazy vector allocation, same seed derivation and domain lattice origin. Do not include source properties in hashes.
- [ ] Generalize exhausted component guard to recognize known zero output while retaining context/plan validation and candidate reservation. Keep all other caps/error context and ordinary no-source path unchanged.
- [ ] Run new/existing topographic/fill suites; compare all five baseline bundles; commit `feat: apply elevation density to topographic mark fills`.

### Task5: CLI examples, visual verification and PR

**Files:** Create `examples/domain-jobs/topographic-elevation-density.json`, `tests/test_topographic_elevation_density_bundle.py`; modify topographic guide, fill reference, README and docs index.

- [ ] Add CLI repeatable audit/SVG bytes, source configuration retention, ordinary/component rules, unused channels, unsupported source and callback/source failure atomicity preserving an existing destination. Fix evidenced integration defects red/green.
- [ ] Add small example showing normal/inverted mapping with dots/field marks and concave clipping. Generate separate controlled same-effective-seed comparisons; distinguish independent CLI panels from identical terrain. Show mapping bounds, multiplier and inversion clearly in preview-only labels.
- [ ] Document strict syntax, global multiplier, source sampling/clamping/outside policy, approximate coverage, seed independence, known-zero/full candidate budgets and unsupported effects. No raster/physical claims.
- [ ] Generate fresh neutral bundles and separate colored previews, render/inspect composed and individual surfaces, validate current plotter-workflow contracts read-only. Compare all five saved baselines, run full suite/Ruff/whitespace, then commit `docs: demonstrate elevation-driven mark density`.
- [ ] Request one fresh independent whole-branch read-only review. Reproduce substantive findings red, fix green in one verified pass, rerun relevant/full checks and commit fixes; ledger minor notes.
- [ ] Push/create PR against main under existing authorization, verify PR state and preserve worktree/previews; do not merge. Physical testing remains deferred.

## Plan review

Self-review maps sampling bounds, strict direct entrypoints, unused choices, callback exceptions, exact local thresholds and known-zero budgets to explicit tests/tasks. No-source output comparison spans every earlier feature. Written spec approved; plan awaits review. Native execution remains selected.
