from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_preposition
from .model import real_preposition
from .schemas import PrepositionRequest, PrepositionResponse

router = APIRouter()


@router.post("/preposition", response_model=PrepositionResponse)
async def preposition(req: PrepositionRequest) -> dict:
    return await resolve("preposition", real_preposition, mock_preposition, req.model_dump())
