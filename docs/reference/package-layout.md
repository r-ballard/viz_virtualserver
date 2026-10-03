# Python package layout and compatibility

HAR-39 makes `viz_virtualserver` the canonical installed package. Its source tree has four responsibilities:

```text
viz_virtualserver/
  canvas/                 domain, semantics, rendering, and bundle contracts
  generators/             concentric, radial tiles, Voronoi cells, and L-systems
  legacy/                 older geometry handlers used by HTTP routes
  cli/domain_bundle.py    versioned domain-job command
  server.py               FastAPI application
```

The wheel contains this namespace and compatibility packages for the previous imports: `viz_canvas`, `concentric`, `lsystem`, `radial_tiles`, and `voronoi_cells`. Each compatibility package points its submodules at the canonical module object. Existing imports and monkeypatches therefore use the same classes and functions. New code should import from `viz_virtualserver`.

The supported installed command is `viz-domain-bundle`. The repository path `python scripts/generate_domain_bundle.py` remains available and calls the same implementation. `server:app` remains an importable source-checkout alias; Docker starts `viz_virtualserver.server:app`. The HTTP route paths and versioned JSON/bundle formats did not change.

From the repository root:

```bash
uv sync --locked --all-packages --dev
uv run --locked viz-domain-bundle examples/domain-jobs/voronoi-three-polygons.json --output-dir output/voronoi-three-polygons
```

The build declares the canonical package and compatibility packages explicitly in `pyproject.toml`. The aliases are a migration surface: remove one only after checking downstream callers and documenting a deprecation period. Root-level `server.py` and geometry-handler files are source-checkout shims; the installed package uses `viz_virtualserver.server` and `viz_virtualserver.legacy`.
