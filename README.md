# viz_virtualserver

Generate vector artwork from versioned polygon-domain jobs, or run the geometry
and py5 renderer services. A bundle contains `design.json`, `design.svg`, and
one SVG per surface. The separate
[`plotter-workflow`](https://github.com/r-ballard/plotter-workflow) repository
handles paper placement, pens, HP-GL conversion, and plotter transport.

## Redeploy locally

Install Python 3.12 and `uv`. From this repository's root:

```powershell
uv python install 3.12
uv sync --locked --all-packages --dev
uv run --locked viz-domain-bundle --help
```

`viz_virtualserver` is the only installed Python package. Import from
`viz_virtualserver.canvas`, `viz_virtualserver.generators`, or
`viz_virtualserver.server`; the old root import aliases and
`scripts/generate_domain_bundle.py` have been removed.

Generate a checked-in example and inspect its SVGs:

```powershell
uv run --locked viz-domain-bundle examples/domain-jobs/voronoi-three-polygons.json --output-dir output/voronoi-three-polygons
```

Choose another job from `examples/domain-jobs/` for a different algorithm.
Generated bundles belong in `output/` or another chosen directory and are
ignored by Git.

## Run the services

With Docker Desktop's Linux engine running:

```powershell
docker compose build
docker compose up -d
Invoke-WebRequest http://localhost:5699/
Invoke-WebRequest http://localhost:5700/health
```

`compute` serves the FastAPI geometry endpoints on port 5699;
`renderer` serves the py5 runtime on port 5700. Stop them with
`docker compose down`. The [runtime guide](docs/reference/runtime-modernization.md)
includes a renderer smoke check. The HTTP route paths and versioned bundle
formats remain stable across the package cleanup.

## Algorithms and documentation

| Algorithm | Guide | Example jobs |
| --- | --- | --- |
| Synthetic topographic contours | [Topographic artwork](docs/algorithms/topographic.md) | `examples/domain-jobs/topographic-tuning.json` |
| Recursive Voronoi cells | [Voronoi cells](docs/how-to/voronoi-cells.md) | `examples/domain-jobs/voronoi-three-polygons.json` |
| Radial tiles | [Radial tiles](docs/algorithms/radial-tiles.md) | `examples/domain-jobs/radial-tiles-three-polygons.json` |
| Truchet grammar and multi-scale curves | [Truchet tiles](docs/algorithms/truchet.md) | `examples/domain-jobs/truchet-*.json` |
| Orbital concentric | [Orbital concentric](docs/algorithms/orbital-concentric.md) | `examples/domain-jobs/orbital-concentric-*.json` |
| Concentric points | [Concentric points](docs/algorithms/concentric-points.md) | `examples/concentric/` |
| L-systems | [L-systems](docs/algorithms/lsystem.md) | `examples/lsystems/` |

The [operator guide](docs/how-to/generate-polygon-artwork.md) explains the job
format and bundle handoff. The [documentation map](docs/README.md) links the
canvas contract, package layout, gallery, and other references.

## Verify a redeployment

```powershell
uv run --locked python -m pytest -q
uv run --locked ruff check .
```
