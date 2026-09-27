from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_dispatch_rank
from .model import real_dispatch_rank
from .schemas import DispatchRankRequest, DispatchRankResponse

router = APIRouter()


@router.post("/dispatch-rank", response_model=DispatchRankResponse)
async def dispatch_rank(req: DispatchRankRequest) -> dict:
    return await resolve("dispatch_rank", real_dispatch_rank, mock_dispatch_rank, req.model_dump())
