# Multi-scale Truchet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. The user selected native execution, followed by one independent whole-branch review.

**Goal:** Generate reproducible multi-scale Truchet boundary curves within independent polygon domains.

**Architecture:** Subdivide a domain-relative square grid into immutable leaves. Construct two winged motif regions per leaf, compose them from coarse to fine with depth-parity inversion, then clip their boundaries to the target polygon. Keep placement identity separate from rendering and physical imposition.

**Tech Stack:** Existing Python environment, Pydantic, Shapely, pytest, Ruff, existing domain-bundle CLI and SVG exporter; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-10-03-truchet-multiscale-design.md` (approved by the user's October 4 instruction to proceed).

## Global Constraints

- Register `truchet-multiscale`; preserve classic `truchet` behavior and defaults.
- Require exactly the logical layer `truchet-curves`; return domain-local paths and no derived domains.
- Defaults: `base_tile_size=40.0`, `max_depth=3`, `split_probability=0.45`, `curve_tolerance=0.02`.
- Strict integer depth 0 through 6; finite positive size/tolerance; probability in [0,1]; reject extra fields, numeric strings, booleans, and nonfinite values.
- One full base-tile halo per side; at most 10,000 leaves including halo and 2,000,000 estimated motif points per domain.
- Effective tolerance no greater than min(requested tolerance, smallest leaf side / 100).
- No rasterization, silent topology repair, user-visible fills, shared-coordinate job fields, physical placement, margins, or borders.
- Do not execute or bundle the reference implementation.

## Review Focus

- Very large translated coordinates must preserve relative geometry or raise a clear precision error, rather than collapse points (Tasks 1, 3).
- Extremely small tolerance must fail before allocating millions of points or overflowing arc calculations (Tasks 2, 3).
- Exact tangent contacts and closed-loop clipping must not create duplicate strokes or unexpected pen lifts (Task 3).
- Independent domains with identical bounds must use their own context seeds and ownership (Task 4).
- Rejected jobs must not publish a partial bundle, including when a later domain exceeds limits (Task 4).

## File Map

- Create `viz_virtualserver/generators/truchet/multiscale_models.py`: parameters, symbolic addresses, immutable leaves and arrangement frame.
- Create `multiscale_subdivision.py` in that directory: seeded subdivision and leaf budget.
- Create `multiscale_motifs.py`: analytical unit-square circuits, arc sampling, region invariants and sample budget.
- Create `multiscale_composition.py`: normalized precision, parity painting, boundary clipping and canonical output.
- Create `multiscale_service.py`: existing runner adapter.
- Modify `viz_virtualserver/cli/domain_bundle.py`: algorithm registry only.
- Create corresponding `tests/test_truchet_multiscale_{subdivision,motifs,composition,service}.py`; extend `tests/test_generate_domain_bundle.py`.
- Extend `docs/algorithms/truchet.md`, README and documentation index where algorithms are listed; add two examples under `examples/domain-jobs/`.

## Verification Commands

Run from `.worktrees/truchet-multiscale` with the existing root interpreter:

```powershell
$truchetPython = 'C:/Users/hardcase/Documents/developer/codex-repos/viz_virtualserver/.venv/Scripts/python.exe'
& $truchetPython -m pytest tests/test_truchet_multiscale_subdivision.py -q -p no:cacheprovider
& $truchetPython -m pytest tests -q -p no:cacheprovider --basetemp .artifacts/multiscale-pytest --tb=short
& $truchetPython -m ruff check . --no-cache
git diff --check
```

Use the targeted test file for each task's RED/GREEN cycle. Existing Windows temporary-directory ACL restrictions may require elevated test execution. Commit each completed task using the supplied author identity `r-ballard <russellcballard@gmail.com>` and explicit file staging.

### Task 1: Strict controls and deterministic placement

**Files:** `multiscale_models.py`, `multiscale_subdivision.py`, subdivision tests; reuse classic `assembly._tile_count` without changing its semantics.

**Interfaces:**
- `TileAddress(root_column: int, root_row: int, quadrants: tuple[int, ...])` is frozen and sortable.
- `MultiscaleLeaf(address: TileAddress, parent: TileAddress | None, bounds: tuple[float,float,float,float], depth: int, orientation: int)` uses bounds in base-tile units.
- `MultiscaleArrangement(origin: Point, base_tile_size: float, leaves: tuple[MultiscaleLeaf, ...])` retains the frame.
- `assemble_multiscale(bounds: tuple[float,float,float,float], *, parameters: MultiscaleParameters, seed: int) -> MultiscaleArrangement`.

- [x] Write failing parameter tests asserting the exact defaults, depth bounds, and rejection classes in Global Constraints.
- [x] Write failing partition tests: a one-root interior with depth 0 has one leaf; forced depth 3 has 64 equal-area leaves; every root including halo has total area 1 and disjoint interiors. Assert unique addresses, parentage, quadrant order and two possible orientations.
- [x] Write failing determinism tests: repeated seed equality, translated decimal bounds preserve normalized leaves, tolerance changes preserve leaves, and adding root enumeration order does not alter existing address choices. Assert excessive roots/forced subdivision raise leaf-limit errors.
- [x] Run subdivision tests and confirm failures are missing implementation or unmet assertions.
- [x] Implement strict parameters and immutable records. Use SHA-256 of a documented canonical encoding of seed, signed root indices, quadrant address and stream tag to derive independent split/orientation choices. Do not use Python hash. Count pending subdivision leaves before expansion so rejected requests remain bounded.
- [x] Run subdivision tests and existing classic assembly tests; expect all pass. Commit the placement implementation.

### Task 2: Winged motif regions

**Files:** `multiscale_motifs.py`, motif tests.

**Interfaces:**
- `MotifRegions(region_zero: BaseGeometry, region_one: BaseGeometry, sampled_points: int)`.
- `estimate_motif_points(*, orientation: int, tolerance: float) -> int` uses normalized unit tolerance without allocating samples.
- `build_motif(*, orientation: int, tolerance: float) -> MotifRegions` returns validated unit-square polygons, without depth inversion.

- [x] Write failing fixtures for exact eight ports and base connection pairs `(1,8),(2,7),(3,6),(4,5)`; orientation 1 rotates ports by two. Assert both region identities are nonempty, cover the content square to the declared approximation budget, have disjoint interiors, and fit bounds `[-1/3,4/3]`.
- [x] Write failing tests for circuit membership coverage, sampled arc deviation within tolerance, shared endpoint equality and rotation equivalence. Tiny tolerance must produce a bounded estimate or clear ValueError without polygon allocation.
- [x] Run motif tests and confirm RED.
- [x] Implement alternating interior-pair/exterior-successor circuits with tangent alternation and parity assignment from the spec. Represent circular arcs dimensionlessly; derive adaptive sample counts before sampling. Preserve exact endpoints, validate polygons and coverage explicitly; do not repair invalid polygons with buffer(0).
- [x] Run motif tests and subdivision tests; expect PASS. Commit the motif construction.

### Task 3: Scale composition and clipped curves

**Files:** `multiscale_composition.py`, composition tests.

**Interfaces:**
- `compose_regions(arrangement: MultiscaleArrangement, *, curve_tolerance: float) -> BaseGeometry` returns region 1 in the normalized frame.
- `render_multiscale(arrangement: MultiscaleArrangement, domain: PolygonDomain, *, curve_tolerance: float) -> tuple[CurvePath, ...]` returns canonical domain-coordinate curves.

- [x] Write failing hand-built neighbor fixtures at equal scales and ratios 2:1, 4:1 and 8:1 across both orientations/depth parities. Assert no dangling interior endpoints, no content-square seam strokes, and equal-depth order equivalence via symmetric-difference area within the precision budget.
- [x] Write failing halo-versus-larger-neighborhood tests and square/triangle/concave clipping tests, including negative coordinates, clockwise vertices, tangent-only contacts and clipped closed loops. Assert segment containment, canonical repeated output, no duplicate strokes and no target perimeter introduced by clipping.
- [x] Write failing precision/resource tests: large translations either match relative output within representable error or fail clearly; tolerance under representable resolution fails; total sampling over 2,000,000 rejects before any motif polygon construction.
- [x] Run composition tests and confirm RED.
- [x] Implement normalized tolerance and precision policy: reserve one quarter of effective error for snapping; choose grid spacing `min(effective_normalized_tolerance / 16, smallest_normalized_side / 1024)`. Reject if coordinate ULPs or snap displacement cannot fit that reserved budget; give analytical sampling the remaining budget. Document the policy beside the code.
- [x] Preflight all leaf sample estimates, caching identical orientation/tolerance motifs. Paint increasing depth then address using `painted.difference(footprint).union(region_one_after_parity)`. Start with explicit sequential operations; batch only if measured performance requires it and order-equivalence tests still pass.
- [x] Extract boundary before intersection with the normalized domain. Canonicalize component order/direction and loop start, remove duplicate consecutive points, discard point contacts and transform back; validate precision after transformation.
- [x] Run all multi-scale tests and classic geometry tests; expect PASS. Commit composition and clipping.

### Task 4: Runner, CLI, examples and visible acceptance

**Files:** `multiscale_service.py`, CLI registry, service/CLI tests, algorithm guide, README/index, `examples/domain-jobs/truchet-multiscale.json`, `examples/domain-jobs/truchet-multiscale-polygons.json`.

**Interfaces:** `TruchetMultiscaleDomainAlgorithm.generate` matches the existing classic adapter keyword-only signature and returns `DesignResult`; capabilities support simple convex/concave polygons.

- [x] Write failing adapter tests for required layer, strict parameters, domain ownership, domain-specific seeds, no derived domains and repeatable paths. Extend CLI tests for deterministic audit JSON/combined/per-surface SVG, unknown parameters and a later-domain resource failure leaving no published bundle.
- [x] Run targeted service/CLI tests and confirm RED.
- [x] Implement the adapter and registry entry using existing context seeds and error handling; keep classic adapter unchanged.
- [x] Run service/CLI tests and all multi-scale tests; expect PASS.
- [x] Add documented examples with verified mixed-depth seeds and independent square/triangle/concave polygons. Explain controls, winged composition, limits, curve-only output and future imposition boundary. Generate example bundles with the module CLI, following existing example schemas.
- [x] Generate an ignored SVG tuning sheet and previews for depth 0/1/3 and probability 0/0.45/1 using a fixed seed. Render with available existing tooling and inspect actual curves at mixed-scale transitions and polygon clipping. Adjust only after a failing geometric test captures any discovered defect.
- [x] Run the complete tests directory, Ruff and diff check using Verification Commands; record actual results. Commit integration, examples and documentation.

### Task 5: Independent review and completion

- [x] Request one fresh independent whole-branch review against the approved spec and this plan; use the requesting-code-review skill and native execution's final review convention.
- [x] Resolve actionable findings with a reproducing test first; rerun affected checks. Repeat full verification if changes affect integration or geometry.
- [x] Report verified behavior, test evidence, rendered SVG locations and any remaining limitations. Follow finishing-a-development-branch guidance within the user's existing integration authorization; do not silently merge or discard worktrees.

## Plan Self-Review

All spec sections map to Tasks 1–4; later imposition remains explicitly deferred. Interfaces consistently use normalized leaf bounds and domain-coordinate returned paths. The five Review Focus cases have tests assigned above. Geometry implementation remains gated by invariant tests and actual SVG inspection; the plan specifies decisions rather than copying the reference source.
