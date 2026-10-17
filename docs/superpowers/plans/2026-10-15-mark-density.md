# Deterministic Mark Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Native execution remains selected. Track steps with checkboxes.

**Goal:** Thin dot and field-mark lattices reproducibly while preserving retained geometry and full-density output.

**Architecture:** A pure versioned lattice selector supplies exact density thresholds. Catalogue controls and renderer hooks apply selection before field sampling/clipping; topographic styles derive domain-local seeds and retain existing component choices and budgets.

**Tech Stack:** Existing Python, hashlib, Pydantic, Shapely, pytest and Ruff; no new dependencies.

**Spec:** [Approved density design](../specs/2026-10-14-mark-density-design.md).

## Global constraints

- Worktree `.worktrees/mark-density`, branch `feat/mark-density`, based on merged PR24 (`6164d30`). Preserve root checkout, other worktrees and previews.
- Support stroke-dots, vortex-marks and field-marks only. Density defaults to1 and is a finite real in inclusive 0–1; reject bool/string/null. Seed is a strict signed 64-bit integer, separate from numeric controls.
- Stable row/column thresholds, no RNG stream or physical-coordinate hash. Select before field sampling and clipping; fragments share their candidate's one decision.
- Topographic seed derivation excludes component, choice, band, layer, effect and numeric controls. Component assignment and terrain generation remain unchanged.
- Full planned candidate costs apply at every density, including0. Preserve all per-effect, aggregate, scalar and combined pass vertex limits; no partial publication.
- Omitted/explicit full density retains stroke and neutral output bytes. No pen/neutral schema change; no new Truchet controls, raster processing or variable-density field.
- Physical plotting deferred. Native execution, one fresh final read-only review, push/create PR against main; do not merge automatically.

## Review focus

1. A rounded float threshold must not change membership near an exact hash cutoff (Task1).
2. Invalid seeds/controls and missing field context must fail even at zero/full density or empty geometry (Tasks2–3).
3. Thinning must keep every fragment from a candidate together and avoid vector sampling for rejected candidates (Task3).
4. Changing component ownership must not reseed the shared local mask (Task4).
5. Density0 must retain channels, enforce candidate caps and avoid gradient allocation, including when the pass vertex allowance is exhausted (Task4).

## Verification conventions

Before code, fetch/check latest main and run the baseline. Save SHA256 digests of all neutral files for topographic-tuning, topographic-band-fills, topographic-gradient-marks and topographic-component-choices jobs in a plan-scoped ignored ledger. Generate new output directories.

Use `../../.venv/Scripts/python.exe` from the worktree. Tests use a unique system-temp base; elevate when Windows temp ACLs require it:

```powershell
$densityTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-density-' + [guid]::NewGuid().ToString('N'))
& '../../.venv/Scripts/python.exe' -m pytest tests/test_mark_selection.py -q -p no:cacheprovider --basetemp $densityTemp --tb=short
```

Observe meaningful red, implement, run each task's tests green, check Ruff/whitespace and commit named files using `r-ballard <russellcballard@gmail.com>`. Ledger: `.superpowers/sdd/2026-10-15-mark-density/progress.md`; use native PowerShell bookkeeping and record rulings/counts.

### Task1: Exact seeded lattice selection

**Files:** Create `fill_effects/mark_selection.py`, `tests/test_mark_selection.py`.

**Interfaces:** `validate_density_seed(seed: object) -> int`; frozen `MarkSelection(density: float = 1.0, seed: int = 0)` with `accepts(row: int, column: int) -> bool`; `derive_density_seed(domain_seed: int, style_seed: int) -> int`.

- [x] Write literal digest/membership fixtures for positive/negative/large indices and signed seed boundaries. Independently encode versioned length-prefixed fields and pin literal expected results. Test nested sets at0,.25,.5,.75,1, different seeds, independent call order, strict indices/seeds/density and exact endpoint fast paths with hashing spies.
- [x] Add an exact threshold test: compute numerator/denominator from density.as_integer_ratio and use integer arithmetic `(numerator << 256) // denominator`. Assert membership immediately around the resulting integer boundary with a controlled digest, avoiding approximate percentages.
- [x] Run to red. Implement tag `viz-mark-density-v1`, decimal seed,row,column, each UTF-8 field prefixed with unsigned 8-byte big-endian length; SHA256 unsigned digest versus exact threshold. Validate even endpoint controls; avoid hashing at0/1.
- [x] Implement domain derivation with tag `viz-topographic-density-v1`, decimal domain seed and style seed, same encoding; first 8 digest bytes interpreted signed big-endian. Validate domain seed is an integer and style seed signed 64-bit. No component/context fields enter the hash.
- [x] Run selector tests green; commit `feat: select mark candidates with exact seeded density thresholds`.

### Task2: Catalogue bounds and density controls

**Files:** Modify `fill_effects/models.py`, `catalogue.py`; extend catalogue tests, create `tests/test_mark_density_parameters.py`.

**Interfaces:** `EffectParameter.minimum/maximum: float | None = None`; append density parameter only to supported descriptors. `render_fill_effect(..., density_seed: int = 0)` validates seed; forwards it only to supported renderers. `estimate_fill_candidates` validates density, then strips it before unchanged planners.

- [x] Write descriptor/default/bound tests, all invalid density types/ranges on empty and nonempty regions, seed limits/types even at0/1, unsupported density controls/effect seed combinations and unchanged field-context requirements. Ordinary effects allow only the harmless default seed0 at catalogue boundary.
- [x] Run to red. Extend shared declared-bound validation without changing existing exclusive minima, parameter order or numeric acceptance. Update legitimate default descriptor assertions for the new density entry; retain old geometry fixtures.
- [x] Wire catalogue controls and seed dispatch together with Task3 renderer signatures; keep this task's commit coherent by completing Tasks2–3 before committing if necessary. Record that dependency ruling rather than checking in a broken dispatch.
- [x] Verify candidate estimates independent of density and unchanged limits at density 0. Run catalogue/candidate tests green.

### Task3: Apply selection before mark evaluation

**Files:** Modify `stroke_dots.py`, `field_marks.py`, `vortex_marks.py`; create `tests/test_mark_density_rendering.py`; update existing mark descriptor/default assertions as required.

**Interfaces:** Add optional `density: float = 1.0, density_seed: int = 0` to supported renderers. Construct MarkSelection once per render call; existing lattice planners do not consume thinning controls.

- [x] Write tests for omitted/explicit1 geometry equality, empty output at0, nested retained candidate geometry across densities, unchanged surviving endpoints and the same mask across dot/field/vortex evaluators. Test vector changes do not reshuffle candidate centres.
- [x] Use a region with a hole splitting one mark into multiple fragments: all fragments survive or disappear together. Verify concave clipping and no field sample calls for rejected marks. Test cardinal/rotated lattices and negative indices.
- [x] Run to red. After full candidate planning and finite-centre checks, apply selection before vector sampling, endpoint construction or clipping. Density0 may return after successful planning. Preserve existing geometry/sorting arithmetic for density 1, without hashing.
- [x] Keep direct-renderer controls strict, not only catalogue dispatch. Vortex forwards density/seed to the common field renderer. Retain context, region and full candidate caps at every density.
- [x] Run all fill suites and candidate tests; regenerate four baseline jobs and compare every saved digest. Commit coherent Tasks2–3 as `feat: add deterministic density to dot and field mark effects`.

### Task4: Topographic styles and independent seed context

**Files:** Modify `generators/topographic/fill_styles.py`, `component_models.py`, `fills.py`; create `tests/test_topographic_mark_density.py`.

**Interfaces:** Add strict signed 64-bit density_seed default 0 to mark styles/choices. Other effects must omit it; blank choices forbid it. Reuse the shared style validator and immutable numeric maps. Service continues supplying effective domain_seed.

- [x] Write tests for ordinary/component syntax, invalid unused density/seed, explicit seeds on unsupported/blank styles, retained channels at0 and early validation before terrain sampling. Existing raw audit/default output must stay unchanged.
- [x] Test seed derivation independent of component/choice/band/layer/effect IDs; compare candidate masks under equivalent union/component clipping. Changing density_seed changes marks while terrain curves and weighted decisions stay identical. Exercise translation, winding/order and simplification invariance.
- [x] Add zero-density field tests proving no SampledGradient allocation or vector samples, missing terrain still fails, candidate caps remain enforced and an exhausted vertex allowance does not reject a valid zero-output style merely because it declares an effect.
- [x] Run to red. Derive seeds for mark styles only; require domain_seed for thinning below1 in direct helpers. Preserve old full-density ordinary helper calls without context.
- [x] Make gradient construction lazy through a per-domain field-view adapter/getter: validate sampled terrain availability immediately, allocate shared arrays at the first retained vector sample, cache direction views. Do not substitute an invalid dummy field at0. Preserve shared arrays across rendered styles.
- [x] In component loops, reserve candidate work even at0; skip the exhausted-vertex pre-render rejection for known zero-density styles while retaining their validation/planning. Other styles keep the existing guard. No component reseeding or lattice rebasing.
- [x] Run topographic/catalogue/selection suites and four baseline digests green; commit `feat: integrate independent density masks in topographic fills`.

### Task5: CLI examples, documentation and final review

**Files:** Create `examples/domain-jobs/topographic-mark-density.json`, `tests/test_topographic_mark_density_bundle.py`; update topographic guide, fill reference, README and docs index.

- [x] Add CLI reproducibility/audit control retention, zero-density unused channels, component choices plus ordinary rules, unsupported controls, and atomic overwrite failure tests. Resolve missing integration with red/green regressions.
- [x] Add a small tuning job using sparse dots and field marks, including a concave target. Separately render a controlled same-seed/domain comparison at0,.25,.5,.75,1; distinct CLI panel identities are not identical terrain. Inspect monotonically increasing marks without moved survivors, clipping, holes and unchanged contours.
- [x] Document density versus spacing/length, index-mask semantics, independent seeds, full planned costs, declared empty channels, approximate coverage and unsupported hatch/ring/Truchet controls. Do not claim calibrated ink coverage or hardware testing.
- [x] Generate fresh neutral and separately colored previews, inspect composed and surface SVGs, validate current plotter-workflow contracts read-only. Compare all saved baseline files, run full suite/Ruff/whitespace and commit `docs: demonstrate deterministic mark density`.
- [x] Request one fresh independent whole-branch read-only review. Reproduce substantive findings red, fix green in one verified pass, rerun relevant/full verification and commit fixes; ledger minor notes.
- [ ] Push/create PR against main under existing authorization, verify state and preserve worktree/previews. Do not merge; physical testing remains deferred.

## Plan review

Self-review maps exact thresholds, seed separation, endpoint validation, fragment ownership, full candidate budgets and lazy zero-density fields to explicit tests/tasks. Tasks2–3 share dispatch signatures and form one coherent commit gate. Written spec and implementation plan approved in conversation. Native execution remains selected.

## Execution evidence

Baseline1066 tests passed, two existing dependency warnings. Missing selector observed before implementation, then16 selector tests green. Missing density controls/rendering15 failures reproduced; coherent catalogue/renderer gate131 selected tests passed. Topographic integration4 red failures then54 selected tests green. Updated default parameter expectations include density1; old geometry fixtures remain unchanged.

All four saved ordinary bundles remain byte-identical. Three new surfaces accepted by current plotter-workflow validator. Composed and neutral concave previews inspected; controlled identical-terrain mark counts0/71/132/209/295 form nested sets at0/.25/.5/.75/1. CLI41 tests passed; initial expanded full suite1111 passed with two existing warnings.

Fresh independent review found two P2 direct-entrypoint validation gaps: invalid dot region at zero density and wrong terrain type hidden by lazy fields. Both reproduced red and fixed with immediate validation;73 targeted tests passed. Literal domain-seed fixture added and documentation range corrected. Final full verification: 1113 tests passed, two existing dependency warnings; Ruff and whitespace checks passed. Physical plotting remains deferred.

Ruling: one transient Windows atomic-directory rename denial during baseline generation; fresh unique destinations succeeded without product changes. Native PowerShell ledger bookkeeping retained. Catalogue and renderer signature tasks were committed together as planned.
