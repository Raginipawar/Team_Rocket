from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_photo_triage
from .model import real_photo_triage
from .schemas import PhotoTriageRequest, PhotoTriageResult

router = APIRouter()


@router.post("/photo-triage", response_model=PhotoTriageResult)
async def photo_triage(req: PhotoTriageRequest) -> dict:
    return await resolve("photo_triage", real_photo_triage, mock_photo_triage, req.model_dump())
