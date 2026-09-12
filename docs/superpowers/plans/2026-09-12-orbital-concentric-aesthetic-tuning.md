# Orbital-Concentric Aesthetic Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish reproducible orbital-concentric presets, select a visually effective plotter-safe treatment, and validate it across polygon surfaces and the cootie-catcher workflow.

**Architecture:** Keep `OrbitalConcentricDomainAlgorithm` parameter-driven and unchanged unless the tuning exercise exposes a missing control or defect. Add a small deterministic preview-matrix script that creates ordinary versioned job files and invokes the existing bundle pipeline; selected presets remain readable JSON examples rather than hidden code constants. Complete software acceptance in `viz_virtualserver`, then defer physical imposition and plotting to `plotter-workflow` at the available plotter workstation.

**Tech Stack:** Python 3.12, Pydantic, pytest, Ruff, `viz_canvas` domain jobs and SVG bundle exporter, Inkscape for visual inspection, `plotter-workflow` for later HP-GL acceptance.

**Spec:** `ORBITAL_CONCENTRIC.md`

## Global Constraints

- Preserve `concentric-points` behavior and its one-layer HTTP/SVG compatibility surface.
- Preserve the ordered `orbits`, `primary-bodies`, `accent-bodies` logical-layer contract.
- All generated variants must be deterministic from committed job inputs and seeds.
- Keep artwork in domain coordinates; physical placement, scaling, pen assignment, and transport remain in `plotter-workflow`.
- Support arbitrary 1:n convex simple-polygon sets without embedding cootie-catcher placement in the algorithm.
- Use strict task-by-task TDD for scripts, validation, and behavior changes.
- Do not alter algorithm behavior solely to make one selected preview look better; expose a reusable parameter only when existing controls cannot express the desired result.

---

### Task 1: Deterministic Tuning Matrix

**Files:**
- Create: `scripts/generate_orbital_tuning_matrix.py`
- Create: `examples/domain-jobs/orbital-concentric-tuning-base.json`
- Test: `tests/test_generate_orbital_tuning_matrix.py`

**Interfaces:**
- Consumes: a versioned `DomainArtworkJob` JSON containing one square, one triangle, and one pentagon plus an `orbital-concentric` pass.
- Produces: `generate_matrix(base_job: Path, output_root: Path) -> tuple[Path, ...]`, with one named directory per deterministic parameter variant and a `matrix.json` manifest containing names, seeds, parameters, and bundle paths.

- [ ] **Step 1: Write the failing manifest test**

```python
def test_matrix_generates_named_deterministic_variants(tmp_path: Path) -> None:
    outputs = generate_matrix(BASE_JOB, tmp_path / "matrix")
    assert [path.name for path in outputs] == [
        "density-low", "density-medium", "density-high",
        "eccentricity-circular", "eccentricity-subtle", "eccentricity-varied",
    ]
    manifest = json.loads((tmp_path / "matrix" / "matrix.json").read_text())
    assert [item["name"] for item in manifest["variants"]] == [path.name for path in outputs]
```

- [ ] **Step 2: Run the focused test and confirm it fails because the module is absent**

Run: `uv run pytest tests/test_generate_orbital_tuning_matrix.py -q --basetemp=.test-tmp`

Expected: collection fails with `ModuleNotFoundError: scripts.generate_orbital_tuning_matrix`.

- [ ] **Step 3: Implement the six explicit variants**

Use these literal parameter deltas over the committed base job:

```python
VARIANTS = {
    "density-low": {"orbit_count": 5},
    "density-medium": {"orbit_count": 8},
    "density-high": {"orbit_count": 12},
    "eccentricity-circular": {"orbit_eccentricity": 0.0, "orbit_eccentricity_variation": 0.0},
    "eccentricity-subtle": {"orbit_eccentricity": 0.18, "orbit_eccentricity_variation": 0.06},
    "eccentricity-varied": {"orbit_eccentricity": 0.32, "orbit_eccentricity_variation": 0.22},
}
```

Load and validate each derived job through `read_domain_artwork_job`; execute it with the same registry used by `scripts/generate_domain_bundle.py`; publish with `write_design_bundle`. Refuse an existing output root unless `--overwrite` is passed.

- [ ] **Step 4: Add byte-determinism and no-overwrite tests**

Generate into two fresh roots and assert matching SHA-256 digests for corresponding SVGs and manifests. Create a sentinel in an existing destination and assert the default invocation leaves it unchanged.

- [ ] **Step 5: Run focused tests and Ruff**

Run: `uv run pytest tests/test_generate_orbital_tuning_matrix.py -q --basetemp=.test-tmp`

Run: `uv run ruff check scripts/generate_orbital_tuning_matrix.py tests/test_generate_orbital_tuning_matrix.py`

- [ ] **Step 6: Review and commit**

Verify the matrix uses the generic job runner and does not duplicate geometry generation.

Commit: `feat: add orbital tuning matrix`

---

### Task 2: Select Orbit Density and Ellipse Presets

**Files:**
- Create: `examples/domain-jobs/orbital-concentric-circular.json`
- Create: `examples/domain-jobs/orbital-concentric-elliptical.json`
- Modify: `ORBITAL_CONCENTRIC.md`
- Test: `tests/test_generate_domain_bundle.py`

**Interfaces:**
- Consumes: Task 1 density and eccentricity preview bundles plus Inkscape inspection notes.
- Produces: two complete, directly runnable job examples named `circular` and `elliptical`; neither is a code-level default.

- [ ] **Step 1: Generate the Task 1 matrix and inspect every surface in Inkscape**

Record the selected `orbit_count`, `orbit_eccentricity`, `orbit_eccentricity_variation`, `orbit_rotation`, and `orbit_rotation_variation` values for both presets. Reject variants whose paths are indistinguishable at the intended 1/20-sheet polygon size.

- [ ] **Step 2: Write failing example-contract tests**

```python
@pytest.mark.parametrize("example", [CIRCULAR_EXAMPLE, ELLIPTICAL_EXAMPLE])
def test_orbital_preset_generates_three_surfaces_and_layers(example: Path, tmp_path: Path) -> None:
    result = _run_cli(tmp_path / example.stem, job=example)
    assert result.returncode == 0, result.stderr
    svg = (tmp_path / example.stem / "surfaces" / "triangle.svg").read_text()
    assert all(f'id="{layer}"' in svg for layer in ("orbits", "primary-bodies", "accent-bodies"))
```

- [ ] **Step 3: Run the tests and confirm the examples are missing**

Run: `uv run pytest tests/test_generate_domain_bundle.py -k orbital_preset -q --basetemp=.test-tmp`

- [ ] **Step 4: Add the selected complete jobs and document their intent**

Keep seed `20260912`, the square/triangle/pentagon domains, and all parameters explicit. Explain that presets are starting points and list the exact command for each.

- [ ] **Step 5: Run focused tests, Ruff, and review**

Run: `uv run pytest tests/test_generate_domain_bundle.py -k 'orbital_preset or orbital_example' -q --basetemp=.test-tmp`

Run: `uv run ruff check tests/test_generate_domain_bundle.py`

Commit: `docs: add orbital diagram presets`

---

### Task 3: Tune Bodies, Accents, and Orbit Gaps

**Files:**
- Modify: `scripts/generate_orbital_tuning_matrix.py`
- Modify: `examples/domain-jobs/orbital-concentric-circular.json`
- Modify: `examples/domain-jobs/orbital-concentric-elliptical.json`
- Modify: `ORBITAL_CONCENTRIC.md`
- Test: `tests/test_generate_orbital_tuning_matrix.py`

**Interfaces:**
- Consumes: the two selected orbit presets from Task 2.
- Produces: comparable `bodies-sparse`, `bodies-clustered`, `accents-low`, `accents-high`, `gaps-tight`, and `gaps-generous` variants, followed by final explicit values in both presets.

- [ ] **Step 1: Write a failing test for the six additional named variants**

Assert the manifest contains these literal deltas:

```python
{
    "bodies-sparse": {"bodies_per_orbit_range": [0, 2], "body_radius_range": [0.8, 1.8]},
    "bodies-clustered": {"bodies_per_orbit_range": [2, 5], "minimum_body_separation": 0.0},
    "accents-low": {"accent_probability": 0.1},
    "accents-high": {"accent_probability": 0.35},
    "gaps-tight": {"gap_clearance": 0.35},
    "gaps-generous": {"gap_clearance": 1.25},
}
```

- [ ] **Step 2: Run the focused test and confirm the new variants are absent**

Run: `uv run pytest tests/test_generate_orbital_tuning_matrix.py -q --basetemp=.test-tmp`

- [ ] **Step 3: Add the variants without changing algorithm defaults**

Preserve stable manifest order and deterministic seeds. Generate the full matrix for both Task 2 base presets.

- [ ] **Step 4: Inspect at final physical scale and update preset JSON**

Choose body radii that remain distinct with the intended pen, an accent probability that visibly populates the third layer, and the smallest clearance that prevents orbit lines from touching body circles. Put exact chosen values in both job examples and in the documentation.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_generate_orbital_tuning_matrix.py tests/test_generate_domain_bundle.py -q --basetemp=.test-tmp`

Run: `uv run ruff check .`

Commit: `refactor: tune orbital diagram presets`

---

### Task 4: Cootie-Catcher Software Acceptance

**Files:**
- Create: `examples/domain-jobs/cootie-catcher-orbital.json`
- Modify: `ORBITAL_CONCENTRIC.md`
- Test: `tests/test_generate_domain_bundle.py`

**Interfaces:**
- Consumes: the existing twenty semantic cootie-catcher domains and one selected Task 3 preset.
- Produces: twenty independently seeded, placement-free orbital surface SVGs and a canonical combined SVG/audit bundle.

- [ ] **Step 1: Write the failing twenty-surface acceptance test**

Clone the established semantic ID assertion from the concentric cootie-catcher example, then additionally assert every surface contains at least one `orbits` path and one `primary-bodies` path and that all paths retain the owning domain ID.

- [ ] **Step 2: Run the focused test and confirm the orbital job is absent**

Run: `uv run pytest tests/test_generate_domain_bundle.py -k cootie_catcher_orbital -q --basetemp=.test-tmp`

- [ ] **Step 3: Add the placement-free twenty-domain job**

Reuse the existing four square and sixteen triangular domain definitions and selector/reveal relations. Change only the algorithm, its explicit selected parameters, and its three logical layers. Keep `composition_transforms` empty.

- [ ] **Step 4: Generate twice and verify deterministic audit/SVG digests**

Run both bundles into fresh directories and compare `design.json`, `design.svg`, and all twenty surface SVG SHA-256 digests.

- [ ] **Step 5: Run full software verification and request review**

Run: `uv run pytest -q --basetemp=.test-tmp`

Run: `uv run ruff check .`

Run: `git diff --check`

Commit: `feat: add cootie catcher orbital artwork example`

---

### Task 5: Deferred Plotter Acceptance

**Files:**
- No `viz_virtualserver` source change is expected.
- Record results in the relevant Linear issue and, if commands or behavior differ from the guide, update the corresponding `plotter-workflow` documentation in its own repository and pull request.

**Interfaces:**
- Consumes: the accepted twenty-surface bundle from Task 4.
- Produces: an imposed SVG, preserved three-pen plan, HP-GL output, preflight report, and one physical proof sheet.

- [ ] **Step 1: At the plotter workstation, follow the plotter workflow guide exactly**

Impose the twenty surfaces using the approved cootie-catcher template. Map `orbits`, `primary-bodies`, and `accent-bodies` to three explicitly documented pen slots.

- [ ] **Step 2: Convert and preflight without sending to the device**

Use the generated pen-plan file as authoritative; do not combine it with `--pen-policy` or `--pen-map`. Confirm page size, orientation, paper origin, coordinate bounds, path counts, and pen sequence in the report.

- [ ] **Step 3: Plot one proof sheet**

Confirm pen acquisition, orbit/body separation, smallest body legibility, polygon clipping, fold-safe placement, and absence of visible unintended seams.

- [ ] **Step 4: Record acceptance**

Attach the preflight report and proof-sheet observations to Linear. Open narrowly scoped defects for any failed criterion; do not fold plotter transport fixes into the artwork branch.
