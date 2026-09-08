# Generate artwork for arbitrary polygon sets

This guide takes you from a JSON job to a placement-free design bundle containing
one SVG per polygon surface. It is written for Windows with Git Bash and `uv`.
A Docker alternative is included near the end.

Stop after this guide if your next step is physical imposition. Sheet size, slot
placement, rotation, pens, HP-GL conversion, and plotter transport belong to
`plotter_workflow`, not to the polygon artwork job.

## What you will produce

The tutorial job contains three independent design domains:

- `square`, with four ordered vertices;
- `triangle`, with its apex at vertex 0; and
- `pentagon`, an irregular convex five-vertex polygon.

Running the job creates:

```text
output/three-polygons/
├── design.json
├── design.svg
└── surfaces/
    ├── pentagon.svg
    ├── square.svg
    └── triangle.svg
```

`design.svg` is the canonical combined design. Files under `surfaces/` are the
placement-free inputs for an imposition workflow. `design.json` is the audit
record: it identifies the validated job, passes, derived geometry, output files,
and SHA-256 digests.

## Prerequisites

Install:

- Git for Windows, including Git Bash;
- Python 3.12; and
- `uv`.

Open Git Bash and change to the repository root. Replace the example path below
with the location of your own clone. In Git Bash, a Windows path such as
`C:\path\to\viz_virtualserver` is written as `/c/path/to/viz_virtualserver`:

```bash
cd /c/path/to/viz_virtualserver
```

Confirm that you are in the correct directory:

```bash
pwd
test -f pyproject.toml
test -f scripts/generate_domain_bundle.py
```

The two `test` commands are silent on success. If either command reports an
error or returns to the prompt with a nonzero status, correct the repository
path before continuing.

Install the locked project and development dependencies:

```bash
uv sync --locked --all-packages
```

## Generate the three-polygon bundle

The ready-to-run tutorial job is
`examples/domain-jobs/three-polygons.json`. Generate it with:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/three-polygons.json \
  --output-dir output/three-polygons
```

On success, the command prints absolute paths for `design.json`, `design.svg`,
and `surfaces`. It exits nonzero and prints an `error:` message if validation or
publication fails.

Verify the bundle without requiring extra command-line tools:

```bash
test -f output/three-polygons/design.json
test -f output/three-polygons/design.svg
test -f output/three-polygons/surfaces/square.svg
test -f output/three-polygons/surfaces/triangle.svg
test -f output/three-polygons/surfaces/pentagon.svg
find output/three-polygons/surfaces -maxdepth 1 -type f -name '*.svg' | sort
```

The final command must print exactly these three paths:

```text
output/three-polygons/surfaces/pentagon.svg
output/three-polygons/surfaces/square.svg
output/three-polygons/surfaces/triangle.svg
```

Open the SVGs in a browser or vector editor for a visual check. Artwork must be
clipped to each polygon. The SVG coordinates are design coordinates; they do not
describe a paper location.

## Understand the job

Open `examples/domain-jobs/three-polygons.json` in an editor. Its top-level
sections are evaluated in this order:

1. `schema_version` selects the strict version-1 job format.
2. `seed` makes seeded generation reproducible.
3. `domains` defines ordered polygon geometry.
4. `surfaces` names the independently exported designs.
5. `groups` and `relations` add optional semantic context.
6. `composition_transforms` is empty because this example generates each design
   in its own local domain coordinates.
7. `passes` selects an algorithm and parameters for each target domain.

### Domains and vertex order

A domain is a simple polygon expressed as ordered `[x, y]` pairs. The closing
edge from the last vertex back to vertex 0 is implicit. Do not repeat the first
vertex at the end.

```json
{"id": "triangle", "vertices": [[50, 0], [100, 100], [0, 100]]}
```

Vertex order is stable and meaningful. `vertex:0` is `[50, 0]`, and `edge:0`
runs from vertex 0 to vertex 1. Clockwise and counterclockwise polygons are both
legal, but the loader never reorders them. A domain must have at least three
finite vertices, nonzero edges and area, and no self-intersection.

The units are arbitrary design units. A 100-by-100 domain is not automatically
100 mm. Physical scale is chosen later by the imposition workflow.

### Surfaces

Each surface points to exactly one domain:

```json
{"id": "triangle", "domain_id": "triangle"}
```

Surface order controls the audit and export order. Surface IDs also determine
safe filenames. Keep IDs short and stable; IDs that collide after filename
sanitization are rejected.

If `surfaces` is omitted, the system creates one surface per source domain in
domain order and reuses each domain ID as its surface ID. An explicitly empty
`surfaces` array is invalid.

### Groups and relations

The `teaching-set` group provides an ordered semantic collection. It does not
merge its polygons or place them beside one another. The
`triangle-to-pentagon` relation says that their vertex-0 features correspond;
it does not infer a transform or alter either shape.

Groups and relations are optional. Declare them only when an algorithm needs
that semantic context.

### Passes and algorithms

Each pass independently targets one domain:

```json
{
  "id": "draw-triangle",
  "algorithm": "concentric-points",
  "target_domain_ids": ["triangle"],
  "parameters": {
    "point_count": 2,
    "ring_count": 3,
    "ring_spacing": "linear",
    "boundary_mode": "clip",
    "radius_scale": 0.65,
    "overlap_mode": "allow",
    "coordinate_frame": "domain"
  },
  "logical_layers": [{"id": "artwork", "label": "Artwork"}]
}
```

The command-line registry currently exposes `concentric-points`. Unknown
algorithm names fail before a bundle is published. Its principal controls are:

- `point_count`: number of seeded centers in each target;
- `ring_count`: rings generated around each center;
- `ring_spacing`: `linear`, `random`, or `progressive`;
- `boundary_mode`: use `clip` to retain only drawable geometry inside the
  polygon;
- `radius_scale`: scales ring radii relative to available boundary distance;
- `overlap_mode`: controls whether generated rings may overlap; and
- `coordinate_frame`: `domain` for independent local generation or
  `composition` for coordinated generation using explicit transforms.

Logical layers express artwork intent. They are not plotter pen numbers.
Physical pen assignment happens after imposition.

## Regenerate intentionally

Publication refuses to replace an existing destination by default. Repeating
the first command should fail with an `output destination already exists`
message, leaving the original bundle untouched.

When replacement is intentional, run:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/three-polygons.json \
  --output-dir output/three-polygons \
  --overwrite
```

The replacement is staged and verified before publication. Do not use
`--overwrite` reflexively: a different output directory is safer when comparing
design variants.

## Confirm deterministic output

Generate two independent bundles:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/three-polygons.json \
  --output-dir output/three-polygons-a

uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/three-polygons.json \
  --output-dir output/three-polygons-b

diff -r output/three-polygons-a output/three-polygons-b
```

`diff` must print nothing and return success. If it reports a difference, first
confirm that both commands used the same job file and committed software
revision.

## Make your own polygon set

Copy the tutorial job instead of editing the known-good example:

```bash
cp examples/domain-jobs/three-polygons.json examples/domain-jobs/my-polygons.json
```

Then edit `my-polygons.json`:

1. Change a domain ID and its ordered vertices.
2. Make the matching `surfaces[].domain_id` and pass target use that same ID.
3. Give every domain, surface, group, relation, and pass a unique ID.
4. Remove or update group and relation references that no longer exist.
5. Change the top-level seed or pass parameters to create a variant.
6. Write to a new output directory while comparing results.

Generate the edited job:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/my-polygons.json \
  --output-dir output/my-polygons
```

The generic workflow supports one or many simple polygon domains, including
concave domains when the selected algorithm declares that capability. The CLI's
currently registered `concentric-points` algorithm supports convex polygons
only. Keep polygons convex in this tutorial and in edited jobs that continue to
use `concentric-points`. Each declared surface produces one surface SVG,
including a valid surface whose algorithm emits no paths.

## Generate the 20-surface cootie-catcher artwork

The same command runs the larger placement-free example:

```bash
uv run python scripts/generate_domain_bundle.py \
  examples/domain-jobs/cootie-catcher.json \
  --output-dir output/cootie-design-bundle
```

Verify the surface count:

```bash
find output/cootie-design-bundle/surfaces -maxdepth 1 -type f -name '*.svg' | wc -l
```

The result must be `20`: four `outer-*`, eight `selector-*`, and eight
`reveal-*` SVGs. These files are ready for semantic slot mapping in
`plotter_workflow`; they are not yet imposed on a sheet.

## Docker alternative

Start Docker Desktop and wait until its Linux engine reports that it is
running. The repository's container normally runs the HTTP service. To run this
filesystem-producing CLI in the same dependency environment while keeping the
bundle on the host, mount the checkout as `/workspace`:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "$PWD:/workspace" \
  -w /workspace \
  compute \
  /app/.venv/bin/python scripts/generate_domain_bundle.py \
  examples/domain-jobs/three-polygons.json \
  --output-dir output/three-polygons-docker
```

`MSYS_NO_PATHCONV=1` prevents Git Bash from rewriting Linux container paths.
Docker may build the `compute` image the first time. The output directory is
created in the host checkout because `/workspace` is a bind mount.

Use `uv` for ordinary editing and repeated CLI runs. Use Docker when you need
the repository's containerized dependency boundary or want to reproduce its
Linux runtime.

## Troubleshooting

### `output destination already exists`

Choose a new output directory, remove or archive the old bundle yourself, or
add `--overwrite` only when replacement is intended.

### `unknown algorithm`

The job's `algorithm` value is not registered by
`scripts/generate_domain_bundle.py`. Use `concentric-points`, or implement and
register another domain algorithm before referencing it in JSON.

### Validation error mentioning an unknown field

The version-1 job schema is strict. Check spelling and move physical placement,
rotation, pen, HP-GL, and transport settings into `plotter_workflow`.

### Invalid polygon, edge, or intersection

Check that the polygon has at least three finite points, that adjacent vertices
are different, that the area is nonzero, and that non-adjacent edges do not
cross. Do not duplicate the first vertex at the end.

### `algorithm does not support concave domains`

The polygon is structurally valid but concave, and `concentric-points` declares
convex-only support. Move every inward vertex outward until the polygon is
convex, or implement and register an algorithm whose capabilities explicitly
include concave polygons. Changing only the schema or suppressing validation is
not a valid remedy.

### Invalid semantic reference

Confirm that every surface, group member, relation endpoint, pass target, and
context ID refers to an object declared in the same job. Feature indices are
zero-based and must exist on the referenced polygon.

### Composition-frame error

A composition-frame pass requires an explicit invertible transform for every
source target. Derived domains are domain-local in schema version 1 and cannot
be targeted by composition-frame passes. Use domain-frame generation unless
the algorithm truly coordinates geometry across multiple placed domains.

### Git Bash reports `command not found` for an SVG or HP-GL file

The shell is trying to execute an output file. Pass the file as an argument to
the documented Python command. Use a trailing backslash (`\`) for Git Bash line
continuation; PowerShell's backtick is not valid Git Bash continuation syntax.

### Docker cannot connect to `dockerDesktopLinuxEngine`

Docker Desktop is not running or its Linux engine is not ready. Start Docker
Desktop, wait for the engine-ready indication, and repeat the command. No bundle
is published when the container never starts.

## Reference

See [`CANVAS.md`](../../CANVAS.md) for the complete geometry, job-schema, frame,
SVG metadata, audit, and repository-boundary contracts.
