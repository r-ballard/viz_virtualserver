# viz_virtualserver

Python geometry producers for generative artwork. A versioned polygon-domain job creates a placement-free design bundle with `design.json`, `design.svg`, and one SVG per surface. The separate plotter workflow handles paper placement, pens, HP-GL, and transport.

## Start here

| Goal | Entrypoint |
| --- | --- |
| Generate a polygon design bundle | `viz-domain-bundle` and [the operator guide](docs/how-to/generate-polygon-artwork.md) |
| Understand the job and geometry contract | [Polygon canvas reference](docs/reference/canvas.md) |
| Use the HTTP endpoints | `viz_virtualserver/server.py` and the algorithm guides below |
| Run the py5 renderer service | `renderer/` and [runtime setup](docs/reference/runtime-modernization.md) |

From the repository root, with Python 3.12 and `uv` installed:

```bash
uv sync --locked --all-packages --dev
uv run --locked viz-domain-bundle \
  examples/domain-jobs/voronoi-three-polygons.json \
  --output-dir output/voronoi-three-polygons
```

Inspect `output/voronoi-three-polygons/design.svg` and the individual SVGs under `surfaces/`. Choose a different job in `examples/domain-jobs/` to try another algorithm.

## Algorithms

| Algorithm | Guide | Example jobs |
| --- | --- | --- |
| Recursive Voronoi cells | [Voronoi cells](docs/how-to/voronoi-cells.md) | `examples/domain-jobs/voronoi-three-polygons.json` |
| Radial tiles | [Radial tiles](docs/algorithms/radial-tiles.md) | `examples/domain-jobs/radial-tiles-three-polygons.json` |
| Orbital concentric | [Orbital concentric](docs/algorithms/orbital-concentric.md) | `examples/domain-jobs/orbital-concentric-*.json` |
| Concentric points | [Concentric points](docs/algorithms/concentric-points.md) | `examples/concentric/` and `examples/domain-jobs/three-polygons.json` |
| L-systems | [L-systems](docs/algorithms/lsystem.md) and [lineage layers](docs/algorithms/lsystem-lineage.md) | `examples/lsystems/` |

The domain-bundle runner registers algorithms in `viz_virtualserver/cli/domain_bundle.py`. Generator implementations live under `viz_virtualserver/generators/`; the shared domain and bundle contract lives in `viz_virtualserver/canvas/`. The older handler algorithms live under `viz_virtualserver/legacy/` for HTTP compatibility. Previous import paths and the repository script path still work through compatibility shims. See the [package layout reference](docs/reference/package-layout.md).

See the [documentation index](docs/README.md) for references, gallery files, and development plans.
