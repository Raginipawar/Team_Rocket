from fastapi import APIRouter
from .schemas import BedNowcastRequest, BedNowcastResponse

router = APIRouter(prefix="/ml/v1")

@router.post("/bed-nowcast", response_model=BedNowcastResponse)
async def get_bed_nowcast_route(req: BedNowcastRequest):
    if req.minutes_since_report < 10:
        p = 0.85
    else:
        p = max(0.3, 0.85 - req.minutes_since_report * 0.01)
    
    return BedNowcastResponse(
        p_available_at_eta=p,
        expected_free_at_eta=req.last_reported_free,
        interval=[max(0.0, req.last_reported_free - 1.0), req.last_reported_free + 1.0]
    )
