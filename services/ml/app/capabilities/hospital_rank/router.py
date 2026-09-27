from fastapi import APIRouter
from .schemas import HospitalRankRequest, HospitalRankResponse
from .model import rank_hospitals

router = APIRouter(prefix="/ml/v1")

@router.post("/hospital-rank", response_model=list[HospitalRankResponse])
async def rank_hospitals_route(req: HospitalRankRequest):
    return await rank_hospitals(req)
