# Runtime modernization

This change establishes a Python 3.12 + uv workspace and two containerized services without modifying the legacy application source files.

## Components

- `compute`: existing FastAPI application (`server:app`) on port `5699`
- `renderer`: Python 3 / py5 rendering service on port `5700`
- one root `uv.lock` shared by the workspace

## Bootstrap

From the repository root:

```bash
uv python pin 3.12
uv lock
uv sync --all-packages --dev
```

Commit `uv.lock`. The container builds intentionally require the committed lockfile.

## Run

```bash
docker compose build
docker compose up
```

Check the compute service:

```bash
curl http://localhost:5699/
```

Check the renderer service:

```bash
curl http://localhost:5700/health
```

Exercise the actual py5/Processing runtime:

```bash
docker compose run --rm renderer \
  xvfb-run -a /app/.venv/bin/python smoke_sketch.py
```

## Why this patch is additive

The first modernization pass intentionally does not edit `server.py`, `polygon_handlers.py`, or `voronoi_handlers.py`. Runtime/deprecation cleanup and L-system endpoints should be separate commits so infrastructure changes do not conflict with local changes in the legacy geometry code.
