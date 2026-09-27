from pydantic import BaseModel


class Segment(BaseModel):
    start: float
    end: float
    text: str


class STTResponse(BaseModel):
    transcript: str
    language: str
    confidence: float
    segments: list[Segment]
    model_version: str = ""
    latency_ms: float = 0.0
