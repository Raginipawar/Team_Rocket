from pydantic import BaseModel


class HandoverRequest(BaseModel):
    transcript: str
    extracted: dict = {}
    followup_answers: list[str] = []
    profile: dict = {}
    triage: dict = {}


class SourceSpan(BaseModel):
    field: str
    quote: str


class HandoverResponse(BaseModel):
    situation: str
    background: str
    assessment: str
    recommendation: str
    source_spans: list[SourceSpan]
    model_version: str = ""
    latency_ms: float = 0.0
