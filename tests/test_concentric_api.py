import xml.etree.ElementTree as ET

from fastapi import FastAPI
from fastapi.testclient import TestClient

from concentric.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_concentric_endpoint_returns_geometry() -> None:
    response = client.post(
        "/ConcentricPoints",
        json={
            "canvas": {"shape": "triangle", "width": 120, "height": 100},
            "seed": 9,
            "point_count": 3,
            "ring_count": 4,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm"] == "concentric-points"
    assert payload["canvas"]["shape"] == "triangle"
    assert len(payload["points"]) == 3
    assert all(len(point["radii"]) == 4 for point in payload["points"])


def test_concentric_svg_endpoint_returns_pen_layered_svg() -> None:
    response = client.post(
        "/ConcentricPointsSvg?stroke_width=1.5",
        json={
            "canvas": {"shape": "triangle", "width": 120, "height": 100},
            "seed": 9,
            "point_count": 2,
            "ring_count": 3,
            "pen": 2,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    root = ET.fromstring(response.text)
    namespace = "{http://www.w3.org/2000/svg}"
    layer = next(child for child in root if child.tag == f"{namespace}g")
    assert layer.attrib["id"] == "pen-2"


def test_impossible_sampling_returns_422() -> None:
    response = client.post(
        "/ConcentricPoints",
        json={
            "canvas": {"shape": "triangle", "width": 100, "height": 100},
            "point_count": 2,
            "center_margin": 1000,
            "max_sampling_attempts": 10,
        },
    )
    assert response.status_code == 422
