from importlib.metadata import version

from fastapi import FastAPI

app = FastAPI(title="viz renderer", version="0.1.0")


@app.get("/")
async def default() -> dict[str, str]:
    return {"service": "viz-renderer", "backend": "py5"}


@app.get("/health")
async def health() -> dict[str, str]:
    # This verifies the locked py5 installation without starting the JVM.
    return {"status": "ok", "renderer": "py5", "py5": version("py5")}
