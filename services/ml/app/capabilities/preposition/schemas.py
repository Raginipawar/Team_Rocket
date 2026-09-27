from pydantic import BaseModel


class IdleAmbulance(BaseModel):
    id: str
    location: dict  # {lat, lng}
    type: str  # BLS | ALS


class PrepositionRequest(BaseModel):
    idle_ambulances: list[IdleAmbulance]
    forecast: list[dict] = []


class Suggestion(BaseModel):
    ambulance_id: str
    target: dict  # {lat, lng}
    h3_cell: str
    expected_coverage_gain: float


class PrepositionResponse(BaseModel):
    suggestions: list[Suggestion]
    model_version: str = ""
    latency_ms: float = 0.0
