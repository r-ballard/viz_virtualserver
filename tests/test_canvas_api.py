import xml.etree.ElementTree as ET

from fastapi import FastAPI
from fastapi.testclient import TestClient

from viz_canvas.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_canvas_endpoint_returns_resolved_geometry() -> None:
    response = client.post(
        "/Canvas",
        json={"shape": "triangle", "width": 120, "height": 90},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["shape"] == "triangle"
    assert payload["polygon"] == [[60.0, 0.0], [120.0, 90.0], [0.0, 90.0]]
    assert payload["up_anchor"] == "vertex:0"
    assert payload["up_vector"] == [0.0, -1.0]


def test_canvas_svg_endpoint_returns_metadata_bearing_svg() -> None:
    response = client.post(
        "/CanvasSvg?boundary=true&boundary_stroke_width=2",
        json={"shape": "square", "width": 100, "height": 100, "up_anchor": "vertex:0"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    root = ET.fromstring(response.text)
    assert root.attrib["data-viz-canvas-shape"] == "square"
    assert root.attrib["data-viz-canvas-up-anchor"] == "vertex:0"


def test_invalid_polygon_returns_validation_error() -> None:
    response = client.post(
        "/Canvas",
        json={
            "shape": "polygon",
            "width": 100,
            "height": 100,
            "points": [[0, 0], [100, 100], [0, 100], [100, 0]],
        },
    )
    assert response.status_code == 422
