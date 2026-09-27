from pydantic import BaseModel


class PrankRequest(BaseModel):
    phone: str
    channel: str
    hour: int
    calls_24h: int
    calls_7d: int
    prior_prank_flags: int
    transcript_len: int
    coherence: float
    location_jump_km: float
    text_repeat_ratio: float


class PrankResponse(BaseModel):
    score: float
    suspicious: bool
    reasons: list[str]
    model_version: str = ""
    latency_ms: float = 0.0
