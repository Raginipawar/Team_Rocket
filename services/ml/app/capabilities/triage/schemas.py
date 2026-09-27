from pydantic import BaseModel, Field


class TriageRequest(BaseModel):
    text: str
    extracted: dict = Field(default_factory=dict)
    profile_summary: str | None = None
    followup_answers: list[str] = Field(default_factory=list)


class TriageResponse(BaseModel):
    acuity: str
    acuity_probs: dict[str, float]
    facility: str
    facility_probs: dict[str, float]
    confidence: float
    needs_review: bool
    fragility: bool
    mlc_flag: bool
    model_version: str = ""
    latency_ms: float = 0.0
