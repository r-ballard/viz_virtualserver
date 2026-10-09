# Synthetic Topographic Artwork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native execution was selected by the user. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate deterministic natural terrain contours as polygon-clipped, plotter-ready artwork with adjustable terrain smoothing.

**Architecture:** A reusable scalar-field package evaluates and samples heights, then extracts continuous contours. A separate topographic domain algorithm handles parameter validation, clipping, safe simplification, and logical layers through existing bundle contracts.

**Tech Stack:** Python 3.12, NumPy, SciPy Gaussian filtering, Shapely, pytest, existing domain-bundle CLI. No new dependencies.

**Spec:** [Approved architecture spec](../specs/2026-10-09-topographic-design.md).

## Global constraints

- Worktree `.worktrees/topographic`, branch `feat/topographic`; preserve root checkout and prior worktrees.
- Independent polygon artwork; use existing per-domain seeds and domain coordinate frame. Reject composition-frame terrain.
- Preserve existing concentric and Truchet behavior; no job/bundle schema changes or plotter-workflow writes.
- Implement independently from reference source; do not copy or bundle its code, assets, GUI, or pen settings.
- Require exactly two distinct logical layers: intermediate first, index second; retain empty declared channels.
- Per-domain caps: 250,000 halo-backed samples, 12,000,000 samples times contour levels, 1,000,000 extracted segments.
- Final plotted vertices: 1,000,000 per pass across all targeted domains.
- No silent grid coarsening, contour dropping, gap bridging, or partial bundle publication.
- Use `64 * machine_epsilon * max(1, abs(minimum), abs(maximum))` as negligible height-range threshold.
- Commit with `r-ballard <russellcballard@gmail.com>`; one fresh whole-branch review after native implementation, then push/create PR under the existing workflow. Do not merge automatically.

## Review focus

1. Tiny positive sample spacing or very large smoothing must fail before integer overflow or allocation (Task 1).
2. Exact-level plateaus and saddle ties must not create doubled paths or nondeterministic connectivity (Task 3).
3. Translation to negative coordinates and reversed polygon winding must preserve relative artwork (Task 5).
4. Boundary tangencies can produce point-only intersections; omit those without joining disconnected chains (Task 4).
5. Several individually acceptable domains can exceed the pass-wide vertex cap; abort atomically (Tasks 5–6).

## File map

- `viz_virtualserver/scalar_fields/models.py`: scalar protocol, frozen grid/contour records and resource constants.
- `viz_virtualserver/scalar_fields/sampling.py`: grid planning, halo sampling, smoothing, normalization.
- `viz_virtualserver/scalar_fields/terrain.py`: seeded gradient noise, fractal sum, domain warp.
- `viz_virtualserver/scalar_fields/contours.py`: marching squares, saddle decisions, canonical stitching.
- `viz_virtualserver/scalar_fields/__init__.py`: small public interface.
- `viz_virtualserver/generators/topographic/models.py`: strict topographic parameters.
- `viz_virtualserver/generators/topographic/geometry.py`: conservative simplification and polygon clipping.
- `viz_virtualserver/generators/topographic/service.py`: domain algorithm and pass resource accounting.
- `viz_virtualserver/generators/topographic/__init__.py`: package marker.
- Modify `viz_virtualserver/cli/domain_bundle.py`: algorithm registration only.
- Tests: `tests/test_scalar_sampling.py`, `test_scalar_terrain.py`, `test_scalar_contours.py`, `test_topographic_geometry.py`, `test_topographic_service.py`; extend `tests/test_generate_domain_bundle.py`.
- Documentation/example: `docs/algorithms/topographic.md`, `examples/domain-jobs/topographic-tuning.json`, `README.md`, `docs/README.md`.

## Test commands and execution conventions

From this worktree, use the root environment:

```powershell
$topoPython = '../../.venv/Scripts/python.exe'
$topoTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('viz-topographic-' + [guid]::NewGuid().ToString('N'))
& $topoPython -m pytest tests/test_scalar_sampling.py -p no:cacheprovider --basetemp $topoTemp --tb=short
```

Create a fresh temp path for every run. Substitute the task's named tests for the
sampling test. Use escalated execution if the environment requires it. Confirm
red failures reflect missing behavior, then implement and confirm green. No
dependency installation is needed. Run the full suite once before implementation
to establish the baseline, and once after integration; rerun after review fixes.
Commit each task's named files only, with `git diff --cached --check` and the
configured per-command author identity. A failing check stops the commit.

### Task 1: Validated sampling and smoothing

**Files:** Create scalar models, sampling, package initializer, topographic models and package initializer; create `tests/test_scalar_sampling.py`.

**Interfaces:**
- `ScalarField.sample(x: float, y: float) -> float` protocol.
- Frozen `GridPlan`: `origin`, `nx`, `ny`, `dx`, `dy`, `interior_rows`, `interior_columns`, `sigma_samples`.
- Frozen `SampledField`: `origin`, `dx`, `dy`, `values` (read-only float64 2-D array); dimensions derive from the array.
- Frozen `Contour`: `level: float`, `points: tuple[Point, ...]`, `closed: bool`; closed points omit repeated endpoint.
- `plan_grid(bounds: tuple[float, float, float, float], *, spacing: float, smoothing: float, contour_count: int) -> GridPlan`.
- `sample_field(field: ScalarField, plan: GridPlan) -> SampledField`.
- `smooth_normalize(field: SampledField, plan: GridPlan) -> SampledField | None`.
- `TopographicParameters`: strict frozen Pydantic model with defaults/ranges exactly matching the spec's parameter table.

- [ ] Write failing tests: `test_parameter_defaults_and_strict_rejections` asserts all nine defaults and rejects unknown fields, bools, strings, nonfinite values, invalid ranges. `test_grid_anchors_bounds_and_accounts_for_halo` asserts endpoints are grid nodes, actual step does not exceed spacing, and halo covers `ceil(4*sigma/step)+1` cells per side.
- [ ] Add `test_cost_rejected_before_sampling` with a counting field, tiny spacing and large smoothing; expect `ValueError`, zero calls, and no array allocation. Check exactly-at-limit and above-limit costs. `test_smoothing_zero_identity_and_constant_empty` asserts no filtering at zero and `None` for constant/negligible ranges. `test_normalization_uses_interior_not_halo` verifies halo values may remain outside [0, 1].
- [ ] Run sampling tests; confirm missing interfaces/behavior fail.
- [ ] Implement interfaces. Plan integer dimensions with finite-ratio checks before conversion/allocation. Use at least one interior interval per axis; equal steps span bounds; integer halo preserves anchoring. Use `scipy.ndimage.gaussian_filter` with four-sigma support and immutable resulting buffers. Reject any nonfinite sampled or filtered value.
- [ ] Add smoothing tests on a deterministic oscillatory fixture: reduced high-frequency variation, equivalent interior values with sufficient extra halo, and explicit nonfinite-field rejection. Run tests to green.
- [ ] Commit `feat: add validated scalar field sampling and smoothing`.

### Task 2: Seeded natural terrain

**Files:** Create `scalar_fields/terrain.py`, `tests/test_scalar_terrain.py`; extend public exports.

**Interfaces:** `TerrainField(seed: int, *, scale: float, octaves: int, roughness: float, warp_strength: float)` implements `ScalarField`. Coordinates are already local; field evaluator does not subtract polygon bounds.

- [ ] Write `test_terrain_seed_repeatability_and_variation`: identical construction yields exactly equal sampled values, different seeds produce different arrays, all values finite. `test_terrain_does_not_mutate_global_rng` checks Python and NumPy global RNG states remain unchanged.
- [ ] Write `test_zero_warp_and_zero_roughness`: zero roughness equals a single octave and zero warp equals the unwarped base fractal evaluator; large/negative finite coordinate fixtures remain finite or produce a clear validation error on unrepresentable intermediate values.
- [ ] Run terrain tests to establish red.
- [ ] Implement deterministic 2-D gradient noise using a local seeded permutation, smooth interpolation, and normalized weighted octave sum (frequency multiplier 2). Derive independent warp seeds with stable tagged hashing; sample low-frequency warp at half base frequency and displacement `warp_strength * scale`. Keep field construction/evaluation independent of grid resolution and polygon identity.
- [ ] Run terrain and sampling tests to green. Check samples at negative coordinates and across integer noise-cell boundaries are continuous within fixture tolerances.
- [ ] Commit `feat: add seeded natural terrain scalar field`.

### Task 3: Continuous contour extraction

**Files:** Create `scalar_fields/contours.py`, `tests/test_scalar_contours.py`; extend public exports.

**Interfaces:** `extract_contours(field: SampledField, levels: tuple[float, ...], *, max_segments: int = 1_000_000) -> tuple[Contour, ...]`. Input levels are finite, strictly increasing. Output ordered by level, then canonical geometry.

- [ ] Write `test_plane_contour_is_one_open_chain`: for height x on a 3-by-3 grid, level .5 produces one vertical chain with all x=.5. `test_radial_hill_produces_closed_loops` checks closedness, three distinct vertices minimum, and no repeated endpoint. `test_constant_field_has_no_contours` expects empty output.
- [ ] Add saddle fixtures with both asymptotic-decider outcomes and an exact tie; assert expected edge pairs and stable connectivity under repeated calls. Add exact-level vertices, plateaus, two hills with a saddle, and contours crossing the outer grid border; assert no duplicate edges, zero-length segments, or broken chains.
- [ ] Run contour tests to establish red.
- [ ] Implement marching squares with shared integer edge identities and interpolated intersections. For saddle values shifted by level, use the bilinear determinant, with a fixed documented tie connectivity. Classify equal-height vertices consistently on one side; canonicalize coincident vertex crossings so equality does not yield duplicated edges. Walk open chains before loops and canonicalize direction/loop rotation. Enforce segment cap while extracting, before constructing an oversized graph.
- [ ] Run analytic contour fixtures and prior scalar tests to green. Add `test_contour_budget_aborts` using a deliberately small segment cap and verify no partial result.
- [ ] Commit `feat: extract deterministic continuous terrain contours`.

### Task 4: Safe contour geometry

**Files:** Create `topographic/geometry.py`, `tests/test_topographic_geometry.py`.

**Interfaces:** `simplify_contours(contours: tuple[Contour, ...], *, tolerance: float) -> tuple[Contour, ...]`; `clip_contours(contours: tuple[Contour, ...], polygon: PolygonDomain) -> tuple[Contour, ...]`; `prepare_contours(contours: tuple[Contour, ...], polygon: PolygonDomain, *, tolerance: float) -> tuple[Contour, ...]` orchestrates simplification, clipping, and post-clipping fallback. Functions retain elevation and canonical ordering; use existing Point/domain types and Shapely.

- [ ] Write `test_zero_tolerance_preserves_contours` and `test_safe_simplification_respects_error_and_closedness`; assert closed loops keep three distinct vertices and simplification stays within tolerance of the original polylines.
- [ ] Write `test_close_contours_revert_unsafe_simplification` and a self-intersection fixture. Assert newly intersecting candidates revert to original paths, while safe neighbors still simplify. Preserve original intersection relationships rather than treating every touching raw contour as invalid.
- [ ] Write concave/convex clipping tests: complete segments covered by polygon, clipped loops become open fragments, inside loops remain closed, reversed winding equivalent, boundary tangency points omitted, disconnected fragments remain separate.
- [ ] Run geometry tests to establish red.
- [ ] Implement Shapely simplification with error/closedness checks and an STRtree to find affected contour pairs. Conservatively revert candidates that introduce intersections or remove loops. Clip paths independently, handle GeometryCollection/point-only results, remove only degenerate zero-length output, and canonicalize. In `prepare_contours`, recheck topology after clipping and fall back to clipped original paths for affected candidates.
- [ ] Run geometry and analytic contour tests to green.
- [ ] Commit `feat: preserve terrain contour topology through clipping`.

### Task 5: Topographic domain algorithm

**Files:** Create `topographic/service.py`, `tests/test_topographic_service.py`; modify CLI algorithm registry.

**Interfaces:** `TopographicDomainAlgorithm.generate(*, canvas, domains, design_pass, context) -> DesignResult`, matching `canvas.design.DomainAlgorithm`. Return domain-frame `VectorPath` values with ownership, producing pass ID, and the two declared layers.

- [ ] Write service helper following `tests/test_truchet_service.py`. Test deterministic repeatability, different seeds, target-order invariance, same-domain translation (including negative origins), reversed polygon winding, concave containment, and unchanged unrelated domains.
- [ ] Test exactly two nonempty distinct layer IDs; index i starts at 1, every Nth level on the second layer, index_every=1 and index_every>count empty-channel behavior. Assert no derived domains, no physical pen metadata, and explicit composition-frame rejection through the runner.
- [ ] Test invalid parameters before evaluation and pass-wide vertex cap across multiple domains. Make resource constants monkeypatchable for small fixtures; assert errors identify target domain and do not return partial results.
- [ ] Run service tests to establish red.
- [ ] Implement local bounds/seed resolution, grid planning, sampling/filtering/normalization, levels `i/(count+1)`, extraction, safe simplification and clipping. Restore polygon origin for paths. Return an empty result for negligible range. Accumulate final vertex count across the pass. Register `topographic` without modifying existing CLI projection handling.
- [ ] Run service, geometry, scalar, concentric, and Truchet service tests to green.
- [ ] Commit `feat: register topographic polygon artwork generator`.

### Task 6: Bundles, tuning sheet, documentation, review

**Files:** Extend `tests/test_generate_domain_bundle.py`; create `examples/domain-jobs/topographic-tuning.json`, `docs/algorithms/topographic.md`; modify `README.md`, `docs/README.md`.

- [ ] Add failing CLI integration tests using small jobs: reproducible audit/SVG output, both logical channels retained, multiple independent surfaces, and a cost error that leaves an existing destination unchanged under overwrite. Confirm downstream neutral-layer contract accepts exported surface SVGs and manifest.
- [ ] Run the integration tests to establish red where behavior is absent; fix only actual integration defects. Use the existing bundle writer unchanged unless evidence demonstrates a necessary defect.
- [ ] Build the tuning job with smoothing 0, 1, and 3, plus a second terrain realization and concave domain. For the separate controlled same-seed visual comparison, call the service with the same domain ID and explicit `AlgorithmContext.domain_seeds` value 31 at all three smoothing settings, render temporary SVGs with existing canvas SVG utilities, and document that comparison. The ordinary CLI tuning job retains its independently derived seeds; do not describe those panels as the same terrain seed.
- [ ] Generate `output/topographic-tuning/` via the existing CLI, render SVG to PNG with installed Inkscape, and inspect smoothing, natural terrain, major contours, clipping, and plotting detail. Do not commit generated output. Use comparison evidence to tune only parameters, not to relax correctness requirements.
- [ ] Write the algorithm guide with the nine parameter defaults/ranges, normalized elevations, intrinsic units, layer ordering, sample/smoothing/simplification distinctions, limits, and downstream imposition/pen assignment. Link it in both doc indexes.
- [ ] Run full suite with a fresh system-temp basetemp and Ruff `check . --no-cache`. Verify existing concentric/Truchet fixtures unchanged and neutral bundle contract accepted. Record test counts/warnings and actual visual observations.
- [ ] Commit `docs: demonstrate topographic plotting workflow` with integration tests and example.
- [ ] Invoke requesting-code-review for one fresh read-only whole-branch reviewer under native execution. Resolve substantiated findings with regression tests, rerun affected/full checks as needed, then push branch and create a PR targeting `main`. Preserve worktree/artifacts; leave merge to user.

## Plan review and handoff

Self-review checks every spec requirement against these tasks, including plateau
ties, simplification fallback after clipping, resource ceilings, and empty layers.
Native execution remains selected. Written-plan approval is required before
implementation; this plan contains no authorization to skip that gate.
