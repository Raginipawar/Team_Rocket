from pydantic import BaseModel


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str


class TranslateResponse(BaseModel):
    translated_text: str
    cached: bool = False
    model_version: str = ""
    latency_ms: float = 0.0
