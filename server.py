import uvicorn
from fastapi import FastAPI

from concentric.api import router as concentric_router
from datatypes import (
    ClippedVoronoiData,
    PolygonsInterpolateData,
    RandomPointsInsidePolygonData,
)
from lsystem.api import router as lsystem_router
from polygon_handlers import polygons_interpolate, random_points_inside_polygon
from viz_canvas.api import router as canvas_router
from voronoi_handlers import get_clipped_voronoi

app = FastAPI()
app.include_router(lsystem_router)
app.include_router(canvas_router)
app.include_router(concentric_router)


@app.get("/")
async def default():
    return "Hello World!"


@app.post("/PolygonsInterpolate")
async def polygons_interpolate_(data: PolygonsInterpolateData):
    return polygons_interpolate(polygons=data.polygons,
                                displacement_f=data.displacement_f,
                                displacement=data.displacement,
                                min_area=data.min_area,
                                max_iter=data.max_iter)


@app.post("/RandomPointsInsidePolygon")
async def random_points_inside_polygon_(data: RandomPointsInsidePolygonData):
    return random_points_inside_polygon(polygon=data.polygon, n=data.n, seed=data.seed)


@app.post("/ClippedVoronoi")
async def get_clipped_voronoi_(data: ClippedVoronoiData):
    return get_clipped_voronoi(polygon=data.polygon, points=data.points)


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=5699, log_level="info")