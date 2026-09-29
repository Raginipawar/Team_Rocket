from pydantic import BaseModel

class RoadComfortRequest(BaseModel):
    geometry: str

class RoadComfortComponents(BaseModel):
    surface: float
    smoothness: float
    class_val: float
    breakers: float
    turns: float

class RoadComfortResponse(BaseModel):
    score: float
    components: RoadComfortComponents
    data_coverage: float
    estimated: bool
