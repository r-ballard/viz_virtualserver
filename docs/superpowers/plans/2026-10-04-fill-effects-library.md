# Shared Fill Effects Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Native execution is the user's preserved choice.

**Goal:** Extract reusable parallel hatching into a discoverable Python library while preserving existing Truchet outputs.

**Architecture:** A small package owns immutable stroke values, an explicit catalogue, and the existing clipping scanner. Truchet selects regions and converts coordinates, then attaches its own semantic provenance and logical layers. Its old hatching entry point remains a compatibility adapter.

**Tech Stack:** Python 3.12, existing Shapely 2.1 dependency, pytest, Ruff. No added dependencies.

**Spec:** [Approved design](../specs/2026-10-04-fill-effects-library-design.md)

## Global Constraints

- The initial effect ID is `parallel-hatch`.
- `spacing` defaults to 2 and must be positive; `angle` defaults to 45 degrees.
- Unknown fields and unknown effect IDs raise clear `ValueError` failures.
- The shared package must not import Truchet modules or `CurvePath`.
- Spacing uses the input geometry's units; phase is anchored at coordinate zero.
- Preserve the 100,000-row guard and 2,000,000 sampled-point guard.
- No job-schema or CLI changes are introduced.
- Existing SVGs, neutral metadata, path order, and hashes remain byte-for-byte unchanged for identical inputs in the installed environment.
- No new styles or copied Patternfills assets in this increment; crosshatch is the next catalogue addition.

## Review Focus

1. Booleans, numeric strings, and non-finite controls must fail clearly rather than coerce silently (Task 1).
2. Caller mutation must not change catalogue defaults or previously returned strokes (Task 1).
3. Non-polygonal and invalid regions must fail clearly; empty polygonal collections return no strokes (Task 1).
4. Tiny spacing at large coordinates must retain the precision rejection; disconnected fragments must never bridge holes (Task 1).
5. Both compatibility calls and normalized Truchet calls must preserve ordering and world-coordinate safeguards (Task 2).

## File map

| File | Responsibility |
| --- | --- |
| `viz_virtualserver/fill_effects/__init__.py` | Export the public API and value types |
| `viz_virtualserver/fill_effects/models.py` | Frozen `FillStroke`, `EffectParameter`, `FillEffectDescriptor` values |
| `viz_virtualserver/fill_effects/catalogue.py` | Explicit descriptor/renderer registration, strict validation and dispatch |
| `viz_virtualserver/fill_effects/parallel_hatch.py` | Existing scanline and clipping algorithm with shared geometry output |
| `viz_virtualserver/generators/truchet/hatching.py` | Compatibility adapter and limit re-exports |
| `viz_virtualserver/generators/truchet/multiscale_composition.py` | Shared API call in the existing normalized frame |
| `tests/test_fill_effects.py` | Independent public contract and geometry tests |
| `tests/test_truchet_hatching.py` | Compatibility and integration regressions |
| `docs/reference/fill-effects.md` | Catalogue, standalone usage, frame and ownership contract, future motif roadmap |
| `docs/README.md`, `docs/algorithms/truchet.md` | Link the shared library documentation |

## Execution environment

Work in `.worktrees/har43-fill-effects` on `feat/har43-fill-effects`.
Set `$fillPython` to the root repository's `.venv/Scripts/python.exe`; run all
commands from the worktree so imports resolve to its code. Create `.artifacts`
before tests with an explicit basetemp. Use a fresh basetemp per invocation.
Use the supplied commit identity `r-ballard <russellcballard@gmail.com>`.
Git metadata writes and Windows temporary-directory operations may need the
environment's elevated tool execution; do not modify unrelated repositories.

### Task 1: Shared catalogue and parallel-hatch engine

**Files:** Create the four package files and `tests/test_fill_effects.py` from the file map.

**Interfaces:**

- `FillStroke(points: tuple[tuple[float, float], ...], closed: bool = False)` is frozen and snapshots its input into tuples. Require finite 2D points and at least two distinct open or three distinct closed vertices. This value has no ownership or styling fields.
- `EffectParameter(name: str, default: float, unit: str, exclusive_minimum: float | None = None)` is frozen. Units are `input-units` for spacing and `degrees` for angle.
- `FillEffectDescriptor(id: str, name: str, description: str, parameters: tuple[EffectParameter, ...])` is frozen.
- `list_fill_effects() -> tuple[FillEffectDescriptor, ...]` returns implemented descriptors in registration order.
- `render_fill_effect(region: BaseGeometry, *, effect: str, parameters: Mapping[str, object] | None = None) -> tuple[FillStroke, ...]` validates and dispatches.
- Internal `parallel_hatches(region: BaseGeometry, *, spacing: float, angle: float) -> tuple[FillStroke, ...]` uses the existing scanner and exports `MAX_HATCH_ROWS`, `MAX_HATCH_POINTS`.

- [ ] Capture a baseline before changing product code: run `$fillPython -m viz_virtualserver.cli.domain_bundle examples/domain-jobs/truchet-hatching.json --output-dir .artifacts/fill-effects-before`. Require exit 0 and save the four files: `design.json`, `design.svg`, `surfaces/painted-square.svg`, `surfaces/unpainted-triangle.svg`.
- [ ] Write public-contract tests. `test_catalogue_defaults_and_immutability` asserts exactly `parallel-hatch`, spacing 2/input-units/exclusive minimum 0, angle 45/degrees, and frozen descriptors. `test_default_parameters_match_explicit_controls` compares omitted parameters with spacing 2/angle 45. `test_invalid_controls_fail` parametrizes unknown effect, unknown field, bool, string, zero/negative spacing, NaN and infinity, expecting `ValueError` even for an empty region.
- [ ] Write geometry tests. `test_horizontal_literal_endpoints` expects `(((1.,2.),(9.,2.)), ((1.,4.),(9.,4.)), ((1.,6.),(9.,6.)), ((1.,8.),(9.,8.)))` for `box(1,1,9,9)` with spacing 2/angle 0. `test_holes_and_disconnected_regions_never_bridge` checks the two middle fragments `(0,5)-(4,5)` and `(6,5)-(10,5)` around a rectangular hole and separate intervals for two disjoint boxes. `test_angles_and_zero_phase` asserts 0/180 equality, vertical rows on even x coordinates, and 45-degree slope with absolute tolerance `1e-12`.
- [ ] Write boundary tests. `test_empty_region_returns_tuple` covers empty Polygon/MultiPolygon/GeometryCollection. `test_region_contract` accepts collections containing polygons only and rejects Point, LineString, mixed collections, and a self-intersecting polygon with `ValueError`. `test_stroke_values_snapshot_and_validate` checks caller-list mutation, frozen fields, NaN, malformed coordinates, and insufficient distinct vertices. `test_hatch_limits_and_precision` exercises the literal row limit, translated-coordinate precision rejection, and a monkeypatched small point limit to avoid allocating millions of points.
- [ ] Run `$fillPython -m pytest tests/test_fill_effects.py -q -p no:cacheprovider --basetemp .artifacts/fill-effects-red`. Require failures due to the missing public API, rather than setup problems.
- [ ] Implement the value types, descriptor, validation and dispatcher. Accept real numeric controls excluding bool; copy supplied mappings, reject unknown names, validate finite values before rendering. Validate polygonal input recursively without repairing it. Keep registry private and explicit.
- [ ] Copy the existing scanner into `parallel_hatch.py`, replacing only `CurvePath` construction with `FillStroke`; preserve arithmetic, cardinal snapping, fragment ordering, GEOS error conversion and guards. Leave the old Truchet implementation in place until Task 2.
- [ ] Run the new tests and existing hatching tests with a fresh basetemp; require all pass. Run `$fillPython -m ruff check viz_virtualserver/fill_effects tests/test_fill_effects.py --no-cache`; require exit 0.
- [ ] Commit the standalone package and tests: `feat: add reusable parallel hatch fill catalogue`.

### Task 2: Truchet integration and compatibility

**Files:** Modify the two Truchet modules and `tests/test_truchet_hatching.py`.

**Interfaces:** Consume Task 1's public rendering API. Preserve old
`parallel_hatches(region, *, spacing, angle) -> tuple[CurvePath, ...]` and both
importable limit names. The multiscale renderer's signature and return types stay unchanged.

- [ ] Add `test_compatibility_adapter_matches_shared_geometry`, comparing adapter points/closed flags with shared strokes for a holed polygon and a multipolygon at angles 0, 45 and 135. Assert adapter results remain `CurvePath`. Add `test_multiscale_uses_shared_catalogue`, wrapping the compositor's shared renderer call and asserting effect `parallel-hatch`, normalized spacing and supplied angle; retain the existing literal geometry tests as independent correctness evidence.
- [ ] Run these focused tests and require the shared-dispatch test fails before integration.
- [ ] Replace old scanner with the thin shared-engine adapter. Re-export the shared limit constants. Replace the compositor's adapter import/call with `render_fill_effect(selected, effect="parallel-hatch", parameters={"spacing": hatch_spacing / arrangement.base_tile_size, "angle": hatch_angle})`. Preserve region composition, world precision guard, scaling, canonicalization and ownership assignment.
- [ ] Run `$fillPython -m pytest tests/test_fill_effects.py tests/test_truchet_hatching.py tests/test_truchet_multiscale_composition.py tests/test_truchet_multicolor.py tests/test_truchet_panels.py -q -p no:cacheprovider --basetemp .artifacts/fill-effects-integration`; require all pass.
- [ ] Generate the same example into `.artifacts/fill-effects-after`. Compare the four baseline files with `Path.read_bytes()`; require exact equality for each, reporting mismatches by filename.
- [ ] Commit: `refactor: route Truchet hatching through shared fill effects`.

### Task 3: Documentation, validation and delivery

**Files:** Create `docs/reference/fill-effects.md`; modify the two documentation links from the file map. No additional public behavior.

**Interfaces:** Document Task 1's actual descriptor fields and rendering signature; preserve Truchet's existing job interface.

- [ ] Document a runnable standalone call using `box(1,1,9,9)` and horizontal spacing 2; expected four open strokes. Explain SVG angles, zero-anchored phase, caller-selected units, valid composed regions, holes, strict validation, precision/resource limits, and ownership/layer assignment by generators.
- [ ] Document Patternfills as a motif reference with its repository/license links and the approved roadmap: stripe coverage now; crosshatch next; rings and plotted dots later; filled motifs need polygon construction. Clearly distinguish implemented catalogue entries from future effects.
- [ ] Run the documented example; require the literal four-stroke result. Run the full suite: `$fillPython -m pytest tests -q -p no:cacheprovider --basetemp .artifacts/fill-effects-full --tb=short`; require no failures. Run `$fillPython -m ruff check . --no-cache` and `git -c core.safecrlf=false diff --check`; require exit 0.
- [ ] Render the generated combined SVG with the installed Inkscape CLI and inspect its PNG. Validate the generated neutral bundle using the existing read-only `plotter-workflow/logical_layer_contract.py` helpers (`inspect_svg_contract`, `load_logical_layer_manifest`, `validate_surface_against_manifest`), following the prior hatching validation script and preventing bytecode writes outside this worktree. Require all surface paths/layers/provenance validate.
- [ ] Commit documentation: `docs: describe shared fill catalogue and plotter contract`.
- [ ] Request one fresh independent whole-branch review, per the preserved native workflow. Give it the approved spec, this plan, base `b7a339dc21864bede2b8aa95595057bd870b4864`, test evidence and Review Focus. Resolve substantive findings and rerun affected checks; broad checks need repetition only if subsequent changes justify it.
- [ ] Verify clean git status and final diff. Check PR #14 state: if open, push this branch and create a stacked PR targeting `feat/truchet-hatching`; if merged, use `main`, resolving any integration changes and rerunning affected checks first. Do not merge automatically.
- [ ] Update HAR-43 with the PR link and verified outcome; leave completion status consistent with the project's existing PR workflow. Report shared API behavior, preserved output checks and PR link to the user.

## Plan self-review

All approved spec sections map to the three tasks. Shared names and return types
are consistent across the catalogue, compatibility adapter and compositor.
Each Review Focus condition has an explicit owning test. Existing generator
regressions plus baseline bytes protect integration; future motifs remain outside
this extraction. This plan awaits user review before native implementation.
