from pydantic import BaseModel


class FirstAidRequest(BaseModel):
    facility: str
    acuity: str
    extracted: dict = {}


class FirstAidResponse(BaseModel):
    protocol_id: str
    title: str
    steps: list[str]
    donts: list[str]
    audio_urls: list[str]
    model_version: str = ""
    latency_ms: float = 0.0
