from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
    language: str


class TTSResponse(BaseModel):
    audio_url: str
    cached: bool = False
    model_version: str = ""
    latency_ms: float = 0.0
