from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_handover
from .model import real_handover
from .schemas import HandoverRequest, HandoverResponse

router = APIRouter()


@router.post("/handover", response_model=HandoverResponse)
async def handover(req: HandoverRequest) -> dict:
    return await resolve("handover", real_handover, mock_handover, req.model_dump())
