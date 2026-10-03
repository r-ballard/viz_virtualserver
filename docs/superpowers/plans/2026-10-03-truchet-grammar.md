# Compiled Truchet Grammar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Generate seeded, compatible square Truchet tilings as connected,
polygon-clipped vector paths in domain artwork bundles.

**Architecture:** Compile rotations and complementary region variants into
symbolic states. Assemble a compatible rectangular grid independently of motif
geometry, render and trace its connections, then clip to each target domain.

**Tech Stack:** Python 3.12, Pydantic, Shapely, pytest, existing viz_canvas contracts.

**Spec:** `docs/superpowers/specs/2026-10-03-truchet-grammar-design.md`

## Global Constraints

- Algorithm ID: `truchet`; exactly one logical layer: `truchet-curves`.
- Domain-local output; independent runner-provided domain seeds; no derived domains.
- No changes to shared job/bundle schemas or physical plotting responsibilities.
- `tile_size=10.0`, `arc_a=arc_b=sqrt(2)/2-0.5`, `curve_tolerance=0.02`.
- Arc controls range from 0.5-sqrt(2)/2 to 0.45 (corrected during execution); size and tolerance finite and positive.
- Maximum 100,000 tiles and 2,000,000 estimated sampled points per domain.
- Exclude overlapping motifs, fill paths, mixed sizes, and additional tile shapes.

## Review Focus

1. Translated or negatively positioned polygons must preserve relative grid geometry.
2. Very small sagitta must behave stably without huge-radius cancellation.
3. Clipping a loop into multiple pieces must not reconnect across exterior gaps.
4. Complementary states must preserve geometric identity while reversing regions.
5. Tiny tolerance and extreme aspect ratio must trigger limits before large allocations.

## Files and Responsibilities

- `truchet/models.py`: parameters and immutable tile, placement, and curve records.
- `truchet/grammar.py`: state compilation and edge compatibility.
- `truchet/assembly.py`: seeded rectangular arrangement and tile count checks.
- `truchet/geometry.py`: arc sampling, midpoint graph tracing, and polygon clipping.
- `truchet/service.py`: domain algorithm adapter; `truchet/__init__.py`: public exports.
- `scripts/generate_domain_bundle.py`: algorithm registration.
- `tests/test_truchet_{grammar,assembly,geometry,service}.py`: component tests.
- `tests/test_generate_domain_bundle.py`: CLI integration coverage.
- `docs/algorithms/truchet.md`, `README.md`, `docs/README.md`: user documentation.
- `examples/domain-jobs/truchet-{classic,asymmetric,polygon-targets}.json`: runnable jobs.

## Execution Setup

- [x] Read the spec and this plan; detect existing isolation with git rev-parse.
  Follow using-git-worktrees and the user's workspace preference. Work on a
  feature branch, not main; commit approved spec and plan there with explicit paths.
- [x] Inspect available Python/uv runtimes, use the locked development environment,
  and run `uv run --frozen pytest -q` to establish the baseline. If uv is unavailable,
  locate or install the required runner rather than changing dependency pins.
- [x] Keep temporary PDF tools and renders out of commits. No deletion outside
  verified workspace paths; do not stage unrelated files.

### Task 1: Parameters and Compiled Tile States

**Files:** Create models.py, grammar.py, __init__.py and test_truchet_grammar.py.

**Interfaces:**
- `TruchetParameters`: strict validated fields from Global Constraints.
- `TileState`: frozen record with `quarter_turn: int`, `complement: bool`,
  `connections: tuple[tuple[int, int], ...]`,
  `edge_regions: tuple[tuple[int, int], ...]`.
- `compile_states() -> tuple[TileState, ...]`: eight ordered states.
- `compatible(a: TileState, a_edge: int, b: TileState, b_edge: int) -> bool`.

Document edges clockwise as bottom, right, top, left; each signature follows
the boundary traversal. Base connections pair edges (0,3) and (1,2).

- [x] Write failing tests for exact defaults, allowed endpoints, strict invalid
  types/nonfinite inputs, four rotations, complement swapping, and reversed-edge
  matching. Assert eight symbolic states remain even for symmetric geometry.
- [x] Run `uv run --frozen pytest tests/test_truchet_grammar.py -q`; confirm failures
  refer to the missing feature rather than environment problems.
- [x] Implement the records, parameters, rotated signatures, and compatibility.
  Base corner regions occupy the bottom-left and top-right corners; complement
  swaps 0/1. Preserve the ordered first/second connection for arc_a/arc_b.
- [x] Run that test file; require all tests to pass.
- [x] Commit only this task's files: `feat: compile square Truchet tile states`.

### Task 2: Seeded Compatible Assembly

**Files:** Create assembly.py and test_truchet_assembly.py; extend models.py.

**Interfaces:**
- `TilePlacement`: frozen `(column: int, row: int, state: TileState)`.
- `TileArrangement`: frozen `(origin: Point, tile_size: float, columns: int,
  rows: int, tiles: tuple[TilePlacement, ...])`.
- `assemble_grid(bounds: tuple[float, float, float, float], *, tile_size: float,
  seed: int) -> TileArrangement`.

- [x] Write failing tests for identical seed output, variation across a set of
  seeds, every shared edge matching, fractional bounds covered with whole tiles,
  and translation preserving states. Exhaustively enumerate reachable left/below
  constraints and assert candidate existence. Test 100,000 permitted tiles and
  rejection above the limit without allocating their records.
- [x] Run `uv run --frozen pytest tests/test_truchet_assembly.py -q`; confirm failure.
- [x] Implement row-major assembly using ceil bounds coverage, stable compiled
  candidate order, and random.Random(seed). Filter against left and below tiles;
  raise an invariant error for no candidates. Check tile count first.
- [x] Run grammar and assembly tests; require pass.
- [x] Commit: `feat: assemble seeded compatible Truchet grids`.

### Task 3: Sample and Trace Motif Curves

**Files:** Create geometry.py and test_truchet_geometry.py; extend models.py.

**Interfaces:**
- `CurvePath`: frozen `(points: tuple[Point, ...], closed: bool)`.
- `sample_connection(start: Point, end: Point, *, sagitta_ratio: float,
  tolerance: float) -> tuple[Point, ...]` (positive bows toward square center;
  supply endpoint ordering consistent with that convention).
- `render_arrangement(arrangement: TileArrangement,
  parameters: TruchetParameters) -> tuple[CurvePath, ...]`.

- [x] Write failing tests for classic radius=tile_size/2, exact endpoints,
  zero-sagitta straight segments, positive/negative extremes staying inside tiles,
  near-zero stability, and chord error <= tolerance. Test asymmetric rotations
  and complement geometry equality. Exercise open chains and closed loops,
  asserting each tile connection is consumed once and joins aren't duplicated.
  Assert parameter changes never mutate symbolic arrangement.
- [x] Run geometry tests and confirm feature failures.
- [x] Implement stable circular sampling with an explicit straight case and
  numerically stable small-sagitta evaluation. Estimate point count for all arcs
  before allocation and reject totals over 2,000,000, including tiny tolerance.
  Use integer lattice midpoint keys (twice grid coordinates) for connectivity;
  trace degree-one chains first, then remaining cycles, in stable order.
- [x] Run grammar, assembly, and geometry tests; require pass.
- [x] Commit: `feat: render and trace continuous Truchet curves`.

### Task 4: Polygon Clipping and Domain Adapter

**Files:** Extend geometry.py/tests; create service.py and test_truchet_service.py.

**Interfaces:**
- `clip_paths(paths: tuple[CurvePath, ...], domain: PolygonDomain)
  -> tuple[CurvePath, ...]`.
- `TruchetDomainAlgorithm.generate(*, canvas: CanvasGeometry,
  domains: tuple[PolygonDomain, ...], design_pass: DesignPass,
  context: AlgorithmContext) -> DesignResult`.

- [x] Write failing clipping tests for fully retained loops, partially cut loops,
  multiple components across a concavity, vertex tangencies, and clockwise input.
  Verify entire emitted LineStrings are covered by polygon.buffer(1e-9), rather
  than checking vertices alone. Test negative/transformed domain positions.
  Write service tests for repeated output, exact layer validation, domain seed
  independence, invalid controls, neutral ownership, and no derived domains.
- [x] Run geometry/service tests; confirm failures.
- [x] Implement Shapely intersection and recursive extraction of line components,
  dropping point-only/degenerate results. Normalize closed/open representation,
  component direction, and sort order. Never merge disconnected clipped pieces.
  Implement the adapter with simple/concave capabilities and strict layer checks.
- [x] Run all Truchet tests; require pass.
- [x] Commit: `feat: clip Truchet curves to polygon domains`.

### Task 5: Bundle Integration, Examples, and Visual Verification

**Files:** Modify runner registration, CLI tests, README/doc index; add guide/jobs.

**Interfaces:** Existing `ALGORITHMS['truchet']` and versioned domain job schema.

- [x] Add a failing CLI test using a small truchet job and assert audit JSON,
  combined SVG, and per-surface SVG retain domain IDs and truchet-curves layer.
- [x] Run the focused CLI test and confirm unknown-algorithm failure.
- [x] Register the adapter. Add classic, asymmetric (`arc_a=0.08`, `arc_b=0.35`),
  and polygon-target examples with explicit seeds/layers. Document parameters,
  clipping, tangent limitations, subset of paper rules, limits, and backlog.
- [x] Run `uv run --frozen pytest -q` and `uv run --frozen ruff check .`.
  Require no introduced failures; compare any existing lint issues to baseline.
- [x] Generate all three examples with scripts/generate_domain_bundle.py into
  `tmp/truchet-preview/`. Render their SVGs using an available SVG renderer and
  inspect images for seams, unintended borders, duplicated strokes, clipping
  gaps, and readable asymmetric curves. Keep preview tools outside dependencies.
- [x] Run `git diff --check` and review the whole feature diff against the spec.
  Resolve findings and rerun affected tests. Follow requesting-code-review for
  the execution method selected by the user.
- [x] Commit explicit files: `feat: expose Truchet domain bundle generator`.

## Completion

Report implemented behavior, verification evidence, example commands, and any
remaining limitations. Preserve backlog in the algorithm guide. Follow the
development-branch finishing workflow without merging or publishing unless
authorized. Mark plan checkboxes only after each step actually succeeds.

## Execution record

Native execution completed in .worktrees/truchet-grammar on
eat/truchet-grammar, using the existing locked development environment.
PowerShell equivalents replaced the bash bookkeeping commands on Windows.
Tasks 3 and 4 share one commit; other component and integration commits remain
separate. Arc controls were narrowed to the correct outward quarter-circle bound.
Visual QA caught and verified a second-corner chord-direction correction.
Independent review found decimal-boundary grid sizing changes under translation;
the fix snaps only within coordinate-derived floating-point error and its
regression passed RED then GREEN.

Deferred minor: extreme subnormal curvature/tolerance can incorrectly trigger
the sampling limit through radius overflow; documented in the algorithm guide.
Clipping pieces at a closed path starting point may add a pen lift; geometry
remains correct, so further stitching is an optional optimization.

PR integration update: merged current main's package consolidation into the
feature branch. The generator now lives at `viz_virtualserver/generators/truchet/`,
uses `viz_virtualserver.canvas` imports, and is registered in
`viz_virtualserver/cli/domain_bundle.py`. The operator command is
`uv run --locked viz-domain-bundle`. The historical task paths above describe
the initial implementation; no compatibility aliases were reintroduced.
Full post-integration verification: 532 tests passed and Ruff checks passed.
