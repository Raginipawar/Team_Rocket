from pydantic import BaseModel
from typing import List, Optional

class Point(BaseModel):
    lat: float
    lng: float

class ETARequest(BaseModel):
    origin: Point
    destination: Point
    depart_at: Optional[str] = None
    alternatives: bool = False

class Step(BaseModel):
    instruction: str
    distance_m: float
    maneuver_type: str
    maneuver_modifier: Optional[str] = None

class Route(BaseModel):
    route_id: str
    geometry: str
    distance_m: float
    eta_sec: float
    eta_low_sec: float
    eta_high_sec: float
    source: str
    road_comfort: Optional[float] = None
    steps: List[Step] = []

class ETAResponse(BaseModel):
    routes: List[Route]

class ETAMatrixRequest(BaseModel):
    origins: List[Point]
    destinations: List[Point]

class ETAMatrixResponse(BaseModel):
    durations: List[List[float]]
    distances: List[List[float]]
