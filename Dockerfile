# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# The repository is a uv workspace. Generate and commit uv.lock before building.
COPY pyproject.toml uv.lock README.md ./
COPY renderer/pyproject.toml renderer/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package viz-virtualserver --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package viz-virtualserver --no-dev

EXPOSE 5699

# The legacy application already exposes GET /, so the infrastructure patch
# does not need to modify server.py just to add a health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5699/', timeout=2)"]

CMD ["/app/.venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5699"]
