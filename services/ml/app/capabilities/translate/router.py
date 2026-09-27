from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_translate
from .model import real_translate
from .schemas import TranslateRequest, TranslateResponse

router = APIRouter()


@router.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest) -> dict:
    return await resolve("translate", real_translate, mock_translate, req.model_dump())
