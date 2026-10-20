from fastapi import APIRouter

from app.config import get_settings
from app.util.base_router import resolve

from .mock import mock_triage
from .model import real_triage
from .model_qwen import real_triage_qwen
from .schemas import TriageRequest, TriageResponse

router = APIRouter()


@router.post("/triage", response_model=TriageResponse)
async def triage(req: TriageRequest) -> dict:
    # TRIAGE_ENGINE=qwen switches this; unset/"muril" is the unchanged
    # default (model.py's trained MuRIL classifier).
    engine_fn = real_triage_qwen if get_settings().triage_engine == "qwen" else real_triage
    return await resolve("triage", engine_fn, mock_triage, req.model_dump())
