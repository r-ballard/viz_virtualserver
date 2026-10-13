# Component Fill Choices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native execution remains selected. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Assign seeded weighted effects or blank treatment independently to disconnected topographic region components.

**Architecture:** A reusable polygon identity/selection module supplies canonical component decisions. Strict topographic choice rules feed the existing catalogue renderer with aggregate candidate and remaining vertex budgets, retaining ordinary whole-union behavior.

**Tech Stack:** Existing Python, Shapely, Pydantic, hashlib, pytest and Ruff; no dependencies added.

**Spec:** [Approved component-choice design](../specs/2026-10-13-component-fill-choices-design.md).

## Global constraints

- Work in `.worktrees/component-fill-choices`, branch `feat/component-fill-choices`, based on merged PR23 (`8f966b8`). Preserve other worktrees and artifacts.
- Union selected bands before component identification; holes remain attached, point-touching MultiPolygon members stay separate, every positive-area island is retained.
- Full-precision domain-local identities, no quantization, repairs, ordinal IDs or mutable RNG. Exactly equivalent local geometry retains choices under placement and reordering.
- Choice IDs are exact case-sensitive nonblank strings; 1–32 unique choices. Strict integer weights1–1,000,000. Explicit null effect means blank and forbids rendering fields.
- All six catalogue effects, strict field orientation, existing controls/channels and independent terrain remain supported.
- At most100,000 components and 1,000,000 input polygon coordinates per selected union. Aggregate100,000 candidate positions per component rule, crosshatch counts both families. Preserve per-effect caps and combined 1,000,000 pass vertices.
- Ordinary contour, fill and gradient bundles stay byte-identical. No neutral or physical pen schema change, no partial publication.
- Physical testing deferred; native implementation, one fresh whole-branch review, push/create PR against main without merging.

## Review focus

1. Repeated ring vertices, signed zero and alternate ring starts must not destabilize full-precision identity (Task1).
2. Hash collisions or unrelated component additions must not cause shared identities or change unchanged choices (Task1).
3. Unselected invalid choices and ambiguous old/new rule mixtures must fail before sampling (Task2).
4. Candidate accounting must use the actual padded rotated lattice or scan rows, especially circle rings and crosshatch (Task3).
5. A blank-only palette needs no fill channels or gradient allocation; declared nonblank choices remain channels when unused (Tasks2/4).

## Verification conventions

Use `../../.venv/Scripts/python.exe`. Fetch/check main and run a clean baseline before product changes. Save every neutral file digest for `topographic-tuning.json`, `topographic-band-fills.json` and `topographic-gradient-marks.json` in a plan-scoped ignored ledger. Use new output directories.

```powershell
$componentTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-components-' + [guid]::NewGuid().ToString('N'))
& '../../.venv/Scripts/python.exe' -m pytest tests/test_region_selection.py -q -p no:cacheprovider --basetemp $componentTemp --tb=short
```

Elevate tests if required by Windows temp ACLs. Observe meaningful red failures before implementation; run the named task suite to green, whitespace checks and Ruff, then commit named files as `r-ballard <russellcballard@gmail.com>`. Ledger path `.superpowers/sdd/2026-10-13-component-fill-choices/progress.md`; record actual counts and rulings. Preserve native PowerShell bookkeeping conventions.

### Task1: Canonical polygon components and seeded weighted decisions

**Files:** Create `viz_virtualserver/region_selection/__init__.py`, `components.py`, `weighted.py`, and `tests/test_region_selection.py`.

**Interfaces:** Frozen `RegionComponent(id: str, geometry: Polygon)`; `identify_components(region: BaseGeometry) -> tuple[RegionComponent, ...]`. Frozen `WeightedOption(id: str, weight: int)`; frozen `ComponentDecision(component: RegionComponent, choice_id: str)`; `choose_components(components, options, *, domain_seed: int, component_seed: int, bands: tuple[int, ...]) -> tuple[ComponentDecision, ...]`. This package has no catalogue/terrain dependency.

- [x] Write analytic identity fixtures for polygon/empty union, attached holes, disconnected/point-touching members and tiny islands. Assert counts, geometry equality and IDs invariant under winding, all ring starts, hole/member order and signed zero. Assert different full-precision shapes produce different IDs. Include repeated ring vertices without deleting vertices.
- [x] Add invalid/nonfinite geometry and coordinate/component-cap tests; monkeypatch limits to prove checks precede expensive canonicalization. Simulate digest collisions and assert explicit failure for unequal canonical bytes.
- [x] Pin canonical bytes and versioned weighted hashing with an independently encoded rectangle fixture and known expected choice. Verify choice reordering, unrelated component addition/removal, integer validation, duplicate/blank IDs, seed changes and ID/weight versus rendering-control independence.
- [x] Run to red (missing package).
- [x] Implement ring canonicalization: normalize signed zero, remove only the closing duplicate for cyclic comparison, choose lexicographically minimal cyclic coordinate sequence across both directions, restore closure; sort canonical hole sequences. Use an efficient minimal-rotation algorithm rather than allocating all rotations. Preserve repeated interior vertices. Encode fixed-endian2D WKB without SRID; SHA256 IDs, stable sorting and explicit collision detection.
- [x] Implement weighted selection using length-prefixed versioned UTF-8 scalar fields: tag `viz-component-choice-v1`, decimal domain_seed, decimal component_seed, comma-separated sorted decimal bands, component hex ID. Length prefix is unsigned8-byte big-endian for every field. Hash bytes, convert digest to unsigned integer modulo sum weights, select half-open cumulative intervals in ID order. Validate generic inputs without relying on topographic models.
- [x] Run region-selection tests green; commit `feat: identify and select polygon components deterministically`.

### Task2: Strict component-choice topographic rules

**Files:** Create `generators/topographic/component_models.py`, `tests/test_topographic_component_parameters.py`; modify `models.py`, `service.py` validation helpers where needed.

**Interfaces:** Frozen strict `ComponentFillChoice` with required id/weight/effect and optional rendering fields; frozen strict `ComponentFillRule` with bands, component_seed default 0, component_choices tuple. `TopographicParameters.band_fills` accepts `BandFillRule | ComponentFillRule`. `iter_rule_styles(rule)` yields nonblank validated rendering styles for channel/precision preflight without sampling.

- [x] Test both forms, frozen canonical ID-order choices, all effects, blank syntax, omitted versus explicit null rendering controls, strict weights and seeds, count caps, duplicate/blank IDs, empty/null choice arrays, extra keys and ambiguous top-level old/new controls. Existing whole-union rules still reject component fields.
- [x] Test mixed-rule overlap/range validation and canonical band/rule order. Declared fill channel set includes every potential nonblank choice, while all-blank rules need only contour channels. Sampling spies prove invalid unused choices/aliases fail early, including empty eventual regions.
- [x] Run to red. Implement strict union parsing with extra-forbid models; do not infer ambiguous defaults. Reuse catalogue validation and existing field_direction constraints, share focused style validation rather than duplicate validators. Store immutable parameter mappings.
- [x] Refactor service preflight to traverse potential styles for exact channels and numeric precision controls; retain old error behavior and raw supplied audit parameters.
- [x] Run model/preflight and existing topographic parameter/service tests green; commit `feat: validate weighted topographic component palettes`.

### Task3: Shared candidate planning and exact cost accounting

**Files:** Modify `fill_effects/catalogue.py`, `__init__.py`, `parallel_hatch.py`, `stroke_dots.py`, `circle_rings.py`, `field_marks.py`, and `vortex_marks.py` only as needed; create `tests/test_fill_candidate_costs.py`.

**Interface:** Public `estimate_fill_candidates(region, *, effect, parameters=None) -> int`, independent of a field evaluator. Renderer and estimator consume the same private frame/lattice planning functions. Existing render signatures/output remain valid.

- [x] Write literal counts for hatch rows, both crosshatch families, padded dots/rings/field-mark lattices, rotated/cardinal cases, empty regions, boundary-touch candidates and very large angles. Compare estimator counts to actual renderer candidate iteration using sampling/clipping spies where appropriate, not output stroke counts.
- [x] Test ring radius padding, dot along-axis padding versus arbitrary-field two-axis padding, invalid controls/regions and precision/cost failures. Keep existing individual row/candidate/point caps.
- [x] Run to meaningful red. Factor planning arithmetic without reordering operations or changing cardinal snapping. `_scan_frame` is already shared; crosshatch uses the same reduced perpendicular angles. Extract dot/ring/field lattice plans from their renderers, preserving their distinct padding, indices and precision guards. Vortex uses the field-mark plan.
- [x] Dispatch estimator through catalogue controls to those same planners; no independent approximation or seeded sampling. Validate controls even for empty regions.
- [x] Run all fill suites; regenerate three ordinary jobs and compare saved hashes. Commit `refactor: share fill candidate plans for aggregate budgets`.

### Task4: Per-component rendering, gradients and aggregate budgets

**Files:** Modify `generators/topographic/fills.py`, `service.py`; create `tests/test_topographic_component_fills.py`.

**Interface:** Extend `render_band_fills(..., *, domain_seed: int | None = None, sampled_field=None, max_vertices=...)`. Component rules require the effective domain seed; old rules retain their prior call path. Service passes `context.domain_seeds[domain.id]`.

- [x] Test selected-band union before splitting, known weighted effects/blanks, component containment with holes/concave boundaries, preserved tiny islands and domain-local lattice phase. Use geometry/seed fixtures with pinned choice assignments, not chance-based assertions.
- [x] Test component/rule/domain order, winding, exact local translations, composition placement, simplification invariance and component_seed changes with unchanged terrain. Unchanged components retain choices after unrelated additions.
- [x] Test shared one gradient adapter across ordinary and choice rules, zero allocation for blank selections, missing seed/field context and errors identifying bands/component/choice.
- [x] Test cumulative candidate excess before the failing component renderer executes; crosshatch both families count. Test remaining pass vertex excess stops subsequent components, all-blank palettes, unused channels and no geometry repair/truncation.
- [x] Run to red. Keep ordinary renderer path and sorting unchanged. For choice rules identify canonical components, select, skip blank, reserve exact candidate cost against100,000 per rule, then render using component geometry in the existing frame. Canonicalize strokes per component and append in component-ID order. Reuse one lazy gradient adapter for rendered field choices.
- [x] Pass domain seed from service and preserve topographic-fill IDs/provenance. Wrap errors with domain/rule/component/choice context. Continue checking remaining pass vertices while consuming results.
- [x] Run new/existing topographic and selection/fill suites, compare all three baseline jobs, then commit `feat: render seeded component fill choices`.

### Task5: CLI examples, visual review and completion

**Files:** Create `examples/domain-jobs/topographic-component-choices.json`, `tests/test_topographic_component_bundle.py`; modify topographic guide, fill reference, README and docs index.

- [x] Add CLI reproducibility, mixed old/new rules, audit choice/seed retention, empty potential channels, all-blank palette, failure atomicity and existing-destination preservation tests. Run to red where integration behavior is missing and resolve evidenced defects.
- [x] Add a small N8 reviewed example with weighted blank/dots/hatch/terrain-mark choices and a concave target. Inspect actual seed assignments and retain enough components to show variety. Do not claim exact palette proportions or identical terrain across differently identified panels.
- [x] Document rule syntax, deterministic component/choice IDs, full-precision translation limit, holes/point-touch semantics, fixed lattice origin, seed decoupling, potential layers, aggregate costs and unchanged ordinary rules. Add no hardware claims or new external schema.
- [x] Generate fresh neutral bundles and separate colored review previews; render/inspect composed and surface SVGs for selected blanks, holes/islands, effect variety and clipping. Validate all surfaces with current plotter-workflow neutral validator read-only.
- [x] Run full suite, Ruff and whitespace checks, and compare every saved contour/fill/gradient digest. Commit `docs: demonstrate seeded component fills`.
- [x] Request one fresh independent whole-branch read-only review. Reproduce substantive findings red, fix green, rerun relevant/full verification, then commit fixes. Ledger minor notes.
- [ ] Push/create PR against main under existing user authorization, verify PR state, preserve worktree and previews; do not merge. Physical testing remains deferred.

## Plan review

Self-review maps all spec constraints to tests/tasks, with shared effect planning preventing estimator drift and generic selection isolated from catalogue ownership. Written spec and plan approved in conversation. Native execution remains selected.

## Execution evidence

Baseline1014 tests passed, two existing dependency warnings. Task1 missing-package red then9 analytic tests green; Task2 missing palette red then45 parameter tests green; Task3 missing estimator red then121 fill tests green; Task4 absent integration4 failures then57 selected suites green. Additional generic boundary errors were reproduced and corrected before review.

All ordinary contour, band-fill and gradient bundles remain byte-identical. Two new surfaces pass the current plotter-workflow validator. Composed and neutral concave previews inspected; example contains dots, hatch, field marks and blank regions with holes retained.

One fresh independent review found two P2 cases: empty union's GeometryCollection representation and a renderer call after exact vertex exhaustion. Both were reproduced failing then fixed, with29 targeted tests green. The reviewed example remains byte-identical after fixes and both final surfaces are accepted. Literal canonical digest and choice fixtures were added; approval-status documentation corrected. Final full verification: 1066 tests passed, two existing dependency warnings; Ruff and whitespace checks passed.
