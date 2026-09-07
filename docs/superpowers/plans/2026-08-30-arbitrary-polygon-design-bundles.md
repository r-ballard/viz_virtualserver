# Arbitrary Polygon Design Bundles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a placement-independent runner that accepts one or more polygon domains, executes deterministic domain-aware design passes, and atomically exports a canonical design bundle with one intrinsic SVG per surface.

**Architecture:** Extend neutral paths with explicit domain ownership and coordinate-frame identity, add reusable domain-local/composition transforms, and introduce an immutable `DomainArtworkJob`. A runner executes existing algorithm adapters with stable per-domain seeds, then a projector and atomic bundle writer emit the audit JSON, canonical multi-domain SVG, and ordered surface SVGs. Physical imposition remains in `plotter-workflow`.

**Tech Stack:** Python 3.12, frozen dataclasses, Pydantic 2, Shapely 2, FastAPI-compatible models, `xml.etree.ElementTree`, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-30-arbitrary-polygon-design-bundles-design.md`

## Global Constraints

- Preserve all existing single-domain HTTP endpoints and SVG compatibility metadata.
- Accept `N >= 1` arbitrary simple polygon domains; never hard-code cootie-catcher counts or shapes.
- Keep domain-local, optional composition, and physical placement coordinate frames distinct.
- Preserve declared domain, surface, group-member, pass, result, layer, and projection order.
- Derive independent randomness from the job seed, pass ID, algorithm name, and stable domain ID, never a list index.
- Every projected path has one explicit source or derived domain ID and an explicit `domain` or `composition` coordinate frame.
- Emit one intrinsic projection for every declared or implicit surface, including empty artwork.
- Publish bundles atomically; a failed job must not expose partial output or replace a valid bundle.
- Do not add physical placement, pen assignment, HP-GL, or transport behavior to `viz_virtualserver`.
- Follow strict TDD for every task: RED, minimal GREEN, focused verification, Ruff, specification review, independent review, checkpoint, then commit.
- Preserve the user's unrelated uncommitted `CONCENTRIC_POINTS.md` change.

## File Structure

- Modify `viz_canvas/design.py`: add domain ownership to neutral paths and validate algorithm results.
- Create `viz_canvas/frames.py`: affine local-to-composition transforms and resolution.
- Create `viz_canvas/jobs.py`: immutable job model, implicit surfaces, semantic validation, and stable seed derivation.
- Create `viz_canvas/job_io.py`: versioned JSON request parsing into existing domain/semantic/pass types.
- Create `viz_canvas/runner.py`: execute independent and coordinated passes with deterministic context.
- Create `viz_canvas/projection.py`: select, transform, clip, and rebase paths per surface.
- Modify `viz_canvas/svg.py`: serialize domain-owned paths, transforms, and intrinsic projections.
- Create `viz_canvas/bundle.py`: audit payloads, digests, filename safety, and atomic publication.
- Create `scripts/generate_domain_bundle.py`: generic JSON-to-bundle command-line entry point.
- Create `examples/domain-jobs/cootie-catcher.json`: placement-free twenty-surface example.
- Modify `viz_canvas/__init__.py`: stable public exports.
- Modify `CANVAS.md`: job format, bundle outputs, CLI use, and repository boundary.

---

### Task 1: Explicit Domain Ownership and Coordinate Frame for Neutral Paths

**Files:**
- Modify: `viz_canvas/design.py`
- Modify: `concentric/service.py`
- Modify: `tests/test_canvas_design.py`
- Modify: `tests/test_canvas_svg.py`
- Modify: `tests/test_concentric_service.py`

**Interfaces:**
- Produces: `VectorPath(points, closed, layer_id, domain_id, coordinate_frame="domain")`.
- Produces: result validation that accepts path domain IDs from the pass targets or domains derived by the same result.
- Produces: frame validation limited to `"domain"` and `"composition"`.
- Preserves: `DesignResult.paths` ordering and all existing logical-layer behavior.

- [ ] **Step 1: Write failing ownership tests**

Add tests that construct two overlapping domains and require explicit, unambiguous ownership:

```python
def test_vector_path_requires_a_domain_id() -> None:
    with pytest.raises(ValueError, match="domain id must not be empty"):
        VectorPath(points=((0, 0), (1, 1)), closed=False, layer_id="ink", domain_id="")


def test_vector_path_rejects_unknown_coordinate_frame() -> None:
    with pytest.raises(ValueError, match="coordinate frame"):
        VectorPath(
            points=((0, 0), (1, 1)),
            closed=False,
            layer_id="ink",
            domain_id="target",
            coordinate_frame="physical",
        )


def test_design_executor_rejects_path_for_undeclared_domain() -> None:
    algorithm = StubAlgorithm(
        DesignResult(
            paths=(VectorPath(((0, 0), (1, 1)), False, "ink", "other"),),
            derived_domains=(),
            producing_pass_id="pass-1",
        )
    )
    with pytest.raises(ValueError, match="undeclared domain: other"):
        execute_design_pass(
            canvas=canvas,
            state=state,
            design_pass=DesignPass("pass-1", "stub", ("target",)),
            algorithms={"stub": algorithm},
        )
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
uv run python -m pytest tests/test_canvas_design.py tests/test_concentric_service.py -q
```

Expected: failures because `VectorPath` has no `domain_id` field and multi-target concentric paths cannot yet identify their source domain.

- [ ] **Step 3: Implement minimal path ownership**

Change the neutral type to:

```python
@dataclass(frozen=True, slots=True)
class VectorPath:
    points: tuple[Point, ...]
    closed: bool
    layer_id: str
    domain_id: str
    coordinate_frame: Literal["domain", "composition"] = "domain"

    def __post_init__(self) -> None:
        if not self.domain_id:
            raise ValueError("vector path domain id must not be empty")
        if self.coordinate_frame not in {"domain", "composition"}:
            raise ValueError("unknown vector path coordinate frame")
        # Retain the existing point and minimum-length validation.
```

After an algorithm returns, validate each path against:

```python
allowed_path_domains = {
    *design_pass.target_domain_ids,
    *(domain.id for domain in result.derived_domains),
}
```

Update every production and test constructor. In the concentric adapter, assign the currently iterated `domain.id` to every emitted path and retain the default `domain` frame.

- [ ] **Step 4: Run focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_design.py tests/test_canvas_svg.py tests/test_concentric_service.py -q
uv run python -m ruff check viz_canvas/design.py concentric/service.py tests/test_canvas_design.py tests/test_canvas_svg.py tests/test_concentric_service.py
```

Expected: all focused tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 5: Review, checkpoint, and commit**

Confirm legacy endpoint SVGs remain unchanged except for internal ownership. Request independent code review, report files/results/deviations, then commit:

```bash
git add viz_canvas/design.py concentric/service.py tests/test_canvas_design.py tests/test_canvas_svg.py tests/test_concentric_service.py
git commit -m "feat: associate design paths with polygon domains"
```

---

### Task 2: Domain-Local and Composition Transforms

**Files:**
- Create: `viz_canvas/frames.py`
- Create: `tests/test_canvas_frames.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `AffineTransform(a, b, c, d, e, f)` using SVG affine semantics.
- Produces: `CompositionTransform(domain_id, transform)`.
- Produces: `resolve_composition_transforms(domains, transforms) -> Mapping[str, AffineTransform]`.
- Consumes: existing `Point` and `PolygonDomain`.

- [ ] **Step 1: Write failing transform tests**

```python
def test_affine_transform_round_trips_a_point() -> None:
    transform = AffineTransform(a=2, b=0, c=0, d=3, e=10, f=-5)
    point = transform.apply((4, 6))
    assert point == pytest.approx((18, 13))
    assert transform.inverse().apply(point) == pytest.approx((4, 6))


def test_composition_transform_rejects_singular_matrix() -> None:
    with pytest.raises(ValueError, match="invertible"):
        AffineTransform(a=1, b=2, c=2, d=4, e=0, f=0)


def test_composition_transform_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError, match="unknown domain: missing"):
        resolve_composition_transforms(
            domains=(triangle,),
            transforms=(CompositionTransform("missing", AffineTransform.identity()),),
        )
```

- [ ] **Step 2: Run the new test and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_frames.py -q
```

Expected: import failure because `viz_canvas.frames` does not exist.

- [ ] **Step 3: Implement immutable affine transforms**

Use finite six-value matrices, determinant validation with the existing `1e-9` geometry tolerance, `apply()`, `inverse()`, `compose()`, and `identity()`. Copy transform collections to tuples/mapping proxies. Reject duplicate transform domain IDs and unknown domains. Do not create implicit composition transforms.

- [ ] **Step 4: Verify focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_frames.py -q
uv run python -m ruff check viz_canvas/frames.py tests/test_canvas_frames.py viz_canvas/__init__.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/frames.py viz_canvas/__init__.py tests/test_canvas_frames.py
git commit -m "feat: add intrinsic polygon composition frames"
```

---

### Task 3: Immutable One-to-Many Artwork Job

**Files:**
- Create: `viz_canvas/jobs.py`
- Create: `tests/test_canvas_jobs.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `DomainArtworkJob(schema_version, seed, domains, surfaces, groups, relations, composition_transforms, passes)`.
- Produces: `DomainArtworkJob.resolved_surfaces` with one implicit surface per domain when `surfaces is None`.
- Produces: `derive_domain_seed(job_seed, pass_id, algorithm, domain_id) -> int`.
- Consumes: existing domain, semantic, pass, and transform types.

- [ ] **Step 1: Write failing cardinality and determinism tests**

```python
def test_job_omitted_surfaces_create_one_ordered_surface_per_domain() -> None:
    job = DomainArtworkJob(
        schema_version=1,
        seed=42,
        domains=(triangle, square),
        surfaces=None,
        groups=(),
        relations=(),
        composition_transforms=(),
        passes=(design_pass,),
    )
    assert [(item.id, item.domain_id) for item in job.resolved_surfaces] == [
        ("triangle", "triangle"),
        ("square", "square"),
    ]


def test_domain_seed_is_stable_across_unrelated_reordering() -> None:
    before = derive_domain_seed(42, "pass", "algorithm", "stable")
    after = derive_domain_seed(42, "pass", "algorithm", "stable")
    assert before == after
    assert before != derive_domain_seed(42, "pass", "algorithm", "other")
```

Also cover explicit empty surfaces, duplicate IDs, unknown references, invalid pass graphs, and immutable defensive copies.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_jobs.py -q
```

- [ ] **Step 3: Implement the job model**

Use a frozen dataclass. Preserve `None` versus an explicit empty surface tuple long enough to enforce:

```python
if self.surfaces is not None and not self.surfaces:
    raise ValueError("explicit surfaces collection must not be empty")
```

Call `validate_semantics`, `validate_pass_graph`, and transform validation in `__post_init__`. Derive seeds with SHA-256 over a length-delimited UTF-8 encoding of the four stable inputs and convert the first eight digest bytes to an unsigned integer.

- [ ] **Step 4: Verify focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_jobs.py tests/test_canvas_semantics.py tests/test_canvas_design.py -q
uv run python -m ruff check viz_canvas/jobs.py tests/test_canvas_jobs.py viz_canvas/__init__.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/jobs.py viz_canvas/__init__.py tests/test_canvas_jobs.py
git commit -m "feat: add one-to-many polygon artwork jobs"
```

---

### Task 4: Versioned JSON Job Loader

**Files:**
- Create: `viz_canvas/job_io.py`
- Create: `tests/test_canvas_job_io.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `load_domain_artwork_job(payload: Mapping[str, object]) -> DomainArtworkJob`.
- Produces: `read_domain_artwork_job(path: Path) -> DomainArtworkJob`.
- Consumes: schema version `1` and existing canonical model types.

- [ ] **Step 1: Write failing loader tests**

Use a complete two-domain payload and assert ordered construction of domains, aliases, groups, relations, affine transforms, logical layers, pass contexts, dependencies, and parameters. Add exact failures for unsupported schema versions, malformed endpoints, missing domains, nonnumeric matrices, and unknown fields.

```python
def test_loader_builds_ordered_two_domain_job() -> None:
    job = load_domain_artwork_job(TWO_DOMAIN_PAYLOAD)
    assert [domain.id for domain in job.domains] == ["triangle", "square"]
    assert [surface.id for surface in job.resolved_surfaces] == ["front", "back"]
    assert job.passes[0].target_domain_ids == ("triangle", "square")
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_job_io.py -q
```

- [ ] **Step 3: Implement strict parsing**

Define private Pydantic request models with `ConfigDict(extra="forbid")`, convert them into the existing immutable domain types, and let canonical constructors perform geometry and semantic validation. Parse relation endpoints by the presence of `feature_type` and `index`; never guess a feature relation from geometry.

- [ ] **Step 4: Verify focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_job_io.py tests/test_canvas_jobs.py -q
uv run python -m ruff check viz_canvas/job_io.py tests/test_canvas_job_io.py viz_canvas/__init__.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/job_io.py viz_canvas/__init__.py tests/test_canvas_job_io.py
git commit -m "feat: load versioned polygon artwork jobs"
```

---

### Task 5: Deterministic Independent and Coordinated Runner

**Files:**
- Create: `viz_canvas/runner.py`
- Create: `tests/test_canvas_runner.py`
- Modify: `viz_canvas/design.py`
- Modify: `concentric/service.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `AlgorithmContext(job_seed, pass_seed, domain_seeds, surfaces, groups, relations, composition_transforms)`.
- Changes: `DomainAlgorithm.generate(..., context: AlgorithmContext) -> DesignResult`.
- Produces: `run_domain_artwork_job(job, algorithms) -> DesignState`.

- [ ] **Step 1: Write failing runner tests**

```python
def test_independent_results_survive_unrelated_domain_reordering() -> None:
    first = run_domain_artwork_job(job_with_domains((a, b)), {"record": algorithm})
    second = run_domain_artwork_job(job_with_domains((extra, b, a)), {"record": algorithm})
    assert paths_for(first, "a") == paths_for(second, "a")
    assert paths_for(first, "b") == paths_for(second, "b")


def test_coordinated_pass_requires_requested_composition_transforms() -> None:
    with pytest.raises(ValueError, match="composition transform required for domain: b"):
        run_domain_artwork_job(coordinated_job_without_b_transform, {"record": algorithm})
```

Cover pass dependency order, ordered target IDs in coordinated seeds, semantic context filtering via `group_context_ids` and `relation_context_ids`, and rejection of path/result mismatches.

Also require every path returned by a domain-local pass to have `coordinate_frame == "domain"`, and every path returned by a composition pass to have `coordinate_frame == "composition"`. This makes projection behavior explicit rather than inferred from geometry.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_runner.py -q
```

- [ ] **Step 3: Implement the runner and context**

Build one deterministic `CanvasGeometry` carrier whose rectangle is the union of the numeric bounds of the ordered source-domain vertices; it carries the job domains but has no placement semantics. A pass is coordinated only when `parameters["coordinate_frame"] == "composition"`; remove that runner-reserved key before validating algorithm-specific parameters, require a transform for every target, and require returned paths to declare the `composition` frame. All other passes receive domain-local geometry, stable `domain_seeds`, and must return `domain`-frame paths.

Define `AlgorithmContext` in `runner.py`; use forward annotations under `TYPE_CHECKING` in `design.py` and `concentric/service.py` to avoid an import cycle. Update every algorithm implementation, stub, and direct test call to pass the context. Update `ConcentricDomainAlgorithm.generate` to derive a request copy with `seed=context.domain_seeds[domain.id]` for each target, without mutating pass parameters. This satisfies the approved per-domain stability requirement rather than retaining one shared request seed.

- [ ] **Step 4: Verify focused and compatibility tests**

```bash
uv run python -m pytest tests/test_canvas_runner.py tests/test_canvas_design.py tests/test_concentric_service.py tests/test_concentric_api.py -q
uv run python -m ruff check viz_canvas/runner.py viz_canvas/design.py concentric/service.py tests/test_canvas_runner.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/runner.py viz_canvas/design.py viz_canvas/__init__.py concentric/service.py tests/test_canvas_runner.py
git commit -m "feat: run deterministic polygon artwork jobs"
```

---

### Task 6: Surface Projection and Intrinsic SVG Serialization

**Files:**
- Create: `viz_canvas/projection.py`
- Create: `tests/test_canvas_projection.py`
- Modify: `viz_canvas/svg.py`
- Modify: `tests/test_canvas_svg.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `SurfaceProjection(surface, domain, paths, layers, bounds, up_anchor)`.
- Produces: `project_surfaces(job, state) -> tuple[SurfaceProjection, ...]`.
- Produces: `surface_projection_to_svg(projection) -> str`.
- Consumes: explicit `VectorPath.domain_id`, `VectorPath.coordinate_frame`, and declared surface order.

- [ ] **Step 1: Write failing projection tests**

```python
def test_projection_rebases_paths_and_preserves_surface_order() -> None:
    projections = project_surfaces(two_surface_job, completed_state)
    assert [item.surface.id for item in projections] == ["first", "second"]
    assert projections[0].domain.vertices[0] == pytest.approx((0, 0))
    assert projections[0].paths[0].points[0] == pytest.approx((0, 0))


def test_empty_surface_still_serializes_intrinsic_polygon_metadata() -> None:
    svg = surface_projection_to_svg(empty_projection)
    root = ET.fromstring(svg)
    assert root.attrib["data-viz-canvas-polygon"]
    assert root.findall("svg:g", NS) == []
```

Also cover concave clipping, path partitioning by explicit domain ID, logical-layer order, intrinsic up metadata, coordinated composition-to-local inverse mapping, and no structural border artwork.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_projection.py tests/test_canvas_svg.py -q
```

- [ ] **Step 3: Implement projection**

For domain-local paths, translate the domain bounds minimum to `(0, 0)`. For composition-frame paths, apply the owning domain's inverse composition transform before rebasing. Reject composition-frame paths whose owning domain has no transform. Use Shapely intersection against the local polygon for coordinated crossing paths, preserving all resulting line components in source order. Serialize top-level `data-viz-role="logical-layer"` groups and existing intrinsic canvas metadata; do not emit `pen-N` groups.

- [ ] **Step 4: Verify focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_projection.py tests/test_canvas_svg.py tests/test_concentric_svg.py -q
uv run python -m ruff check viz_canvas/projection.py viz_canvas/svg.py tests/test_canvas_projection.py tests/test_canvas_svg.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/projection.py viz_canvas/svg.py viz_canvas/__init__.py tests/test_canvas_projection.py tests/test_canvas_svg.py
git commit -m "feat: project polygon surfaces to intrinsic SVG"
```

---

### Task 7: Atomic Canonical Bundle Writer

**Files:**
- Create: `viz_canvas/bundle.py`
- Create: `tests/test_canvas_bundle.py`
- Modify: `viz_canvas/svg.py`
- Modify: `viz_canvas/__init__.py`

**Interfaces:**
- Produces: `write_design_bundle(job, state, output_dir) -> DesignBundle`.
- Produces: `DesignBundle(root, audit_path, design_svg_path, surface_paths)`.
- Produces: deterministic `design.json`, `design.svg`, and `surfaces/<sanitized-id>.svg`.

- [ ] **Step 1: Write failing bundle tests**

```python
def test_bundle_writes_ordered_surface_files_and_digests(tmp_path: Path) -> None:
    bundle = write_design_bundle(job, state, tmp_path / "bundle")
    assert [path.name for path in bundle.surface_paths] == ["first.svg", "second.svg"]
    audit = json.loads(bundle.audit_path.read_text())
    assert [item["surface_id"] for item in audit["surfaces"]] == ["first", "second"]
    assert all(len(item["sha256"]) == 64 for item in audit["surfaces"])


def test_failed_bundle_does_not_replace_existing_output(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("original")
    with pytest.raises(ValueError, match="filename collision"):
        write_design_bundle(colliding_job, state, destination)
    assert sentinel.read_text() == "original"
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_canvas_bundle.py -q
```

- [ ] **Step 3: Implement deterministic atomic publication**

Sanitize IDs to lowercase ASCII `[a-z0-9._-]`, replace other runs with `-`, reject empty results and post-sanitization collisions. Write to `tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)`, verify every expected file and digest, then publish with a sibling backup/restore sequence so an exception retains the previous bundle. Remove only the exact validated temporary or backup directory created by this function.

The canonical `design.svg` serializes domain-owned paths in declared result order. A `domain`-frame path is mapped through its owning domain's declared composition transform when one exists and otherwise retained in local coordinates; a `composition`-frame path is already canonical and is not transformed again. Never invent a layout.

- [ ] **Step 4: Verify focused tests and Ruff**

```bash
uv run python -m pytest tests/test_canvas_bundle.py tests/test_canvas_projection.py tests/test_canvas_svg.py -q
uv run python -m ruff check viz_canvas/bundle.py viz_canvas/svg.py tests/test_canvas_bundle.py
```

- [ ] **Step 5: Review, checkpoint, and commit**

```bash
git add viz_canvas/bundle.py viz_canvas/svg.py viz_canvas/__init__.py tests/test_canvas_bundle.py
git commit -m "feat: publish atomic polygon design bundles"
```

---

### Task 8: Generic CLI and Twenty-Surface Example

**Files:**
- Create: `scripts/generate_domain_bundle.py`
- Create: `tests/test_generate_domain_bundle.py`
- Create: `examples/domain-jobs/cootie-catcher.json`
- Modify: `CANVAS.md`

**Interfaces:**
- Produces CLI: `python scripts/generate_domain_bundle.py JOB.json --output-dir PATH [--overwrite]`.
- Registers: `concentric-points` through `ConcentricDomainAlgorithm`.
- Consumes: a versioned job JSON and publishes one atomic bundle.

- [ ] **Step 1: Write failing CLI and example tests**

```python
def test_cli_generates_one_to_many_bundle(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_domain_bundle.py",
            "examples/domain-jobs/cootie-catcher.json",
            "--output-dir",
            str(tmp_path / "cootie"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert len(list((tmp_path / "cootie" / "surfaces").glob("*.svg"))) == 20
```

Validate that the example contains exactly four square outer domains, eight selector triangles, and eight reveal triangles; contains explicit selector/reveal correspondence relations; has no sheet dimensions or physical placement coordinates; and exports surface IDs in semantic order.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run python -m pytest tests/test_generate_domain_bundle.py -q
```

- [ ] **Step 3: Implement the CLI and example**

The CLI reads the job, refuses an existing destination unless `--overwrite` is present, executes the registered algorithms, writes the bundle, and prints the three canonical output locations. It does not import `plotter-workflow` or invoke imposition.

The example uses local `100 x 100` squares and right triangles `[[0, 0], [100, 0], [0, 100]]`, stable semantic IDs `outer-1..4`, `selector-1..8`, and `reveal-1..8`, plus eight `corresponds_to` relations between paired selector and reveal domains. Give each domain one independent `concentric-points` pass with one logical layer and these exact parameters: `point_count=2`, `ring_count=3`, `ring_spacing="linear"`, `boundary_mode="clip"`, `radius_scale=0.65`, `overlap_mode="allow"`, and `coordinate_frame="domain"`. Defaults supply the remaining validated concentric options; the runner removes `coordinate_frame` before constructing `ConcentricPointsRequest`.

- [ ] **Step 4: Verify CLI, full suite, and Ruff**

```bash
uv run python -m pytest tests/test_generate_domain_bundle.py -q
uv run python -m pytest
uv run python -m ruff check .
```

- [ ] **Step 5: Review specification coverage and documentation**

Run the example twice into separate temporary directories and compare normalized `design.json`, `design.svg`, and all twenty projection digests. Confirm `CANVAS.md` documents Git Bash commands and the handoff to a separate `cootie.json` placement manifest.

- [ ] **Step 6: Request final code review and show checkpoint**

Report files changed, focused/full tests, Ruff, deterministic comparison, deviations, and proposed commit. Resolve every Critical or Important finding before proceeding.

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_domain_bundle.py tests/test_generate_domain_bundle.py examples/domain-jobs/cootie-catcher.json CANVAS.md
git commit -m "feat: generate arbitrary polygon design bundles"
```

---

## Final Acceptance Verification

- [ ] Run the complete suite:

```bash
uv run python -m pytest
```

- [ ] Run Ruff:

```bash
uv run python -m ruff check .
```

- [ ] Run whitespace and repository checks without staging the user's unrelated documentation change:

```bash
git diff --check
git status --short
git log -10 --oneline
```

- [ ] Generate the twenty-surface example and inspect:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/cootie-catcher.json \
  --output-dir output/cootie-design-bundle \
  --overwrite
```

- [ ] Confirm the bundle contains one audit JSON, one canonical multi-domain SVG, and twenty intrinsic surface SVGs in the approved semantic order.
- [ ] Confirm the bundle contains no physical sheet size, slot polygon, physical rotation, pen assignment, HP-GL, or transport data.
- [ ] Confirm the existing cootie-catcher imposition can consume a separately authored manifest pointing to the twenty generated surface SVGs without changing `cootie_impose.py`.
- [ ] Request final independent review against the architecture specification.
- [ ] Show the final checkpoint before any integration action.
