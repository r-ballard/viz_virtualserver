# Runtime setup

The repository uses a Python 3.12 `uv` workspace and two containerized services.

## Components

- `compute`: FastAPI application (`viz_virtualserver.server:app`) on port `5699`
- `renderer`: Python 3 / py5 rendering service on port `5700`
- one root `uv.lock` shared by the workspace

## Bootstrap

From the repository root:

```bash
uv python install 3.12
uv sync --locked --all-packages --dev
```

The container builds use the committed `uv.lock`.

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
