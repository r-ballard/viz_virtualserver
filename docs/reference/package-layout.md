# Python package layout

`viz_virtualserver` is the installed package. Its source tree has five responsibilities:

```text
viz_virtualserver/
  canvas/                 domain, semantics, rendering, and bundle contracts
  generators/             concentric, radial tiles, Voronoi cells, and L-systems
  legacy/                 older geometry handlers used by HTTP routes
  cli/domain_bundle.py    versioned domain-job command
  server.py               FastAPI application
```

The wheel contains only `viz_virtualserver`. Import canvas contracts from `viz_virtualserver.canvas`, algorithms from `viz_virtualserver.generators`, and the application from `viz_virtualserver.server`.

The installed command is `viz-domain-bundle`. Docker starts `viz_virtualserver.server:app`. The HTTP route paths and versioned JSON/bundle formats did not change.

From the repository root:

```bash
uv sync --locked --all-packages --dev
uv run --locked viz-domain-bundle examples/domain-jobs/voronoi-three-polygons.json --output-dir output/voronoi-three-polygons
```

The build declares the canonical package in `pyproject.toml`. Root-level import and CLI shims have been removed. The `legacy/` directory contains the implementation of established HTTP endpoints; it is part of the canonical package.
