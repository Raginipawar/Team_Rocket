from pydantic import BaseModel


class ExtractRequest(BaseModel):
    text: str
    language: str


class ExtractedFacts(BaseModel):
    age: int | None = None
    age_confidence: str = "unknown"  # stated | estimated | unknown
    sex: str | None = None
    patient_count: int = 1
    conscious: bool | None = None
    breathing: str | None = None
    bleeding: str | None = None
    symptoms: list[str] = []
    mechanism: str = "none"
    pregnant: bool = False
    landmark: str | None = None
    for_whom: str | None = None
    coherence: float = 0.5
    model_version: str = ""
    latency_ms: float = 0.0
