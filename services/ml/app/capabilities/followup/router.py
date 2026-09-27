import time

from fastapi import APIRouter

from app.config import get_settings

from .mock import mock_followup_next, mock_followup_parse
from .model import ModelNotLoaded, real_followup_next, real_followup_parse
from .schemas import FollowupNextRequest, FollowupNextResponse, FollowupParseRequest, FollowupParseResponse

router = APIRouter()


@router.post("/followup/next", response_model=FollowupNextResponse)
async def followup_next(req: FollowupNextRequest) -> dict:
    start = time.perf_counter()
    payload = req.model_dump()
    settings = get_settings()

    result = None
    version = "followup:mock:v0"
    if settings.capability_mode("followup") != "mock":
        try:
            result = await real_followup_next(payload)
            version = "followup:llm:v0"
        except ModelNotLoaded:
            result = None

    if result is None:
        result = mock_followup_next(payload)
        version = "followup:rule-fallback:v0" if version == "followup:llm:v0" else version

    result["model_version"] = version
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return result


@router.post("/followup/parse", response_model=FollowupParseResponse)
async def followup_parse(req: FollowupParseRequest) -> dict:
    start = time.perf_counter()
    payload = req.model_dump()
    settings = get_settings()

    result = None
    version = "followup:mock:v0"
    if settings.capability_mode("followup") != "mock":
        try:
            result = await real_followup_parse(payload)
            version = "followup:llm:v0"
        except ModelNotLoaded:
            result = None

    if result is None:
        result = mock_followup_parse(payload)
        version = "followup:rule-fallback:v0" if version == "followup:llm:v0" else version

    result["model_version"] = version
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return result
