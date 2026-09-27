import time

from fastapi import APIRouter

from .mock import select_first_aid
from .schemas import FirstAidRequest, FirstAidResponse

router = APIRouter()


@router.post("/first-aid", response_model=FirstAidResponse)
async def first_aid(req: FirstAidRequest) -> dict:
    start = time.perf_counter()
    result = select_first_aid(req.model_dump())
    result["model_version"] = "first_aid:rule-table:v0"
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return result
