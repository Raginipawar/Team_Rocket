from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_prank
from .model import real_prank
from .schemas import PrankRequest, PrankResponse

router = APIRouter()


@router.post("/prank-score", response_model=PrankResponse)
async def prank_score(req: PrankRequest) -> dict:
    return await resolve("prank", real_prank, mock_prank, req.model_dump())
