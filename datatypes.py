
from pydantic import BaseModel


class PolygonsInterpolateData(BaseModel):
    polygons: list[list]
    displacement_f: float = None
    displacement: float = 10
    min_area: float = 10
    max_iter: int = 100


class RandomPointsInsidePolygonData(BaseModel):
    polygon: list[list]
    n: int = None
    seed: int = -1


class ClippedVoronoiData(BaseModel):
    polygon: list[list]
    points: list