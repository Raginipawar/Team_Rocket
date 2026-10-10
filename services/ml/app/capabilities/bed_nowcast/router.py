from fastapi import APIRouter
from .schemas import BedNowcastRequest, BedNowcastResponse
from .model import predict_bed_availability

router = APIRouter()

@router.post("/bed-nowcast", response_model=BedNowcastResponse)
async def get_bed_nowcast_route(req: BedNowcastRequest):
    return await predict_bed_availability(req)
