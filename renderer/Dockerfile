# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

# py5 requires a non-headless Java 17+ runtime; Java 21 is preferred by the
# current py5 documentation. Xvfb supplies a virtual display in the container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-21-jre \
        xvfb \
        xauth \
        libgl1 \
        libxi6 \
        libxrender1 \
        libxtst6 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY renderer/pyproject.toml renderer/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package viz-renderer --no-dev

COPY renderer/ renderer/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package viz-renderer --no-dev

WORKDIR /app/renderer
EXPOSE 5700

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5700/health', timeout=2)"]

CMD ["xvfb-run", "-a", "/app/.venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5700"]
