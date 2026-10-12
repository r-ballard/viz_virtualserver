# Terrain-Gradient Marks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native execution is selected. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render deterministic slope- or contour-oriented fixed marks inside explicitly selected topographic bands.

**Architecture:** A sampled-gradient adapter supplies raw vectors to the existing field-mark renderer through a context-dependent catalogue effect. Topographic rules select orientation and provide the existing normalized terrain; other generators reject effects requiring unavailable context.

**Tech Stack:** Existing Python, NumPy, Shapely, Pydantic, pytest and Ruff; no new dependencies.

**Spec:** [Approved terrain-gradient design](../specs/2026-10-11-terrain-gradient-marks-design.md).

## Global constraints

- Worktree `.worktrees/terrain-gradient-marks`, branch `feat/terrain-gradient-marks`, based on merged PR22 (`bdf937a`). Preserve root checkout and previous previews.
- Reuse the exact normalized sampled terrain and halo. Never resample seeded terrain or derive vectors from simplified curves.
- Independent polygon artwork, bounds-local lattice phase, selected-band unions, channel ownership and `topographic-fill` provenance remain unchanged.
- Directions are `slope` and `contour`; strokes are undirected, fixed length. No automatic density, length modulation, streamlines or shared terrain.
- Flat threshold: `64 * float_epsilon * max(1, max(abs(field.values))) / min(dx, dy)`; gradients at or below it return zero.
- Maximum field samples: 250,000. Preserve region caps, 100,000 field-mark candidates, 2,000,000 clipped mark points and the combined 1,000,000 final vertices per pass.
- Numeric/precision/budget failures are explicit and atomic. No geometry repair, tiny-island deletion, truncation, coarsening or fragment bridging.
- All five existing effects and existing contour/fill bundle bytes remain unchanged.
- Physical plotting is deferred. Native implementation, one fresh final independent review, push/create PR against main, no automatic merge.

## Review focus

1. Padded mark centres outside the sampled rectangle must return zero without indexing errors (Task1).
2. Unequal spacing and 2-by-2 fields must preserve correct raw derivatives and exact boundary interpolation (Task1).
3. Registering a contextual effect must not let Truchet advertise acceptance without a field source (Task2).
4. Explicit null or misplaced orientation must fail before sampling even for empty bands (Task3).
5. Multi-rule fills must fail as soon as the remaining pass budget is exceeded without altering deterministic order (Task4).

## Verification conventions

Use `../../.venv/Scripts/python.exe` from the worktree. Before code, fetch/check origin/main and run the full baseline. Save SHA256 digests of every file in contour-only `topographic-tuning.json` and existing `topographic-band-fills.json` bundles in a plan-scoped ignored execution ledger. Do not overwrite previous output directories.

Tests use a unique system-temp base directory; elevate where Windows temp ACLs require it:

```powershell
$gradientTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-gradients-' + [guid]::NewGuid().ToString('N'))
& '../../.venv/Scripts/python.exe' -m pytest tests/test_scalar_gradients.py -q -p no:cacheprovider --basetemp $gradientTemp --tb=short
```

Each task observes meaningful red failures, implements, verifies green, checks whitespace, and commits named files with `r-ballard <russellcballard@gmail.com>`. Run Ruff on changed code and the full tree before completion. Track evidence in `.superpowers/sdd/2026-10-12-terrain-gradient-marks/progress.md`.

### Task1: Immutable sampled-gradient adapter

**Files:** Create `viz_virtualserver/scalar_fields/gradients.py`, `tests/test_scalar_gradients.py`.

**Interface:** `SampledGradient(field: SampledField)` constructs immutable raw gradient arrays; `vector_field(direction: Literal["slope", "contour"]) -> VectorField` creates a lightweight view sharing them. Each view implements `sample(x: float, y: float) -> VectorSample`.

- [ ] Write `test_plane_raw_vectors`: heights `2*x + 3*y` return `(2,3)` at nodes and interior points, contour returns `(-3,2)`, including unequal dx/dy and nonzero origin. Add a non-planar fixture with independently calculated bilinear component interpolation; assert normalization happens afterward in VectorSample.direction.
- [ ] Add tests for constant/near-flat fields, exactly-at-threshold behavior, coordinate scaling, 2-by-2 fields, exact last row/column, all four outside edges/corners, nonfinite queries, invalid directions, immutable arrays, sample cap and arithmetic overflow. Outside finite queries return `(0,0)`; invalid values raise.
- [ ] Run new tests to red (missing adapter).
- [ ] Implement central interior and first-order one-sided outer differences using actual dx/dy. Validate cap/bounds/finite arithmetic before publication; store byte-backed immutable arrays. Bilinearly interpolate without extrapolation, using the last cell for exact upper boundaries. Apply the specified numerical floor after interpolation; rotated views share arrays.
- [ ] Run scalar-gradient and existing scalar tests to green; commit `feat: evaluate immutable sampled terrain gradients`.

### Task2: Context-dependent field-mark catalogue effect

**Files:** Modify `fill_effects/models.py`, `catalogue.py`, public exports as needed; extend `tests/test_fill_effects.py` and existing vector-field/field-mark tests. Audit `generators/truchet/models.py` and catalogue consumers in `classic_fills.py`, `multiscale_composition.py`; adjust validation ownership where needed.

**Interfaces:** `FillEffectDescriptor.requires_field: bool = False`; `render_fill_effect(region, *, effect, parameters=None, field: VectorField | None = None) -> tuple[FillStroke, ...]`. Numeric validation remains independent of field context.

- [ ] Write descriptor/dispatch tests: existing ordered five IDs followed by `field-marks`; only the last requires_field. Controls/defaults spacing8, mark_length0.5, angle0. A constant `(2,3)` field produces the same clipped strokes as direct `render_field_marks`.
- [ ] Test missing/noncallable field on empty and nonempty regions, supplied context for ordinary effects, bad VectorSample results, controls rejected before rendering, and early Truchet rejection without invoking costly geometry helpers. Existing effect bytes/strokes must remain unchanged.
- [ ] Run to meaningful red.
- [ ] Register the effect and delegate to the common renderer; do not duplicate lattice/clipping. Validate context explicitly. Existing generators without a source reject requires_field effects during parameter validation; preserve their current accepted effects/defaults.
- [ ] Run catalogue, field-mark and affected Truchet suites to green; commit `feat: add contextual field marks to fill catalogue`.

### Task3: Strict topographic orientation rules

**Files:** Modify `generators/topographic/models.py`; extend `tests/test_topographic_band_parameters.py`.

**Interface:** `BandFillRule.field_direction: Literal["slope", "contour"] | None = None`.

- [ ] Write tests accepting explicit slope/contour only for field-marks. Assert missing direction on field-marks, explicit null, unknown direction, wrong types, and direction supplied on old effects fail. Existing rule immutability, canonical order, overlap/range/channel checks remain valid.
- [ ] Run to red; implement before/after validation distinguishing omitted from explicitly supplied null. Keep catalogue numeric controls validated before sampling.
- [ ] Test invalid selections and directions with sampling monkeypatched to fail if reached, including an empty selected band.
- [ ] Run parameter/service validation tests to green; commit `feat: validate terrain mark orientation rules`.

### Task4: Same-field rendering and incremental pass budget

**Files:** Modify `generators/topographic/fills.py`, `service.py`; extend `tests/test_topographic_band_fills.py`.

**Interfaces:** `render_band_fills(regions, rules, *, sampled_field: SampledField | None = None, max_vertices: int = MAX_VERTICES) -> tuple[tuple[str, FillStroke], ...]`. Existing positional calls continue working for ordinary rules. Missing terrain for a field rule is a contextual error.

- [ ] Write service tests proving exactly one gradient-array construction per domain when both orientations are used, none for old rules, and no second terrain sampling. Analytic slope/contour marks must follow known plane axes and be covered by selected unions, preserving holes/concave clipping.
- [ ] Add translation, winding, domain/rule order, simplification invariance, normalizationNone and empty-channel tests. Compare fills at simplify0 and0.5 exactly. Direction changes affect vectors, lattice angle changes centres independently.
- [ ] Add budget regressions: combined contour/fill overflow; a second rule renderer spy must not run after the first exceeds the remaining budget. No partial bundle publication. Invalid numeric gradient data raises with domain/rule context.
- [ ] Run to red. Supply the same normalized field, construct one shared gradient adapter only if needed, and pass the selected view to contextual catalogue calls. Canonicalize as before.
- [ ] Prepare contours and count their vertices before rendering fills, while extracting regions from unsimplified terrain as before. Pass remaining vertex allowance and enforce it while consuming each rule's canonical strokes; retain the final service guard. Individual catalogue calls still have their existing caps.
- [ ] Run service/scalar/catalogue tests; regenerate both baseline jobs and compare all saved digests. Commit `feat: render terrain gradient marks within selected bands`.

### Task5: CLI example, documentation and final verification

**Files:** Create `examples/domain-jobs/topographic-gradient-marks.json`; modify `docs/algorithms/topographic.md`, `docs/reference/fill-effects.md`, `README.md`, `docs/README.md`; extend `tests/test_generate_domain_bundle.py`.

- [ ] Add CLI tests for repeatable manifest/surface bytes, fill roles/channel order, mixed old/contextual effects, unused fill channels, invalid orientation and failure preserving existing destination under overwrite.
- [ ] Run integration tests to red where behavior is absent, fix evidenced defects, and verify green.
- [ ] Add a small N8 example with slope square, contour square and selected-band concave panel, spacing3/mark_length1.5 initially. State distinct panels use independent terrain. Generate a separate controlled same-seed Python comparison for visual slope/contour inspection.
- [ ] Document catalogue context requirements, topographic orientation syntax, undirected slope axis, lattice-angle distinction, gradient approximation/flat threshold, halo/outside policy and budgets. Link guide/example; no hardware claims.
- [ ] Generate fresh neutral bundles and separate colored review previews, render in Inkscape, inspect both surfaces and composed artwork for orientation, retained holes/islands and clipping. Validate every surface using current plotter-workflow neutral validator read-only.
- [ ] Run full suite/Ruff/whitespace, compare saved ordinary contour/fill digests, and commit `docs: demonstrate topographic terrain gradient marks`.
- [ ] Request one fresh whole-branch read-only review. Reproduce and fix substantive findings with red/green regressions, rerun appropriate/full checks, then commit fixes.
- [ ] Push/create PR against main under the user's existing authorization. Verify PR state; preserve worktree/previews, do not merge. Record final evidence and links.

## Plan review

Self-review: all spec interfaces, context validation, numeric limits, same-field reuse, flat/outside policy and unchanged old outputs map to tasks. Task4 also resolves the prior review's accumulation-budget note without adding a second clipping renderer. Written spec approved; this plan awaits user review. Native execution remains selected.
