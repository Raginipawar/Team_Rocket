from pydantic import BaseModel


class EmergencyForDup(BaseModel):
    text: str
    location: dict  # {lat, lng}
    time: str
    extracted: dict = {}


class Candidate(BaseModel):
    emergency_id: str
    text: str
    location: dict
    time: str


class DuplicateRequest(BaseModel):
    emergency: EmergencyForDup
    candidates: list[Candidate]


class DuplicateResponse(BaseModel):
    duplicate_of: str | None
    similarity: float
    same_incident: bool
    additional_patients: bool
    model_version: str = ""
    latency_ms: float = 0.0
