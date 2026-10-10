from fastapi import APIRouter
from .schemas import RoadComfortRequest, RoadComfortResponse
from .model import get_road_comfort

router = APIRouter()

@router.post("/road-comfort", response_model=RoadComfortResponse)
async def predict_road_comfort(req: RoadComfortRequest):
    return await get_road_comfort(req)
