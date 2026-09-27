from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_extract
from .model import real_extract
from .schemas import ExtractedFacts, ExtractRequest

router = APIRouter()


@router.post("/extract", response_model=ExtractedFacts)
async def extract(req: ExtractRequest) -> dict:
    return await resolve("extract", real_extract, mock_extract, req.model_dump())
