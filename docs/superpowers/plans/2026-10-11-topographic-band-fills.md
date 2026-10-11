# Topographic Elevation-Band Fills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Native execution remains selected. Track steps with checkboxes.

**Goal:** Fill explicitly selected elevation bands with catalogue effects while preserving islands, holes, and contour-only output.

**Architecture:** Shared marching-square cell topology supports both continuous contours and polygonal height-threshold regions. Indexed bands are differences of nested threshold regions. The topographic service renders configured band unions through the existing fill catalogue and neutral bundle adapter.

**Tech Stack:** Existing Python 3.12, NumPy, SciPy, Shapely, Pydantic, pytest and Ruff; no new dependencies.

**Spec:** [Approved band-fill spec](../specs/2026-10-09-topographic-band-fills-design.md).

## Global constraints

- Work in `.worktrees/topographic-band-fills`, branch `feat/topographic-band-fills`; preserve other worktrees and previews.
- Band identities are 0..N for N contours; empty bands retain their indices. The first/last cover remaining low/high terrain.
- Use the same normalized sampled field and levels as contours, before simplification; no second seeded terrain pass.
- Fill rules are explicit, optional and disjoint in selected band indices. Unspecified bands are unfilled.
- First two channels remain intermediate/index contours; additional channels exactly match referenced fill layer IDs.
- Preserve contour-only path and bundle bytes, neutral schema, domain frames, and independent polygon artwork.
- All five current catalogue effects are supported; do not duplicate their parameter or renderer implementation.
- Per-domain region cell-level workload cap: 12,000,000. Intermediate polygon-coordinate budget: 1,000,000. Preserve existing field/contour/catalogue caps; final contour plus fill vertices share 1,000,000 per-pass limit.
- Do not repair topology with buffer(0), delete small islands, silently coarsen grids, or publish partial output.
- Physical plotter testing is deferred by the user. Software tests, downstream contract checks, and SVG inspection remain required.
- Native execution with one fresh final reviewer, then push/create PR against main; do not merge automatically.

## Review focus

1. Exact-level vertices and plateaus can create degenerate cell cuts; regions must follow equality-below and preserve coverage (Tasks 1-2).
2. Saddle connectivity changes across thresholds; superlevel regions must remain nested and agree with contour boundaries (Task 2).
3. A tiny hole or island must survive composition even when its area is below the partition-check tolerance (Task 2).
4. Invalid effect parameters in an empty band still fail before sampling (Task 3).
5. Simplification, rule ordering, or translated domains must not change selected fills or lattice phase (Tasks 4-5).

## File map and interfaces

- Create `viz_virtualserver/scalar_fields/cells.py`: frozen `Crossing(key: tuple, point: Point)`; `cell_segments(field: SampledField, column: int, row: int, level: float) -> tuple[tuple[Crossing, Crossing], ...]`. Preserve existing edge/vertex keys, interpolated coordinates, saddle determinant sign/tie and equality policy exactly.
- Modify `scalar_fields/contours.py` to consume that helper; preserve contour canonicalization/stitching and ordering.
- Create `scalar_fields/regions.py`: frozen `BandRegion(index: int, lower: float | None, upper: float | None, geometry: BaseGeometry)` and `extract_band_regions(field: SampledField, levels: tuple[float, ...], polygon: PolygonDomain) -> tuple[BandRegion, ...]`.
- Modify `fill_effects/catalogue.py`: factor `validate_fill_parameters(*, effect: str, parameters: Mapping[str, object] | None = None) -> dict[str, float]` from the existing dispatch; render_fill_effect consumes it unchanged. Export the validator from `fill_effects/__init__.py`.
- Modify `generators/topographic/models.py`: frozen strict `BandFillRule` (bands, effect, parameters, layer_id), and `TopographicParameters.band_fills`, accepting JSON arrays but stored as tuples with immutable parameter mappings.
- Create `generators/topographic/fills.py`: `render_band_fills(regions: tuple[BandRegion, ...], rules: tuple[BandFillRule, ...]) -> tuple[tuple[str, FillStroke], ...]`; union each rule's chosen polygons, then render and canonicalize stroke order.
- Modify `generators/topographic/service.py`: validate channels/rules before evaluation, extract regions only when fills configured, emit contour paths then fill paths with shared budget and contextual errors.
- Reuse `generators/topographic/bundle.py`; attach existing `SemanticPath`/`PathGeometry` values with role topographic-fill in service rather than changing neutral projection rules.
- Tests: `tests/test_scalar_cells.py`, `test_scalar_regions.py`, `test_topographic_band_parameters.py`, `test_topographic_band_fills.py`; extend `test_scalar_contours.py`, `test_fill_effects.py`, and `test_generate_domain_bundle.py`.
- Example/docs: `examples/domain-jobs/topographic-band-fills.json`, `docs/algorithms/topographic.md`, `docs/reference/fill-effects.md`, `README.md`, `docs/README.md`.

## Verification conventions

Before execution, fetch/check latest main, integrate routine upstream changes in this isolated branch, and run the baseline. Use the root environment `../../.venv/Scripts/python.exe` from the worktree. Tests use unique system-temp basetemp paths and `-p no:cacheprovider --tb=short`; elevate if Windows temp permissions require it.

```powershell
$bandsTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-bands-' + [guid]::NewGuid().ToString('N'))
& '../../.venv/Scripts/python.exe' -m pytest tests/test_scalar_regions.py -q -p no:cacheprovider --basetemp $bandsTemp --tb=short
```

For each component, write tests, watch meaningful red failures, implement, verify green, and commit named files with whitespace checks and the established r-ballard author identity. Maintain the execution ledger. Save baseline contour-only bundle digests for the existing topographic tuning example before any refactor; include every SVG and design.json in the comparison. Do not overwrite the user's existing preview directories.

### Task 1: Shared scalar-cell topology

**Files:** cells.py, contours.py, test_scalar_cells.py, existing contour tests.

- [ ] Write fixtures for one-corner, adjacent-corner, diagonal/saddle, exact-level and constant cells. Assert the shared crossing key/point pairs equal existing contour segments, including both determinant signs and zero tie. Neighboring cells must share the same edge identity and coordinate. Include extreme finite heights from the current contour regression.
- [ ] Run cell tests to red, then extract existing contour crossing/pair logic into the exact helper interface. Do not change arithmetic order or segment visitation order; omit identical-coordinate/zero-length cuts as the current extractor does.
- [ ] Refactor contour extraction to use returned crossings, retaining graph keys, duplicate-edge elimination, budgets, and canonical paths. Run cell/contour tests and compare baseline topographic bundle bytes to green.
- [ ] Commit `refactor: share scalar cell topology with region extraction`.

### Task 2: Indexed polygonal band regions

**Files:** regions.py and test_scalar_regions.py.

- [ ] Write analytic tests for a plane (exact strip areas), radial hill and depression (nested holes), two hills/saddle, both saddle decisions/tie, exact-level plateaus, constant supplied fields, and levels outside range. Assert N+1 stable records, valid polygonal geometry, full target coverage, disjoint interiors, and boundary agreement with unsimplified contour cuts.
- [ ] Add convex/concave, reversed-winding, negative-origin and tiny-island/hole fixtures. Test a target outside the sampled rectangle is rejected rather than partially filled. Add workload and coordinate-budget failures before allocation/composition with monkeypatched small limits.
- [ ] Run tests to red.
- [ ] Build each superlevel region from scalar cells using Task 1's cuts. Fully high cells are aggregated into contiguous row-run rectangles to avoid allocating one polygon per cell/level. Empty cells contribute nothing. For cut cells, node the shared cuts with the cell boundary, polygonize faces, and retain faces incident to a strictly-above corner. Equality-only corners do not label a high face. Preserve every positive-area polygon; don't use representative-point terrain classification or a fixed triangulation that changes saddle decisions.
- [ ] Batch/compose contributions into threshold regions, then clip to the target polygon. Count polygon coordinates incrementally while creating contributions and after composition/difference/clip outputs, aborting at 1,000,000. Precheck total `(nx-1)*(ny-1)*len(levels)` against 12,000,000. Catch Shapely topology errors as clear ValueErrors with spacing/count guidance.
- [ ] Validate nesting. Difference each consecutive superlevel region to form bands; band0 is target minus first threshold, bandN is the last. Empty polygons remain indexed empty polygonal geometry. Bounds are None for unbounded outer elevations. Validate union/overlap area with `64 * float_epsilon * max(1, target.area, target_bounds_area)` tolerance; tolerance permits numerical checks only, not geometry deletion or repair. Non-nested/invalid geometry fails clearly. Fully constant generic fields partition at the supplied levels; service normalization's existing None behavior remains unchanged.
- [ ] Run analytic/geometry/budget tests to green; commit `feat: extract indexed elevation band regions`.

### Task 3: Strict fill rules and shared parameter validation

**Files:** catalogue.py, fill_effects/__init__.py, topographic/models.py, parameter/catalogue tests.

- [ ] Write tests for sorted bands/rules, immutable parameters, defaults, all five catalogue effects, strict band indices, duplicate/overlapping/out-of-range selection, unknown/null fields, effect-specific invalid parameters, and no fills by default. An invalid rule must fail even when its selected band is empty.
- [ ] Run to red. Factor catalogue validation without changing descriptors, defaults, numeric acceptance, or render dispatch output. Store the canonical validated controls in frozen rule parameter mappings; reject explicit null parameters before calling the catalogue validator.
- [ ] Validate band range and cross-rule disjointness in TopographicParameters; canonicalize rule ordering by bands and bands ascending. Support duplicate layer IDs across non-overlapping rules, not duplicate band assignments. Reject numeric strings/booleans/nulls and unknown fields. Keep the new default from altering ordinary job audit serialization, which records supplied parameters.
- [ ] Run existing catalogue tests and new parameter tests to green; commit `feat: validate deterministic topographic band fill rules`.

### Task 4: Service rendering and neutral channels

**Files:** fills.py, topographic/service.py, band-fill tests; bundle.py only if evidence requires it.

- [ ] Write service tests for alternating filled/unfilled bands, different effects/channels, per-rule adjacent-band union, disconnected islands and holes. Assert every complete fill stroke is covered by its selected union. Exercise all five effects through the catalogue and validate no fill-layer aliases with contour channels.
- [ ] Test source translation, reversed winding, domain independence/order, rule/index order invariance, empty regions/channels, zero-rule fast path, normalization returning None, and pass-wide contour-plus-fill vertex overflow. Assert invalid rules/channels are rejected before terrain evaluation.
- [ ] Run to red. Resolve the same sampled field once per domain. Extract unsimplified regions before plotting simplification; render each rule union in the bounds-local frame, restoring origin once for VectorPaths. Canonicalize stroke orientation/order with closedness intact; do not bridge independent fragments.
- [ ] Keep first two contour channels and exact additional referenced fill-channel set. Append fills after contours and attach topographic-fill semantic provenance using the existing path geometry/role mechanism, with stable per-pass/domain path IDs. Count all vertices together against the existing pass cap. Wrap errors with domain/rule identity; invalid geometry stays an error, not an automatic repair.
- [ ] Run new service tests, existing topographic tests, and no-fill bundle digest comparison to green; commit `feat: render topographic band fills through catalogue effects`.

### Task 5: CLI bundles and examples

**Files:** test_generate_domain_bundle.py, band-fill tests, example job, algorithm/reference/index docs.

- [ ] Add CLI tests for reproducible audit/SVG bytes, fill roles/layer catalog order, declared empty fill channels, concave surfaces, multiple rules, and failure preserving existing destination under overwrite. Verify downstream neutral-contract acceptance using plotter-workflow's current main validator read-only.
- [ ] Add `test_simplification_does_not_change_region_fills`: generate the same effective seed/geometry/rules at two contour simplification tolerances and compare fill paths exactly. Regions and lattice phase must be unchanged even when contour vertex counts differ.
- [ ] Run integration tests to red where behavior is absent, fix concrete integration defects, then verify green. Reuse the current neutral adapter/unused-layer retention; don't change producer or physical pen schemas.
- [ ] Add a small tuning job with an alternating stroke-dot square, mixed-effect/channel square, and concave target. Use N=8 and explicit selected bands; pick reviewed seeds exposing holes/islands. Include a controlled same-seed comparison if example pass/domain seed derivation would otherwise obscure the differences.
- [ ] Document band indexing, explicit union semantics, unfilled bands, effects/parameters, local coordinate phase, channel rules, budgets, constant-field behavior, and unsimplified fills versus simplified curves. Link the example and guide. No physical plotting or hardware assertions.
- [ ] Commit `docs: demonstrate topographic elevation band fills`.

### Task 6: Visual verification, regressions and PR

- [ ] Generate a fresh output/topographic-band-fills bundle; make a colored review SVG separately from neutral exports. Render with installed Inkscape and inspect alternating bands, unfilled holes, disconnected islands, boundaries and concave clipping. Inspect both whole design and surface SVGs. Record observations; tune example settings without dropping required geometry.
- [ ] Run full suite and Ruff; verify baseline contour-only outputs unchanged and downstream neutral validation accepted. Repeat/broaden checks only for new changes or unresolved concerns.
- [ ] Request one fresh whole-branch read-only review. Resolve substantive findings in one verified fix pass, with regressions watched red then green, and rerun relevant/full checks.
- [ ] Commit verified fixes, push and create PR against main. Preserve worktree/output previews; do not merge. Physical pen-force testing remains deferred independently.

## Plan review and handoff

Self-review maps every spec requirement to these tasks, especially scalar saddle/equality behavior, polygon partition integrity, early empty-band validation, output budgets, and contour-only invariance. Native execution remains selected. Review this written plan before implementation.
