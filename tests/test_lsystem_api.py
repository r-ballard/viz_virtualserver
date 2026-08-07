from fastapi import FastAPI
from fastapi.testclient import TestClient

from lsystem.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_lsystem_endpoint_returns_geometry():
    response = client.post(
        "/LSystem",
        json={
            "axiom": "F",
            "rules": {"F": "FF"},
            "generations": 2,
            "step": 1,
            "angle": 90,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_segments"] == 7
    assert payload["layers"][2]["generations"][0]["segment_count"] == 4


def test_lsystem_svg_endpoint_returns_svg():
    response = client.post(
        "/LSystemSvg",
        json={"axiom": "F", "rules": {"F": "F+F"}, "generations": 1, "angle": 90},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert '<g id="pen-1"' in response.text
