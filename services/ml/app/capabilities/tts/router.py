from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_tts
from .model import real_tts
from .schemas import TTSRequest, TTSResponse

router = APIRouter()


@router.post("/tts", response_model=TTSResponse)
async def tts(req: TTSRequest) -> dict:
    return await resolve("tts", real_tts, mock_tts, req.model_dump())
