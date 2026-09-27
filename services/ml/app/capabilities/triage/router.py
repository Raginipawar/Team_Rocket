from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_triage
from .model import real_triage
from .schemas import TriageRequest, TriageResponse

router = APIRouter()


@router.post("/triage", response_model=TriageResponse)
async def triage(req: TriageRequest) -> dict:
    return await resolve("triage", real_triage, mock_triage, req.model_dump())
