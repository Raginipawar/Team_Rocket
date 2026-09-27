from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_duplicate
from .model import real_duplicate
from .schemas import DuplicateRequest, DuplicateResponse

router = APIRouter()


@router.post("/duplicate-check", response_model=DuplicateResponse)
async def duplicate_check(req: DuplicateRequest) -> dict:
    return await resolve("duplicate", real_duplicate, mock_duplicate, req.model_dump())
