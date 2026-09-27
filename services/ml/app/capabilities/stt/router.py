from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.util.base_router import resolve

from .mock import mock_stt
from .model import real_stt
from .schemas import STTResponse

router = APIRouter()

MAX_BYTES = 5 * 1024 * 1024
MAX_SECONDS = 60


@router.post("/stt", response_model=STTResponse)
async def stt(audio: UploadFile = File(...), lang_hint: str | None = Form(None)) -> dict:
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_BYTES:
        raise HTTPException(400, "audio exceeds 5 MB")

    payload = {"filename": audio.filename, "size": len(audio_bytes), "lang_hint": lang_hint}

    async def _real(_payload: dict) -> dict:
        return await real_stt(audio_bytes, lang_hint)

    return await resolve("stt", _real, mock_stt, payload)
